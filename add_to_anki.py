#!/usr/bin/env python3
"""
Add Arabic vocabulary words to Anki using AnkiConnect.
Adds 5 random words per day (10 cards: Arabic->English and English->Arabic).
"""

import json
import urllib.request
import urllib.error
import sys
import random
import subprocess
import time
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

# Configuration
WORDS_PER_DAY = 10
DECK_NAME = "Arabic"
REMAINING_WORDS_FILE = Path(__file__).parent / "remaining_words.json"
BACKUP_FILE = Path(__file__).parent / "levantine_vocabulary.json"
LOG_FILE = Path(__file__).parent / "notifs.log"
CSS_FILE = Path(__file__).parent / "anki_card_style.css"
ANKI_CONNECT_URL = "http://localhost:8765"
ANKI_STARTUP_WAIT = 5  # seconds to wait for Anki to start
AUDIO_DIR = Path(__file__).parent / "audio"

def send_notification(title: str, message: str, urgency: str = "normal") -> None:
    """Send desktop notification using notify-send."""
    try:
        subprocess.run(
            ["notify-send", "-u", urgency, "-a", "Anki Arabic", title, message],
            check=False,
            timeout=5
        )
        # Log notification to file
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {title}: {message}\n")
    except Exception:
        pass  # Silently fail if notify-send is not available

def is_anki_running() -> bool:
    """Check if Anki process is running."""
    try:
        result = subprocess.run(["pgrep", "-x", "anki"], capture_output=True)
        return result.returncode == 0
    except Exception:
        return False


def is_ankiconnect_ready() -> bool:
    """Check if AnkiConnect API is responding."""
    try:
        request_data = json.dumps({"action": "version", "version": 6}).encode("utf-8")
        req = urllib.request.Request(ANKI_CONNECT_URL, request_data)
        urllib.request.urlopen(req, timeout=1).read()
        return True
    except Exception:
        return False


