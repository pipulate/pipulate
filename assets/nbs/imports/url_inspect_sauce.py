# assets/nbs/imports/url_inspect_sauce.py
import pandas as pd
from pipulate import wand
from . import core_sauce as core
import time
import random
import yaml


async def scrape(job, **kwargs):
    """
    Thin wrapper for URL auditing acquisition. 
    Now strictly state-driven, pulling the target from the wand.
    """
    # Pull the URL set by the widget in the notebook
    target_url = wand.get(job, 'target_url')
    
    if not target_url:
        print("❌ Error: No target_url found in state. Did you run the widget cell?")
        return []
        
    urls = [target_url]
    
    # Still set url_list for compatibility with downstream core logic
    wand.set(job, "url_list", urls)
    
    return await core.universal_scrape(job, urls, **kwargs)

async def generate_extractions_post_scrape(job, verbose=False):
    """Use core batch optics for auditing."""
    return await core.generate_optics_batch(job, verbose=verbose)

def stack_seo_data(job):
    """Load core extraction data for SEO audit."""
    data = wand.get(job, "extracted_data", [])
    return pd.DataFrame(data)

def export_audits_to_excel(job, df):
    """Professional egress via core engine."""
    return core.format_excel_pro(job, df, sheet_name="SEO_Audit")

# --- Keep your existing fetch_http_info and ai_audit_em functions below this line ---
# They contain the unique business logic that makes this specific wand work.

async def fetch_http_info(job: str, delay_range: tuple = (2, 5)):
    """
    Fetches HTTP status, redirect chain, and final headers for each URL using requests.
    Saves the info to http_info.json in the respective browser_cache directory.
    Runs requests calls in a thread executor to avoid blocking the main asyncio loop.
    """
    print("🔗 Fetching HTTP redirect and header info...")
    urls_to_process = wand.get(job, URL_LIST_STEP, [])
    if not urls_to_process:
        print("❌ No URLs found in the job state.")
        return

    # --- Path Setup ---
    base_dir = wand.paths.browser_cache
    print(f"🔍 Using topological browser_cache path for HTTP info: {base_dir}")
    # --- End Path Setup ---

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
    }
    success_count = 0
    fail_count = 0

    # Get the current asyncio event loop
    loop = asyncio.get_running_loop()

    for i, url in enumerate(urls_to_process):
        # --- Fuzzed Delay ---
        if i > 0 and delay_range and isinstance(delay_range, (tuple, list)) and len(delay_range) == 2:
             min_delay, max_delay = delay_range
             if isinstance(min_delay, (int, float)) and isinstance(max_delay, (int, float)) and min_delay <= max_delay:
                 delay = random.uniform(min_delay, max_delay)
                 print(f"  -> ⏳ Waiting {delay:.2f}s before fetching {url}")
                 await asyncio.sleep(delay) # Use asyncio.sleep for async compatibility
        # --- End Delay ---

        http_info = {
            "original_url": url,
            "final_url": None,
            "status_code": None,
            "redirect_chain": [],
            "final_headers": None,
            "error": None
        }

        try:
            print(f"  -> 🔗 Fetching [{i+1}/{len(urls_to_process)}] {url}")

            # Run synchronous requests.get in a thread executor
            response = await loop.run_in_executor(
                None, # Use default executor
                lambda u=url: requests.get(u, headers=headers, allow_redirects=True, timeout=20)
            )
            # No need to manually raise_for_status, check status code directly

            http_info["final_url"] = response.url
            http_info["status_code"] = response.status_code
            http_info["final_headers"] = dict(response.headers) # Convert CaseInsensitiveDict

            # Save the raw HTML source from requests
            domain, url_path_slug = get_safe_path_component(url)
            output_dir = base_dir / domain / url_path_slug
            source_html_path = output_dir / "source.html"
            source_html_path.write_text(response.text, encoding='utf-8')

            # Extract redirect chain (if any)
            if response.history:
                for resp_hist in response.history:
                    # Check if status code indicates a redirect before adding
                    if 300 <= resp_hist.status_code < 400:
                         http_info["redirect_chain"].append({
                            "url": resp_hist.url,
                            "status_code": resp_hist.status_code,
                            # Optional: "headers": dict(resp_hist.headers)
                         })
            success_count += 1

        except requests.exceptions.RequestException as e:
            print(f"  -> ❌ Request failed for {url}: {e}")
            http_info["error"] = str(e)
            if hasattr(e, 'response') and e.response is not None:
                http_info["status_code"] = e.response.status_code
                http_info["final_url"] = e.response.url # Url that caused the error
                http_info["final_headers"] = dict(e.response.headers)
            fail_count += 1
        except Exception as e:
            print(f"  -> ❌ Unexpected error for {url}: {e}")
            http_info["error"] = f"Unexpected error: {str(e)}"
            fail_count += 1

        # --- Save results ---
        try:
            domain, url_path_slug = get_safe_path_component(url) # Use original URL for path consistency
            output_path = base_dir / domain / url_path_slug / "http_info.json"
            output_path.parent.mkdir(parents=True, exist_ok=True) # Ensure directory exists
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(http_info, f, indent=2, ensure_ascii=False) # Use ensure_ascii=False
            if http_info["error"] is None:
                 print(f"  -> ✅ Saved HTTP info for {url}")
        except Exception as e:
            print(f"  -> ❌ Error saving http_info.json for {url}: {e}")
            # Don't increment fail_count again if request already failed
            if http_info["error"] is None:
                fail_count += 1
                success_count -=1 # Decrement success if save failed

    print(f"✅ HTTP info fetching complete. Success: {success_count}, Failures: {fail_count}")


