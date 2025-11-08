#!/usr/bin/env python3
"""
Generate Arabic audio files for Levantine vocabulary using ElevenLabs.
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

# Configuration
VOCAB_FILE = Path(__file__).parent / "levantine_vocabulary.json"
OUTPUT_DIR = Path(__file__).parent / "audio"
VOICE_ID = "drMurExmkWVIH5nW8snR"
MODEL_ID = "eleven_flash_v2_5"
OUTPUT_FORMAT = "mp3_44100_128"  # 128kbps mp3

def load_vocabulary():
    """Load vocabulary from JSON file."""
    with open(VOCAB_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_audio_files():
    """Generate audio files for all vocabulary words."""
    # Load environment and initialize client
    load_dotenv()
    api_key = os.getenv("ELEVENLABS_API_KEY")

    if not api_key:
        print("Error: ELEVENLABS_API_KEY not found in .env file")
        return

    client = ElevenLabs(api_key=api_key)

    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Load vocabulary
    vocab = load_vocabulary()
    total = len(vocab)

    print(f"Generating audio for {total} vocabulary words...")
    print(f"Voice ID: {VOICE_ID}")
    print(f"Output format: {OUTPUT_FORMAT}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("-" * 60)

    # Track progress
    successful = 0
    failed = 0
    skipped = 0

    for idx, entry in enumerate(vocab, start=1):
        arabic_text = entry['arabic']
        filename = f"{idx:03d}.mp3"
        output_path = OUTPUT_DIR / filename

        # Skip if file already exists
        if output_path.exists():
            print(f"[{idx:03d}/{total}] Skipping (already exists): {arabic_text}")
            skipped += 1
            continue

        try:
            # Voice settings for consistent vocabulary pronunciation
            voice_settings = {
                "stability": 1.0,  # Maximum stability, no drama
                "style": 0.0,      # No style exaggeration
            }

            # Generate audio
            audio = client.text_to_speech.convert(
                text=arabic_text,
                voice_id=VOICE_ID,
                model_id=MODEL_ID,
                output_format=OUTPUT_FORMAT,
                voice_settings=voice_settings,
            )

            # Handle both bytes and generator responses
            if isinstance(audio, bytes):
                audio_data = audio
            else:
                # Generator - collect all chunks
                audio_data = b"".join(audio)

            # Save to file
            with open(output_path, 'wb') as f:
                f.write(audio_data)

            print(f"[{idx:03d}/{total}] Generated: {arabic_text} -> {filename}")
            successful += 1

        except Exception as e:
            print(f"[{idx:03d}/{total}] FAILED: {arabic_text} - {str(e)}")
            failed += 1

    # Summary
    print("-" * 60)
    print(f"Complete!")
    print(f"  Successful: {successful}")
    print(f"  Skipped (already exists): {skipped}")
    print(f"  Failed: {failed}")
    print(f"  Total: {total}")

if __name__ == "__main__":
    generate_audio_files()
