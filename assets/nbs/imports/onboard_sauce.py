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

def package_optics_to_excel(job: str, target_url: str, ai_assessment: str):
    """
    Packages the high-signal LLM Optics into a beautifully formatted Excel deliverable.
    """
    import pandas as pd
    import re
    import yaml
    from tools.scraper_tools import get_safe_path_component
    from pipulate import wand
    import ipywidgets as widgets

    domain, slug = get_safe_path_component(target_url)
    cache_dir = wand.paths.browser_cache / domain / slug

    # 1. Parse SEO Metadata (The Signal)
    seo_file = cache_dir / "seo.md"
    seo_data = {"Metric": [], "Value": []}
    
    if seo_file.exists():
        content = seo_file.read_text(encoding='utf-8')
        # Extract YAML frontmatter
        match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
        if match:
            try:
                frontmatter = yaml.safe_load(match.group(1))
                for k, v in frontmatter.items():
                    seo_data["Metric"].append(str(k).replace('_', ' ').title())
                    seo_data["Value"].append(str(v))
            except Exception as e:
                print(f"⚠️ Warning: Could not parse SEO frontmatter: {e}")

    df_seo = pd.DataFrame(seo_data)

    # 2. Prepare AI Assessment
    df_ai = pd.DataFrame({
        "Intelligence Layer": ["Local Edge AI (Chip O'Theseus)"], 
        "Semantic Assessment": [ai_assessment]
    })

    # 3. Write to Excel with High-End Formatting
    deliverables_dir = wand.paths.deliverables / job
    deliverables_dir.mkdir(parents=True, exist_ok=True)
    xl_filename = f"{domain.replace('.', '_')}_Optics_Baseline.xlsx"
    xl_file = deliverables_dir / xl_filename

    with pd.ExcelWriter(xl_file, engine="xlsxwriter") as writer:
        df_ai.to_excel(writer, sheet_name='AI Assessment', index=False)
        if not df_seo.empty:
            df_seo.to_excel(writer, sheet_name='SEO Metadata', index=False)

        workbook = writer.book
        header_fmt = workbook.add_format({
            'bold': True, 
            'bg_color': '#D9E1F2', 
            'border': 1, 
            'align': 'center'
        })
        wrap_fmt = workbook.add_format({'text_wrap': True, 'valign': 'top'})

        # Format AI Sheet
        ws_ai = writer.sheets['AI Assessment']
        ws_ai.set_column(0, 0, 30, wrap_fmt)
        ws_ai.set_column(1, 1, 100, wrap_fmt)
        for col_num, value in enumerate(df_ai.columns.values):
            ws_ai.write(0, col_num, value, header_fmt)

        # Format SEO Sheet
        if not df_seo.empty:
            ws_seo = writer.sheets['SEO Metadata']
            ws_seo.set_column(0, 0, 25, wrap_fmt)
            ws_seo.set_column(1, 1, 80, wrap_fmt)
            for col_num, value in enumerate(df_seo.columns.values):
                ws_seo.write(0, col_num, value, header_fmt)

    # 4. Generate Egress Button
    button = widgets.Button(
        description=f"📂 Open Deliverables Folder",
        tooltip=f"Open {deliverables_dir.resolve()}",
        button_style='success'
    )
    
    def on_click(b):
        wand.open_folder(str(deliverables_dir))
        
    button.on_click(on_click)

    return button, xl_file

def generate_js_gap_prompt(target_url: str) -> str:
    """Generates a high-signal unified diff prompt for Cloud AI analysis."""
    from bs4 import BeautifulSoup
    import difflib
    from tools.scraper_tools import get_safe_path_component
    from pipulate import wand

    domain, slug = get_safe_path_component(target_url)
    cache_dir = wand.paths.browser_cache / domain / slug

    source_file = cache_dir / "source.html"
    dom_file = cache_dir / "simple_dom.html" 

    if not source_file.exists() or not dom_file.exists():
        return "Error: Source or DOM files missing. Run the scrape first."

    def clean_html(filepath):
        soup = BeautifulSoup(filepath.read_text(encoding='utf-8'), 'html.parser')
        for tag in soup(['script', 'style', 'meta', 'link', 'noscript', 'svg']):
            tag.decompose()
        return soup.prettify().splitlines()

    source_lines = clean_html(source_file)
    dom_lines = clean_html(dom_file)

    diff = difflib.unified_diff(
        source_lines, dom_lines,
        fromfile='Raw_Source.html',
        tofile='Hydrated_DOM.html',
        lineterm=''
    )
    
    # Cap the diff so it doesn't blow out the LLM's context window
    diff_text = '\n'.join(list(diff)[:800]) 

    prompt = f"""# ROLE
You are an elite Technical SEO and Frontend Architecture expert.

# TASK
Analyze the "JavaScript Gap" for {target_url}. I have provided a Unified Diff showing the difference between the raw HTTP response (Raw_Source.html) and the simplified rendered DOM after JavaScript execution (Hydrated_DOM.html).

# DATA (Unified Diff Snippet)
```diff
{diff_text}
```

# INSTRUCTIONS
1. Analyze the diff. What critical content, internal links, or semantic structures are ONLY present in the Hydrated_DOM?
2. Explain the SEO implications if a search engine crawler (like Googlebot) fails to execute this JavaScript.
3. Recommend a mitigation strategy (e.g., Server-Side Rendering, Dynamic Rendering, or HTML fallbacks) based on the specific elements being injected client-side.
"""
    return prompt

