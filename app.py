# app.py

import base64
import asyncio
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from flask import Flask, request, jsonify, render_template_string
from tts_engine import TTSEngine
from voice_config import VOICE_LIBRARY

# --- FLASK APP INITIALIZATION ---
app = Flask(__name__)
tts_engine = TTSEngine()
app_start_time = time.time()

VOICE_IDS = {
    voice["id"]
    for accent_data in VOICE_LIBRARY.values()
    for voice in accent_data["voices"]
}

MAX_TEXT_LENGTH = 2000
RATE_MIN = -50
RATE_MAX = 50
PITCH_MIN = -25
PITCH_MAX = 25
EXPRESSIVENESS_MIN = 0
EXPRESSIVENESS_MAX = 100
STABILITY_MIN = 0
STABILITY_MAX = 100
SENTENCE_PAUSE_MIN = 80
SENTENCE_PAUSE_MAX = 1200
JOB_TTL_SECONDS = 30 * 60
MAX_JOBS = 200

jobs = {}
jobs_lock = Lock()
job_executor = ThreadPoolExecutor(max_workers=2)


def _sanitize_int(value, default, min_value, max_value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(min(parsed, max_value), min_value)


def _sanitize_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _validate_synthesis_payload(data):
    if not isinstance(data, dict):
        return None, "Invalid JSON payload."

    text = str(data.get("text", "")).strip()
    voice_id = str(data.get("voice_id", "")).strip()

    if not text:
        return None, "Text is required."
    if len(text) > MAX_TEXT_LENGTH:
        return None, f"Text exceeds {MAX_TEXT_LENGTH} characters."
    if not voice_id:
        return None, "Voice ID is required."
    if voice_id not in VOICE_IDS:
        return None, "Invalid voice ID."

    rate = _sanitize_int(data.get("rate", 0), 0, RATE_MIN, RATE_MAX)
    pitch = _sanitize_int(data.get("pitch", 0), 0, PITCH_MIN, PITCH_MAX)

    natural_input = data.get("natural", {}) or {}
    if not isinstance(natural_input, dict):
        natural_input = {}

    natural = {
        "enabled": _sanitize_bool(natural_input.get("enabled", True), True),
        "expressiveness": _sanitize_int(
            natural_input.get("expressiveness", 60),
            60,
            EXPRESSIVENESS_MIN,
            EXPRESSIVENESS_MAX,
        ),
        "stability": _sanitize_int(
            natural_input.get("stability", 70),
            70,
            STABILITY_MIN,
            STABILITY_MAX,
        ),
        "sentence_pause_ms": _sanitize_int(
            natural_input.get("sentence_pause_ms", 320),
            320,
            SENTENCE_PAUSE_MIN,
            SENTENCE_PAUSE_MAX,
        ),
        "cleanup_text": _sanitize_bool(natural_input.get("cleanup_text", True), True),
    }

    return {
        "text": text,
        "voice_id": voice_id,
        "rate": rate,
        "pitch": pitch,
        "natural": natural,
    }, None


def _prune_jobs_locked(now):
    stale_ids = [
        job_id
        for job_id, job in jobs.items()
        if now - job["created_at"] > JOB_TTL_SECONDS
    ]
    for job_id in stale_ids:
        jobs.pop(job_id, None)

    while len(jobs) > MAX_JOBS:
        oldest_id = min(jobs, key=lambda item: jobs[item]["created_at"])
        jobs.pop(oldest_id, None)


def _run_synthesis_job(job_id, payload):
    start = time.time()
    try:
        audio_data = asyncio.run(
            tts_engine.process_tts_request(payload["text"], payload["voice_id"], payload["rate"], payload["pitch"], options=payload["natural"])
        )
        encoded_audio = base64.b64encode(audio_data).decode("utf-8")
        with jobs_lock:
            job = jobs.get(job_id)
            if job:
                job.update(
                    {
                        "status": "completed",
                        "audio": f"data:audio/mp3;base64,{encoded_audio}",
                        "completed_at": time.time(),
                        "duration_ms": int((time.time() - start) * 1000),
                    }
                )
    except Exception as exc:
        with jobs_lock:
            job = jobs.get(job_id)
            if job:
                job.update(
                    {
                        "status": "failed",
                        "error": str(exc),
                        "completed_at": time.time(),
                        "duration_ms": int((time.time() - start) * 1000),
                    }
                )

# --- UI TEMPLATE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JAx</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-0: #111827;
            --bg-1: #243041;
            --card: rgba(255, 255, 255, 0.12);
            --card-border: rgba(255, 255, 255, 0.34);
            --accent: #f59e0b;
            --accent-2: #fb7185;
            --ok: #34d399;
            --warn: #f59e0b;
            --text: #ffffff;
            --muted: #e8e8e8;
        }
        body {
            font-family: 'Space Grotesk', sans-serif;
            color: var(--text);
            min-height: 100%;
            background:
                radial-gradient(circle at 12% 18%, rgba(255, 255, 255, 0.18), transparent 34%),
                radial-gradient(circle at 88% 12%, rgba(251, 191, 36, 0.18), transparent 30%),
                linear-gradient(135deg, var(--bg-0), var(--bg-1));
        }
        .mono { font-family: 'IBM Plex Mono', monospace; }
        .glass {
            background: var(--card);
            border: 1px solid var(--card-border);
            backdrop-filter: blur(12px);
        }
        .voice-card {
            position: relative;
            overflow: hidden;
            transition: transform 0.15s ease, border-color 0.15s ease, background-color 0.15s ease;
        }
        .voice-card:hover { transform: translateY(-1px); }
        .voice-card.selected { border-color: rgba(34, 211, 238, 0.8); background: rgba(34, 211, 238, 0.08); }

        .play-btn .play-icon, .play-btn.playing .pause-icon { display: block; }
        .play-btn .pause-icon, .play-btn.playing .play-icon { display: none; }
        .play-btn {
            color: #f8fafc;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08), 0 8px 20px rgba(2, 6, 23, 0.28);
            transition: transform 0.15s ease, border-color 0.15s ease, background-color 0.15s ease, box-shadow 0.15s ease, color 0.15s ease;
        }
        .play-btn:hover {
            transform: translateY(-1px) scale(1.02);
            border-color: rgba(251, 191, 36, 0.75);
            background: rgba(15, 23, 42, 0.98);
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.1), 0 10px 24px rgba(245, 158, 11, 0.18);
        }
        .play-btn:active {
            transform: scale(0.98);
        }
        .play-btn.playing {
            color: #111827;
            border-color: rgba(251, 191, 36, 0.95);
            background: linear-gradient(135deg, #fcd34d, #f59e0b);
            box-shadow: 0 10px 26px rgba(245, 158, 11, 0.35);
        }
        .play-btn.loading {
            opacity: 0.7;
            cursor: wait;
        }
        .play-btn:focus-visible {
            outline: none;
            box-shadow: 0 0 0 3px rgba(251, 191, 36, 0.28), 0 10px 24px rgba(245, 158, 11, 0.18);
        }
        .progress-bar {
            position: absolute;
            bottom: 0;
            left: 0;
            height: 3px;
            width: 0%;
            background: linear-gradient(90deg, #ffffff, var(--accent));
            transition: width 0.1s linear;
        }
        .status-dot {
            width: 9px;
            height: 9px;
            border-radius: 9999px;
            display: inline-block;
            background: var(--warn);
            box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.7);
            animation: pulse 1.6s infinite;
        }
        .status-dot.ok {
            background: var(--ok);
            animation: none;
            box-shadow: none;
        }
        .toast {
            opacity: 0;
            transform: translateY(8px);
            transition: 0.2s ease;
        }
        .toast.show {
            opacity: 1;
            transform: translateY(0);
        }
        .helper-chip {
            border: 1px solid rgba(148, 163, 184, 0.28);
            background: rgba(15, 23, 42, 0.5);
            transition: border-color 0.15s ease, background-color 0.15s ease, transform 0.15s ease;
        }
        .helper-chip:hover {
            border-color: rgba(251, 191, 36, 0.45);
            background: rgba(30, 41, 59, 0.72);
            transform: translateY(-1px);
        }
        .control-note {
            color: rgba(226, 232, 240, 0.72);
            font-size: 0.75rem;
        }
        .section-title {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
        }
        .section-kicker {
            letter-spacing: 0.08em;
            text-transform: uppercase;
            font-size: 0.7rem;
            color: #fbbf24;
        }
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.7); }
            70% { box-shadow: 0 0 0 10px rgba(245, 158, 11, 0); }
            100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0); }
        }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body class="h-full p-3 pb-24 md:p-6 md:pb-6">
    <div class="mx-auto w-full max-w-7xl">
        <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
                <h1 class="text-2xl md:text-3xl font-bold tracking-tight">JAx</h1>
                <p class="text-sm text-slate-300">Write your script, pick a voice, preview it, then render your audio.</p>
            </div>
            <div class="hidden md:block glass rounded-xl px-3 py-2 text-xs mono text-slate-200">Shortcut: <span class="text-amber-300">Ctrl</span> + <span class="text-amber-300">Enter</span> to generate</div>
        </div>

        <main class="grid grid-cols-1 gap-4 md:gap-5 lg:grid-cols-[1fr_430px]">
            <section class="glass rounded-2xl p-4 md:p-6 space-y-4">
                <div class="rounded-2xl border border-slate-500/25 bg-slate-950/35 p-4">
                    <div class="section-title">
                        <div>
                            <div class="section-kicker">Quick Start</div>
                            <h2 class="mt-1 text-lg font-semibold">Create audio in three steps</h2>
                        </div>
                        <div class="hidden md:block text-xs text-slate-400">1. Write  2. Preview  3. Generate</div>
                    </div>
                    <div class="mt-3 grid gap-2 text-sm text-slate-300 md:grid-cols-3">
                        <div class="rounded-xl border border-slate-600/35 bg-slate-900/45 p-3">Paste or type your script on the left.</div>
                        <div class="rounded-xl border border-slate-600/35 bg-slate-900/45 p-3">Preview voices until one fits your tone.</div>
                        <div class="rounded-xl border border-slate-600/35 bg-slate-900/45 p-3">Adjust the controls and generate the final audio.</div>
                    </div>
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                    <div class="rounded-xl border border-slate-600/50 bg-slate-900/40 p-3">
                        <div class="text-slate-400">Characters</div>
                        <div id="metricChars" class="mt-1 text-lg font-semibold">0</div>
                    </div>
                    <div class="rounded-xl border border-slate-600/50 bg-slate-900/40 p-3">
                        <div class="text-slate-400">Words</div>
                        <div id="metricWords" class="mt-1 text-lg font-semibold">0</div>
                    </div>
                    <div class="rounded-xl border border-slate-600/50 bg-slate-900/40 p-3">
                        <div class="text-slate-400">Est. Duration</div>
                        <div id="metricDuration" class="mt-1 text-lg font-semibold">0s</div>
                    </div>
                </div>

                <div class="space-y-3">
                    <div class="section-title">
                        <div>
                            <div class="section-kicker">Script</div>
                            <h2 class="mt-1 text-lg font-semibold">Narration text</h2>
                        </div>
                        <div class="flex flex-wrap gap-2">
                            <button id="sampleTextButton" type="button" class="helper-chip rounded-lg px-3 py-1.5 text-xs text-slate-100">Use sample text</button>
                            <button id="clearTextButton" type="button" class="helper-chip rounded-lg px-3 py-1.5 text-xs text-slate-100">Clear</button>
                        </div>
                    </div>
                    <p class="control-note">Keep it under 2000 characters. Short sentences usually sound more natural in preview and final output.</p>
                </div>

                <div class="relative">
                    <textarea id="textInput" class="w-full h-[260px] md:h-[340px] rounded-xl border border-slate-600/60 bg-slate-950/60 p-4 text-slate-100 placeholder:text-slate-500 outline-none focus:ring-2 focus:ring-amber-400/60" placeholder="Drop your narration script here..."></textarea>
                    <div id="charCounter" class="absolute bottom-3 right-4 text-xs text-slate-400 mono">0 / 2000</div>
                </div>

                <div class="section-title">
                    <div>
                        <div class="section-kicker">Controls</div>
                        <h2 class="mt-1 text-lg font-semibold">Voice shaping</h2>
                    </div>
                    <div class="text-xs text-slate-400">Fine-tune delivery before you render</div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div class="glass rounded-xl p-4 space-y-2">
                        <label for="speedSlider" class="flex justify-between text-sm"><span>Speed</span><span id="speedValue" class="mono text-amber-300">0%</span></label>
                        <input id="speedSlider" type="range" min="-50" max="50" value="0" class="w-full accent-amber-400">
                        <p class="control-note">Higher values make the voice speak faster.</p>
                    </div>
                    <div class="glass rounded-xl p-4 space-y-2">
                        <label for="pitchSlider" class="flex justify-between text-sm"><span>Pitch</span><span id="pitchValue" class="mono text-amber-300">0Hz</span></label>
                        <input id="pitchSlider" type="range" min="-25" max="25" value="0" class="w-full accent-amber-400">
                        <p class="control-note">Use small changes for the most natural result.</p>
                    </div>
                    <div class="glass rounded-xl p-4 space-y-2">
                        <label for="volumeSlider" class="flex justify-between text-sm"><span>Volume</span><span id="volumeValue" class="mono text-amber-300">100%</span></label>
                        <input id="volumeSlider" type="range" min="0" max="100" value="100" class="w-full accent-amber-400">
                        <p class="control-note">Changes playback volume in the built-in player.</p>
                    </div>
                </div>

                <div class="glass rounded-xl p-4 space-y-4">
                    <div class="flex items-center justify-between">
                        <label for="naturalMode" class="text-sm font-semibold">Natural Speech Mode</label>
                        <input id="naturalMode" type="checkbox" class="h-4 w-4 accent-amber-400" checked>
                    </div>
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div>
                            <label for="expressivenessSlider" class="flex justify-between text-xs text-slate-300"><span>Expressiveness</span><span id="expressivenessValue" class="mono text-amber-300">60</span></label>
                            <input id="expressivenessSlider" type="range" min="0" max="100" value="60" class="mt-1 w-full accent-amber-400">
                        </div>
                        <div>
                            <label for="stabilitySlider" class="flex justify-between text-xs text-slate-300"><span>Stability</span><span id="stabilityValue" class="mono text-amber-300">70</span></label>
                            <input id="stabilitySlider" type="range" min="0" max="100" value="70" class="mt-1 w-full accent-amber-400">
                        </div>
                        <div>
                            <label for="pauseSlider" class="flex justify-between text-xs text-slate-300"><span>Sentence Pause</span><span id="pauseValue" class="mono text-amber-300">320ms</span></label>
                            <input id="pauseSlider" type="range" min="80" max="1200" value="320" class="mt-1 w-full accent-amber-400">
                        </div>
                    </div>
                    <p class="control-note">Natural mode adds slight variation across longer scripts so the output feels less robotic.</p>
                </div>

                <div class="flex flex-wrap gap-2">
                    <button data-preset="default" class="preset-btn rounded-lg border border-slate-500/50 px-3 py-1.5 text-xs hover:border-amber-300">Neutral</button>
                    <button data-preset="ad" class="preset-btn rounded-lg border border-slate-500/50 px-3 py-1.5 text-xs hover:border-amber-300">Ad Voice</button>
                    <button data-preset="story" class="preset-btn rounded-lg border border-slate-500/50 px-3 py-1.5 text-xs hover:border-amber-300">Story</button>
                    <button data-preset="podcast" class="preset-btn rounded-lg border border-slate-500/50 px-3 py-1.5 text-xs hover:border-amber-300">Podcast</button>
                </div>
            </section>

            <aside class="space-y-4 lg:sticky lg:top-4 lg:self-start">
                <section class="glass rounded-2xl p-4 space-y-3">
                    <div class="section-title">
                        <div>
                            <div class="section-kicker">Voices</div>
                            <h2 class="mt-1 text-lg font-semibold">Find a voice</h2>
                        </div>
                        <div class="text-xs text-slate-400">Preview before selecting</div>
                    </div>
                    <div>
                        <label for="accentSelect" class="text-sm text-slate-300">Accent / Language</label>
                        <select id="accentSelect" class="mt-1 w-full rounded-lg border border-slate-600/60 bg-slate-900/70 p-2.5 text-sm outline-none focus:ring-2 focus:ring-amber-400/60"></select>
                    </div>
                    <div>
                        <label for="voiceSearch" class="text-sm text-slate-300">Find voice</label>
                        <input id="voiceSearch" type="text" placeholder="Search by name, style, gender..." class="mt-1 w-full rounded-lg border border-slate-600/60 bg-slate-900/70 p-2.5 text-sm outline-none focus:ring-2 focus:ring-amber-400/60">
                    </div>
                    <div id="selectedVoiceSummary" class="rounded-xl border border-slate-600/45 bg-slate-950/50 p-3 text-sm text-slate-200">
                        Select a voice to see its details here.
                    </div>
                    <div id="voiceList" class="h-[240px] md:h-[300px] overflow-y-auto space-y-2 rounded-xl border border-slate-600/50 bg-slate-950/50 p-2"></div>
                </section>

                <section id="audioOutput" class="hidden glass rounded-2xl p-4">
                    <h2 class="text-lg font-semibold">Generated Audio</h2>
                    <audio id="audioPlayer" controls class="mt-3 w-full"></audio>
                    <a id="downloadButton" class="mt-3 inline-flex w-full justify-center rounded-lg bg-amber-400 px-4 py-2 font-semibold text-stone-950 hover:bg-amber-300">Download MP3</a>
                </section>

                <section id="actionPanel" class="glass rounded-2xl p-4 space-y-3 sticky bottom-3 z-20 lg:static">
                    <button id="generateButton" class="w-full rounded-xl bg-amber-400 px-4 py-3.5 text-base font-bold text-stone-950 hover:bg-amber-300">Generate Speech</button>
                    <div class="rounded-lg border border-slate-600/50 bg-slate-900/50 p-3">
                        <div class="mb-2 flex items-center justify-between text-xs text-slate-300">
                            <span id="statusText">Idle</span>
                            <span id="statusDot" class="status-dot"></span>
                        </div>
                        <div class="h-2 w-full overflow-hidden rounded-full bg-slate-700/70">
                            <div id="jobProgress" class="h-full w-0 bg-gradient-to-r from-white to-amber-300 transition-all"></div>
                        </div>
                    </div>
                    <div id="errorMessage" class="hidden rounded-lg bg-rose-500/20 p-3 text-sm text-rose-200"></div>
                </section>
            </aside>
        </main>
    </div>

    <div id="toast" class="toast fixed bottom-20 left-3 right-3 md:left-auto md:right-5 md:bottom-5 rounded-lg border border-slate-500/60 bg-slate-900/90 px-4 py-2 text-sm text-slate-100"></div>

    <script>
        const $ = (id) => document.getElementById(id);

        let voiceLibrary = {};
        let selectedVoiceId = null;
        let previewAudio = new Audio();
        let activePreviewBtn = null;
        let activePreviewVoiceId = null;
        let pollingHandle = null;
        let progressHandle = null;
        let previewRequestId = 0;
        const previewCache = new Map();

        const elements = {
            textInput: $('textInput'),
            charCounter: $('charCounter'),
            metricChars: $('metricChars'),
            metricWords: $('metricWords'),
            metricDuration: $('metricDuration'),
            speedSlider: $('speedSlider'),
            speedValue: $('speedValue'),
            pitchSlider: $('pitchSlider'),
            pitchValue: $('pitchValue'),
            volumeSlider: $('volumeSlider'),
            volumeValue: $('volumeValue'),
            naturalMode: $('naturalMode'),
            expressivenessSlider: $('expressivenessSlider'),
            expressivenessValue: $('expressivenessValue'),
            stabilitySlider: $('stabilitySlider'),
            stabilityValue: $('stabilityValue'),
            pauseSlider: $('pauseSlider'),
            pauseValue: $('pauseValue'),
            accentSelect: $('accentSelect'),
            voiceSearch: $('voiceSearch'),
            voiceList: $('voiceList'),
            selectedVoiceSummary: $('selectedVoiceSummary'),
            generateButton: $('generateButton'),
            statusText: $('statusText'),
            statusDot: $('statusDot'),
            jobProgress: $('jobProgress'),
            errorMessage: $('errorMessage'),
            audioOutput: $('audioOutput'),
            audioPlayer: $('audioPlayer'),
            downloadButton: $('downloadButton'),
            toast: $('toast'),
            actionPanel: $('actionPanel'),
            sampleTextButton: $('sampleTextButton'),
            clearTextButton: $('clearTextButton')
        };

        const PRESETS = {
            default: { rate: 0, pitch: 0 },
            ad: { rate: 14, pitch: 4 },
            story: { rate: -8, pitch: -2 },
            podcast: { rate: -2, pitch: 1 }
        };

        function showToast(message) {
            elements.toast.textContent = message;
            elements.toast.classList.add('show');
            clearTimeout(showToast._timer);
            showToast._timer = setTimeout(() => elements.toast.classList.remove('show'), 1800);
        }

        function showError(message) {
            elements.errorMessage.textContent = message;
            elements.errorMessage.classList.remove('hidden');
        }

        function hideError() {
            elements.errorMessage.classList.add('hidden');
        }

        function setStatus(text, done = false) {
            elements.statusText.textContent = text;
            elements.statusDot.classList.toggle('ok', done);
        }

        function setProgress(percent) {
            elements.jobProgress.style.width = `${Math.max(0, Math.min(100, percent))}%`;
        }

        function resetPreviewButton(btn) {
            if (!btn) return;
            const card = btn.closest('.voice-card');
            const bar = card ? card.querySelector('.progress-bar') : null;
            btn.classList.remove('playing', 'loading');
            btn.disabled = false;
            btn.title = 'Play voice preview';
            if (bar) {
                bar.style.width = '0%';
            }
        }

        function stopActivePreview() {
            if (previewAudio) {
                previewAudio.pause();
                previewAudio.currentTime = 0;
            }
            resetPreviewButton(activePreviewBtn);
            activePreviewBtn = null;
            activePreviewVoiceId = null;
        }

        function updateTextStats() {
            const text = elements.textInput.value || '';
            const chars = text.length;
            const words = text.trim() ? text.trim().split(/\s+/).length : 0;
            const estSeconds = Math.max(0, Math.round(words / 2.6));

            elements.charCounter.textContent = `${chars} / 2000`;
            elements.metricChars.textContent = chars;
            elements.metricWords.textContent = words;
            elements.metricDuration.textContent = `${estSeconds}s`;
            elements.generateButton.disabled = !text.trim();
            elements.generateButton.classList.toggle('opacity-60', !text.trim());
        }

        function updateControlLabels() {
            elements.speedValue.textContent = `${elements.speedSlider.value}%`;
            elements.pitchValue.textContent = `${elements.pitchSlider.value}Hz`;
            elements.volumeValue.textContent = `${elements.volumeSlider.value}%`;
            elements.expressivenessValue.textContent = `${elements.expressivenessSlider.value}`;
            elements.stabilityValue.textContent = `${elements.stabilitySlider.value}`;
            elements.pauseValue.textContent = `${elements.pauseSlider.value}ms`;
            elements.audioPlayer.volume = Number(elements.volumeSlider.value) / 100;

            const disabled = !elements.naturalMode.checked;
            elements.expressivenessSlider.disabled = disabled;
            elements.stabilitySlider.disabled = disabled;
            elements.pauseSlider.disabled = disabled;
            [elements.expressivenessSlider, elements.stabilitySlider, elements.pauseSlider].forEach((el) => {
                el.classList.toggle('opacity-50', disabled);
            });
        }

        function getFilteredVoices() {
            const accent = elements.accentSelect.value;
            let all = [];

            if (accent === '__all_english__') {
                all = Object.entries(voiceLibrary).flatMap(([accentName, data]) =>
                    (data.voices || []).map((voice) => ({ ...voice, _accentName: accentName }))
                );
            } else {
                all = (voiceLibrary[accent]?.voices || []).map((voice) => ({ ...voice, _accentName: accent }));
            }

            const q = elements.voiceSearch.value.trim().toLowerCase();
            if (!q) return all;

            return all.filter((v) => {
                const hay = `${v.name} ${v.gender} ${v.style} ${v.id} ${v._accentName}`.toLowerCase();
                return hay.includes(q);
            });
        }

        function renderAccentOptions() {
            const options = ['<option value="__all_english__">All English</option>'];
            Object.keys(voiceLibrary).forEach((accent) => {
                options.push(`<option value="${accent}">${voiceLibrary[accent].flag} ${accent}</option>`);
            });
            elements.accentSelect.innerHTML = options.join('');
            if (!elements.accentSelect.value) {
                elements.accentSelect.value = '__all_english__';
            }
        }
        function renderVoiceList() {
            const voices = getFilteredVoices();
            if (!selectedVoiceId && voices.length > 0) {
                selectedVoiceId = voices[0].id;
            }
            if (selectedVoiceId && !voices.some(v => v.id === selectedVoiceId) && voices.length > 0) {
                selectedVoiceId = voices[0].id;
            }

            elements.voiceList.innerHTML = voices.length === 0
                ? '<div class="p-4 text-sm text-slate-400">No voices match your search.</div>'
                : voices.map(voice => {
                    const selected = voice.id === selectedVoiceId;
                    return `
                        <div class="voice-card ${selected ? 'selected' : ''} rounded-lg border border-slate-600/60 bg-slate-900/60 p-3" data-voice-id="${voice.id}">
                            <div class="flex items-center gap-3">
                                <button class="play-btn relative flex h-11 w-11 items-center justify-center rounded-full border border-slate-500/60 bg-slate-900" type="button" aria-label="Preview ${voice.name}" title="Play voice preview" data-voice-id-preview="${voice.id}">
                                    <svg class="play-icon h-5 w-5" fill="currentColor" viewBox="0 0 20 20"><path d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z"></path></svg>
                                    <svg class="pause-icon h-5 w-5" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 102 0V8a1 1 0 00-1-1zm4 0a1 1 0 00-1 1v4a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd"></path></svg>
                                </button>
                                <div class="min-w-0 flex-1">
                                    <div class="truncate font-semibold">${voice.name}</div>
                                    <div class="truncate text-xs text-slate-400">${voice.gender} | ${voice.style}${elements.accentSelect.value === "__all_english__" ? ` | ${voice._accentName}` : ""}</div>
                                </div>
                            </div>
                            <div class="progress-bar"></div>
                        </div>
                    `;
                }).join('');

            elements.voiceList.querySelectorAll('.voice-card').forEach(card => {
                card.addEventListener('click', (e) => {
                    if (!e.target.closest('.play-btn')) {
                        selectedVoiceId = card.dataset.voiceId;
                        renderVoiceList();
                        showToast('Voice selected');
                    }
                });
            });

            elements.voiceList.querySelectorAll('.play-btn').forEach(btn => {
                btn.addEventListener('click', () => handlePreview(btn));
            });

            updateSelectedVoiceSummary();
        }

        function updateSelectedVoiceSummary() {
            const allVoices = Object.entries(voiceLibrary).flatMap(([accentName, data]) =>
                (data.voices || []).map((voice) => ({ ...voice, _accentName: accentName, _flag: data.flag }))
            );
            const voice = allVoices.find((item) => item.id === selectedVoiceId);
            if (!voice) {
                elements.selectedVoiceSummary.innerHTML = 'Select a voice to see its details here.';
                return;
            }

            elements.selectedVoiceSummary.innerHTML = `
                <div class="flex items-start justify-between gap-3">
                    <div>
                        <div class="text-xs uppercase tracking-[0.08em] text-amber-300">Selected voice</div>
                        <div class="mt-1 text-base font-semibold text-slate-50">${voice.name}</div>
                        <div class="mt-1 text-xs text-slate-400">${voice._flag} ${voice._accentName}</div>
                    </div>
                    <div class="rounded-full border border-slate-500/45 bg-slate-900/70 px-2.5 py-1 text-xs text-slate-200">${voice.gender}</div>
                </div>
                <div class="mt-3 text-sm text-slate-300">${voice.style}</div>
            `;
        }

        async function handlePreview(btn) {
            if (btn.disabled) return;

            const voiceId = btn.dataset.voiceIdPreview;
            const requestId = ++previewRequestId;

            if (activePreviewBtn === btn && !previewAudio.paused) {
                stopActivePreview();
                return;
            }

            if (activePreviewBtn && activePreviewBtn !== btn) {
                stopActivePreview();
            } else {
                resetPreviewButton(activePreviewBtn);
            }

            elements.voiceList.querySelectorAll('.play-btn').forEach(b => {
                if (b !== btn) {
                    resetPreviewButton(b);
                }
            });

            activePreviewBtn = btn;
            activePreviewVoiceId = voiceId;
            btn.classList.add('loading');
            btn.disabled = true;
            try {
                let audioSrc = previewCache.get(voiceId);
                if (!audioSrc) {
                    const response = await fetch(`/api/preview_voice?voice_id=${encodeURIComponent(voiceId)}`);
                    const result = await response.json();
                    if (!response.ok) throw new Error(result.error || 'Preview failed.');
                    audioSrc = result.audio;
                    previewCache.set(voiceId, audioSrc);
                }
                if (requestId !== previewRequestId) return;

                btn.classList.remove('loading');
                btn.disabled = false;
                btn.classList.add('playing');
                btn.title = 'Pause voice preview';

                previewAudio.src = audioSrc;
                previewAudio.currentTime = 0;
                await previewAudio.play();
            } catch (err) {
                btn.classList.remove('loading');
                btn.disabled = false;
                btn.title = 'Play voice preview';
                showError(err.message || 'Could not play preview.');
            }
        }

        function applyPreset(name) {
            const preset = PRESETS[name];
            if (!preset) return;
            elements.speedSlider.value = preset.rate;
            elements.pitchSlider.value = preset.pitch;

            if (name === 'ad') {
                elements.naturalMode.checked = true;
                elements.expressivenessSlider.value = 75;
                elements.stabilitySlider.value = 55;
                elements.pauseSlider.value = 240;
            } else if (name === 'story') {
                elements.naturalMode.checked = true;
                elements.expressivenessSlider.value = 68;
                elements.stabilitySlider.value = 70;
                elements.pauseSlider.value = 430;
            } else if (name === 'podcast') {
                elements.naturalMode.checked = true;
                elements.expressivenessSlider.value = 48;
                elements.stabilitySlider.value = 82;
                elements.pauseSlider.value = 320;
            } else {
                elements.naturalMode.checked = true;
                elements.expressivenessSlider.value = 60;
                elements.stabilitySlider.value = 70;
                elements.pauseSlider.value = 320;
            }

            updateControlLabels();
            showToast(`Preset: ${name}`);
        }

        function startSimulatedProgress() {
            clearInterval(progressHandle);
            setProgress(6);
            progressHandle = setInterval(() => {
                const current = parseFloat(elements.jobProgress.style.width) || 0;
                if (current < 88) setProgress(current + 3);
            }, 350);
        }

        function stopProgress(finalValue = 100) {
            clearInterval(progressHandle);
            setProgress(finalValue);
        }

        async function pollJob(jobId) {
            clearInterval(pollingHandle);
            pollingHandle = setInterval(async () => {
                try {
                    const response = await fetch(`/api/jobs/${jobId}`);
                    const data = await response.json();
                    if (!response.ok) throw new Error(data.error || 'Job polling failed.');

                    if (data.status === 'queued') {
                        setStatus('Rendering audio...');
                        return;
                    }
                    if (data.status === 'completed') {
                        clearInterval(pollingHandle);
                        stopProgress(100);
                        setStatus('Completed', true);
                        elements.audioOutput.classList.remove('hidden');
                        if (window.innerWidth < 1024) {
                            elements.audioOutput.scrollIntoView({ behavior: 'smooth', block: 'start' });
                        }
                        elements.audioPlayer.src = data.audio;
                        elements.downloadButton.href = data.audio;
                        elements.audioPlayer.volume = Number(elements.volumeSlider.value) / 100;
                        await elements.audioPlayer.play();
                        setLoading(false);
                        showToast('Audio ready');
                        return;
                    }
                    if (data.status === 'failed') {
                        throw new Error(data.error || 'Synthesis failed.');
                    }
                } catch (err) {
                    clearInterval(pollingHandle);
                    stopProgress(0);
                    setStatus('Failed');
                    setLoading(false);
                    showError(err.message || 'Unable to fetch job status.');
                }
            }, 650);
        }

        function setLoading(isLoading) {
            elements.generateButton.disabled = isLoading;
            elements.generateButton.classList.toggle('opacity-60', isLoading);
            if (!isLoading) return;
            hideError();
            setStatus('Queueing render...');
        }

        async function handleGenerate() {
            const payload = {
                text: elements.textInput.value,
                voice_id: selectedVoiceId,
                rate: Number(elements.speedSlider.value),
                pitch: Number(elements.pitchSlider.value),
                natural: {
                    enabled: elements.naturalMode.checked,
                    expressiveness: Number(elements.expressivenessSlider.value),
                    stability: Number(elements.stabilitySlider.value),
                    sentence_pause_ms: Number(elements.pauseSlider.value),
                    cleanup_text: true
                }
            };

            if (!payload.text.trim()) {
                showError('Enter text before generating speech.');
                return;
            }
            if (!payload.voice_id) {
                showError('Select a voice before generating speech.');
                return;
            }

            setLoading(true);
            startSimulatedProgress();
            if (window.innerWidth < 1024 && elements.actionPanel) {
                elements.actionPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }

            try {
                const response = await fetch('/api/synthesize_async', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || 'Could not create synthesis job.');

                setStatus('Job accepted');
                await pollJob(result.job_id);
            } catch (err) {
                stopProgress(0);
                setLoading(false);
                setStatus('Failed');
                showError(err.message || 'Synthesis failed.');
            }
        }

        async function initialize() {
            try {
                const [voicesResponse, statsResponse] = await Promise.all([
                    fetch('/api/voices'),
                    fetch('/api/stats')
                ]);
                voiceLibrary = await voicesResponse.json();
                renderAccentOptions();
                renderVoiceList();
                updateTextStats();
                updateControlLabels();

                if (statsResponse.ok) {
                    const stats = await statsResponse.json();
                    setStatus(`Ready â€¢ ${stats.voices_available} voices`, true);
                } else {
                    setStatus('Ready', true);
                }
            } catch (err) {
                showError('Failed to initialize voice library.');
            }
        }

        elements.accentSelect.addEventListener('change', () => {
            selectedVoiceId = null;
            renderVoiceList();
        });
        elements.voiceSearch.addEventListener('input', renderVoiceList);
        elements.textInput.addEventListener('input', updateTextStats);
        elements.speedSlider.addEventListener('input', updateControlLabels);
        elements.pitchSlider.addEventListener('input', updateControlLabels);
        elements.volumeSlider.addEventListener('input', updateControlLabels);
        elements.naturalMode.addEventListener('change', updateControlLabels);
        elements.expressivenessSlider.addEventListener('input', updateControlLabels);
        elements.stabilitySlider.addEventListener('input', updateControlLabels);
        elements.pauseSlider.addEventListener('input', updateControlLabels);
        elements.generateButton.addEventListener('click', handleGenerate);
        elements.sampleTextButton.addEventListener('click', () => {
            elements.textInput.value = 'Welcome to JAx. This short sample helps you preview a voice, adjust the pacing, and generate polished narration quickly.';
            updateTextStats();
            showToast('Sample text added');
        });
        elements.clearTextButton.addEventListener('click', () => {
            elements.textInput.value = '';
            updateTextStats();
            elements.textInput.focus();
            showToast('Script cleared');
        });

        document.querySelectorAll('.preset-btn').forEach(btn => {
            btn.addEventListener('click', () => applyPreset(btn.dataset.preset));
        });

        document.addEventListener('keydown', (event) => {
            if (event.ctrlKey && event.key === 'Enter') {
                event.preventDefault();
                handleGenerate();
            }
        });

        previewAudio.addEventListener('timeupdate', () => {
            if (!activePreviewBtn) return;
            const card = activePreviewBtn.closest('.voice-card');
            const bar = card ? card.querySelector('.progress-bar') : null;
            if (bar && previewAudio.duration) {
                bar.style.width = `${(previewAudio.currentTime / previewAudio.duration) * 100}%`;
            }
        });

        previewAudio.addEventListener('ended', () => {
            stopActivePreview();
        });

        initialize();
    </script>
