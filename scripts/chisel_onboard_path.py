import re
from pathlib import Path

def fix_onboard_sauce():
    """Aligns show_artifacts path logic with the scraper's looking_at directory."""
    f = Path("assets/nbs/imports/onboard_sauce.py")
    if not f.exists():
        print(f"⚠️ {f} not found.")
        return

    txt = f.read_text(encoding="utf-8")

    # Replace the broken cache_dir assignment
    old_path_logic = "    cache_dir = wand.paths.browser_cache / domain / url_path_slug"
    
    # We add the 'looking_at' subfolder to match the default behavior of wand.scrape()
    new_path_logic = "    cache_dir = wand.paths.browser_cache / 'looking_at' / domain / url_path_slug"

    if old_path_logic in txt:
        txt = txt.replace(old_path_logic, new_path_logic)
        f.write_text(txt, encoding="utf-8")
        print("✅ assets/nbs/imports/onboard_sauce.py: show_artifacts path aligned with scraper output!")
    elif new_path_logic in txt:
        print("⏭️  assets/nbs/imports/onboard_sauce.py already has the correct path logic.")
    else:
        print("❌ Could not find exact string match in onboard_sauce.py.")

def fix_interrogate_local_ai():
    """Aligns interrogate_local_ai path logic with the scraper's looking_at directory."""
    f = Path("assets/nbs/imports/onboard_sauce.py")
    if not f.exists():
        return

    txt = f.read_text(encoding="utf-8")

    # Replace the broken md_file assignment
    old_path_logic = '    md_file = wand.paths.browser_cache / domain / url_path_slug / "accessibility_tree.json"'
    
    # We add the 'looking_at' subfolder
    new_path_logic = '    md_file = wand.paths.browser_cache / "looking_at" / domain / url_path_slug / "accessibility_tree.json"'

    if old_path_logic in txt:
        txt = txt.replace(old_path_logic, new_path_logic)
        f.write_text(txt, encoding="utf-8")
        print("✅ assets/nbs/imports/onboard_sauce.py: interrogate_local_ai path aligned!")
    elif new_path_logic in txt:
        print("⏭️  interrogate_local_ai already has the correct path logic.")
    else:
        print("❌ Could not find exact string match for interrogate_local_ai in onboard_sauce.py.")

if __name__ == "__main__":
    print("🔨 Initiating Onboard Path Alignment...")
    fix_onboard_sauce()
    fix_interrogate_local_ai()
    print("🏁 Strike complete.")