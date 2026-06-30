import sys
import os

def test_vertex_tts():
    try:
        from google.cloud import texttospeech
        import os
        
        project_id = os.environ.get("VERTEX_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
        location = os.environ.get("VERTEX_LOCATION", "us-central1")
        if not location:
            location = "us-central1"
            
        endpoint = f"{location}-texttospeech.googleapis.com"
        print(f"Initializing TextToSpeechClient with endpoint: {endpoint}")
        client = texttospeech.TextToSpeechClient(
            client_options={"api_endpoint": endpoint}
        )
        
        plain_text = "[professional, energetic news anchor. dynamic pacing.] " + ("This is a long sentence to test the length limits. " * 200)
        synthesis_input = texttospeech.SynthesisInput(text=plain_text)
        
        # Gemini voices: Puck, Charon, Kore, Aoede, etc.
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="Puck",
            model_name="gemini-2.5-flash-tts"
        )
        
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )
        
        print("Sending synthesis request...")
        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        
        output_file = "test_journey.mp3"
        with open(output_file, "wb") as out:
            out.write(response.audio_content)
            
        print(f"Success! Audio content written to {output_file}")
        
    except Exception as e:
        print(f"FAILED to generate TTS. Exception: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_vertex_tts()
