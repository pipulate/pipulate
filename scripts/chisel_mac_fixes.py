import re
from pathlib import Path

def patch_scraper_tools():
    """Implements Graceful Degradation for undetected_chromedriver version drift."""
    f = Path("tools/scraper_tools.py")
    txt = f.read_text(encoding="utf-8")

    # The exact block we want to replace
    old_init = """        driver = uc.Chrome(options=options, 
                           user_data_dir=str(profile_path), 
                           browser_executable_path=browser_path,
                           driver_executable_path=driver_path)"""

    # The self-healing block
    new_init = """        try:
            driver = uc.Chrome(options=options, 
                               user_data_dir=str(profile_path), 
                               browser_executable_path=browser_path,
                               driver_executable_path=driver_path)
        except Exception as e:
            error_msg = str(e)
            if "Current browser version is" in error_msg:
                import re
                match = re.search(r'Current browser version is (\d+)', error_msg)
                if match:
                    fallback_version = int(match.group(1))
                    logger.warning(f"⚠️ Chrome version mismatch detected. Auto-healing with version_main={fallback_version}")
                    driver = uc.Chrome(options=options, 
                                       user_data_dir=str(profile_path), 
                                       browser_executable_path=browser_path,
                                       driver_executable_path=driver_path,
                                       version_main=fallback_version)
                else:
                    raise
            else:
                raise"""

    if old_init in txt:
        txt = txt.replace(old_init, new_init)
        f.write_text(txt, encoding="utf-8")
        print("✅ tools/scraper_tools.py: Antifragile Chrome initialization injected!")
    elif "fallback_version" in txt:
        print("⏭️  tools/scraper_tools.py already patched.")
    else:
        print("❌ Could not find exact string match in scraper_tools.py. Check formatting.")

def patch_voice_synthesis():
    """Exorcises the 'assets' ghost from Piper TTS and binds it to the wand."""
    f = Path("imports/voice_synthesis.py")
    if not f.exists():
        print(f"⚠️ {f} not found. Skipping.")
        return

    txt = f.read_text(encoding="utf-8")

    # 1. Ensure wand is imported so we can use its manifold
    if "from pipulate import wand" not in txt:
        # Insert after the first batch of imports
        txt = re.sub(
            r'^(import os\n.*?)(?=\nclass|\ndef )', 
            r'\1\nfrom pipulate import wand\n', 
            txt, 
            count=1, 
            flags=re.DOTALL | re.MULTILINE
        )

    # 2. Find any hardcoded Path containing "assets" and route it to the wand's data dir
    # This targets things like Path("Notebooks/assets/models") or Path("assets/voices")
    old_txt = txt
    txt = re.sub(
        r'Path\([^)]*[\'"](?:Notebooks/)?assets.*?[\'"][^)]*\)', 
        r'(wand.paths.data / "voices")', 
        txt
    )

    if txt != old_txt:
        f.write_text(txt, encoding="utf-8")
        print("✅ imports/voice_synthesis.py: Piper TTS ghost exorcised and bound to the wand!")
    else:
        print("⏭️  imports/voice_synthesis.py: No 'assets' paths found to patch.")

if __name__ == "__main__":
    print("🔨 Initiating Chisel Strike...")
    patch_scraper_tools()
    patch_voice_synthesis()
    print("🏁 Strike complete.")