def start_anki() -> Optional[subprocess.Popen]:
    """Start Anki in the background (offscreen mode)."""
    print("Starting Anki...")
    try:
        # Try to start Anki with minimal display (offscreen Qt platform)
        # Disable GPU acceleration to avoid graphics context errors
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        env["QTWEBENGINE_DISABLE_SANDBOX"] = "1"
        env["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --disable-software-rasterizer --disable-dev-shm-usage"

        process = subprocess.Popen(
            ["anki"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Wait for AnkiConnect to be ready
        for i in range(30):  # Try for 30 seconds
            time.sleep(1)
            if is_ankiconnect_ready():
                print(f"Anki started successfully (PID: {process.pid})")
                # Give Anki extra time to fully initialize in offscreen mode
                print("Waiting for Anki to fully initialize...")
                time.sleep(5)
                return process

        print("Warning: Anki started but AnkiConnect may not be ready")
        return process

    except FileNotFoundError:
        raise Exception("Anki executable not found. Is Anki installed?")
    except Exception as e:
        raise Exception(f"Failed to start Anki: {e}")


def stop_anki() -> None:
    """Stop Anki gracefully using AnkiConnect."""
    try:
        invoke_anki("sync")  # Sync before closing
        time.sleep(1)
        # Note: guiExitAnki might not work in offscreen mode, so we'll let the process continue
        # The systemd service will clean it up if needed
        print("Anki sync completed")
    except Exception as e:
        print(f"Note: Could not sync/close Anki gracefully: {e}")


def invoke_anki(action: str, **params) -> Any:
    """Call AnkiConnect API."""
    request_data = json.dumps({"action": action, "version": 6, "params": params}).encode("utf-8")

    try:
        req = urllib.request.Request(ANKI_CONNECT_URL, request_data)
        response = urllib.request.urlopen(req, timeout=10).read().decode("utf-8")
        result = json.loads(response)

        if result.get("error"):
            raise Exception(f"AnkiConnect error: {result['error']}")

        return result.get("result")
    except urllib.error.URLError as e:
        raise Exception(f"Failed to connect to AnkiConnect: {e}")


def ensure_deck_exists(deck_name: str) -> None:
    """Create deck if it doesn't exist."""
    decks = invoke_anki("deckNames")
    if deck_name not in decks:
        invoke_anki("createDeck", deck=deck_name)
        print(f"Created deck: {deck_name}")


def load_css() -> str:
    """Load CSS from external file."""
    try:
        with open(CSS_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise Exception(f"CSS file not found: {CSS_FILE}")


def store_audio_file(audio_index: int) -> str:
    """Store audio file in Anki's media collection and return HTML audio element."""
    import base64

    # Format: index 1 → 001.mp3, index 2 → 002.mp3, etc.
    audio_filename = f"{audio_index:03d}.mp3"
    audio_path = AUDIO_DIR / audio_filename

    if not audio_path.exists():
        print(f"Warning: Audio file not found: {audio_filename}")
        return ""

    # Read and encode audio file
    with open(audio_path, 'rb') as f:
        audio_data = base64.b64encode(f.read()).decode('utf-8')

    # Store in Anki's media collection
    invoke_anki("storeMediaFile", filename=audio_filename, data=audio_data)

    # Return HTML audio element (manual playback, no auto-play)
    return f'<audio src="{audio_filename}" controls preload="metadata"></audio>'


def get_model_name() -> str:
    """Get or create the note type for Arabic cards with two templates."""
    model_name = "Arabic-Bidirectional-v2"
    models = invoke_anki("modelNames")

    if model_name not in models:
        print(f"Creating note type '{model_name}'...")
        try:
            css = load_css()

            # Create a new model with FOUR fields and TWO card templates
            result = invoke_anki(
                "createModel",
                modelName=model_name,
                inOrderFields=["English", "Arabic", "Pronunciation", "Audio"],
                css=css,
                cardTemplates=[
                    {
                        "Name": "English → Arabic",
                        "Front": '<div class="english">{{English}}</div>',
                        "Back": '{{FrontSide}}<hr id="answer"><div class="arabic">{{Arabic}}</div><div class="pronunciation">{{Pronunciation}}</div><div class="audio">{{Audio}}</div>'
                    },
                    {
                        "Name": "Arabic → English",
                        "Front": '<div class="arabic">{{Arabic}}</div><div class="audio">{{Audio}}</div>',
                        "Back": '{{FrontSide}}<hr id="answer"><div class="english">{{English}}</div><div class="pronunciation">{{Pronunciation}}</div>'
                    }
                ]
            )
            print(f"✓ Note type created: {model_name}")
        except Exception as e:
            print(f"Error creating note type: {e}")
            raise

    return model_name


def initialize_remaining_words() -> None:
    """Copy backup file to remaining_words.json if it doesn't exist."""
    if not REMAINING_WORDS_FILE.exists():
        print(f"Creating {REMAINING_WORDS_FILE.name} from backup...")
        with open(BACKUP_FILE, "r", encoding="utf-8") as src:
            content = src.read()
        with open(REMAINING_WORDS_FILE, "w", encoding="utf-8") as dst:
            dst.write(content)
        print(f"Initialized with {len(json.loads(content))} words")


def load_remaining_words() -> List[Dict[str, str]]:
    """Load remaining words from JSON file."""
    with open(REMAINING_WORDS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_remaining_words(words: List[Dict[str, str]]) -> None:
    """Save remaining words back to JSON file."""
    with open(REMAINING_WORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(words, f, indent=2, ensure_ascii=False)


def add_note(deck: str, model: str, english: str, arabic: str, pronunciation: str, audio: str) -> None:
    """Add a single note to Anki (creates 2 cards automatically via templates)."""
    invoke_anki(
        "addNote",
        note={
            "deckName": deck,
            "modelName": model,
            "fields": {
                "English": english,
                "Arabic": arabic,
                "Pronunciation": pronunciation,
                "Audio": audio
            },
            "options": {
                "allowDuplicate": False
            },
            "tags": ["arabic", "levantine"]
        }
    )


def main():
    """Main function to add words to Anki."""
    anki_process = None
    started_anki = False

    try:
        # Check if Anki is running, start if needed
        if is_ankiconnect_ready():
            print("Anki is already running")
        elif is_anki_running():
            print("Anki process found, waiting for AnkiConnect...")
            # Give it some time to fully start
            for i in range(10):
                time.sleep(1)
                if is_ankiconnect_ready():
                    break
        else:
            print("Anki is not running")
            anki_process = start_anki()
            started_anki = True

        # Verify AnkiConnect is available
        version = invoke_anki("version")
        print(f"Connected to AnkiConnect (version {version})")

        # Setup
        ensure_deck_exists(DECK_NAME)
        model_name = get_model_name()
        initialize_remaining_words()

        # Load remaining words
        remaining_words = load_remaining_words()

        # Validate that all words have index field
        if remaining_words and not all("index" in word for word in remaining_words):
            raise Exception(
                f"Vocabulary missing 'index' field. Delete {REMAINING_WORDS_FILE.name} and restart to regenerate."
            )

        if not remaining_words:
            msg = "All words have been added to Anki! 🎉"
            print(f"No words remaining! {msg}")
            print(f"To start over, delete {REMAINING_WORDS_FILE.name}")
            send_notification("Arabic Learning Complete!", msg, "normal")
            return

        # Select random words
        num_to_add = min(WORDS_PER_DAY, len(remaining_words))
        selected_words = random.sample(remaining_words, num_to_add)

        print(f"Randomly selected {num_to_add} words from {len(remaining_words)} remaining")
        print("-" * 50)

        # Add notes (each note creates 2 cards via templates)
        cards_added = 0
        successfully_added = []

        for word in selected_words:
            english = word["english"]
            arabic = word["arabic"]
            pronunciation = word["pronunciation"]
            audio_index = word["index"]

            try:
                # Store audio file and get [sound:...] tag
                audio_tag = store_audio_file(audio_index)

                # Add one note (creates 2 cards: English→Arabic and Arabic→English)
                add_note(DECK_NAME, model_name, english, arabic, pronunciation, audio_tag)
                cards_added += 2  # One note creates 2 cards

                print(f"✓ Added: {english} ({pronunciation}) ↔ {arabic} [Audio: {audio_index:03d}.mp3]")
                successfully_added.append(word)

            except Exception as e:
                if "duplicate" in str(e).lower():
                    print(f"⊘ Skipped (duplicate): {english} ↔ {arabic}")
                    # Still mark as successfully processed (remove from remaining)
                    successfully_added.append(word)
                else:
                    raise

        # Remove successfully added words from remaining_words
        for word in successfully_added:
            remaining_words.remove(word)

        save_remaining_words(remaining_words)

        print("-" * 50)
        print(f"Successfully added {cards_added} cards ({len(successfully_added)} words)")
        print(f"Remaining: {len(remaining_words)} words")

        if remaining_words:
            print(f"Next run will add {min(WORDS_PER_DAY, len(remaining_words))} more random words")
            # Send success notification
            send_notification(
                "Arabic Words Added! 📚",
                f"Added {len(successfully_added)} new words ({cards_added} cards)\n{len(remaining_words)} words remaining",
                "normal"
            )
        else:
            print("🎉 All words have been added!")
            send_notification("Arabic Learning Complete!", "All vocabulary words have been added! 🎉", "normal")

    except Exception as e:
        error_msg = str(e)
        print(f"Error: {error_msg}", file=sys.stderr)
        send_notification("Arabic Words Error ⚠️", f"Failed to add words: {error_msg}", "critical")
        sys.exit(1)

    finally:
        # Clean up: sync and close Anki if we started it
        if started_anki and anki_process:
            print("\nCleaning up...")
            stop_anki()
            if anki_process.poll() is None:  # Process still running
                print(f"Terminating Anki process (PID: {anki_process.pid})")
                anki_process.terminate()
                try:
                    anki_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print("Force killing Anki process")
                    anki_process.kill()


if __name__ == "__main__":
    main()
