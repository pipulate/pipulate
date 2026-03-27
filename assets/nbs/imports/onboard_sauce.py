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
import imports
from dotenv import dotenv_values
import llm


def check_ai_models(preferred_local=None, preferred_cloud=None):
    """
    Uses the Universal Adapter (llm) to verify AI readiness using fuzzy matching
    against a prioritized list of preferred models.
    """
    if preferred_local:
        wand.speak(f"Scanning for your preferred local models...")
    else:
        wand.speak("Scanning your system for available AI models...")

    try:
        # 1. Gather all models known to the Universal Adapter
        available_models = [m.model_id for m in llm.get_models()]
        
        # 2. Check for ANY local model (Ollama models typically lack provider prefixes)
        has_local = any('ollama' in str(type(m)).lower() for m in llm.get_models())

        # 3. Process User Preferences
        def parse_preferences(pref_string):
            if not pref_string: return []
            return [p.strip().lower() for p in pref_string.split(',')]

        local_prefs = parse_preferences(preferred_local)
        cloud_prefs = parse_preferences(preferred_cloud)

        selected_local = None
        selected_cloud = None

        # 4. Fuzzy Matching Logic (Find highest priority match)
        # We check each preference against the available models. If the preference
        # string is *in* the available model string (e.g., 'gemma3' in 'gemma3:latest'), it's a match.
        for pref in local_prefs:
            match = next((m for m in available_models if pref in m.lower() and 'ollama' in str(type(llm.get_model(m))).lower()), None)
            if match:
                selected_local = match
                break # Found our highest priority local model

        for pref in cloud_prefs:
            match = next((m for m in available_models if pref in m.lower() and 'ollama' not in str(type(llm.get_model(m))).lower()), None)
            if match:
                selected_cloud = match
                break # Found our highest priority cloud model

        # 5. Reporting and Graceful Degradation
        if selected_local:
            wand.speak(f"Excellent. Local model '{selected_local}' is active and ready.")
            print(f"\n✅ Locked in Local Model: {selected_local}")
        elif has_local:
            # Fallback: They have Ollama, but not their preferred model
            wand.speak("I found local models, but not your preferred choices.")
            print(f"\nℹ️  Preferred local models not found, but other local models are available.")
            print(f"Available models: {', '.join([m for m in available_models if 'ollama' in str(type(llm.get_model(m))).lower()])}")
            selected_local = True # Indicate local capacity exists
        else:
            # The Fallback State: No local models detected
            wand.speak("I do not detect a local AI brain on your system.")
            print("\nℹ️  Ollama is not running or not installed.")
            print("Pipulate works perfectly fine without it, but a local AI 'riding shotgun' ensures privacy.")
            print("\nTo upgrade your environment for true Local-First Sovereignty:")
            print("1. Go to https://ollama.com/")
            print("2. Download the installer for your host operating system.")
            print("3. Install it, open a terminal, run 'ollama run gemma3', and try again.")
            
        if selected_cloud:
             print(f"✅ Locked in Cloud Model: {selected_cloud}")

        return {
            "local": selected_local,
            "cloud": selected_cloud,
            "has_any_local": has_local
        }

    except Exception as e:
        print(f"❌ Error communicating with the Universal Adapter: {e}")
        return {"local": False, "cloud": False, "has_any_local": False}


def interrogate_local_ai(target_url: str, preferred_model: str = None):
    """Reads the accessibility tree and asks the local AI to summarize it."""
    from tools.scraper_tools import get_safe_path_component
    
    domain, url_path_slug = get_safe_path_component(target_url)

    md_file = wand.paths.browser_cache / domain / url_path_slug / "accessibility_tree.json"

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


def explain_optics_artifacts(target_url):
    """
    Feeds the AI both the raw source and the rendered DOM structure
    to educate the user on 'The JavaScript Gap'.
    """
    domain, slug = get_safe_path_component(target_url)
    base = wand.paths.browser_cache / domain / slug
    
    source_txt = (base / "source.html").read_text()[:1000] # Snippet
    rendered_txt = (base / "rendered_dom.html").read_text()[:1000] # Snippet

    prompt = f"""
    I am looking at the scrape artifacts for {target_url}.
    
    RAW SOURCE SNIPPET:
    {source_txt}
    
    RENDERED DOM SNIPPET:
    {rendered_txt}
    
    Explain to the human why these two views differ and why a 'Forever Machine' 
    needs to see the Rendered DOM to understand modern web apps. 
    Point out any specific SEO tags or content that only appear in one of them.
    """
    
    response = wand.prompt(prompt)
    display(Markdown(f"### 👁️ Optics Education\n\n{response}"))


