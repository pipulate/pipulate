#!/usr/bin/env python3
import sys
import shutil
import subprocess

def copy_to_clipboard(text: str):
    if not shutil.which('xclip'):
        print("\nWarning: 'xclip' not found. Cannot copy to clipboard.")
        return
    try:
        subprocess.run(['xclip', '-selection', 'clipboard'], input=text.encode('utf-8'), check=True)
        print("✅ Ruler copied to clipboard!")
    except Exception as e:
        print(f"\nWarning: Could not copy to clipboard: {e}")

def generate_ruler(target_bytes=2_500_000):
    """
    Generates a string where every 10 characters represents a block 
    ending with the current character count.
    Format: 00000000100000000020...
    """
    print(f"Generating ruler (~{target_bytes/1000000:.1f} MB)...")
    
    # We generate chunks of 10 characters.
    # The number of chunks needed is target / 10.
    chunks = []
    
    for i in range(10, target_bytes + 10, 10):
        # Format the number 'i' to be 10 chars wide, zero padded
        # e.g., 0000000010
        chunks.append(f"{i:010d}")
        
    return "".join(chunks)

def main():
    # default to 2.5MB, usually enough to hit browser DOM limits
    ruler_text = generate_ruler()
    
    char_count = len(ruler_text)
    print(f"Ruler generated.")
    print(f"Characters: {char_count:,}")
    print(f"Bytes:      {len(ruler_text.encode('utf-8')):,}")
    print("-" * 30)
    print("Instructions:")
    print("1. Run this script.")
    print("2. Paste into the target web form.")
    print("3. Scroll to the very end of the pasted text.")
    print("4. The last complete number you see is your exact character limit.")
    print("-" * 30)
    
    copy_to_clipboard(ruler_text)

if __name__ == "__main__":
    main()