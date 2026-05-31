# tts_engine.py

import asyncio
import hashlib
import re
from collections import OrderedDict
from edge_tts import Communicate
from voice_config import VOICE_LIBRARY


class TTSEngine:
    """
    Core Text-to-Speech engine with bounded caching and runtime stats.
    Includes a natural-speech pipeline that chunks long text and applies
    gentle deterministic prosody variation across chunks.
    """

    def __init__(self):
        self.synthesis_cache = OrderedDict()
        self.preview_cache = OrderedDict()
        self.max_synthesis_cache_size = 200
        self.max_preview_cache_size = 100
        self.stats = {
            "synthesis_requests": 0,
            "preview_requests": 0,
            "synthesis_cache_hits": 0,
            "preview_cache_hits": 0,
            "synthesis_errors": 0,
            "preview_errors": 0,
            "natural_mode_requests": 0,
            "chunked_requests": 0,
        }

    def _set_cache(self, cache: OrderedDict, key: str, value: bytes, max_size: int):
        cache[key] = value
        cache.move_to_end(key)
        if len(cache) > max_size:
            cache.popitem(last=False)

    def get_stats(self) -> dict:
        return {
            **self.stats,
            "synthesis_cache_size": len(self.synthesis_cache),
            "preview_cache_size": len(self.preview_cache),
            "max_synthesis_cache_size": self.max_synthesis_cache_size,
            "max_preview_cache_size": self.max_preview_cache_size,
        }

    async def _synthesize(self, text: str, voice_id: str, rate: str = "+0%", pitch: str = "+0Hz") -> bytes:
        communicate = Communicate(text, voice_id, rate=rate, pitch=pitch)
        buffer = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buffer += chunk["data"]
        return buffer

    @staticmethod
    def _clamp(value: int, min_value: int, max_value: int) -> int:
        return max(min_value, min(max_value, value))

    @staticmethod
    def _normalize_text(text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip()
        cleaned = re.sub(r"\s+([,.!?;:])", r"\1", cleaned)
        return cleaned

    @staticmethod
    def _split_sentences(text: str):
        parts = re.split(r"(?<=[.!?])\s+", text)
        return [part.strip() for part in parts if part.strip()]

    @staticmethod
    def _chunk_sentences(sentences, max_chars=280):
        chunks = []
        current = []
        current_len = 0

        for sentence in sentences:
            sentence_len = len(sentence)
            if current and current_len + sentence_len + 1 > max_chars:
                chunks.append(" ".join(current).strip())
                current = [sentence]
                current_len = sentence_len
            else:
                current.append(sentence)
                current_len += sentence_len + 1

        if current:
            chunks.append(" ".join(current).strip())

        return chunks

    @staticmethod
    def _deterministic_offset(seed_text: str, idx: int, spread: int) -> int:
        if spread <= 0:
            return 0
        digest = hashlib.md5(f"{seed_text}-{idx}".encode("utf-8")).hexdigest()
        bucket = int(digest[:6], 16)
        # Map to [-spread, spread]
        return (bucket % (2 * spread + 1)) - spread

    async def _synthesize_natural(self, text: str, voice_id: str, rate: int, pitch: int, options: dict) -> bytes:
        expressiveness = self._clamp(int(options.get("expressiveness", 60)), 0, 100)
        stability = self._clamp(int(options.get("stability", 70)), 0, 100)
        sentence_pause_ms = self._clamp(int(options.get("sentence_pause_ms", 320)), 80, 1200)
        cleanup_text = bool(options.get("cleanup_text", True))

        processed = self._normalize_text(text) if cleanup_text else text.strip()
        sentences = self._split_sentences(processed)
        if not sentences:
            return await self._synthesize(processed, voice_id, rate=f"{rate:+d}%", pitch=f"{pitch:+d}Hz")

        max_chars = 260 if expressiveness >= 60 else 320
        chunks = self._chunk_sentences(sentences, max_chars=max_chars)
        if len(chunks) > 1:
            self.stats["chunked_requests"] += 1

        # Lower stability => more prosody variation. Higher expressiveness => slightly more movement.
        variation_scale = max(0, 100 - stability)
        rate_spread = self._clamp(int((variation_scale / 100.0) * (3 + expressiveness / 25.0)), 0, 8)
        pitch_spread = self._clamp(int((variation_scale / 100.0) * (2 + expressiveness / 35.0)), 0, 5)

        audio = b""
        for idx, chunk in enumerate(chunks):
            chunk_rate = self._clamp(rate + self._deterministic_offset(chunk, idx, rate_spread), -50, 50)
            chunk_pitch = self._clamp(pitch + self._deterministic_offset(chunk[::-1], idx, pitch_spread), -25, 25)

            chunk_text = chunk
            if idx < len(chunks) - 1 and sentence_pause_ms >= 450:
                # Plain-text pause hint for edge-tts (SSML is not used in this pipeline).
                chunk_text += " ..."

            audio += await self._synthesize(
                chunk_text,
                voice_id,
                rate=f"{chunk_rate:+d}%",
                pitch=f"{chunk_pitch:+d}Hz",
            )

        return audio

    async def process_tts_request(self, text: str, voice_id: str, rate: int, pitch: int, options: dict | None = None) -> bytes:
        self.stats["synthesis_requests"] += 1

        options = options or {}
        natural_enabled = bool(options.get("enabled", True))
        if natural_enabled:
            self.stats["natural_mode_requests"] += 1

        cache_key = hashlib.md5(
            f"{text}{voice_id}{rate}{pitch}{natural_enabled}{options}".encode()
        ).hexdigest()

        if cache_key in self.synthesis_cache:
            self.stats["synthesis_cache_hits"] += 1
            self.synthesis_cache.move_to_end(cache_key)
            return self.synthesis_cache[cache_key]

        try:
            if natural_enabled:
                audio_data = await self._synthesize_natural(text, voice_id, rate, pitch, options)
            else:
                audio_data = await self._synthesize(
                    text,
                    voice_id,
                    rate=f"{rate:+d}%",
                    pitch=f"{pitch:+d}Hz",
                )

            self._set_cache(self.synthesis_cache, cache_key, audio_data, self.max_synthesis_cache_size)
            return audio_data
        except Exception:
            self.stats["synthesis_errors"] += 1
            raise

    async def preview_voice(self, voice_id: str) -> bytes:
        self.stats["preview_requests"] += 1
        if voice_id in self.preview_cache:
            self.stats["preview_cache_hits"] += 1
            self.preview_cache.move_to_end(voice_id)
            return self.preview_cache[voice_id]

        preview_text = "Voice preview not available."
        for accent_details in VOICE_LIBRARY.values():
            for voice in accent_details["voices"]:
                if voice["id"] == voice_id:
                    preview_text = voice["preview_text"]
                    break

        try:
            audio_data = await self._synthesize(preview_text, voice_id)
            self._set_cache(self.preview_cache, voice_id, audio_data, self.max_preview_cache_size)
            return audio_data
        except Exception:
            self.stats["preview_errors"] += 1
            raise

    async def precache_previews(self):
        print("Pre-caching voice previews...")
        for accent, accent_details in VOICE_LIBRARY.items():
            for voice in accent_details["voices"]:
                if voice["id"] not in self.preview_cache:
                    try:
                        print(f"  - Caching preview for: {voice['name']} ({accent})")
                        audio_data = await self.preview_voice(voice["id"])
                        if not audio_data:
                            raise ValueError("Received no audio data.")
                        self._set_cache(self.preview_cache, voice["id"], audio_data, self.max_preview_cache_size)
                    except Exception as e:
                        print(f"    [ERROR] Failed to cache preview for {voice['name']}: {e}")

        print(f"Pre-caching complete. {len(self.preview_cache)} previews cached.")
