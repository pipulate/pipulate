import re
from pathlib import Path

def patch_blown_fuse():
    """Rebuilds the consumed ChromeOptions object inside the auto-healing block."""
    f = Path("tools/scraper_tools.py")
    txt = f.read_text(encoding="utf-8")

    # The block we injected last time
    old_fallback = """                    driver = uc.Chrome(options=options, 
                                       user_data_dir=str(profile_path), 
                                       browser_executable_path=browser_path,
                                       driver_executable_path=driver_path,
                                       version_main=fallback_version)"""

    # The new block with fresh options
    new_fallback = """                    # UC consumes the options object. We must forge a fresh one.
                    fresh_options = uc.ChromeOptions()
                    if headless:
                        fresh_options.add_argument("--headless")
                    fresh_options.add_argument("--no-sandbox")
                    fresh_options.add_argument("--disable-dev-shm-usage")
                    fresh_options.add_argument("--start-maximized")
                    fresh_options.add_argument("--window-size=1920,1080")
                    
                    driver = uc.Chrome(options=fresh_options, 
                                       user_data_dir=str(profile_path), 
                                       browser_executable_path=browser_path,
                                       driver_executable_path=driver_path,
                                       version_main=fallback_version)"""

    if old_fallback in txt:
        txt = txt.replace(old_fallback, new_fallback)
        f.write_text(txt, encoding="utf-8")
        print("✅ tools/scraper_tools.py: ChromeOptions blown fuse replaced with a fresh circuit!")
    elif "fresh_options = uc.ChromeOptions()" in txt:
        print("⏭️  tools/scraper_tools.py already has the fresh options patch.")
    else:
        print("❌ Could not find the fallback block in scraper_tools.py.")

def exorcise_aggressive_ghost():
    """A more aggressive sweep for the Notebooks/assets hardcoded string."""
    f = Path("imports/voice_synthesis.py")
    if not f.exists():
        print(f"⚠️ {f} not found. Skipping.")
        return

    txt = f.read_text(encoding="utf-8")
    old_txt = txt

    # Aggressively replace any string literal containing Notebooks/assets
    # We replace it with str(wand.paths.data / "voices") to ensure string concatenation doesn't break
    txt = re.sub(r'["\']Notebooks/assets/[^"\']*["\']', r'str(wand.paths.data / "voices")', txt)
    txt = re.sub(r'["\']assets/[^"\']*["\']', r'str(wand.paths.data / "voices")', txt)

    if txt != old_txt:
        # Ensure wand is imported if we just injected it
        if "from pipulate import wand" not in txt:
            txt = "from pipulate import wand\n" + txt
        f.write_text(txt, encoding="utf-8")
        print("✅ imports/voice_synthesis.py: Aggressive exorcism complete. Ghost banished to wand.paths.data!")
    else:
        print("⏭️  imports/voice_synthesis.py: Still couldn't find the raw assets string. We may need to manually grep it.")

if __name__ == "__main__":
    print("🔨 Initiating Chisel Strike 2...")
    patch_blown_fuse()
    exorcise_aggressive_ghost()
    print("🏁 Strike complete.")