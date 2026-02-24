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
import llm

def check_ai_models(preferred_model=None):
    """Uses the Universal Adapter (llm) to verify AI readiness and preferred models."""
    if preferred_model:
        wand.speak(f"Checking for your preferred AI model: {preferred_model}...")
    else:
        wand.speak("Scanning your system for available AI models...")
    try:
        # Grab all models registered with the llm package
        models = [m.model_id for m in llm.get_models()]
        
        # Check if any local Ollama models are present (they usually don't have a provider prefix like 'gpt-' or 'claude-')
        # The llm-ollama plugin registers them dynamically.
        has_local = any('ollama' in str(type(m)).lower() for m in llm.get_models())
        
        if preferred_model and preferred_model in models:
            wand.speak(f"Excellent! Your preferred model '{preferred_model}' is active and ready.")
            print(f"\n✅ Locked in model: {preferred_model}")
            return preferred_model
            
        if has_local:
            wand.speak(f"I found {len(models)} total models, including local options. Your preferred model was not found.")
            print(f"\nℹ️  '{preferred_model}' not found, but you have local models ready to use.")
            return True # Or return a default local model if you prefer
            
        # The Fallback State: No local models detected
        wand.speak("I do not detect a local AI brain on your system.")
        print("\nℹ️  Ollama is not running or not installed.")
        print("Pipulate works perfectly fine without it, but an AI 'riding shotgun' makes the experience much better.")
        print("\nTo upgrade your environment for true Local-First Sovereignty:")
        print("1. Go to https://ollama.com/")
        print("2. Download the installer for your operating system (Mac/Windows/Linux).")
        print("3. Install it, pull a model (e.g., 'ollama run qwen3:1.7b'), and run this cell again.")
        return False

    except Exception as e:
        print(f"❌ Error communicating with the Universal Adapter: {e}")

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

def interrogate_local_ai(target_url: str, preferred_model: str = None):
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
        
        try:
            # The Universal Adapter handles fallbacks automatically!
            if preferred_model:
                model = llm.get_model(preferred_model)
            else:
                model = llm.get_model()  # Auto-grabs the default
                
            target_model_id = model.model_id
            wand.speak(f"I am now interrogating the scraped data using the Universal Adapter, routed to {target_model_id}.")
            
            # The elegant prompt execution
            response = model.prompt(prompt)
            
            print(f"🤖 Analysis from {target_model_id}:\n")
            print(response.text())                
            wand.speak("Analysis complete. As you can see, I can read and summarize local files instantly.")

        except Exception as e:
            print(f"⚠️ Could not complete local AI analysis: {e}")
    else:
        print(f"⚠️ Could not find {md_file}. Did the previous step complete successfully?")

async def analyze_ai_readiness(job: str, url: str, verbose: bool = True, override_cache: bool = False):
    """
    The master 'Aha!' sequence for onboarding.
    Scrapes a URL and immediately shatters it into LLM Optics.
    """
    wand.speak(f"Beginning AI-Readiness analysis for {url}.")

    if override_cache:
        print("🧹 Cache override engaged. Forcing a fresh scrape.")
    
    # 1. THE SCRAPE (The Acquisition)
    if not override_cache:
        logger.info(f"🚀 Step 1: Checking cache or navigating to {url}...")

    result = await wand.scrape(
        url=url, 
        take_screenshot=True, 
        headless=False, 
        override_cache=override_cache,
        verbose=verbose
    )
    
    if not result.get('success'):
        error_msg = result.get('error', 'Unknown error')
        wand.speak("I encountered an issue during navigation.")
        print(f"❌ Scrape Failed: {error_msg}")
        return False

    if result.get('cached'):
        wand.speak("I already have this data cached locally. Bypassing browser navigation.")
        print("⚡ Cache Hit! Using existing artifacts to save time and compute.")
    else:
        wand.speak("Navigation complete. Page data captured.")
        print("✅ Fresh Scrape Successful.")

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
