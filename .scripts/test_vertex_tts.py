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
        
        # Style instructions belong in the dedicated prompt field (never spoken),
        # not in the text field. Test near the 4000-byte text limit.
        plain_text = "This is a test of the length limit. " * 100
        synthesis_input = texttospeech.SynthesisInput(
            text=plain_text[:3800],
            prompt="You are a seasoned news anchor. Speak in a calm, warm, confident voice at a steady, natural pace.",
        )
        
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
