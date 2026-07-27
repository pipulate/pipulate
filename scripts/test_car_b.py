import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from tools.scraper_tools import (
    get_safe_path_component,
    guided_browser_capture,
)

url = os.environ.get("START_URL", "https://app.botify.com/")
domain, url_path_slug = get_safe_path_component(url)

params = {
    "url": url,
    "domain": domain,
    "url_path_slug": url_path_slug,
    "take_screenshot": False,
    "headless": False,
    "is_notebook_context": False,
    "persistent": True,
    "profile_name": "default",
    "verbose": True,
    "override_cache": True,
    "delay_range": None,
}

result = asyncio.run(guided_browser_capture(params))

receipt = {
    "receipt_version": 1,
    "captured_at_utc": datetime.now(timezone.utc).isoformat(),
    "result": result,
}

receipt_path = Path("/tmp/pipulate-car-b-receipt.json")
receipt_path.write_text(
    json.dumps(receipt, indent=2) + "\n",
    encoding="utf-8",
)

print(json.dumps(receipt, indent=2))
print(f"\nCar B receipt written to: {receipt_path}")

sys.exit(0 if result.get("success") else 2)