</body>
</html>
"""
# --- API ENDPOINTS ---
@app.route('/')
def index():
    """Serves the main HTML user interface."""
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/health')
def api_health():
    return jsonify({"status": "ok", "uptime_seconds": int(time.time() - app_start_time)})


@app.route('/api/stats')
def api_stats():
    with jobs_lock:
        now = time.time()
        _prune_jobs_locked(now)
        queued = sum(1 for job in jobs.values() if job["status"] == "queued")
        completed = sum(1 for job in jobs.values() if job["status"] == "completed")
        failed = sum(1 for job in jobs.values() if job["status"] == "failed")

    return jsonify(
        {
            "uptime_seconds": int(time.time() - app_start_time),
            "voices_available": len(VOICE_IDS),
            "jobs": {
                "total": queued + completed + failed,
                "queued": queued,
                "completed": completed,
                "failed": failed,
                "ttl_seconds": JOB_TTL_SECONDS,
                "max_jobs": MAX_JOBS,
            },
            "engine": tts_engine.get_stats(),
        }
    )


@app.route('/api/voices')
def get_voices():
    """Provides the structured voice library to the frontend."""
    return jsonify(VOICE_LIBRARY)


@app.route('/api/preview_voice')
async def api_preview_voice():
    """Generates and returns a preview of a specific voice."""
    voice_id = request.args.get('voice_id', '').strip()
    if not voice_id:
        return jsonify({"error": "Voice ID is required"}), 400
    if voice_id not in VOICE_IDS:
        return jsonify({"error": "Invalid voice ID"}), 400

    try:
        audio_data = await tts_engine.preview_voice(voice_id)
        encoded_audio = base64.b64encode(audio_data).decode('utf-8')
        return jsonify({"audio": f"data:audio/mp3;base64,{encoded_audio}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/synthesize', methods=['POST'])
async def api_synthesize():
    """Generates speech from user text and selected settings."""
    payload, error = _validate_synthesis_payload(request.get_json(silent=True) or {})
    if error:
        return jsonify({"error": error}), 400

    start = time.time()
    try:
        audio_data = await tts_engine.process_tts_request(
            payload["text"],
            payload["voice_id"],
            payload["rate"],
            payload["pitch"],
            options=payload["natural"],
        )
        encoded_audio = base64.b64encode(audio_data).decode('utf-8')
        return jsonify(
            {
                "audio": f"data:audio/mp3;base64,{encoded_audio}",
                "meta": {
                    "duration_ms": int((time.time() - start) * 1000),
                    "text_length": len(payload["text"]),
                    "voice_id": payload["voice_id"],
                    "rate": payload["rate"],
                    "pitch": payload["pitch"],
                    "natural": payload["natural"],
                },
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/api/synthesize_async', methods=['POST'])
def api_synthesize_async():
    """Queues speech generation and returns a job ID for polling."""
    payload, error = _validate_synthesis_payload(request.get_json(silent=True) or {})
    if error:
        return jsonify({"error": error}), 400

    job_id = str(uuid.uuid4())
    now = time.time()
    with jobs_lock:
        _prune_jobs_locked(now)
        jobs[job_id] = {
            "status": "queued",
            "created_at": now,
            "completed_at": None,
            "duration_ms": None,
            "error": None,
            "audio": None,
            "input": {
                "text_length": len(payload["text"]),
                "voice_id": payload["voice_id"],
                "rate": payload["rate"],
                "pitch": payload["pitch"],
                "natural": payload["natural"],
            },
        }

    job_executor.submit(_run_synthesis_job, job_id, payload)
    return jsonify({"job_id": job_id, "status": "queued"}), 202


@app.route('/api/jobs/<job_id>')
def api_job_status(job_id):
    with jobs_lock:
        _prune_jobs_locked(time.time())
        job = jobs.get(job_id)
        if not job:
            return jsonify({"error": "Job not found or expired."}), 404

        response = {
            "job_id": job_id,
            "status": job["status"],
            "created_at": job["created_at"],
            "completed_at": job["completed_at"],
            "duration_ms": job["duration_ms"],
            "input": job["input"],
        }

        if job["status"] == "completed":
            response["audio"] = job["audio"]
        elif job["status"] == "failed":
            response["error"] = job["error"]

        return jsonify(response)

# --- MAIN EXECUTION ---
if __name__ == '__main__':
    # Pre-cache all voice previews on startup for instant playback.
    # This is a one-time operation.
    try:
        asyncio.run(tts_engine.precache_previews())
    except Exception as e:
        print(f"Error during preview pre-caching: {e}")

    # Note: For production, a proper ASGI server like Gunicorn with Uvicorn workers is recommended.
    app.run(host='127.0.0.1', port=5000, debug=True)








