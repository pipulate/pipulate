# Notebooks/imports/onboard_sauce.py
# Purpose: Bridge the 0nboard notebook to the LLM Optics engine.
# Asserting sovereignty over perception. 👁️

import asyncio
import sys
import json
import socket
import urllib.request
import os
from pathlib import Path
import ipywidgets as widgets
from IPython.display import display
from loguru import logger
from pipulate import wand  # Use wand!

def check_for_ollama():
    """Scans the local system for a running Ollama instance and available models."""
    wand.speak("Scanning your system for a local AI brain...")
    
    # Try multiple common local addresses to bypass DNS/IPv6 routing quirks
    addresses_to_try = [
        "http://127.0.0.1:11434/api/tags",
        "http://localhost:11434/api/tags",
        "http://0.0.0.0:11434/api/tags"
    ]
    
    for url in addresses_to_try:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2) as response:
                if response.getcode() == 200:
                    data = json.loads(response.read())
                    models = [model['name'] for model in data.get('models', [])]
                    if models:
                        wand.speak(f"Excellent! I detect Ollama is running. You have {len(models)} models installed.")
                        print(f"\n✅ Installed Models: {', '.join(models)}")
                    else:
                        wand.speak("Ollama is running, but you don't have any models downloaded yet.")
                    return True
        except (urllib.error.URLError, socket.timeout, ConnectionRefusedError):
            continue # Try the next address
        except Exception as e:
            print(f"  [Debug] Error trying {url}: {e}")
            continue
    
    # The Fallback State (only reached if ALL addresses fail)
    wand.speak("I do not detect a local AI brain on your system.")
    print("\nℹ️  Ollama is not running or not installed.")
    print("Pipulate works perfectly fine without it, but an AI 'riding shotgun' makes the experience much better.")
    print("\nTo upgrade your environment:")
    print("1. Go to https://ollama.com/")
    print("2. Download the installer for your operating system (Mac/Windows/Linux).")
    print("3. Install it, and run this cell again.")
    
    return False

def show_artifacts(target_url: str):
    """Displays a button to open the cache directory for a given URL."""
    from urllib.parse import urlparse, quote
    
    parsed_url = urlparse(target_url)
    domain = parsed_url.netloc
    path = parsed_url.path or '/'
    url_path_slug = quote(path, safe='')
    
    cache_dir = Path(f"browser_cache/{domain}/{url_path_slug}")

    if cache_dir.exists():
        wand.speak("Let's examine the artifacts I extracted. Click the button to open the folder on your computer.")
        print(f"📁 Contents of {cache_dir}:\n")
        
        for item in cache_dir.iterdir():
            if item.is_file():
                size_kb = item.stat().st_size / 1024
                print(f" - {item.name} ({size_kb:.1f} KB)")
                
        # Create the "Open Folder" button
        button = widgets.Button(
            description=f"📂 Open Folder",
            tooltip=f"Open {cache_dir.resolve()}",
            button_style='success'
        )
        
        def on_button_click(b):
            wand.open_folder(str(cache_dir))
            
        button.on_click(on_button_click)
        display(button)
    else:
        print("Directory not found. The scrape may not have completed successfully.")

def interrogate_local_ai(target_url: str):
    """Reads the accessibility tree and asks the local AI to summarize it."""
    from urllib.parse import urlparse, quote
    
    parsed_url = urlparse(target_url)
    domain = parsed_url.netloc
    path = parsed_url.path or '/'
    url_path_slug = quote(path, safe='')
    
    md_file = Path(f"browser_cache/{domain}/{url_path_slug}/accessibility_tree.json")

    if md_file.exists():
        content = md_file.read_text()
        
        # Use first 2000 characters to keep it fast
        prompt = f"Based on the following DevTools accessibility tree extracted from a scrape, what is this page about? Answer in exactly 3 short bullet points.\n\n{content[:2000]}"
        
        req_tags = urllib.request.Request("http://localhost:11434/api/tags")
        try:
            with urllib.request.urlopen(req_tags, timeout=2) as response:
                available_models = [m['name'] for m in json.loads(response.read()).get('models', [])]
                
            if available_models:
                target_model = available_models[0] 
                
                wand.speak(f"I am now interrogating the scraped data using your local AI brain, {target_model}. This analysis costs exactly zero cents.")
                
                req_generate = urllib.request.Request(
                    "http://localhost:11434/api/generate",
                    data=json.dumps({"model": target_model, "prompt": prompt, "stream": False}).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                
                with urllib.request.urlopen(req_generate) as ai_response:
                    result = json.loads(ai_response.read())
                    analysis = result.get("response", "")
                    
                    print(f"🤖 Analysis from {target_model}:\n")
                    print(analysis)
                    
                    wand.speak("Analysis complete. As you can see, I can read and summarize local files instantly, with total privacy.")
                    
        except Exception as e:
            print(f"⚠️ Could not complete local AI analysis: {e}")
    else:
        print(f"⚠️ Could not find {md_file}. Did the previous step complete successfully?")

async def analyze_ai_readiness(job: str, url: str, verbose: bool = True):
    """
    The master 'Aha!' sequence for onboarding.
    Scrapes a URL and immediately shatters it into LLM Optics.
    """
    wand.speak(f"Beginning AI-Readiness analysis for {url}.")
    
    # 1. THE SCRAPE (The Acquisition)
    logger.info(f"🚀 Step 1: Navigating to {url}...")
    result = await wand.scrape(
        url=url, 
        take_screenshot=True, 
        headless=False, 
        verbose=verbose
    )
    
    if not result.get('success'):
        error_msg = result.get('error', 'Unknown error')
        wand.speak("I encountered an issue during navigation.")
        print(f"❌ Scrape Failed: {error_msg}")
        return False

    # 2. THE OPTICS (The Refraction)
    dom_path = result.get("looking_at_files", {}).get("rendered_dom")
    if not dom_path or not Path(dom_path).exists():
        print("❌ Error: Could not locate rendered_dom.html for analysis.")
        return False

    wand.speak("I have captured the page. Now, generating AI Optics.")
    logger.info(f"👁️‍🗨️ Step 2: Running LLM Optics Engine on {dom_path}...")
    
    optics_result = await generate_optics_subprocess(dom_path)
    
    if optics_result.get('success'):
        wand.speak("Analysis complete. You can now see your site through the eyes of an AI.")
        print(f"✅ Success! Optics generated in: {Path(dom_path).parent}")
        return True
    else:
        print(f"⚠️ Optics generation partially failed: {optics_result.get('error')}")
        return False

async def generate_optics_subprocess(dom_file_path: str):
    """Isolated wrapper to call llm_optics.py as a subprocess."""
    script_path = (Path(__file__).resolve().parent.parent.parent / "tools" / "llm_optics.py")
    
    proc = await asyncio.create_subprocess_exec(
        sys.executable, str(script_path), str(dom_file_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await proc.communicate()
    
    if proc.returncode == 0:
        return {"success": True, "output": stdout.decode()}
    else:
        return {"success": False, "error": stderr.decode()}