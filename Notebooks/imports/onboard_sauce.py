# onboard_sauce.py
# Purpose: Bridge the 0nboard notebook to the LLM Optics engine.
# Asserting sovereignty over perception. 👁️

import asyncio
import sys
from pathlib import Path
from loguru import logger
from pipulate import pip

async def analyze_ai_readiness(job: str, url: str, verbose: bool = True):
    """
    The master 'Aha!' sequence for onboarding.
    Scrapes a URL and immediately shatters it into LLM Optics.
    """
    pip.speak(f"Beginning AI-Readiness analysis for {url}.")
    
    # 1. THE SCRAPE (The Acquisition)
    # We use headless=False for the onboarding 'magic' effect.
    logger.info(f"🚀 Step 1: Navigating to {url}...")
    result = await pip.scrape(
        url=url, 
        take_screenshot=True, 
        headless=False, 
        verbose=verbose
    )
    
    if not result.get('success'):
        error_msg = result.get('error', 'Unknown error')
        pip.speak("I encountered an issue during navigation.")
        print(f"❌ Scrape Failed: {error_msg}")
        return False

    # 2. THE OPTICS (The Refraction)
    # Locate the rendered DOM file
    dom_path = result.get("looking_at_files", {}).get("rendered_dom")
    if not dom_path or not Path(dom_path).exists():
        print("❌ Error: Could not locate rendered_dom.html for analysis.")
        return False

    pip.speak("I have captured the page. Now, generating AI Optics.")
    logger.info(f"👁️‍🗨️ Step 2: Running LLM Optics Engine on {dom_path}...")
    
    # Trigger the subprocess via the core magic wand
    # Note: We'll add this method to core.py if not already present
    optics_result = await generate_optics_subprocess(dom_path)
    
    if optics_result.get('success'):
        pip.speak("Analysis complete. You can now see your site through the eyes of an AI.")
        print(f"✅ Success! Optics generated in: {Path(dom_path).parent}")
        return True
    else:
        print(f"⚠️ Optics generation partially failed: {optics_result.get('error')}")
        return False

async def generate_optics_subprocess(dom_file_path: str):
    """
    Isolated wrapper to call llm_optics.py as a subprocess.
    This prevents the Jupyter kernel from hanging during heavy visualization tasks.
    """
    # Find the tool relative to this script
    # Notebooks/imports/onboard_sauce.py -> tools/llm_optics.py
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