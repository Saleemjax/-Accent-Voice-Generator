# tts_engine.py

import asyncio
import hashlib
from edge_tts import Communicate
from voice_config import VOICE_LIBRARY

class TTSEngine:
    """
    Core Text-to-Speech engine with caching for improved performance.
    """
    def __init__(self):
        self.synthesis_cache = {}
        self.preview_cache = {}

    async def _synthesize(self, text: str, voice_id: str, rate: str = "+0%", pitch: str = "+0Hz") -> bytes:
        """
        Private method to handle the core synthesis.
        """
        communicate = Communicate(text, voice_id, rate=rate, pitch=pitch)
        buffer = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buffer += chunk["data"]
        return buffer

    async def process_tts_request(self, text: str, voice_id: str, rate: int, pitch: int) -> bytes:
        """
        Main TTS Generation Pipeline with caching.
        """
        cache_key = hashlib.md5(f"{text}{voice_id}{rate}{pitch}".encode()).hexdigest()
        if cache_key in self.synthesis_cache:
            return self.synthesis_cache[cache_key]

        rate_str = f"{rate:+d}%"
        pitch_str = f"{pitch:+d}Hz"
        
        audio_data = await self._synthesize(text, voice_id, rate_str, pitch_str)
        
        self.synthesis_cache[cache_key] = audio_data
        return audio_data

    async def preview_voice(self, voice_id: str) -> bytes:
        """
        Voice Preview Pipeline with caching.
        """
        if voice_id in self.preview_cache:
            return self.preview_cache[voice_id]
        
        # If not in cache (should be pre-cached, but as a fallback)
        preview_text = "Voice preview not available."
        for accent_details in VOICE_LIBRARY.values():
            for voice in accent_details["voices"]:
                if voice["id"] == voice_id:
                    preview_text = voice["preview_text"]
                    break
        
        audio_data = await self._synthesize(preview_text, voice_id)
        self.preview_cache[voice_id] = audio_data
        return audio_data

    async def precache_previews(self):
        """
        Pre-synthesizes all voice previews sequentially and stores them in the cache.
        This is more reliable than running them all in parallel.
        """
        print("Pre-caching voice previews...")
        for accent, accent_details in VOICE_LIBRARY.items():
            for voice in accent_details["voices"]:
                if voice["id"] not in self.preview_cache:
                    try:
                        print(f"  - Caching preview for: {voice['name']} ({accent})")
                        audio_data = await self.preview_voice(voice["id"])
                        if not audio_data:
                            raise ValueError("Received no audio data.")
                        self.preview_cache[voice["id"]] = audio_data
                    except Exception as e:
                        print(f"    [ERROR] Failed to cache preview for {voice['name']}: {e}")
        
        print(f"Pre-caching complete. {len(self.preview_cache)} previews cached.")