import json
import yaml
import os
import re
from datetime import datetime

# --- CONFIGURATION ---
# Output directory resolved relative to the user's home for portability.
OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "repos", "MikeLev.in", "_posts")
# -------------------

def format_complete_article():
    """
    Reads 'article.txt' and 'edits.json', then creates a complete markdown file
    with a Jekyll front matter, a prepended introduction, inserted subheadings,
    and a reordered book analysis at the end.
    """
    article_path = "article.txt"
    json_path = "edits.json"

    if not os.path.exists(article_path) or not os.path.exists(json_path):
        print(f"Error: Make sure '{article_path}' and '{json_path}' exist in this folder.")
        return

    print(f"Processing complete article: '{article_path}' and '{json_path}'")

    try:
        with open(article_path, 'r', encoding='utf-8') as f:
            article_part = f.read()
        with open(json_path, 'r', encoding='utf-8') as f:
            instructions = json.load(f)
    except Exception as e:
        print(f"An error occurred while reading files: {e}")
        return

    editing_instr = instructions.get("editing_instructions", {})
    analysis_content = instructions.get("book_analysis_content", {})
    yaml_updates = editing_instr.get("yaml_updates", {})

    # 1. Build the Jekyll YAML front matter
    new_yaml_data = {
        'title': yaml_updates.get("title"),
        'permalink': yaml_updates.get("permalink"),
        'description': analysis_content.get("authors_imprint"),
        'meta_description': yaml_updates.get("description"),
        'meta_keywords': yaml_updates.get("keywords"),
        'layout': 'post',
        'sort_order': 1
    }
    final_yaml_block = f"---\n{yaml.dump(new_yaml_data, Dumper=yaml.SafeDumper, sort_keys=False, default_flow_style=False)}---"

    # 2. Get the raw article body
    article_body = article_part.strip()
    article_body = f"## Technical Journal Entry Begins\n\n{article_body}"
        
    # 3. Insert subheadings into the body
    subheadings = editing_instr.get("insert_subheadings", [])
    for item in reversed(subheadings):
        snippet = item["after_text_snippet"]
        subheading = item["subheading"]
        
        cleaned_snippet = snippet.replace("...", "").strip().rstrip('.,;:!?\'"')
        
        # --- FIX FOR LINE BREAKS ---
        # Create a flexible regex pattern. re.escape handles special characters,
        # and replacing spaces with \s+ allows the pattern to match text
        # even if it's broken up by newlines or multiple spaces.
        pattern_text = re.escape(cleaned_snippet).replace(r'\ ', r'\s+')
        
        try:
            match = re.search(pattern_text, article_body, re.IGNORECASE)
        except re.error as e:
            print(f"Regex error for subheading '{subheading}': {e}")
            match = None

        if match:
            # Find the end of the paragraph containing the match by searching for the
            # next newline character *after* the matched snippet ends.
            insertion_point = article_body.find('\n', match.end())
            
            # If no newline is found, the snippet is in the last paragraph.
            # We'll append the subheading at the very end of the article body.
            if insertion_point == -1:
                insertion_point = len(article_body)
            
            # Insert the subheading cleanly after the identified paragraph.
            article_body = (
                article_body[:insertion_point] + 
                f"\n\n{subheading}" + 
                article_body[insertion_point:]
            )
        else:
            print(f"Warning: Snippet not found for subheading '{subheading}': '{snippet}'")

    # 4. Prepend the "Curious Reader" intro
    prepend_text = editing_instr.get("prepend_to_article_body", "")
    if prepend_text:
        if not prepend_text.strip().startswith("##"):
                intro_section = f"## Setting the Stage: Context for the Curious Book Reader\n\n{prepend_text}\n\n---"
        else:
                intro_section = f"{prepend_text}\n\n---"
        article_body = f"{intro_section}\n\n{article_body}"

    # 5. --- REARRANGED & POLISHED BOOK ANALYSIS SECTION ---
    analysis_markdown = "\n## Book Analysis\n"
    
    if 'ai_editorial_take' in analysis_content:
        analysis_markdown += f"\n### Ai Editorial Take\n"
        analysis_markdown += f"{analysis_content['ai_editorial_take']}\n"

    for key, value in analysis_content.items():
        if key in ['authors_imprint', 'ai_editorial_take']:
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
    
    # 6. Assemble the final document
    final_content = f"{final_yaml_block}\n\n{article_body}\n\n---\n{analysis_markdown}"

    # 7. Generate the Jekyll filename
    current_date = datetime.now().strftime('%Y-%m-%d')
    slug = "untitled-article"
    title_brainstorm = analysis_content.get("title_brainstorm", [])
    if title_brainstorm:
        preferred_filename = title_brainstorm[0].get("filename", "untitled.md")
        slug = os.path.splitext(preferred_filename)[0]

    output_filename = f"{current_date}-{slug}.md"

    # 8. Save the result
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_content)

    print(f"✨ Success! Complete article with analysis saved to: {output_path}")

if __name__ == '__main__':
    format_complete_article()