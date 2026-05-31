# app.py

import base64
import asyncio
from flask import Flask, request, jsonify, render_template_string
from tts_engine import TTSEngine
from voice_config import VOICE_LIBRARY

# --- FLASK APP INITIALIZATION ---
app = Flask(__name__)
tts_engine = TTSEngine()

# --- UI TEMPLATE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Voice Studio</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; }
        .main-grid { grid-template-columns: 1fr 420px; }
        
        .voice-card {
            position: relative;
            overflow: hidden; /* For the progress bar */
        }

        .play-btn .play-icon, .play-btn.playing .pause-icon, .play-btn.loading .loading-icon {
            display: block;
        }
        .play-btn .pause-icon, .play-btn.playing .play-icon, .play-btn.loading .play-icon, .play-btn.loading .pause-icon {
            display: none;
        }

        .play-btn.playing::before {
            content: '';
            position: absolute;
            top: -2px; left: -2px; right: -2px; bottom: -2px;
            border-radius: 50%;
            border: 2px solid theme('colors.blue.500');
            animation: pulse 1.5s infinite;
        }
        
        .progress-bar {
            position: absolute;
            bottom: 0;
            left: 0;
            height: 3px;
            background-color: theme('colors.blue.500');
            width: 0%;
            transition: width 0.1s linear;
        }

        @keyframes pulse {
            0% { transform: scale(0.9); opacity: 0.7; }
            50% { transform: scale(1.1); opacity: 1; }
            100% { transform: scale(0.9); opacity: 0.7; }
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        .loading-icon {
            animation: spin 1s linear infinite;
        }
    </style>
</head>
<body class="bg-gray-800 text-gray-200 flex items-center justify-center min-h-screen p-4">
    <main class="bg-gray-900 shadow-2xl rounded-2xl w-full max-w-7xl grid main-grid gap-8 p-8">
        
        <!-- LEFT PANE -->
        <div class="flex flex-col space-y-6">
            <h1 class="text-3xl font-bold text-white">AI Voice Studio</h1>
            <div class="relative">
                <textarea id="textInput" class="w-full h-80 p-4 bg-gray-800 border border-gray-700 rounded-lg resize-none focus:ring-2 focus:ring-blue-500 outline-none" placeholder="Enter your narration text here..."></textarea>
                <div id="charCounter" class="absolute bottom-4 right-4 text-xs text-gray-400">0 / 2000</div>
            </div>
            
            <div class="bg-gray-800 p-6 rounded-lg space-y-6">
                <h2 class="text-xl font-semibold text-white">Voice Controls</h2>
                <!-- Speed, Pitch, Volume sliders -->
                <div>
                    <label for="speedSlider" class="flex justify-between text-sm font-medium text-gray-300"><span>Speed</span><span id="speedValue">0%</span></label>
                    <input id="speedSlider" type="range" min="-50" max="50" value="0" class="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                </div>
                <div>
                    <label for="pitchSlider" class="flex justify-between text-sm font-medium text-gray-300"><span>Pitch</span><span id="pitchValue">0Hz</span></label>
                    <input id="pitchSlider" type="range" min="-25" max="25" value="0" class="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                </div>
                <div>
                    <label for="volumeSlider" class="flex justify-between text-sm font-medium text-gray-300"><span>Volume</span><span id="volumeValue">100%</span></label>
                    <input id="volumeSlider" type="range" min="0" max="100" value="100" class="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                </div>
            </div>
        </div>

        <!-- RIGHT PANE -->
        <div class="flex flex-col space-y-6">
            <div id="audioOutput" class="hidden bg-gray-800 p-6 rounded-lg text-center">
                <h2 class="text-xl font-semibold text-white mb-4">Generated Audio</h2>
                <audio id="audioPlayer" controls class="w-full"></audio>
                <a id="downloadButton" class="mt-4 inline-block w-full text-center bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-lg transition">Download MP3</a>
            </div>

            <div class="space-y-4">
                <div>
                    <label for="accentSelect" class="block text-sm font-medium text-gray-300 mb-2">Accent / Language</label>
                    <select id="accentSelect" class="w-full p-3 bg-gray-800 border border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"></select>
                </div>
                <div id="voiceList" class="h-96 overflow-y-auto space-y-2 p-2 bg-gray-800 rounded-lg border border-gray-700">
                    <!-- Voice cards will be populated here -->
                </div>
            </div>
            
            <button id="generateButton" class="w-full bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-4 rounded-lg transition">Generate Speech</button>
            <div id="loadingSpinner" class="hidden flex justify-center items-center pt-4"><div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div></div>
            <div id="errorMessage" class="hidden bg-red-800/50 text-red-300 text-sm p-3 rounded-lg mt-4"></div>
        </div>
    </main>

    <script>
        const $ = id => document.getElementById(id);
        
        let voiceLibrary = {};
        let selectedVoiceId = null;
        let previewAudio = new Audio();
        let activePreviewBtn = null;

        const elements = {
            // ... (all element references)
            voiceList: $('voiceList'),
            accentSelect: $('accentSelect'),
            generateButton: $('generateButton'),
            loadingSpinner: $('loadingSpinner'),
            errorMessage: $('errorMessage'),
            textInput: $('textInput'),
            charCounter: $('charCounter'),
            speedSlider: $('speedSlider'),
            speedValue: $('speedValue'),
            pitchSlider: $('pitchSlider'),
            pitchValue: $('pitchValue'),
            volumeSlider: $('volumeSlider'),
            volumeValue: $('volumeValue'),
            audioOutput: $('audioOutput'),
            audioPlayer: $('audioPlayer'),
            downloadButton: $('downloadButton'),
        };

        function renderVoiceList() {
            const selectedAccent = elements.accentSelect.value;
            const voices = voiceLibrary[selectedAccent]?.voices || [];

            if (!selectedVoiceId && voices.length > 0) {
                selectedVoiceId = voices[0].id;
            }

            elements.voiceList.innerHTML = voices.map(voice => {
                const isSelected = voice.id === selectedVoiceId;
                const accentInfo = Object.entries(voiceLibrary).find(([_, data]) => data.voices.some(v => v.id === voice.id));
                const accentName = accentInfo ? accentInfo[0].split('(')[1]?.replace(')', '') || accentInfo[0] : '';
                
                return `
                    <div class="voice-card bg-gray-700 rounded-lg p-4 flex items-center cursor-pointer relative ${isSelected ? 'ring-2 ring-blue-500' : 'hover:bg-gray-600'}" data-voice-id="${voice.id}">
                        <button class="play-btn relative flex items-center justify-center w-12 h-12 rounded-full bg-gray-800 hover:bg-blue-500 transition mr-4 flex-shrink-0" data-voice-id-preview="${voice.id}">
                            <svg class="play-icon w-6 h-6" fill="currentColor" viewBox="0 0 20 20"><path d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z"></path></svg>
                            <svg class="pause-icon w-6 h-6" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 102 0V8a1 1 0 00-1-1zm4 0a1 1 0 00-1 1v4a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd"></path></svg>
                            <svg class="loading-icon w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.75V6.25m0 11.5v1.5m-8.25-3.5L5 16.25m14-14l-1.25 1.25M5 7.75L3.75 6.5m16.5 11l1.25 1.25M12 21a9 9 0 100-18 9 9 0 000 18z"></path></svg>
                        </button>
                        <div class="flex-grow">
                            <div class="font-bold text-white">${voice.name}</div>
                            <div class="text-xs text-gray-400">${accentName} • ${voice.gender} • ${voice.style}</div>
                        </div>
                        <div class="progress-bar"></div>
                    </div>
                `;
            }).join('');
            
            // Re-attach event listeners
            elements.voiceList.querySelectorAll('.voice-card').forEach(card => {
                card.addEventListener('click', (e) => {
                    if (!e.target.closest('.play-btn')) {
                        selectedVoiceId = card.dataset.voiceId;
                        renderVoiceList();
                    }
                });
            });
            
            elements.voiceList.querySelectorAll('.play-btn').forEach(btn => {
                btn.addEventListener('click', () => handlePreview(btn));
            });
        }
        
        async function handlePreview(btn) {
            const voiceId = btn.dataset.voiceIdPreview;
            const card = btn.closest('.voice-card');
            const progressBar = card.querySelector('.progress-bar');
            
            if (activePreviewBtn === btn && !previewAudio.paused) {
                previewAudio.pause();
                return;
            }

            if (activePreviewBtn) {
                previewAudio.pause(); // This will trigger the 'onpause' event for the old button
            }
            
            activePreviewBtn = btn;
            
            // Reset all other buttons
            elements.voiceList.querySelectorAll('.play-btn').forEach(b => {
                if (b !== btn) {
                    b.classList.remove('playing', 'loading');
                    b.closest('.voice-card').querySelector('.progress-bar').style.width = '0%';
                }
            });

            btn.classList.remove('playing');
            btn.classList.add('loading');
            
            try {
                const response = await fetch(`/api/preview_voice?voice_id=${voiceId}`);
                const result = await response.json();
                if (!response.ok) throw new Error(result.error);
                
                btn.classList.remove('loading');
                btn.classList.add('playing');
                
                previewAudio = new Audio(result.audio);
                previewAudio.play();
                
                previewAudio.addEventListener('timeupdate', () => {
                    if (previewAudio.duration) {
                        progressBar.style.width = `${(previewAudio.currentTime / previewAudio.duration) * 100}%`;
                    }
                });
                
                const onEnd = () => {
                    btn.classList.remove('playing');
                    progressBar.style.width = '0%';
                    activePreviewBtn = null;
                };
                
                previewAudio.addEventListener('ended', onEnd);
                previewAudio.addEventListener('pause', onEnd);

            } catch (error) {
                showError("Could not play voice preview.");
                btn.classList.remove('loading');
            }
        }
        
        // --- Other functions (initialize, renderAccentOptions, handleGenerate, etc.) ---
        // These can remain largely the same as the previous correct implementation
        async function initialize() {
            try {
                const response = await fetch('/api/voices');
                voiceLibrary = await response.json();
                renderAccentOptions();
                renderVoiceList();
            } catch (error) {
                showError("Failed to load voice library.");
            }
        }

        function renderAccentOptions() {
            elements.accentSelect.innerHTML = Object.keys(voiceLibrary).map(accent => 
                `<option value="${accent}">${voiceLibrary[accent].flag} ${accent}</option>`
            ).join('');
        }
        
        elements.accentSelect.addEventListener('change', () => {
            selectedVoiceId = null;
            renderVoiceList();
        });

        elements.textInput.addEventListener('input', () => elements.charCounter.textContent = `${elements.textInput.value.length} / 2000`);
        elements.speedSlider.addEventListener('input', () => elements.speedValue.textContent = `${elements.speedSlider.value}%`);
        elements.pitchSlider.addEventListener('input', () => elements.pitchValue.textContent = `${elements.pitchSlider.value}Hz`);
        elements.volumeSlider.addEventListener('input', () => {
            elements.volumeValue.textContent = `${elements.volumeSlider.value}%`;
            elements.audioPlayer.volume = elements.volumeSlider.value / 100;
        });

        async function handleGenerate() {
            setLoading(true);
            const payload = {
                text: elements.textInput.value,
                voice_id: selectedVoiceId,
                rate: parseInt(elements.speedSlider.value, 10),
                pitch: parseInt(elements.pitchSlider.value, 10),
            };

            try {
                const response = await fetch('/api/synthesize', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.error);

                elements.audioOutput.classList.remove('hidden');
                elements.audioPlayer.src = result.audio;
                elements.downloadButton.href = result.audio;
                elements.audioPlayer.volume = elements.volumeSlider.value / 100;
                elements.audioPlayer.play();

            } catch (error) {
                showError(error.message);
            } finally {
                setLoading(false);
            }
        }
        
        function setLoading(isLoading) {
            elements.generateButton.disabled = isLoading;
            elements.loadingSpinner.classList.toggle('hidden', !isLoading);
            if(isLoading) hideError();
        }

        function showError(message) {
            elements.errorMessage.textContent = message;
            elements.errorMessage.classList.remove('hidden');
        }
        
        function hideError(){
             elements.errorMessage.classList.add('hidden');
        }

        elements.generateButton.addEventListener('click', handleGenerate);
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

@app.route('/api/voices')
def get_voices():
    """Provides the structured voice library to the frontend."""
    return jsonify(VOICE_LIBRARY)

@app.route('/api/preview_voice')
async def api_preview_voice():
    """Generates and returns a preview of a specific voice."""
    voice_id = request.args.get('voice_id')
    if not voice_id:
        return jsonify({"error": "Voice ID is required"}), 400
    
    try:
        audio_data = await tts_engine.preview_voice(voice_id)
        encoded_audio = base64.b64encode(audio_data).decode('utf-8')
        return jsonify({"audio": f"data:audio/mp3;base64,{encoded_audio}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/synthesize', methods=['POST'])
async def api_synthesize():
    """Generates speech from user text and selected settings."""
    data = request.json
    text = data.get('text')
    voice_id = data.get('voice_id')
    rate = data.get('rate', 0)
    pitch = data.get('pitch', 0)

    if not all([text, voice_id]):
        return jsonify({"error": "Text and voice ID are required."}), 400

    try:
        audio_data = await tts_engine.process_tts_request(text, voice_id, rate, pitch)
        encoded_audio = base64.b64encode(audio_data).decode('utf-8')
        return jsonify({"audio": f"data:audio/mp3;base64,{encoded_audio}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
