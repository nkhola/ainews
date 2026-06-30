import os
import subprocess
import re

def synthesize_with_google_tts(plain_text, audio_file_path, use_gemini=True):
    from google.cloud import texttospeech
    
    project_id = os.environ.get("VERTEX_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("VERTEX_LOCATION", "us-central1")
    if not location:
        location = "us-central1"
        
    endpoint = f"{location}-texttospeech.googleapis.com"
    client = texttospeech.TextToSpeechClient(
        client_options={"api_endpoint": endpoint}
    )
    
    if use_gemini:
        voice_prompt = "[professional energetic news anchor dynamic pacing] "
        steered_text = plain_text
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="Puck",
            model_name="gemini-2.5-flash-tts"
        )
    else:
        voice_prompt = ""
        steered_text = plain_text
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="en-US-Journey-F"
        )

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )
    
    sentences = re.split(r'(?<=[.!?])\s+', steered_text)
    chunks = []
    current_chunk = ""
    for s in sentences:
        if len(current_chunk) + len(s) < 4000:
            current_chunk += s + " "
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = s + " "
    if current_chunk:
        chunks.append(current_chunk.strip())
        
    full_audio_content = b""
    for idx, chunk in enumerate(chunks):
        if not chunk: continue
        
        steered_chunk = voice_prompt + chunk
        
        print(f"  Synthesizing chunk {idx+1}/{len(chunks)}...")
        synthesis_input = texttospeech.SynthesisInput(text=steered_chunk)
        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        full_audio_content += response.audio_content
        
    with open(audio_file_path, "wb") as out:
        out.write(full_audio_content)

def generate_audio_with_fallback(plain_text, audio_file_path, dry_run=False):
    if dry_run:
        print(f"[DRY-RUN] Skipping actual Vertex AI TTS request for {audio_file_path}.")
        with open(audio_file_path, "wb") as f:
            f.write(b"mock audio data")
        return

    print(f"Attempting Vertex AI TTS (Gemini Puck voice) for {audio_file_path}...")
    try:
        synthesize_with_google_tts(plain_text, audio_file_path, use_gemini=True)
        print("Vertex AI TTS (Gemini) successful.")
        return
    except Exception as e:
        print(f"Vertex AI TTS (Gemini) failed: {e}. Falling back to Traditional Cloud TTS...")

    try:
        synthesize_with_google_tts(plain_text, audio_file_path, use_gemini=False)
        print("Vertex AI TTS (Journey) successful.")
        return
    except Exception as e:
        print(f"Vertex AI TTS (Journey) failed: {e}. Falling back to edge-tts...")
    
    # Fallback to edge-tts
    try:
        subprocess.run([
            "edge-tts",
            "--text", plain_text,
            "--write-media", audio_file_path,
            "--voice", "en-US-ChristopherNeural"
        ], check=True)
        print("edge-tts fallback successful.")
    except Exception as e:
        print(f"Error generating audio via edge-tts: {e}")
