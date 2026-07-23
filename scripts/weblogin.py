#!/usr/bin/env python3
"""
weblogin.py — Log into a site by hand once so later scrapes stay signed in.

Opens a VISIBLE Chrome on the house persistent profile — the SAME profile
tools/scraper_tools.py uses for persistent=True, profile_name="default"
(data/uc_profiles/<profile>) — navigates to the given site, and waits for
the human to close the window. Whatever session cookies accumulate persist
in that profile, so subsequent scrapes with persistent=True inherit the login.

Usage:
    weblogin botify.com
    weblogin https://app.example.com/login
    weblogin --profile client_x botify.com
"""
import os
import sys
import time
import shutil
import argparse
import platform
from pathlib import Path
from urllib.parse import urlparse

import undetected_chromedriver as uc

# Anchor the profile to the repo root so weblogin writes the SAME directory
# scraper_tools.py reads, regardless of the shell's CWD. scraper_tools uses a
# CWD-relative 'data/uc_profiles/<name>' and the server/scraper run from the
# repo root, so these resolve to one location. Keep this path in sync with
# scraper_tools.py's persistent-profile line.
REPO_ROOT = Path(os.environ.get("PIPULATE_ROOT") or Path(__file__).resolve().parent.parent)


def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    return raw


def resolve_browser_and_driver():
    """Mirror scraper_tools.py's resolution so weblogin and the scraper share
    one driver stack (and therefore one on-disk profile format)."""
    effective_os = os.environ.get("EFFECTIVE_OS") or platform.system().lower()
    if effective_os == "linux":
        browser_path = shutil.which("chromium") or shutil.which("chromium-browser")
        # scraper_tools resolves the Nix driver as 'undetected-chromedriver'
        # (hyphen); alternates kept as harmless fallbacks.
        driver_path = (
            shutil.which("undetected-chromedriver")
            or shutil.which("chromedriver")
            or shutil.which("undetected_chromedriver")
        )
        if not browser_path:
            sys.exit("weblogin: chromium not found on PATH -- enter the Nix shell first.")
        if not driver_path:
            sys.exit("weblogin: no Nix chromedriver on PATH -- check flake.nix commonPackages.")
        return browser_path, driver_path
    if effective_os == "darwin":
        for candidate in (
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
        ):
            if Path(candidate).exists():
                return candidate, None  # None -> uc/webdriver-manager resolves the driver
        sys.exit("weblogin: Google Chrome not found on macOS.")
    sys.exit(f"weblogin: unsupported EFFECTIVE_OS: {effective_os!r}")


def build_options():
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--start-maximized")
    return options


def launch(profile_path, browser_path, driver_path):
    """Launch uc.Chrome, auto-healing a browser/driver version mismatch once
    (the same failure scraper_tools.py already handles on drifted pins)."""
    try:
        return uc.Chrome(
            options=build_options(),
            user_data_dir=str(profile_path),
            browser_executable_path=browser_path,
            driver_executable_path=driver_path,
        )
    except Exception as e:
        import re
        match = re.search(r"Current browser version is (\d+)", str(e))
        if not match:
            raise
        version_main = int(match.group(1))
        print(f"weblogin: version mismatch; retrying with version_main={version_main}")
        return uc.Chrome(
            options=build_options(),  # uc consumes options; forge a fresh one
            user_data_dir=str(profile_path),
            browser_executable_path=browser_path,
            driver_executable_path=driver_path,
            version_main=version_main,
        )


def main():
    parser = argparse.ArgumentParser(description="Warm a persistent browser login session.")
    parser.add_argument("site", help="Apex domain or full URL, e.g. botify.com")
    parser.add_argument("--profile", default="default",
                        help="Persistent profile name (default: default -- the house scrape profile)")
    args = parser.parse_args()

    url = normalize_url(args.site)
    domain = urlparse(url).netloc
    profile_path = REPO_ROOT / "data" / "uc_profiles" / args.profile
    profile_path.mkdir(parents=True, exist_ok=True)

    browser_path, driver_path = resolve_browser_and_driver()

    print(f"weblogin: opening {url}")
    print(f"  Profile: {profile_path}")
    print("  Log in, then simply CLOSE the browser window when you're done.")

    driver = launch(profile_path, browser_path, driver_path)
    try:
        driver.get(url)
        # Poll until the human closes the window. window_handles raises once
        # the session is gone, which is our "user closed it" signal.
        while True:
            time.sleep(1)
            try:
                if not driver.window_handles:
                    break
            except Exception:
                break
    except KeyboardInterrupt:
        print("\nweblogin: interrupted.")
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    print(f"weblogin: persistent login preserved for {domain} in {profile_path}")
    print("weblogin: sites expire sessions over time -- re-run weblogin if scrapes hit login walls.")
    print("weblogin: close this browser before running a scrape (Chrome locks the profile).")


if __name__ == "__main__":
    main()
