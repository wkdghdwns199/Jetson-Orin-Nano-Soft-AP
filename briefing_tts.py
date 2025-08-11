	# mqtt_tts_player.py
# Run as your NORMAL user (no sudo), or 'default' audio won't work.

from elevenlabs import ElevenLabs, VoiceSettings
from pathlib import Path
import paho.mqtt.client as mqtt
import subprocess
import json
import os
import threading
import sys

# ====== ElevenLabs config ======
API_KEY   = "sk_ac4e09ad0458fc4212d026d3458e83c3c4870f8e3d89be81"  # rotate later
VOICE_ID  = "RAqQjJCAbQp64iKePkJB"
MODEL_ID  = "eleven_multilingual_v2"
OUT_PATH  = Path("./tts_output/first_move.mp3")

# Voice controls
STABILITY          = 0.4
SIMILARITY_BOOST   = 1.0
STYLE_EXAGGERATION = 1.0
SPEED              = 0.93
USE_SPEAKER_BOOST  = True

# ====== MQTT config ======
MQTT_HOST  = "localhost"   # change if your broker is elsewhere
MQTT_PORT  = 1883
MQTT_TOPIC = "/briefing"        # publish your text here

# Prevent overlapping TTS runs
_play_lock = threading.Lock()

def generate_and_play(text: str):
    text = (text or "").strip()
    if not text:
        print("[WARN] Empty text. Ignoring.")
        return

    with _play_lock:  # serialize TTS+play
        # Ensure output directory exists
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

        # ElevenLabs client
        tts_client = ElevenLabs(api_key=API_KEY)

        print(f"[INFO] Synthesizing: {text[:60]}{'...' if len(text) > 60 else ''}")
        stream = tts_client.text_to_speech.convert(
            text=text,
            voice_id=VOICE_ID,
            model_id=MODEL_ID,
            output_format="mp3_44100_128",
            voice_settings=VoiceSettings(
                stability=STABILITY,
                similarity_boost=SIMILARITY_BOOST,
                style=STYLE_EXAGGERATION,
                use_speaker_boost=USE_SPEAKER_BOOST,
                speed=SPEED,
            ),
        )

        # Save MP3
        written = 0
        with open(OUT_PATH, "wb") as f:
            for chunk in stream:
                if chunk:
                    f.write(chunk)
                    written += len(chunk)

        print(f"[OK] Saved: {OUT_PATH} ({written} bytes)")
        if written == 0:
            print("[ERR] No audio was downloaded.")
            return

        # Play exactly as requested
        print(f"[INFO] Playing: mpg123 -a default {OUT_PATH}")
        # IMPORTANT: don’t run this script with sudo, or 'default' may be silent.
        subprocess.run(["mpg123", "-a", "default", str(OUT_PATH)])

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"[OK] Connected to MQTT {MQTT_HOST}:{MQTT_PORT}. Subscribing {MQTT_TOPIC}")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"[ERR] MQTT connect failed with code {rc}")

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8", errors="ignore").strip()
        # Try JSON first: {"text": "..."}
        text = None
        if payload.startswith("{"):
            data = json.loads(payload)
            text = data.get("text")
        else:
            text = payload

        print(f"[MQTT] Topic={msg.topic} Payload='{payload}'")
        generate_and_play(text)
    except Exception as e:
        print(f"[ERR] on_message exception: {e}", file=sys.stderr)

def main():
    if os.geteuid() == 0:
        print("[ERR] Don't run this with sudo. Run as your normal user.")
        sys.exit(1)

    # MQTT client (clean session)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"[INFO] Connecting MQTT to {MQTT_HOST}:{MQTT_PORT} …")
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_forever()

if __name__ == "__main__":
    main()

