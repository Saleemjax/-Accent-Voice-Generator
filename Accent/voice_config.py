# voice_config.py

# --- VOICE LIBRARY ARCHITECTURE ---
# This file serves as the single source of truth for all voice data.
# Each voice includes metadata for UI population and a unique preview script.

VOICE_LIBRARY = {
    "English (United States)": {
        "flag": "🇺🇸",
        "voices": [
            {"id": "en-US-JennyNeural", "name": "Jenny", "gender": "Female", "style": "Conversational, Friendly", "preview_text": "Hello, my name is Jenny. I have a friendly and expressive voice, perfect for a wide range of projects."},
            {"id": "en-US-GuyNeural", "name": "Guy", "gender": "Male", "style": "Professional, Clear", "preview_text": "Hi, I'm Guy. My voice is professional and clear, making me a great choice for presentations and narration."},
            {"id": "en-US-AriaNeural", "name": "Aria", "gender": "Female", "style": "Warm, Engaging", "preview_text": "I'm Aria. My warm and engaging tone is ideal for storytelling and audiobooks that need a personal touch."},
            {"id": "en-US-BrandonNeural", "name": "Brandon", "gender": "Male", "style": "Calm, Reassuring", "preview_text": "This is Brandon. I have a calm and reassuring voice, which is well-suited for instructional content and guided tutorials."},
        ]
    },
    "English (United Kingdom)": {
        "flag": "🇬🇧",
        "voices": [
            {"id": "en-GB-LibbyNeural", "name": "Libby", "gender": "Female", "style": "Sophisticated, Clear", "preview_text": "Hello, I'm Libby. With a sophisticated and clear voice, I am an excellent choice for educational content and documentaries."},
            {"id": "en-GB-RyanNeural", "name": "Ryan", "gender": "Male", "style": "Modern, Engaging", "preview_text": "I'm Ryan. My modern and engaging voice is perfect for marketing materials and explainer videos that need a fresh sound."},
        ]
    },
    "English (Africa)": {
        "flag": "🌍",
        "voices": [
            {"id": "en-NG-AbeoNeural", "name": "Abeo (Nigeria)", "gender": "Male", "style": "Deep, Resonant", "preview_text": "My name is Abeo, from Nigeria. I have a deep and resonant voice that is ideal for storytelling and narration."},
            {"id": "en-KE-AsiliaNeural", "name": "Asilia (Kenya)", "gender": "Female", "style": "Warm, Gentle", "preview_text": "Hello, I am Asilia from Kenya. My voice is warm and gentle, making it perfect for welcoming messages and calm content."},
            {"id": "en-ZA-LeahNeural", "name": "Leah (South Africa)", "gender": "Female", "style": "Clear, Professional", "preview_text": "I'm Leah, from South Africa. I have a clear and professional voice that is suitable for a wide variety of applications."},
        ]
    },
}
