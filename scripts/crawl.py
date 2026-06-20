import asyncio
import json
import re
import argparse
from pathlib import Path
from urllib.parse import urlparse, quote

import tiktoken
from bs4 import BeautifulSoup
from markdownify import markdownify

from tools.scraper_tools import selenium_automation


def main():
    parser = argparse.ArgumentParser(description="Run LLM Optics crawl for a URL (Prompt Fu !https:// companion).")
    parser.add_argument("url", help="Target URL")
    parser.add_argument("--override", "-o", action="store_true", help="Force cache override (equivalent to True)")
    parser.add_argument("--headless", action="store_true", default=False, help="Run headless (default: visible for !https:// compat)")
    parser.add_argument("--persistent", action="store_true", help="Use persistent profile")
    args = parser.parse_args()

    URL = args.url
    HEADLESS = args.headless
    PERSISTENT = args.persistent
    OVERRIDE = args.override
    PROFILE_NAME = "crawl-probe"

    enc = tiktoken.encoding_for_model("gpt-4o")

    def tok(text: str) -> int:
        return len(enc.encode(text or ""))

    def safe_read(path: Path) -> str:
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def path_parts(url: str) -> tuple[str, str]:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.hostname or "unknown"
        slug = quote(parsed.path or "/", safe="").replace("/", "_")[:100] or "%2F"
        return domain, slug

    domain, slug = path_parts(URL)
    out = Path("browser_cache") / domain / slug

    params = {
        "url": URL,
        "domain": domain,
        "url_path_slug": slug,
        "take_screenshot": False,
        "headless": HEADLESS,
        "is_notebook_context": True,
        "verbose": True,
        "persistent": PERSISTENT,
        "profile_name": PROFILE_NAME,
        "override_cache": OVERRIDE,
    }

    print("PARAMS:", params)

    result = asyncio.run(selenium_automation(params))
    print("\nRESULT:")
    print(json.dumps({
        "success": result.get("success"),
        "cached": result.get("cached"),
        "artifact_keys": sorted(result.get("looking_at_files", {}).keys()),
    }, indent=2))

    print("\nTOKEN COUNTS (key defaults):")
    for label, fname in [
        ("seo.md", "seo.md"),
        ("headers.json", "headers.json"),
        ("diff_hierarchy.txt", "diff_hierarchy.txt"),
    ]:
        p = out / fname
        if p.exists():
            text = safe_read(p)
            print(f"{label:25} {tok(text):>7} tokens   {p}")
        else:
            print(f"{label:25} MISSING")

    # Quick body check
    hydrated_html = safe_read(out / "hydrated_dom.html")
    soup = BeautifulSoup(hydrated_html, "html.parser")
    body_md = markdownify(str(soup.body) if soup.body else "", heading_style="ATX")
    print("\nseo.md body tokens approx:", tok(body_md))
    print("Title:", repr(soup.title.string if soup.title else ""))


if __name__ == "__main__":
    main()
