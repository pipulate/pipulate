#!/usr/bin/env python3
import subprocess
import sys
from bs4 import BeautifulSoup
from markdownify import markdownify as md

def transform():
    # 1. Fetch HTML from X11 clipboard
    result = subprocess.run(
        ['xclip', '-selection', 'clipboard', '-target', 'text/html', '-o'],
        capture_output=True, text=True
    )
    
    if not result.stdout.strip():
        # Fallback to plain text if HTML isn't available
        plain = subprocess.run(['xclip', '-selection', 'clipboard', '-o'], 
                               capture_output=True, text=True).stdout
        if not plain:
            sys.exit("❌ Clipboard is empty or contains no compatible data.")
        print("ℹ️ No HTML found, passing plain text.")
        md_text = plain
    else:
        # 2. Clean and Convert
        soup = BeautifulSoup(result.stdout, 'html.parser')
        # Remove script and style tags which clutter Markdown
        for script in soup(["script", "style"]):
            script.extract()
        
        # Target the body if it exists to avoid capturing full <html> overhead
        content = soup.body if soup.body else soup
        md_text = md(str(content))

    # 3. Push back to clipboard
    subprocess.run(['xclip', '-selection', 'clipboard'], 
                   input=md_text.encode('utf-8'), check=True)
    print("✨ Clipboard transformed to Markdown.")

if __name__ == "__main__":
    transform()