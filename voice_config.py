# voice_config.py

# --- VOICE LIBRARY ARCHITECTURE ---
# This file serves as the single source of truth for all voice data.
# Each voice includes metadata for UI population and a unique preview script.

VOICE_LIBRARY = {
    "English (United States)": {
        "flag": "US",
        "voices": [
            {"id": "en-US-JennyNeural", "name": "Jenny", "gender": "Female", "style": "Conversational, Friendly", "preview_text": "Hello, my name is Jenny. I have a friendly and expressive voice, perfect for a wide range of projects."},
            {"id": "en-US-GuyNeural", "name": "Guy", "gender": "Male", "style": "Professional, Clear", "preview_text": "Hi, I'm Guy. My voice is professional and clear, making me a great choice for presentations and narration."},
            {"id": "en-US-AriaNeural", "name": "Aria", "gender": "Female", "style": "Warm, Engaging", "preview_text": "I'm Aria. My warm and engaging tone is ideal for storytelling and audiobooks that need a personal touch."},
            {"id": "en-US-BrandonNeural", "name": "Brandon", "gender": "Male", "style": "Calm, Reassuring", "preview_text": "This is Brandon. I have a calm and reassuring voice, which is well-suited for instructional content and guided tutorials."},
            {"id": "en-US-AvaNeural", "name": "Ava", "gender": "Female", "style": "Bright, Commercial", "preview_text": "I'm Ava. My bright commercial tone works well for ads, promos, and dynamic product demos."},
            {"id": "en-US-AndrewNeural", "name": "Andrew", "gender": "Male", "style": "Balanced, Neutral", "preview_text": "Hi, I'm Andrew. My neutral style is ideal for explainers, e-learning, and business narration."},
        ]
    },
    "English (United Kingdom)": {
        "flag": "UK",
        "voices": [
            {"id": "en-GB-LibbyNeural", "name": "Libby", "gender": "Female", "style": "Sophisticated, Clear", "preview_text": "Hello, I'm Libby. With a sophisticated and clear voice, I am an excellent choice for educational content and documentaries."},
            {"id": "en-GB-RyanNeural", "name": "Ryan", "gender": "Male", "style": "Modern, Engaging", "preview_text": "I'm Ryan. My modern and engaging voice is perfect for marketing materials and explainer videos that need a fresh sound."},
            {"id": "en-GB-SoniaNeural", "name": "Sonia", "gender": "Female", "style": "Polished, Warm", "preview_text": "I'm Sonia. My polished and warm British voice is great for premium brand content and tutorials."},
            {"id": "en-GB-ThomasNeural", "name": "Thomas", "gender": "Male", "style": "Authoritative, Calm", "preview_text": "I'm Thomas. My calm and authoritative style suits narration, courses, and voice-over work."},
        ]
    },
    "English (Africa)": {
        "flag": "AF",
        "voices": [
            {"id": "en-NG-AbeoNeural", "name": "Abeo (Nigeria)", "gender": "Male", "style": "Deep, Resonant", "preview_text": "My name is Abeo, from Nigeria. I have a deep and resonant voice that is ideal for storytelling and narration."},
            {"id": "en-KE-AsiliaNeural", "name": "Asilia (Kenya)", "gender": "Female", "style": "Warm, Gentle", "preview_text": "Hello, I am Asilia from Kenya. My voice is warm and gentle, making it perfect for welcoming messages and calm content."},
            {"id": "en-ZA-LeahNeural", "name": "Leah (South Africa)", "gender": "Female", "style": "Clear, Professional", "preview_text": "I'm Leah, from South Africa. I have a clear and professional voice that is suitable for a wide variety of applications."},
        ]
    },
    "English (Australia)": {
        "flag": "AU",
        "voices": [
            {"id": "en-AU-NatashaNeural", "name": "Natasha", "gender": "Female", "style": "Friendly, Energetic", "preview_text": "Hi, I'm Natasha from Australia. My energetic voice works well for social content and lively narration."},
            {"id": "en-AU-WilliamNeural", "name": "William", "gender": "Male", "style": "Steady, Informative", "preview_text": "I'm William. My steady delivery is useful for product explainers and professional voice-over."},
        ]
    },
    "English (Canada)": {
        "flag": "CA",
        "voices": [
            {"id": "en-CA-ClaraNeural", "name": "Clara", "gender": "Female", "style": "Natural, Friendly", "preview_text": "Hello, I'm Clara from Canada. My natural style is ideal for approachable narration and support content."},
            {"id": "en-CA-LiamNeural", "name": "Liam", "gender": "Male", "style": "Clear, Confident", "preview_text": "I'm Liam. My clear and confident voice fits training, educational, and business scripts."},
        ]
    },
    "English (India)": {
        "flag": "IN",
        "voices": [
            {"id": "en-IN-NeerjaNeural", "name": "Neerja", "gender": "Female", "style": "Warm, Professional", "preview_text": "Hi, I'm Neerja from India. My warm professional tone is great for presentations and e-learning."},
            {"id": "en-IN-PrabhatNeural", "name": "Prabhat", "gender": "Male", "style": "Smooth, Clear", "preview_text": "I'm Prabhat. My smooth and clear style works well for narration, tutorials, and announcements."},
        ]
    },
    "English (Ireland)": {
        "flag": "IE",
        "voices": [
            {"id": "en-IE-EmilyNeural", "name": "Emily", "gender": "Female", "style": "Soft, Expressive", "preview_text": "Hello, I'm Emily from Ireland. My soft expressive voice is a strong fit for storytelling and branded content."},
            {"id": "en-IE-ConnorNeural", "name": "Connor", "gender": "Male", "style": "Rich, Calm", "preview_text": "I'm Connor. My rich calm style is ideal for documentaries and long-form narration."},
        ]
    },
}
