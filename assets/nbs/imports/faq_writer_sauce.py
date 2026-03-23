# secretsauce.py (version 3.0 - Refactored Workflow)
# This module contains the implementation details for a 1-to-many AI enrichment workflow.

import pandas as pd
from pipulate import wand
from imports import core_sauce as core
import json
import nbformat
from pathlib import Path

# --- CONFIGURATION ---
CACHE_DB_FILE = wand.paths.temp / "url_cache.sqlite"
EXTRACTED_DATA_CSV = wand.paths.temp / "_step_extract_output.csv"
AI_LOG_CSV = wand.paths.logs / "_step_ai_log_output.csv"

# Pipulate step names
API_KEY_STEP = "api_key"
URL_LIST_STEP = "url_list"
EXTRACTED_DATA_STEP = "extracted_data"
FAQ_DATA_STEP = "faq_data"
FINAL_DATAFRAME_STEP = "final_dataframe"
EXPORT_FILE_STEP = "export_file_path"


def _get_prompt_from_notebook(notebook_filename="FAQuilizer.ipynb"):
    """Parses a notebook file to extract the prompt from the 'prompt-input' tagged cell."""
    try:
        notebook_path = Path(__file__).parent.parent / notebook_filename
        with open(notebook_path, 'r', encoding='utf-8') as f:
            nb = nbformat.read(f, as_version=4)
        
        for cell in nb.cells:
            if "prompt-input" in cell.metadata.get("tags", []):
                return cell.source
        return None # Return None if the tag isn't found
    except Exception as e:
        print(f"⚠️ Could not read prompt from notebook: {e}")
        return None


def _get_urls_from_notebook(notebook_filename="FAQuilizer.ipynb"):
    """Parses a notebook file to extract URLs from the 'url-list-input' tagged cell."""
    try:
        # Assuming the notebook is in the same directory as this script
        notebook_path = Path(__file__).parent.parent / notebook_filename
        with open(notebook_path, 'r', encoding='utf-8') as f:
            nb = nbformat.read(f, as_version=4)
        
        for cell in nb.cells:
            if "url-list-input" in cell.metadata.get("tags", []):
                urls_raw = cell.source
                urls = [
                    line.split('#')[0].strip() 
                    for line in urls_raw.splitlines() 
                    if line.strip() and not line.strip().startswith('#')
                ]
                return urls
        return []
    except Exception as e:
        print(f"⚠️ Could not read URLs from notebook: {e}")
        return []


async def scrape(job, **kwargs):
    """Configuration wrapper for the core scraper."""
    # Get the URL list defined in the Notebook
    urls = wand.get(job, "url_list", [])
    # Pass the heavy lifting to core
    return await core.universal_scrape(job, urls, **kwargs)


async def generate_visualizations_post_scrape(job, verbose=False):
    """Pass optics generation to core."""
    return await core.generate_optics_batch(job, verbose=verbose)


# -----------------------------------------------------------------------------
# NEW REFACTORED WORKFLOW: Stack 'Em, FAQ 'Em, Rack 'Em
# -----------------------------------------------------------------------------

def stack_em(job):
    """Load core extraction data into a DataFrame for FAQ processing."""
    data = wand.get(job, "extracted_data", [])
    return pd.DataFrame(data)