# Replacement function for Notebooks/secretsauce.py
async def ai_audit_em(job: str, seo_df: pd.DataFrame, debug: bool = False, limit: int = None) -> pd.DataFrame:
    """
    Enriches the DataFrame with AI-generated SEO audits, row by row.
    This step is idempotent and can be limited to a number of new rows.
    """
    import time
    
    # --- 1. Define Cache Path ---
    cache_dir = Path("data")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"audit_cache_{job}.json"

    # --- 2. Load Cached Data ---
    audit_data = []
    if cache_file.exists():
        try:
            raw_content = cache_file.read_text(encoding='utf-8')
            if raw_content.strip():
                audit_data = json.loads(raw_content)
                print(f"✅ Loaded {len(audit_data)} audited rows from cache.")
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ Could not load audit cache. Starting fresh. Error: {e}")
    
    processed_urls = {item.get('url') for item in audit_data}
    print(f"🧠 Auditing {len(seo_df)} pages... ({len(processed_urls)} already cached)")

    # --- 3. Get Prompt & Configure AI ---
    user_prompt_instructions = wand.get(job, 'user_prompt_instructions')
    
    if not user_prompt_instructions:
        print("❌ Error: Instructions not found in state. Did you run the prompt definition cell?")
        return seo_df # Return original df
        
    system_prompt_wrapper = f'''
Your task is to analyze webpage data and generate a structured JSON object based on the user's instructions.
Your output must be **only a single, valid JSON object inside a markdown code block** and nothing else. Adherence to the schema is critical.

--- START USER INSTRUCTIONS ---

{user_prompt_instructions}

--- END USER INSTRUCTIONS ---

**Input Data:**

--- WEBPAGE DATA BEGIN ---
{{webpage_data}}
--- WEBPAGE DATA END ---

**Final Instructions:**

Based *only* on the provided webpage data and the user instructions, generate the requested data.
Your entire output must be a single JSON object in a markdown code block, conforming to this exact schema:

{{
  "ai_selected_keyword": "string",
  "ai_score": "integer (1-5)",
  "keyword_rationale": "string (rationale + intent)"
}}
'''
    
    try:
        model = genai.GenerativeModel('models/gemini-2.5-flash')
    except Exception as e:
        print(f"❌ Error configuring AI model: {e}")
        print("   Did you forget to run pip.api_key(job)?")
        return seo_df

    # --- 4. Process Loop ---
    processed_count = 0
    try:
        for index, row in seo_df.iterrows():
            url = row.get('url')
            if url in processed_urls:
                continue # Skip already processed rows

            if limit is not None and processed_count >= limit:
                print(f"\n🏁 Reached processing limit of {limit} rows.")
                break
                
            print(f"  -> 🤖 AI Call [{processed_count+1}/{limit or 'all new'}]: Processing {url}")
            
            full_prompt = "" # Initialize to empty string
            try:
                webpage_data_str = row.to_json(indent=2)

                # Use .replace() for safer substitution to avoid errors from braces in the data
                full_prompt = system_prompt_wrapper.replace('{webpage_data}', webpage_data_str)
                
                if debug:
                    print("\n--- PROMPT ---")
                    print(full_prompt)
                    print("--- END PROMPT ---\n")

                ai_response = model.generate_content(full_prompt)

                # --- Start Robust Response Handling ---
                if not ai_response.parts:
                    # This indicates the response was empty, likely blocked.
                    block_reason = ai_response.prompt_feedback.block_reason if ai_response.prompt_feedback else "Unknown"
                    safety_ratings = ai_response.prompt_feedback.safety_ratings if ai_response.prompt_feedback else "N/A"
                    print(f"  -> ❌ AI call blocked for {url}. Reason: {block_reason}")
                    print(f"  -> Safety Ratings: {safety_ratings}")
                    continue # Skip to the next URL

                response_text = ai_response.text.strip()
                # --- End Robust Response Handling ---
                
                # Robust JSON cleaning
                clean_json = response_text
                if clean_json.startswith("```json"):
                    clean_json = clean_json[7:]
                if clean_json.startswith("```"):
                    clean_json = clean_json[3:]
                if clean_json.endswith("```"):
                    clean_json = clean_json[:-3]
                clean_json = clean_json.strip()

                ai_json_result = json.loads(clean_json)
                
                # Add the URL for merging
                ai_json_result['url'] = url
                audit_data.append(ai_json_result)
                processed_urls.add(url)
                processed_count += 1
                
                # Give a small delay to respect API rate limits
                time.sleep(1) 

            except json.JSONDecodeError as e:
                print(f"  -> ❌ JSON Decode Error for {url}: {e}")
                print(f"  -> Raw AI Response:\n---\n{response_text}\n---")
                continue
            except Exception as e:
                print(f"  -> ❌ An unexpected error occurred for {url}: {e}")
                if full_prompt:
                    print("\n--- FAILED PROMPT ---")
                    print(full_prompt)
                    print("--- END FAILED PROMPT ---\n")
                else:
                    print("\n--- DEBUG: Error occurred before prompt was fully generated. ---\n")
                print("🛑 Halting execution due to error.")
                break # Stop the loop on the first error

    except KeyboardInterrupt:
        print("\n🛑 Execution interrupted by user.")
    finally:
        print("\n💾 Saving progress to audit cache...")
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(audit_data, f, indent=2)
            print(f"✅ Save complete. {len(audit_data)} total audited rows in cache.")
        except Exception as e:
            print(f"❌ Error saving cache in `finally` block: {e}")

    # --- 5. Merge and Return ---
    if not audit_data:
        print("ℹ️ No new data to merge.")
        return seo_df # Return original DataFrame
        
    ai_df = pd.DataFrame(audit_data)
    
    # Merge AI data back into the original seo_df
    # 'how=left' keeps all original rows and adds AI data where it exists
    merged_df = seo_df.merge(ai_df, on='url', how='left')
    
    # --- Reorder columns to bring AI fields to the front ---
    if 'ai_selected_keyword' in merged_df.columns:
        core_cols = ['url', 'title']
        ai_cols = ['ai_selected_keyword', 'ai_score', 'keyword_rationale']
        
        # Get all other existing columns
        other_cols = [col for col in merged_df.columns if col not in core_cols + ai_cols]
        
        # Combine and apply the new order
        new_order = core_cols + ai_cols + other_cols
        merged_df = merged_df[new_order]
        print("✅ AI audit complete. Reordered columns and merged results.")
    else:
        print("✅ AI audit complete. Merged results into DataFrame.")

    return merged_df
