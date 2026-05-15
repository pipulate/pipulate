#!/usr/bin/env python3
# prompt_feeder.py

import subprocess
import time
import sys
import argparse
import os

def main():
    parser = argparse.ArgumentParser(description="Drip-feed a payload into any UI, bypassing RAG-doll paste heuristics.")
    parser.add_argument("file", nargs="?", default="prompt.md", help="The compiled markdown file to inject.")
    parser.add_argument("--delay", type=int, default=2, help="Milliseconds between keystrokes (default: 2)")
    parser.add_argument("--wait", type=int, default=15, help="Seconds to wait before typing begins (default: 15)")
    parser.add_argument("--chunk", type=int, default=0, help="If > 0, bypass typing and do chunked Ctrl+V pasting (size in chars).")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"❌ Error: Could not find payload file '{args.file}'")
        sys.exit(1)

    print(f"🎯 Target acquired. You have {args.wait} seconds to drop your cursor into the AI's text area...")
    for i in range(args.wait, 0, -1):
        print(f"   Commencing injection in {i}...")
        time.sleep(1)

    if args.chunk == 0:
        # THE IV DRIP: Pure synthetic keystrokes. 
        # Bypasses all paste listeners by acting like a very fast human.
        print("🌊 Flooding stdout to cursor via xdotool...")
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                lines = f.read().split('\n')
            
            for line in lines:
                if line:
                    subprocess.run(["xdotool", "type", "--clearmodifiers", "--delay", str(args.delay), line], check=True)
                
                # The Chisel Strike: Shift+Return prevents premature web UI submission
                subprocess.run(["xdotool", "key", "--clearmodifiers", "shift+Return"], check=True)
            print("\n✅ Injection complete.")
        except subprocess.CalledProcessError as e:
            print(f"\n❌ Error during injection: {e}")
    else:
        # THE BOLUS: For massive payloads.
        # Chunks the text, loads the clipboard, and hits Ctrl+V repeatedly.
        print(f"📦 Commencing chunked bolus injections ({args.chunk} chars per bolus)...")
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                content = f.read()

            chunks = [content[i:i + args.chunk] for i in range(0, len(content), args.chunk)]
            
            for i, chunk in enumerate(chunks, 1):
                # Load chunk into X11 clipboard
                process = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
                process.communicate(input=chunk.encode('utf-8'))
                
                # Fire Ctrl+V
                subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+v"], check=True)
                print(f"   Bolus {i}/{len(chunks)} delivered...")
                time.sleep(0.5)  # Let the browser DOM digest the chunk
                
            print("\n✅ Bolus sequence complete.")
        except Exception as e:
            print(f"\n❌ Error during chunked injection: {e}")

if __name__ == "__main__":
    main()