def ai_faq_em(job: str, debug: bool = False) -> pd.DataFrame:
    """
    Enriches scraped data with AI-generated FAQs, using a JSON file for robust caching
    to avoid re-processing URLs. This is the "FAQ 'Em" step.
    """
    import os
    import json
    from pathlib import Path
    import google.generativeai as genai
    import re

    # --- 1. Define Cache Path ---
    cache_file = wand.paths.temp / f"faq_cache_{job}.json"

    # --- 2. Load Data ---
    extracted_data = wand.get(job, EXTRACTED_DATA_STEP, [])
    if not extracted_data:
        print("❌ No extracted data found. Please run `scrape` first.")
        return pd.DataFrame()

    faq_data = []
    if cache_file.exists():
        try:
            raw_content = cache_file.read_text(encoding='utf-8')
            if raw_content.strip():
                faq_data = json.loads(raw_content)
                print(f"✅ Loaded {len(faq_data)} FAQs from cache.")
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ Could not load cache file. Starting fresh. Error: {e}")
    
    processed_urls = {item.get('url') for item in faq_data}
    print(f"🧠 Generating FAQs for {len(extracted_data)} pages... ({len(processed_urls)} already cached)")

    # --- 3. Get Prompt & Configure AI ---
    user_prompt_instructions = _get_prompt_from_notebook()
    if not user_prompt_instructions:
        print("❌ Error: Prompt not found in 'prompt-input' cell of the notebook.")
        return pd.DataFrame(faq_data)
        
    system_prompt_wrapper = '''
Your task is to analyze webpage data and generate a structured JSON object.
Your output must be **only a single, valid JSON object inside a markdown code block** and nothing else. Adherence to the schema is critical.

--- START USER INSTRUCTIONS ---

{user_instructions}

--- END USER INSTRUCTIONS ---

**Input Data:**

--- WEBPAGE DATA BEGIN ---
{webpage_data}
--- WEBPAGE DATA END ---

**Final Instructions:**

Based *only* on the provided webpage data and the user instructions, generate the requested data.
Remember, your entire output must be a single JSON object in a markdown code block. Do not include any text or explanation outside of this block.

The JSON object must conform to the following schema:

{{
  "faqs": [
    {{
      "priority": "integer (1-5, 1 is highest)",
      "question": "string (The generated question)",
      "target_intent": "string (What is the user's goal in asking this?)",
      "justification": "string (Why is this a valuable question to answer? e.g., sales, seasonal, etc.)"
    }}
  ]
}} 
'''
    # --- 4. Process Loop ---
    try:
        for index, webpage_data_dict in enumerate(extracted_data):
            url = webpage_data_dict.get('url')
            if url in processed_urls:
                print(f"  -> ✅ Skip: URL already cached: {url}")
                continue

            print(f"  -> 🤖 AI Call: Processing URL {index+1}/{len(extracted_data)}: {url}")
            
            try:
                webpage_data_str = json.dumps(webpage_data_dict, indent=2)
                full_prompt = system_prompt_wrapper.format(
                    user_instructions=user_prompt_instructions,
                    webpage_data=webpage_data_str
                )
                
                if debug:
                    print("\n--- PROMPT ---")
                    print(full_prompt)
                    print("--- END PROMPT ---\n")

                # THE CURE: Invoke the Universal Adapter via the Wand
                # We pass the system instructions separately for cleaner LLM routing
                response_text = wand.prompt(
                    prompt_text=full_prompt, 
                    model_name="gemini-2.5-flash"  # You can parameterize this later!
                )
                
                if response_text.startswith("❌"):
                    print(f"  -> {response_text}")
                    break # Stop on auth/API errors
                
                # New robust JSON cleaning
                clean_json = response_text
                if clean_json.startswith("```json"):
                    clean_json = clean_json[7:]
                if clean_json.startswith("```"):
                    clean_json = clean_json[3:]
                if clean_json.endswith("```"):
                    clean_json = clean_json[:-3]
                clean_json = clean_json.strip()

                faq_json = json.loads(clean_json)
                
                new_faqs_for_url = []
                for faq in faq_json.get('faqs', []):
                    new_faqs_for_url.append({
                        'url': url,
                        'title': webpage_data_dict.get('title'),
                        'priority': faq.get('priority'),
                        'question': faq.get('question'),
                        'target_intent': faq.get('target_intent'),
                        'justification': faq.get('justification')
                    })
                
                if new_faqs_for_url:
                    faq_data.extend(new_faqs_for_url)
                    processed_urls.add(url)
                    print(f"  -> ✅ Success: Generated {len(new_faqs_for_url)} new FAQs for {url}.")

            except json.JSONDecodeError as e:
                print(f"  -> ❌ JSON Decode Error for {url}: {e}")
                print(f"  -> Raw AI Response:\n---\n{response_text}\n---")
                continue # Skip to the next URL
            except Exception as e:
                print(f"  -> ❌ AI call failed for {url}: {e}")
                continue

    except KeyboardInterrupt:
        print("\n🛑 Execution interrupted by user.")
    except Exception as e:
        print(f"❌ An error occurred during FAQ generation: {e}")
    finally:
        print("\n💾 Saving progress to cache...")
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(faq_data, f, indent=2)
            print(f"✅ Save complete. {len(faq_data)} total FAQs in cache.")
        except Exception as e:
            print(f"❌ Error saving cache in `finally` block: {e}")

    print("✅ FAQ generation complete.")
    wand.set(job, FAQ_DATA_STEP, faq_data)
    return pd.DataFrame(faq_data)

