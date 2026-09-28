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
import lsa

# --- CONFIGURATION ---
# ~/.config/articleizer/ is retired (2026-09-28): the keys live in
# common.KEYS_FILE under ~/.config/pipulate/, and nothing in this file ever
# read the old folder's path; the constant was the last mention of it.

ARTICLE_FILENAME = "article.txt"
PROMPT_FILENAME = "editing_prompt.txt"
PROMPT_PLACEHOLDER = "[INSERT FULL ARTICLE]"
INSTRUCTIONS_CACHE_FILE = "instructions.json"

# Model Selection - Prefer Flash, then fail over to Lite immediately on a
# retriable availability error. Each model keeps its own exponential-backoff
# clock so alternating retries do not make one inherit the other's penalty.
MODEL_CANDIDATES = (
    'gemini-flash-latest',
    'gemini-flash-lite-latest',
)
MAX_ATTEMPTS_PER_MODEL = 5
INITIAL_RETRY_DELAY = 2
# THE MINUTE IS THE CEILING (read 2026-09-28 off the API's own refusal:
# "generate_content_free_tier_input_token_count, limit: 250000", both
# models). A free Gemini key admits 250,000 input tokens a minute, and one
# request larger than the whole minute can never be served by waiting; the
# day's request count is a separate bucket the key ring turns past, this one
# no free key clears. The estimate divides by 3.5, not 4: a 915,721-char
# prompt read 228,930 at chars/4 and the API counted past 250,000, so 4
# undercounts this corpus by more than a tenth, and an estimate whose job is
# to catch a ceiling errs high on purpose.
FREE_TIER_INPUT_TPM = 250_000
CHARS_PER_TOKEN = 3.5

SPINE_PLACEHOLDER = "[INSERT BOOK SPINE]"
# THE BLOG FOLDER REACHES THE MODEL (banked 2026-09-04). editing_prompt.txt is
# what CAUSES every post's frontmatter to say /futureproof/, so leaving it
# hardwired meant blogs.nix could declare a folder that nothing ever wrote.
# A PATTERN, NOT A PREFIX, and the name follows the value: what gets
# substituted is a whole permalink shape ("/futureproof/[slug]/"), because a
# bare segment would force the template to spell "/[PREFIX]/[slug]/" and an
# empty prefix would then yield a doubled slash -- the exact case
# default_permalink exists to avoid. That same function builds this string,
# so the instruction the model receives and the fallback lsa.py uses can never
# disagree: one function, both answers.
# BASE URL RIDES ALONG because the tweet example hardwired the HOSTNAME too,
# and templating only the folder would hand grimoire the public site's host.
PERMALINK_PATTERN_PLACEHOLDER = "[INSERT PERMALINK PATTERN]"
BASE_URL_PLACEHOLDER = "[INSERT BASE URL]"


# THE FENCES LEAVE FIRST (2026-09-28, the operator's 80/20 after a Workspace
# key read free_tier too: "not gonna pay", "I don't think chunking is good").
# The sanitizer's fence contract runs in both lanes before this script reads
# article.txt: a fence opens at column 0 with a language and closes with a
# bare ``` at column 0, and every other backtick run is neutralized. So one
# regex names every fenced block exactly as the sanitizer's state machine
# does, and link_injector.py already walks the same shape. The stand-in
# keeps the language and the line count so the editing model knows what
# stood there, in square brackets so it reads as nothing the article said.
FENCE_BLOCK_RE = re.compile(r'^```([^\n]*)\n(.*?)^```[ \t]*$\n?', re.MULTILINE | re.DOTALL)
LEAN_NOTE = (
    "\n\n[EDITOR'S NOTE: {n} fenced code blocks were left out of this copy so it fits "
    "the model's window; each stands in as one bracketed line. The published article "
    "carries them in full. Never take an after_text_snippet from a stand-in line.]"
)


def strip_fences(text):
    """Replace every fenced block with a one-line stand-in. Returns (text, count)."""
    def stand_in(match):
        lang = match.group(1).strip() or 'text'
        lines = match.group(2).count('\n')
        return f"[fenced {lang} block, {lines} lines, left out of this copy]\n"
    return FENCE_BLOCK_RE.subn(stand_in, text)


