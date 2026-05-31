# AI Voice Studio

A professional Text-to-Speech (TTS) application built with Flask and `edge-tts`, featuring a clean, intuitive UI/UX, dynamic voice selection with previews, and adjustable voice controls.

## Features

*   **Modern UI/UX:** Responsive two-column layout inspired by professional TTS platforms.
*   **Dynamic Voice Selection:** Choose from various English accents (US, UK, African) with dynamic filtering.
*   **Voice Preview:** Each voice includes a prominent play button to instantly preview a fixed sample with style metadata.
*   **Adjustable Controls:** Real-time sliders for Speed, Pitch, and Volume to fine-tune the audio output.
*   **Performance Optimized:** Voice previews and repeated synthesis requests are cached for near-instant playback.
*   **Clean Architecture:** Separated concerns into `app.py`, `tts_engine.py`, and `voice_config.py` for maintainability and extensibility.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd ai-voice-studio
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  **Run the application:**
    ```bash
    python app.py
    ```
    The application will start a Flask development server, and a web browser will automatically open to `http://127.0.0.1:5000`.

2.  **Generate Speech:**
    *   Enter your desired text in the left-hand text area.
    *   Select an accent from the dropdown.
    *   Browse the available voices. Click the ▶ button to preview a voice.
    *   Click anywhere on a voice card to select it for generation.
    *   Adjust Speed, Pitch, and Volume sliders as needed.
    *   Click "Generate Speech" to synthesize the audio.
    *   Use the audio player to listen or the "Download MP3" button to save the file.

## Project Structure

*   `app.py`: Main Flask application, handles routes and serves the UI.
*   `tts_engine.py`: Core Text-to-Speech logic, including synthesis and caching.
*   `voice_config.py`: Configuration for all available voices and their metadata.
*   `requirements.txt`: Python dependencies.
*   `.gitignore`: Specifies intentionally untracked files to ignore.

## Contributing

(If you plan to allow contributions, you can add guidelines here.)

## License

(Specify your chosen license here, e.g., MIT, Apache 2.0, etc.)
