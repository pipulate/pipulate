import os
import sys
import json
import yaml
import re
from datetime import datetime
from pathlib import Path
import llm
import argparse
import time
import common

# --- CONFIGURATION ---
CONFIG_DIR = Path.home() / ".config" / "articleizer"

ARTICLE_FILENAME = "article.txt"
PROMPT_FILENAME = "editing_prompt.txt"
PROMPT_PLACEHOLDER = "[INSERT FULL ARTICLE]"
INSTRUCTIONS_CACHE_FILE = "instructions.json"

# Model Selection - Use a stable model to avoid low quotas
DEFAULT_MODEL = 'gemini-2.5-flash'

def create_jekyll_post(article_content, instructions, output_dir):
    """
    Assembles and writes a Jekyll post file from the article content and
    structured AI-generated instructions.
    
    Auto-increments 'sort_order' based on existing posts for the current date.
    Wraps content in Liquid {% raw %} tags to prevent template errors.
    """
    print("Formatting final Jekyll post...")

    # 1. Determine Date and Auto-Increment Sort Order
    current_date = datetime.now().strftime('%Y-%m-%d')
    next_sort_order = 1
    
    try:
        target_path = Path(output_dir)
        if target_path.exists():
            # Find all markdown files for today
            todays_posts = list(target_path.glob(f"{current_date}-*.md"))
            
            max_order = 0
            for post_file in todays_posts:
                try:
                    # Read content to parse front matter
                    content = post_file.read_text(encoding='utf-8')
                    if content.startswith('---'):
                        # Split to isolate YAML block (between first two ---)
                        parts = content.split('---', 2)
                        if len(parts) >= 3:
                            front_matter = yaml.safe_load(parts[1])
                            if front_matter and 'sort_order' in front_matter:
                                try:
                                    order = int(front_matter['sort_order'])
                                    if order > max_order:
                                        max_order = order
                                except (ValueError, TypeError):
                                    continue
                except Exception as e:
                    print(f"Warning checking sort_order in {post_file.name}: {e}")
            
            if max_order > 0:
                next_sort_order = max_order + 1
                print(f"📅 Found {len(todays_posts)} posts for today. Auto-incrementing sort_order to {next_sort_order}.")
            else:
                print(f"📅 First post of the day. sort_order set to 1.")
                
    except Exception as e:
        print(f"⚠️ Could not calculate auto-increment sort_order: {e}. Defaulting to 1.")

    # 2. Prepare Data
    editing_instr = instructions.get("editing_instructions", {})
    analysis_content = instructions.get("book_analysis_content", {})
    yaml_updates = editing_instr.get("yaml_updates", {})

    # --- NEW: Construct the absolute Canonical URL ---
    permalink = yaml_updates.get("permalink", "")
    # Ensure proper slash formatting
    if not permalink.startswith("/"):
        permalink = f"/{permalink}"
    canonical_url = f"https://mikelev.in{permalink}"
    # -----------------------------------------------

    new_yaml_data = {
        'title': yaml_updates.get("title"),
        'permalink': permalink,
        'canonical_url': canonical_url,  # <--- INJECTED HERE
        'description': analysis_content.get("authors_imprint"),
        'meta_description': yaml_updates.get("description"),
        'excerpt': yaml_updates.get("description"),
        'meta_keywords': yaml_updates.get("keywords"),
        'layout': 'post',
        'sort_order': next_sort_order
    }
    
    # 3. Assemble Content
    final_yaml_block = f"---\n{yaml.dump(new_yaml_data, Dumper=yaml.SafeDumper, sort_keys=False, default_flow_style=False)}---"

    article_body = article_content.strip()
    article_body = f"## Technical Journal Entry Begins\n\n{article_body}"

    subheadings = editing_instr.get("insert_subheadings", [])
    for item in reversed(subheadings):
        snippet = item.get("after_text_snippet", "")
        subheading = item.get("subheading", "## Missing Subheading")
        if not snippet:
            print(f"Warning: Skipping subheading '{subheading}' due to missing snippet.")
            continue

        words = re.findall(r'\w+', snippet.lower())
        pattern_text = r'.*?'.join(re.escape(word) for word in words)

        match = re.search(pattern_text, article_body, re.IGNORECASE | re.DOTALL)
        if match:
            # SAFETY FIX: Force insertion to the nearest paragraph break (double newline).
            # This prevents headlines from splitting sentences or paragraphs mid-stream.
            match_end = match.end()
            
            # Find the next double newline starting from the end of the match
            insertion_point = article_body.find('\n\n', match_end)
            
            # If no paragraph break is found (end of document), append to the very end.
            if insertion_point == -1:
                insertion_point = len(article_body)
            
            # Insert the subheading surrounded by newlines.
            # If insertion_point finds an existing '\n\n', this logic adds another '\n\n'
            # effectively creating: [End of Para]\n\n[Subheading]\n\n[Start of Next Para]
            article_body = (
                article_body[:insertion_point] +
                f"\n\n{subheading}" +
                article_body[insertion_point:]
            )
        else:
            print(f"Warning: Snippet not found for subheading '{subheading}': '{snippet}'")

    prepend_text = editing_instr.get("prepend_to_article_body", "")
    if prepend_text:
        intro_section = f"## Setting the Stage: Context for the Curious Book Reader\n\n{prepend_text}\n\n---"
        article_body = f"{intro_section}\n\n{article_body}"

    # --- WRAPPING LOGIC START ---
    # Wrap the entire body in {% raw %} ... {% endraw %} to prevent Liquid processing errors
    # only if it's not already wrapped.
    if not article_body.strip().startswith("{% raw %}"):
        article_body = f"{{% raw %}}\n{article_body}\n{{% endraw %}}"
    # --- WRAPPING LOGIC END ---

    analysis_markdown = "\n## Book Analysis\n"
    if 'ai_editorial_take' in analysis_content:
        analysis_markdown += f"\n### Ai Editorial Take\n{analysis_content['ai_editorial_take']}\n"
    if 'promotional_tweet' in analysis_content:
        analysis_markdown += f"\n### 🐦 X.com Promo Tweet\n```text\n{analysis_content['promotional_tweet']}\n```\n"
    for key, value in analysis_content.items():
        if key in ['authors_imprint', 'ai_editorial_take', 'promotional_tweet']:
            continue
        title = key.replace('_', ' ').title()
        analysis_markdown += f"\n### {title}\n"
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    analysis_markdown += f"* **Title Option:** {item.get('title', 'N/A')}\n"
                    analysis_markdown += f"  * **Filename:** `{item.get('filename', 'N/A')}`\n"
                    analysis_markdown += f"  * **Rationale:** {item.get('rationale', 'N/A')}\n"
                else:
                    analysis_markdown += f"- {item}\n"
        elif isinstance(value, dict):
            for sub_key, sub_value in value.items():
                analysis_markdown += f"- **{sub_key.replace('_', ' ').title()}:**\n"
                if isinstance(sub_value, list):
                    for point in sub_value:
                        analysis_markdown += f"  - {point}\n"
                else:
                    analysis_markdown += f"  - {sub_value}\n"
        else:
            analysis_markdown += f"{value}\n"

    final_content = f"{final_yaml_block}\n\n{article_body}\n\n---\n{analysis_markdown}"

    # 4. Generate Filename
    slug = "untitled-article"
    title_brainstorm = analysis_content.get("title_brainstorm", [])
    if title_brainstorm and title_brainstorm[0].get("filename"):
        slug = os.path.splitext(title_brainstorm[0]["filename"])[0]

    output_filename = f"{current_date}-{slug}.md"
    output_path = os.path.join(output_dir, output_filename)
    os.makedirs(output_dir, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_content)

    print(f"✨ Success! Article saved to: {output_path}")
    print("Collect new 404s: python prompt_foo.py assets/prompts/find404s.md --chop CHOP_404_AFFAIR -l [:] --no-tree")