def ensure_cloud_credentials(cloud_model_id):
    """
    The Gatekeeper. Checks for required cloud API keys upfront to prevent 
    mid-workflow lazy-loading crashes. Renders a secure widget if missing.
    """
    import os
    import ipywidgets as widgets
    from IPython.display import display, clear_output
    from dotenv import load_dotenv, set_key

    # Load existing environment variables
    load_dotenv()
    
    if not cloud_model_id:
        print("ℹ️ No cloud model selected or required.")
        wand.imperio()
        return

    # Map the model string to the standard API Key variable
    env_var_name = None
    if 'claude' in cloud_model_id.lower() or 'anthropic' in cloud_model_id.lower():
        env_var_name = 'ANTHROPIC_API_KEY'
    elif 'gpt' in cloud_model_id.lower() or 'openai' in cloud_model_id.lower():
        env_var_name = 'OPENAI_API_KEY'
    elif 'gemini' in cloud_model_id.lower() or 'google' in cloud_model_id.lower():
        env_var_name = 'GEMINI_API_KEY'
        
    if env_var_name and not os.getenv(env_var_name):
        wand.speak(f"I need your API key for {cloud_model_id} to proceed.")
        
        # Build the secure password widget (hides the input)
        key_input = widgets.Password(
            value='',
            placeholder='Paste your API Key here...',
            description=f'🔑 {env_var_name}:',
            style={'description_width': 'initial'},
            disabled=False,
            layout=widgets.Layout(width='80%')
        )
        
        submit_btn = widgets.Button(
            description="Save to Vault", 
            button_style='success',
            icon='lock'
        )
        out = widgets.Output()
        
        def on_submit(b):
            with out:
                clear_output()
                if key_input.value.strip():
                    # 1. Save permanently to .env
                    env_path = Path('.env')
                    env_path.touch(exist_ok=True)
                    set_key(str(env_path), env_var_name, key_input.value.strip())
                    
                    # 2. Export to current runtime environment
                    os.environ[env_var_name] = key_input.value.strip()
                    
                    # 3. Explicitly set it in Simon Willison's 'llm' tool keychain
                    try:
                        import llm
                        key_alias = env_var_name.split('_')[0].lower()
                        llm.set_key(key_alias, key_input.value.strip())
                    except Exception as e:
                        pass # Fail silently if the specific llm set_key implementation differs
                        
                    wand.speak("Key securely saved to the vault. The cloud is connected.")
                    print(f"✅ {env_var_name} successfully encrypted in .env.")
                    wand.imperio()
                else:
                    print("❌ Please enter a valid API key.")
        
        submit_btn.on_click(on_submit)
        display(widgets.VBox([key_input, submit_btn, out]))
        
    else:
        # Key is already present, keep the rhythm flowing
        wand.speak("Cloud credentials verified in your environment.")
        print(f"✅ Secure connection ready for {cloud_model_id}.")
        wand.imperio()

# Add this function to the bottom of assets/nbs/imports/onboard_sauce.py

def audit_environment():
    """
    Provides a safe, transparent readout of the local Python environment
    and securely masks the contents of the .env vault.
    """
    
    print("=== 🌍 YOUR LOCAL REALITY ===")
    print(f"🐍 Python Executable: {sys.executable}")
    print(f"📁 Working Directory: {os.getcwd()}")
    
    print("\n=== 🧬 THE NAMESPACE FUSION ===")
    print("Paths mapped to your 'imports' module:")
    for p in imports.__path__:
        print(f"  - {p}")
        
    try:
        loop = asyncio.get_running_loop()
        print(f"\n⚡ Event Loop: Active ({type(loop).__name__})")
    except RuntimeError:
        print("\n⚡ Event Loop: None detected.")

    print("\n=== 🛡️ THE VAULT (.env) ===")
    env_path = Path.cwd() / '.env'
    if env_path.exists():
        secrets = dotenv_values(env_path)
        if secrets:
            print("Your secrets are encrypted and safe. Here is what we see:")
            for key, val in secrets.items():
                # Mask the value, showing only the first 4 chars for visual confirmation
                masked = f"{val[:4]}••••••••••••••••" if val and len(val) > 4 else "••••••••••••••••"
                print(f"  🔑 {key}: {masked}")
        else:
            print("  Your vault exists but is currently empty.")
    else:
        print("  No .env file found yet. (The Gatekeeper will create one when needed!)")