def rack_em(df: pd.DataFrame) -> pd.DataFrame:
    """
    Pivots and reorders the long-format FAQ data into a wide-format DataFrame.
    Each URL gets one row, with columns for each of its generated FAQs.
    This is the "Rack 'Em" step.
    """
    if df.empty:
        print("⚠️ DataFrame is empty, skipping the pivot.")
        return pd.DataFrame()

    print("🔄 Racking the data into its final wide format...")

    # 1. Create a unique identifier for each FAQ within a URL group.
    df['faq_num'] = df.groupby('url').cumcount() + 1

    # 2. Set index and unstack to pivot the data.
    pivoted_df = df.set_index(['url', 'title', 'faq_num']).unstack(level='faq_num')

    # 3. Flatten the multi-level column index.
    pivoted_df.columns = [f'{col[0]}_{col[1]}' for col in pivoted_df.columns]
    pivoted_df = pivoted_df.reset_index()

    # --- NEW: Reorder columns for readability ---
    print("🤓 Reordering columns for logical grouping...")

    # Identify the static columns
    static_cols = ['url', 'title']
    
    # Dynamically find the stems (e.g., 'priority', 'question')
    # This makes the code adaptable to different column names
    stems = sorted(list(set(
        col.rsplit('_', 1)[0] for col in pivoted_df.columns if '_' in col
    )))

    # Dynamically find the max FAQ number
    num_faqs = max(
        int(col.rsplit('_', 1)[1]) for col in pivoted_df.columns if col.rsplit('_', 1)[-1].isdigit()
    )

    # Build the new column order
    new_column_order = static_cols.copy()
    for i in range(1, num_faqs + 1):
        for stem in stems:
            new_column_order.append(f'{stem}_{i}')
    
    # Apply the new order
    reordered_df = pivoted_df[new_column_order]
    
    print("✅ Data racked and reordered successfully.")
    return reordered_df


def display_results_log(job: str):
    """
    MODIFIED: Displays the FAQ log AND saves it to an intermediate CSV.
    """
    print("📊 Displaying raw FAQ log...")
    faq_data = wand.get(job, FAQ_DATA_STEP, [])
    if not faq_data:
        print("No FAQ data to display. Please run the previous steps.")
        return
    
    df = pd.DataFrame(faq_data)
    
    # NEW: Save the second "factory floor" file for transparency.
    try:
        df.to_csv(AI_LOG_CSV, index=False)
        print(f"  -> Intermediate AI log saved to '{AI_LOG_CSV}'")
    except Exception as e:
        print(f"⚠️ Could not save AI log CSV: {e}")

    wand.set(job, FINAL_DATAFRAME_STEP, df.to_json(orient='records'))
    with pd.option_context('display.max_rows', None, 'display.max_colwidth', 80):
        display(df)

def export_to_excel(job: str):
    """
    Exports the final DataFrame to a formatted Excel file.
    """
    print("📄 Exporting data to Excel...")
    final_json = wand.get(job, FINAL_DATAFRAME_STEP)
    if not final_json:
        print("❌ No final data found to export. Please run the 'display_results' step first.")
        return
    df_final = pd.read_json(StringIO(final_json))
    output_filename = f"{job}_output.xlsx"
    try:
        with pd.ExcelWriter(output_filename, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False, sheet_name='Faquillizer_Data')
            worksheet = writer.sheets['Faquillizer_Data']
            for column in worksheet.columns:
                max_length = max((df_final[column[0].value].astype(str).map(len).max(), len(str(column[0].value))))
                adjusted_width = (max_length + 2) if max_length < 80 else 80
                worksheet.column_dimensions[column[0].column_letter].width = adjusted_width
        wand.set(job, EXPORT_FILE_STEP, output_filename)
        print(f"✅ Success! Data exported to '{output_filename}'")
    except Exception as e:
        print(f"❌ Failed to export to Excel: {e}")


def export_and_format_excel(job, df):
    """Submit the pivoted data to the core professional formatter."""
    return core.format_excel_pro(job, df, sheet_name="FAQ_Analysis")
    
    