def scan_corpus(output_dir):
    """One-pass frontmatter scan of the published corpus.

    Returns (entries, errors): entries is a list of dicts with filename,
    date, slug (date-stripped), permalink, and title; errors counts posts
    whose frontmatter could not be read (census-incompleteness signal).
    """
    entries, errors = [], 0
    target = Path(output_dir)
    if not target.exists():
        return entries, errors
    for post in sorted(target.glob("*.md")):
        stem = post.stem
        slug = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', stem)
        date = stem[:10]
        title, permalink = "", ""
        try:
            content = post.read_text(encoding='utf-8')
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    fm = yaml.safe_load(parts[1]) or {}
                    title = str(fm.get('title') or "")
                    permalink = str(fm.get('permalink') or "")
        except Exception:
            errors += 1
        entries.append({'filename': post.name, 'date': date, 'slug': slug,
                        'permalink': permalink, 'title': title})
    return entries, errors


def normalize_permalink(permalink):
    """Case-insensitive, slash-agnostic identity for collision checks."""
    return (permalink or "").strip().strip('/').lower()


def build_taken_identities(entries):
    """Map every taken slug and permalink identity to its owning filename."""
    taken = {}
    for e in entries:
        taken.setdefault(e['slug'].lower(), e['filename'])
        p = normalize_permalink(e['permalink'])
        if p:
            taken.setdefault(p, e['filename'])
    return taken


SPINE_FULL_DETAIL_COUNT = 150  # newest N entries carry date+slug+title


def build_book_spine(entries, full_detail_count=SPINE_FULL_DETAIL_COUNT):
    """Two-tier spine for the editing model's 40K view.

    Deep archive rides as bare slugs (the uniqueness census — the slug IS
    the identity, and the deterministic collision guard enforces it anyway);
    the newest entries ride full 'date slug | title' (the trajectory arc).
    Deterministic and non-generative; ~58% smaller than the all-titles spine.
    """
    if full_detail_count <= 0 or len(entries) <= full_detail_count:
        older, recent = [], entries
    else:
        older, recent = entries[:-full_detail_count], entries[-full_detail_count:]
    lines = [e['slug'] for e in older]
    if older and recent:
        lines.append("--- RECENT ENTRIES (full detail) ---")
    lines += [f"{e['date']} {e['slug']} | {e['title']}" for e in recent]
    return "\n".join(lines)

def create_jekyll_post(article_content, instructions, output_dir, preview_port, base_url=""):
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
    base_url = (base_url or "").rstrip("/")
    canonical_url = f"{base_url}{permalink}" if base_url else ""
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
    
    # --- NEW: Fix Dialogue Header Collisions ---
    # Converts "**Speaker**: ### Header" to "**Speaker**:\n\n### Header"
    article_body = re.sub(r'(\*\*[^*]+\*\*:\s*)(#{1,6}\s)', r'\1\n\n\2', article_body)
    # -------------------------------------------

    # --- NEW: Compress Code Block Spacing ---
    # Replaces double newlines before a closing code block with a single newline
    article_body = re.sub(r'\n\n```\n', '\n```\n', article_body)
    # -------------------------------------------

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
            
            # HEADING COLLISION GUARD (optics-convicted 2026-07-12): when the
            # article body already carries its own markdown headers (dialogue
            # partners now write them), inserting ours immediately before an
            # existing one creates stacked/empty H2s — the orphan-header
            # pattern the Semantic Outline lens caught on the Dune article.
            following = article_body[insertion_point:].lstrip('\n')
            if following.startswith('#'):
                print(f"Skipping subheading '{subheading}': heading already present at insertion point.")
                continue

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

    # --- COLLISION GUARD (deterministic, corpus-wide) ---
    entries, scan_errors = scan_corpus(output_dir)
    taken = build_taken_identities(entries)
    if scan_errors:
        print(f"⚠️ Collision census incomplete: {scan_errors} post(s) unreadable.")
    collisions = []
    slug_owner = taken.get(slug.lower())
    if slug_owner and slug_owner != output_filename:
        collisions.append(f"slug '{slug}' already owned by {slug_owner}")
    perma_owner = taken.get(normalize_permalink(permalink))
    if perma_owner and perma_owner != output_filename:
        collisions.append(f"permalink '{permalink}' already owned by {perma_owner}")
    if collisions:
        print("🛑 COLLISION GUARD: refusing to write new article.")
        for c in collisions:
            print(f"   - {c}")
        print("   Pick a new slug/permalink (edit instructions.json, rerun with --local).")
        return None

    output_path = os.path.join(output_dir, output_filename)
    os.makedirs(output_dir, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_content)

    print(f"✨ Success! Article saved to: {output_path}")
    print("Collect new 404s: python prompt_foo.py assets/prompts/find404s.md --chop CHOP_404_AFFAIR -l [:] --no-tree")

    # --- NEW: Construct Preview URL and Copy to Clipboard ---
    local_url = f"http://localhost:{preview_port}{permalink}"
    try:
        import subprocess
        subprocess.run(
            ['xclip', '-selection', 'clipboard'], 
            input=local_url.encode('utf-8'), 
            check=True
        )
        print(f"🔗 Paste-ready preview URL copied to clipboard:\n   {local_url}")
    except Exception as e:
        print(f"⚠️ Could not copy URL to clipboard: {e}")

    return output_path

