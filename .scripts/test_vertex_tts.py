import sys
import os

def test_vertex_tts():
    try:
        from google.cloud import texttospeech
    except ImportError:
        print("google-cloud-texttospeech is not installed!")
        sys.exit(1)
        
    try:
        print("Initializing TextToSpeechClient...")
        client = texttospeech.TextToSpeechClient()
        
        plain_text = "Hello! This is a test of the Google Cloud Text-to-Speech API using the Gemini Puck voice."
        synthesis_input = texttospeech.SynthesisInput(text=plain_text)
        
        # Gemini voices: Puck, Charon, Kore, Aoede, etc.
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="Puck"
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
