#!/usr/bin/env python3
import subprocess
import sys
import platform
from bs4 import BeautifulSoup
from markdownify import markdownify as md

def get_clipboard_html():
    """TODO: Expand for macOS (pbpaste) and Windows (win32clipboard)."""
    system = platform.system().lower()
    if system == "linux":
        result = subprocess.run(['xclip', '-selection', 'clipboard', '-target', 'text/html', '-o'], 
                                capture_output=True, text=True)
        return result.stdout if result.stdout.strip() else None
    return None

def get_clipboard_text():
    """TODO: Expand for macOS (pbpaste) and Windows (win32clipboard)."""
    system = platform.system().lower()
    if system == "linux":
        result = subprocess.run(['xclip', '-selection', 'clipboard', '-o'], 
                                capture_output=True, text=True)
        return result.stdout
    return ""

def set_clipboard(text: str):
    """TODO: Expand for macOS (pbcopy) and Windows (win32clipboard)."""
    system = platform.system().lower()
    if system == "linux":
        subprocess.run(['xclip', '-selection', 'clipboard'], input=text.encode('utf-8'), check=True)

def transform():
    html_content = get_clipboard_html()
    
    if not html_content:
        md_text = get_clipboard_text()
        if not md_text:
            sys.exit("❌ Clipboard is empty or contains no compatible data.")
        print("ℹ️ No HTML found, passing plain text.")
    else:
        # 2. Clean and Convert
        soup = BeautifulSoup(html_content, 'html.parser')
        for script in soup(["script", "style"]):
            script.extract()
        content = soup.body if soup.body else soup
        md_text = md(str(content))

    # 3. Push back
    set_clipboard(md_text)
    print("✨ Clipboard transformed to Markdown.")

if __name__ == "__main__":
    transform()