def main():
    parser = argparse.ArgumentParser(description="Process an article with the Gemini API and format it for Jekyll.")
    parser.add_argument(
        '-l', '--local',
        action='store_true',
        help=f"Use local '{INSTRUCTIONS_CACHE_FILE}' cache instead of calling the API."
    )
    common.add_standard_arguments(parser)
    args = parser.parse_args()

    # Use common to securely lock target
    output_dir = common.get_target_path(args)

    if not os.path.exists(ARTICLE_FILENAME):
        print(f"Error: Article file '{ARTICLE_FILENAME}' not found.")
        return
    with open(ARTICLE_FILENAME, 'r', encoding='utf-8') as f:
        article_text = f.read()

    instructions = None

    if args.local:
        print(f"Attempting to use local cache file: {INSTRUCTIONS_CACHE_FILE}")
        if not os.path.exists(INSTRUCTIONS_CACHE_FILE):
            print(f"Error: Cache file not found. Run without --local to create it.")
            return
        try:
            with open(INSTRUCTIONS_CACHE_FILE, 'r', encoding='utf-8') as f:
                instructions = json.load(f)
            print("Successfully loaded instructions from local cache.")
        except json.JSONDecodeError:
            print("Error: Could not parse the local instructions cache file. It may be corrupt.")
            return
    else:
        api_key = common.get_api_key(args.key)
        if not api_key:
            print("API Key not provided. Exiting.")
            return

        if not os.path.exists(PROMPT_FILENAME):
            print(f"Error: Prompt file '{PROMPT_FILENAME}' not found.")
            return
        with open(PROMPT_FILENAME, 'r', encoding='utf-8') as f:
            prompt_template = f.read()

        full_prompt = prompt_template.replace(PROMPT_PLACEHOLDER, article_text)

        print(f"Calling the Universal Adapter (using {DEFAULT_MODEL})...")
        max_retries = 5
        retry_delay = 2
        for attempt in range(max_retries):
            try:
                # Use a free-tier compatible model.
                model = llm.get_model(DEFAULT_MODEL)
                model.key = api_key  # Assign the key directly to the adapter
                response = model.prompt(full_prompt)
                gemini_output = response.text()
                print("Successfully received response from API.")
                
                json_match = re.search(r'```json\s*([\s\S]*?)\s*```', gemini_output)
                json_str = json_match.group(1) if json_match else gemini_output
                instructions = json.loads(json_str)
                print("Successfully parsed JSON instructions.")
                
                with open(INSTRUCTIONS_CACHE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(instructions, f, indent=4)
                print(f"✅ Instructions saved to '{INSTRUCTIONS_CACHE_FILE}' for future use.")
                break  # Exit the loop on success
            
            except Exception as e:
                # Check for retriable server-side or rate-limit errors
                error_str = str(e)
                if ("429" in error_str and "Quota" in error_str) or \
                   ("504" in error_str and "timed out" in error_str) or \
                   ("503" in error_str) or \
                   ("500" in error_str):
                    
                    print(f"Retriable API Error: {e}")
                    print(f"Retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries})")

                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    print(f"\nAn unrecoverable error occurred while calling the API: {e}")
                    if 'gemini_output' in locals():
                        print("--- API Raw Output ---\n" + gemini_output)
                    return
        else: # This block runs if the loop completes without a break
            print("Error: Max retries exceeded. Failed to get a successful response from the API.")
            return

    if instructions:
        create_jekyll_post(article_text, instructions, output_dir)

if __name__ == '__main__':
    main()