def main():
    parser = argparse.ArgumentParser(description="Process an article with the Gemini API and format it for Jekyll.")
    parser.add_argument(
        '-l', '--local',
        action='store_true',
        help=f"Use local '{INSTRUCTIONS_CACHE_FILE}' cache instead of calling the API."
    )
    parser.add_argument(
        '--copy',
        action='store_true',
        help="Copy the generated prompt to the clipboard and exit without calling the API."
    )
    common.add_standard_arguments(parser)
    parser.add_argument(
        '-m', '--keys', type=str,
        help="Comma-separated key aliases from keys.json to rotate through when a key's "
             "quota is spent, or 'all' for every alias in file order (same -m as publishizer)."
    )
    parser.add_argument(
        '--model', type=str,
        help="One llm model id to use instead of the Gemini pair (any installed llm plugin; "
             "`llm models` lists them). With no -k/-m, llm resolves that provider's own key."
    )
    parser.add_argument(
        '--lean', action='store_true',
        help="Leave fenced code blocks out of the editor's copy (done unasked when the prompt "
             "exceeds a free key's minute); the published article keeps them."
    )
    args = parser.parse_args()

    # Use common to securely lock target
    output_dir = common.get_target_path(args)

    # Fetch the target configuration to get the preview port
    targets = common.load_targets()
    target_config = targets.get(str(args.target), targets.get("1", {}))
    preview_port = target_config.get("preview_port", 4000) # Default to 4000

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
        # THE KEY RING (2026-09-28). -m names a ring of keys.json aliases, or
        # `all` for every alias in file order, the same -m contextualizer.py
        # already turns; -k names one key; neither names "default". --model
        # with no key at all hands the credential to llm itself (its own key
        # store or the provider's env var), so a non-Gemini model is never
        # handed a Gemini key. The first key is drawn here and the rest wait
        # on the ring for the quota branch below. get_api_key exits on a
        # missing alias, so every key drawn is a real one.
        if args.keys:
            requested = [k.strip() for k in args.keys.split(',') if k.strip()]
            if requested == ['all']:
                requested = list(common.load_keys_dict().keys())
            keys_queue = [(k, common.get_api_key(k)) for k in requested]
        elif args.model and not args.key:
            keys_queue = [(None, None)]
        else:
            keys_queue = [(args.key or "default", common.get_api_key(args.key))]
        if not keys_queue:
            print("API Key not provided. Exiting.")
            return
        key_name, api_key = keys_queue.pop(0)
        if key_name:
            print(f"🔑 Key ring: '{key_name}' drawn, {len(keys_queue)} more waiting.")
        else:
            print("🔑 No keys.json key drawn; llm resolves the model's own credential.")

        if not os.path.exists(PROMPT_FILENAME):
            print(f"Error: Prompt file '{PROMPT_FILENAME}' not found.")
            return
        with open(PROMPT_FILENAME, 'r', encoding='utf-8') as f:
            prompt_template = f.read()

        # SUBSTITUTE INTO THE TEMPLATE, BEFORE THE ARTICLE LANDS. The order is
        # load-bearing for the guard below: an article ABOUT this system quotes
        # placeholder names in its prose (the one introducing this code does),
        # so a guard run on the ASSEMBLED prompt would refuse to publish the
        # very article documenting the mechanism -- THE INSTRUMENT BECOMES
        # BAIT. Scanning the template alone cannot see the article and so
        # cannot be baited by it.
        prompt_prefix = lsa.permalink_prefix(target_config)
        # `is None`, never `or`: target 4 declares base_url = "" ON PURPOSE
        # (a private wiki with no public URL), and an or-chain would hand it
        # the public site's hostname. Mirrors this file's own canonical_url
        # logic further down, and permalink_prefix's None-vs-falsy rule.
        prompt_base_url = target_config.get("base_url")
        if prompt_base_url is None:
            prompt_base_url = target_config.get("url", "https://mikelev.in")
        prompt_template = prompt_template.replace(
            PERMALINK_PATTERN_PLACEHOLDER,
            lsa.default_permalink("[slug]", prompt_prefix) + "/")
        prompt_template = prompt_template.replace(
            BASE_URL_PLACEHOLDER, prompt_base_url.rstrip("/"))
        # THE UNSUBSTITUTED-PLACEHOLDER AIRLOCK: if editing_prompt.txt carries
        # a placeholder this file does not know -- a typo, or a template
        # patched ahead of its reader -- the literal "[INSERT ...]" reaches the
        # model and lands verbatim in a permalink. Refuse instead. FULL ARTICLE
        # and BOOK SPINE are exempt because they are substituted after this
        # point, which is the only reason this guard can run here at all.
        leftover = sorted(set(re.findall(r"\[INSERT [A-Z ]+\]", prompt_template))
                          - {PROMPT_PLACEHOLDER, SPINE_PLACEHOLDER})
        if leftover:
            print(f"❌ Unsubstituted placeholder(s) in {PROMPT_FILENAME}: {leftover}")
            print("   Refusing to call the API; the model would copy the literal text into your frontmatter.")
            return
        # THE ARTICLE LANDS LAST (2026-09-28): the spine is substituted into
        # the template below and the article after it, so an article that
        # quotes the spine placeholder's text is never rewritten, and the lean
        # copy can take the article's place by one substitution.

        # --- BOOK SPINE INJECTION (40K-foot view for the editing model) ---
        if SPINE_PLACEHOLDER in prompt_template:
            spine_entries, spine_errors = scan_corpus(output_dir)
            if spine_errors:
                print(f"⚠️ Spine census incomplete: {spine_errors} post(s) unreadable.")
            spine = build_book_spine(spine_entries)
            prompt_template = prompt_template.replace(SPINE_PLACEHOLDER, spine)
            print(f"📚 Book spine injected: {len(spine_entries)} articles, {len(spine):,} chars.")

        full_prompt = prompt_template.replace(PROMPT_PLACEHOLDER, article_text)
        # THE SIZE READING (2026-09-28). "Too big" on a free Gemini key is the
        # per-minute input-token quota and it wears the same quota message as a
        # spent day; the ring cannot turn its way past it, since every free key
        # has the same minute. The estimate is printed on every run so the
        # number is read before the call; past the free minute the escape is
        # named and the run continues on the key that was named, because a
        # paid key on the same alias grammar is exactly how the ceiling is
        # cleared, and this script cannot tell a paid key from a free one.
        est_tokens = int(len(full_prompt) / CHARS_PER_TOKEN)
        # THE FENCES LEAVE FIRST (2026-09-28): a journal entry that carries its
        # own receipts is mostly fenced blocks, and the editing model wants
        # none of them; it names a title, writes a paragraph and places each
        # subheading by quoting the END of a prose paragraph, and every quote
        # is matched against the ORIGINAL article in create_jekyll_post, which
        # never sees this copy. So past the free minute, or on --lean, every
        # fenced block leaves the editor's copy for a stand-in, the copy ends
        # with a note saying so, the prompt is rebuilt and the size read again.
        fences_out = 0
        if args.lean or est_tokens > FREE_TIER_INPUT_TPM:
            lean_article, fences_out = strip_fences(article_text)
            if fences_out:
                full_prompt = prompt_template.replace(
                    PROMPT_PLACEHOLDER, lean_article + LEAN_NOTE.format(n=fences_out))
                lean_tokens = int(len(full_prompt) / CHARS_PER_TOKEN)
                print(f"✂️  {fences_out} fenced block(s) left out of the editor's copy: "
                      f"about {est_tokens:,} tokens -> about {lean_tokens:,}; the published article keeps them.")
                est_tokens = lean_tokens
        print(f"📏 Prompt: {len(full_prompt):,} chars, about {est_tokens:,} tokens (chars/{CHARS_PER_TOKEN}, an estimate that errs high).")
        if est_tokens > FREE_TIER_INPUT_TPM:
            print(f"⚠️  Larger than a free Gemini key's whole minute ({FREE_TIER_INPUT_TPM:,} input tokens): "
                  "no free key and no wait can serve it, and the fenced blocks are already out or there were none, "
                  "so what remains is prose. Continuing on the key named; the escapes are a shorter article, "
                  "or --model <id> -k <alias> onto a larger window.")
        if args.copy:
            try:
                # We borrow the existing robust clipboard function from prompt_foo
                import subprocess
                subprocess.run(['pbcopy'] if sys.platform == 'darwin' else ['xclip', '-selection', 'clipboard'], input=full_prompt.encode('utf-8'), check=True)
                print("📋 Prompt copied to clipboard! You can now paste it into any web UI.")
            except Exception as e:
                print(f"❌ Failed to copy to clipboard: {e}")
            return

        models = (args.model,) if args.model else MODEL_CANDIDATES
        fallback = f", fallback {models[1]}" if len(models) > 1 else ", no fallback"
        print(f"Calling the Universal Adapter (primary {models[0]}{fallback})...")
        total_attempts = MAX_ATTEMPTS_PER_MODEL * len(models) * (1 + len(keys_queue))
        retry_delays = {name: INITIAL_RETRY_DELAY for name in models}
        retry_after = {name: 0.0 for name in models}
        quota_hit = set()
        for attempt in range(total_attempts):
            model_name = models[attempt % len(models)]
            model_attempt = (attempt // len(models)) % MAX_ATTEMPTS_PER_MODEL + 1
            wait = max(0.0, retry_after[model_name] - time.monotonic())
            if wait:
                print(
                    f"Waiting {wait:.0f} seconds before retrying {model_name} "
                    f"(Attempt {model_attempt}/{MAX_ATTEMPTS_PER_MODEL})..."
                )
                time.sleep(wait)

            try:
                model = llm.get_model(model_name)
                if api_key:
                    model.key = api_key  # a keys.json key; else llm's own store
                response = model.prompt(full_prompt)
                gemini_output = response.text()
                print(f"Successfully received response from API via {model_name}.")
                
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
                lowered = error_str.lower()
                # THE CLASSIFIER ASKED FOR THE WRONG WORD (convicted 2026-09-28
                # by the receipt that mounted this ride): it demanded "429" AND
                # "Quota" in one message, and the Gemini plugin's quota text
                # carries neither the status code nor the capital ("You exceeded
                # your current quota ... Quota exceeded for metric: ...
                # free_tier_requests, limit: 20"), so the commonest failure this
                # script has fell through to the UNRECOVERABLE branch with the
                # fallback model never tried. contextualizer.py's sibling check
                # had read the lowercase word all along. A quota is named by
                # the word; a bad JSON body is retried on the other model rather
                # than ending the run with the output printed and nothing saved.
                is_parse = isinstance(e, json.JSONDecodeError)
                is_quota = (not is_parse) and (
                    "quota" in lowered or "resource_exhausted" in lowered
                    or "429" in error_str)
                if is_quota or is_parse or \
                   ("504" in error_str and "timed out" in error_str) or \
                   ("503" in error_str) or \
                   ("500" in error_str) or \
                   ("high demand" in lowered):
                    
                    # THE MINUTE IS THE CEILING (2026-09-28, the grim receipt):
                    # a quota on the input-token metric whose limit sits below
                    # this prompt's own estimate is not a window that reopens.
                    # The loop waited 57 seconds for one before the operator
                    # cut it; every free key carries the same limit and every
                    # retry spends one of the day's twenty requests, so it stops
                    # here with the verdict instead of turning the ring or
                    # honoring a hint that names a minute the request cannot fit
                    # in. A paid key or another provider is named by hand.
                    limit_match = re.search(r'limit:\s*(\d+)', error_str)
                    is_size = (is_quota and 'input_token' in lowered and limit_match is not None
                               and est_tokens > int(limit_match.group(1)))
                    if is_size:
                        limit = int(limit_match.group(1))
                        print(f"API Error [SIZE] from {model_name}: {e}")
                        print(f"⛔ SIZE: this key admits {limit:,} input tokens a minute and the prompt "
                              f"is about {est_tokens:,}; no wait and no other free key can serve it.")
                        if fences_out:
                            print("   The fenced blocks are already out; what remains is prose. Escapes: a shorter "
                                  "article, or --model <id> -k <alias> onto a larger window. --copy still pastes it.")
                        else:
                            print("   Escapes: --lean (the fenced blocks leave the editor's copy; the estimate read "
                                  "under and the API read over), --model <id> -k <alias>, or a shorter article.")
                        return
                    kind = "QUOTA" if is_quota else ("PARSE" if is_parse else "TRANSIENT")
                    print(f"Retriable API Error [{kind}] from {model_name}: {e}")
                    if is_parse and 'gemini_output' in locals():
                        print("--- API Raw Output (head) ---\n" + gemini_output[:400])
                    # QUOTA WINDOW DISCIPLINE (live-fire convicted 2026-07-19):
                    # each model gets its own exponential clock. A failure on
                    # Flash therefore falls through to Lite immediately, while
                    # the failed model honors its own server hint before its
                    # next turn in the alternation.
                    hint = re.search(r'retry in (\d+(?:\.\d+)?)s', error_str)
                    hinted_delay = float(hint.group(1)) + 1 if hint else 0
                    wait = max(retry_delays[model_name], hinted_delay)
                    retry_after[model_name] = time.monotonic() + wait
                    retry_delays[model_name] *= 2
                    if is_quota:
                        quota_hit.add(model_name)
                    # THE KEY RING TURNS (2026-09-28). A quota is per key and per
                    # model, so a key is spent only when every model on it has
                    # said quota; then the next key on the ring is drawn with
                    # fresh clocks and no wait, because a spent key's retry hint
                    # names the minute and not the day. With one key on the ring
                    # the hint is honored exactly as before.
                    if is_quota and quota_hit >= set(models) and keys_queue:
                        key_name, api_key = keys_queue.pop(0)
                        quota_hit.clear()
                        retry_after = {name: 0.0 for name in models}
                        retry_delays = {name: INITIAL_RETRY_DELAY for name in models}
                        print(f"🔑 Every model on the current key reports quota; "
                              f"rotating to '{key_name}' ({len(keys_queue)} more waiting).")
                        continue

                    if attempt + 1 < total_attempts:
                        next_model = models[(attempt + 1) % len(models)]
                        next_wait = max(0.0, retry_after[next_model] - time.monotonic())
                        if next_wait:
                            print(
                                f"Switching to {next_model}; its backoff has "
                                f"{next_wait:.0f} seconds remaining."
                            )
                        else:
                            print(f"Switching to {next_model} immediately.")
                else:
                    print(f"\nAn unrecoverable error occurred while calling the API: {e}")
                    if 'gemini_output' in locals():
                        print("--- API Raw Output ---\n" + gemini_output)
                    print(f"Manual lane: --copy, paste into a web UI, save its JSON as "
                          f"{INSTRUCTIONS_CACHE_FILE}, rerun with --local.")
                    return
        else:  # This block runs if the loop completes without a break
            print(
                f"Error: {MAX_ATTEMPTS_PER_MODEL} attempts per model on every key exhausted. "
                "Failed to get a successful response from the API.\n"
                f"Manual lane: --copy, paste into a web UI, save its JSON as {INSTRUCTIONS_CACHE_FILE}, rerun with --local."
            )
            return

    if instructions:
        base_url = target_config.get("base_url")
        if base_url is None:
            base_url = target_config.get("url", "https://mikelev.in")
        saved_path = create_jekyll_post(article_text, instructions, output_dir, preview_port, base_url)
        if saved_path:
            common.record_last_published(args.target, saved_path, target_config.get("name"))


if __name__ == '__main__':
    main()