def _open_folder(path_str: str = "."):
    """
    Opens the specified folder in the system's default file explorer.
    Handles Windows, macOS, and Linux.
    """
    folder_path = Path(path_str).resolve()
    print(f"Attempting to open folder: {folder_path}")
    
    if not folder_path.exists() or not folder_path.is_dir():
        print(f"❌ Error: Path is not a valid directory: {folder_path}")
        return

    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(folder_path)
        elif system == "Darwin":  # macOS
            subprocess.run(["open", folder_path])
        else:  # Linux
            subprocess.run(["xdg-open", folder_path])
    except Exception as e:
        print(f"❌ Failed to open folder. Please navigate to it manually. Error: {e}")


# Replacement function for Notebooks/secretsauce.py

async def generate_visualizations_post_scrape(job: str, verbose: bool = False):
    """
    Generates DOM visualizations by calling the standalone visualize_dom.py script
    as a subprocess for each scraped URL in a job.
    """
    # --- Make imports local ---
    import asyncio
    from pipulate import wand # Make sure pip is accessible
    from tools.scraper_tools import get_safe_path_component
    from pathlib import Path
    from loguru import logger # Use logger for output consistency
    import sys # Needed for sys.executable
    # --- End local imports ---

    logger.info("🎨 Generating DOM visualizations via subprocess for scraped pages...")
    extracted_data = wand.get(job, "extracted_data", []) # Use string for step name
    urls_processed = {item['url'] for item in extracted_data if isinstance(item, dict) and 'url' in item} # Safer extraction

    if not urls_processed:
        logger.warning("🟡 No scraped URLs found in the job state to visualize.") # Use logger
        return

    success_count = 0
    fail_count = 0
    tasks = []

    script_location = Path(__file__).resolve().parent # /home/mike/.../Notebooks/imports
    project_root_notebooks = script_location.parent  # /home/mike/.../Notebooks
    base_dir = project_root_notebooks / "browser_cache" # /home/mike/.../Notebooks/browser_cache
    logger.info(f"Using absolute base_dir: {base_dir}") # Log confirmation

    script_path = (Path(__file__).parent / "seo_gadget.py").resolve()

    if not script_path.exists():
         logger.error(f"❌ Cannot find visualization script at: {script_path}")
         logger.error("   Please ensure seo_gadget.py is in the Notebooks/imports/ directory.")
         return

    python_executable = sys.executable # Use the same python that runs the notebook

    for i, url in enumerate(urls_processed):
        domain, url_path_slug = get_safe_path_component(url)
        output_dir = base_dir / domain / url_path_slug
        dom_path = output_dir / "rendered_dom.html"

        if not dom_path.exists():
            if verbose: # Control logging with verbose flag
                logger.warning(f"  -> Skipping [{i+1}/{len(urls_processed)}]: rendered_dom.html not found for {url}")
            fail_count += 1
            continue

        # Create a coroutine for each subprocess call
        async def run_visualizer(url_to_viz, dom_file_path):
            nonlocal success_count, fail_count # Allow modification of outer scope vars
            proc = await asyncio.create_subprocess_exec(
                python_executable, str(script_path), str(dom_file_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()

            log_prefix = f"  -> Viz Subprocess [{url_to_viz}]:" # Indent subprocess logs

            if proc.returncode == 0:
                if verbose: logger.success(f"{log_prefix} Success.")
                # Log stdout from the script only if verbose or if there was an issue (for debug)
                if verbose and stdout: logger.debug(f"{log_prefix} STDOUT:\n{stdout.decode().strip()}")
                success_count += 1
            else:
                logger.error(f"{log_prefix} Failed (Code: {proc.returncode}).")
                # Always log stdout/stderr on failure
                if stdout: logger.error(f"{log_prefix} STDOUT:\n{stdout.decode().strip()}")
                if stderr: logger.error(f"{log_prefix} STDERR:\n{stderr.decode().strip()}")
                fail_count += 1

        # Add the coroutine to the list of tasks
        tasks.append(run_visualizer(url, dom_path))

    # Run all visualization tasks concurrently
    if tasks:
         logger.info(f"🚀 Launching {len(tasks)} visualization subprocesses...")
         await asyncio.gather(*tasks)
    else:
         logger.info("No visualizations needed or possible.")


    logger.success(f"✅ Visualization generation complete. Success: {success_count}, Failed/Skipped: {fail_count}") # Use logger
