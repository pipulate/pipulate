#!/usr/bin/env python3
"""
🌊 Stream Orchestrator
The 'Mind' of the Honeybot.
Handles the intro, launches the visualizer, and eventually manages the browser.
"""

import os
import sys
import time
import subprocess
from pathlib import Path

# --- Configuration ---
# We assume the system capabilities (piper, aplay) are present via configuration.nix
MODEL_DIR = Path.home() / ".local/share/piper_voices"
MODEL_NAME = "en_US-amy-low.onnx"

def speak(text):
    """Speak text using the system's piper-tts capability."""
    print(f"🔊 Speaking: {text}")
    
    # Check if model exists (it should, thanks to the 'hello' script or manual setup)
    # If not, we could download it here, but let's assume the system is primed.
    model_path = MODEL_DIR / MODEL_NAME
    
    if not model_path.exists():
        print(f"❌ Voice model not found at {model_path}")
        return

    try:
        # Pipeline: echo -> piper -> aplay
        # We use Popen to stream data
        p1 = subprocess.Popen(["echo", text], stdout=subprocess.PIPE)
        p2 = subprocess.Popen(
            ["piper", "--model", str(model_path), "--output_raw"],
            stdin=p1.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        p1.stdout.close()
        subprocess.run(
            ["aplay", "-r", "22050", "-f", "S16_LE", "-t", "raw"],
            stdin=p2.stdout,
            stderr=subprocess.DEVNULL,
            check=True
        )
    except Exception as e:
        print(f"❌ Speech failed: {e}")

def run_sonar():
    """Launch the Sonar log visualizer."""
    print("🌊 Launching Sonar...")
    # We assume sonar.py is in the same directory
    script_dir = Path(__file__).parent
    sonar_script = script_dir / "sonar.py"
    
    # We need to pipe the logs into sonar. 
    # In the full deployment, this might be handled differently, 
    # but for now we mirror the 'tail -f' behavior.
    
    # Command: tail -f /var/log/nginx/access.log | python3 sonar.py
    try:
        tail_proc = subprocess.Popen(
            ["tail", "-f", "/var/log/nginx/access.log"],
            stdout=subprocess.PIPE
        )
        
        # We run sonar and let it take over the foreground
        subprocess.run(
            [sys.executable, str(sonar_script)],
            stdin=tail_proc.stdout,
            check=True
        )
    except KeyboardInterrupt:
        print("\n🌊 Sonar stopped.")
    finally:
        tail_proc.terminate()

def main():
    print("🎬 Stream Orchestrator Starting...")
    
    # 1. The Intro
    speak("System Online. Connecting to the Black River.")
    time.sleep(1)
    
    # 2. The Main Event
    run_sonar()
    
    # 3. The Outro (If Sonar crashes or exits)
    speak("Visual link lost. Resetting connection.")
    time.sleep(1)

if __name__ == "__main__":
    main()