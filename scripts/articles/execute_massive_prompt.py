#!/usr/bin/env python3
import argparse
import sys
import os
from pathlib import Path
import llm
import common

# --- CONFIGURATION ---
# Default to the heavy lifter since this is for massive context windows
DEFAULT_MODEL = 'gemini-flash-latest'

def main():
    parser = argparse.ArgumentParser(description="Execute massive prompts directly via the LLM API.")
    parser.add_argument('prompt_file', type=str, help="Path to the file containing the full generated prompt.")
    parser.add_argument('-m', '--model', type=str, default=DEFAULT_MODEL, help=f"Model to use (default: {DEFAULT_MODEL})")
    
    # Use common to get API keys safely
    common.add_standard_arguments(parser)
    args = parser.parse_args()

    prompt_path = Path(args.prompt_file)
    if not prompt_path.exists():
        print(f"❌ Error: File not found at {prompt_path}")
        sys.exit(1)

    print(f"📖 Reading prompt from {prompt_path.name}...")
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_content = f.read()
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        sys.exit(1)

    # Get the API Key using your existing robust method
    api_key = common.get_api_key(args.key)

    print(f"🚀 Engaging Universal Adapter: {args.model}...")
    try:
        model = llm.get_model(args.model)
        model.key = api_key
        
        # Stream the response if the model supports it, otherwise wait
        print("⏳ Waiting for response (this may take a minute for massive contexts)...\n")
        print("--- RESPONSE START ---\n")
        
        response = model.prompt(prompt_content)
        
        # Try to stream for immediate feedback
        try:
            for chunk in response:
                print(chunk, end="", flush=True)
            print("\n")
        except TypeError:
            # Fallback if the specific plugin doesn't support streaming
            print(response.text())
            print("\n")
            
        print("--- RESPONSE END ---")
        print("✅ Execution complete.")

    except Exception as e:
        print(f"\n❌ API Execution Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
