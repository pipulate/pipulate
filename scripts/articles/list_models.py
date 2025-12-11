import os
import getpass
import google.generativeai as genai
from pathlib import Path

# Load API Key using the same logic as your main script
CONFIG_DIR = Path.home() / ".config" / "articleizer"
API_KEY_FILE = CONFIG_DIR / "api_key.txt"

if API_KEY_FILE.exists():
    api_key = API_KEY_FILE.read_text().strip()
else:
    api_key = getpass.getpass("Enter API Key: ")

genai.configure(api_key=api_key)

print("🔍 querying available models...\n")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"✅ {m.name}")
except Exception as e:
    print(f"❌ Error listing models: {e}")