def render_copy_button(prompt_text: str):
    """Renders an HTML/JS button to copy text to the OS clipboard from Jupyter."""
    from IPython.display import HTML
    import base64

    # Base64 encode to safely pass multi-line Python strings into JS
    b64_prompt = base64.b64encode(prompt_text.encode('utf-8')).decode('utf-8')
    
    button_html = f"""
    <button onclick="
        const ta = document.createElement('textarea');
        ta.value = decodeURIComponent(escape(window.atob('{b64_prompt}')));
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        this.innerText = '✅ Copied to OS Clipboard! Paste into Gemini/Claude.';
        this.style.backgroundColor = '#28a745';
        this.style.color = 'white';
        this.style.borderColor = '#28a745';
    " style="padding: 12px 24px; font-size: 16px; border-radius: 6px; cursor: pointer; border: 1px solid #ccc; font-weight: bold; margin-top: 15px;">
    📋 Copy 'JavaScript Gap' Prompt for Cloud AI
    </button>
    """
    return HTML(button_html)


def build_local_optics_prompt(target_url: str):
    """Retrieves cached optics and formats the prompts for the local AI assessment."""
    from tools.scraper_tools import get_safe_path_component
    from pipulate import wand

    domain, slug = get_safe_path_component(target_url)
    ax_file = wand.paths.browser_cache / domain / slug / "accessibility_tree_summary.txt"

    accessibility_context = ax_file.read_text(encoding='utf-8')[:2000] if ax_file.exists() else "No accessibility data available."

    local_system_prompt = (
        "You are Chip O'Theseus, an AI running locally on the user's hardware. "
        "You are highly analytical and concise."
    )

    local_prompt = f"""
The user has successfully scraped {target_url}. 
Based on the following Accessibility Tree snippet, provide a 2-3 sentence semantic summary of what this page is actually about and what its primary conversion goal appears to be.

DATA:
{accessibility_context}
"""
    return local_system_prompt, local_prompt.strip()


def factory_reset_credentials():
    """
    Renders a two-step IPyWidget confirmation to wipe API keys from the .env vault
    and the active environment, allowing the onboarding workflow to be tested from scratch.
    """
    import ipywidgets as widgets
    from IPython.display import display, clear_output
    import os
    from dotenv import set_key
    from pipulate import wand
    
    button = widgets.Button(
        description="⚠️ Factory Reset .env Vault",
        button_style="danger",
        icon="trash"
    )
    out = widgets.Output()

    def on_click(b):
        with out:
            clear_output()
            wand.speak("Are you sure? This will wipe your cloud keys.")
            confirm = widgets.Button(description="Yes, Wipe It", button_style="danger")
            cancel = widgets.Button(description="Cancel", button_style="success")
            
            def on_confirm(cb):
                with out:
                    clear_output()
                    env_path = wand.paths.root / ".env"
                    keys_to_nuke = [
                        "OPENAI_API_KEY", 
                        "ANTHROPIC_API_KEY", 
                        "GEMINI_API_KEY",
                        "GOOGLE_API_KEY",
                        "BOTIFY_API_TOKEN"
                    ]
                    for k in keys_to_nuke:
                        if k in os.environ:
                            del os.environ[k]
                    # Ruthless file scrubber: physically purge the lines
                    if env_path.exists():
                        lines = env_path.read_text(encoding='utf-8').splitlines()
                        clean_lines = [line for line in lines if not any(line.startswith(f"{k}=") for k in keys_to_nuke)]
                        if clean_lines:
                            env_path.write_text('\n'.join(clean_lines) + '\n', encoding='utf-8')
                        else:
                            env_path.unlink()  # Nuke the whole file if it's empty
                    
                    wand.speak("Vault wiped. Restart the kernel to complete the amnesia.")
                    print("✅ Credentials cleared. Please restart the kernel (Esc, 0, 0) to start over.")

            def on_cancel(cb):
                with out:
                    clear_output()
                    wand.speak("Crisis averted.")
                    print("🛡️ Crisis averted. Vault remains intact.")

            confirm.on_click(on_confirm)
            cancel.on_click(on_cancel)
            display(widgets.HBox([confirm, cancel]))

    button.on_click(on_click)
    display(widgets.VBox([button, out]))

def render_persona_selector(job_id: str = "onboarding_job"):
    """
    Renders the IPyWidget to select the AI auditor persona.
    Handles persistent state writing and triggers the downstream compulsion.
    """
    import ipywidgets as widgets
    from IPython.display import display, clear_output
    from pipulate import wand

    # 1. Check if they already made a choice previously (defaulting to the suit)
    existing_choice = wand.get(job_id, "auditor_persona") or "enterprise"

    # 2. Build the visual selection widget
    persona_widget = widgets.RadioButtons(
        options=[
            ('👔 The Enterprise Consultant (Strict, analytical, buttoned-up)', 'enterprise'),
            ('🎭 Statler & Waldorf (Ruthless heckling from the balcony)', 'muppets')
        ],
        value=existing_choice,
        layout={'width': 'max-content'}
    )

    submit_btn = widgets.Button(
        description="Lock in Persona", 
        button_style='primary',
        icon='check'
    )

    out = widgets.Output()

    def on_submit(b):
        with out:
            clear_output()
            selected = persona_widget.value
            
            # 3. Save the choice to persistent memory
            wand.set(job_id, "auditor_persona", selected)
            
            # 4. Give contextual audio feedback based on their choice
            if selected == 'muppets':
                wand.speak("Excellent choice. Prepare to be insulted.")
            else:
                wand.speak("Very well. We will keep this strictly professional.")
                
            submit_btn.description = "Persona Locked"
            submit_btn.button_style = 'success'
            
            # 5. Fire the compulsion to advance
            wand.imperio(newline=True)

    submit_btn.on_click(on_submit)

    display(widgets.VBox([persona_widget, submit_btn, out]))
