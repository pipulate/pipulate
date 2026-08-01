#!/usr/bin/env python3
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import prompt_foo
import walk


class MotherCatRep2Tests(unittest.TestCase):
    def test_pageworkers_trail_satisfies_strict_car_a_schema(self):
        trail_path = REPO_ROOT / "assets" / "trails" / "botify_pageworkers.yaml"
        trail = walk.load_trail(trail_path)

        self.assertEqual(trail["schema_version"], 1)
        self.assertEqual(trail["name"], "botify_pageworkers")
        self.assertEqual(
            [stop["url_env"] for stop in trail["stops"]],
            [
                "PIPULATE_TRAIL_BOTIFY_OPTIMIZATION_URL",
                "PIPULATE_TRAIL_BOTIFY_MONITORING_URL",
                "PIPULATE_TRAIL_BOTIFY_REPORTING_URL",
            ],
        )
        self.assertEqual(
            {
                "headless": trail["defaults"]["headless"],
                "persistent": trail["defaults"]["persistent"],
                "override_cache": trail["defaults"]["override_cache"],
                "is_notebook_context": trail["defaults"]["is_notebook_context"],
                "profile_name": trail["defaults"]["profile_name"],
            },
            {
                "headless": False,
                "persistent": True,
                "override_cache": True,
                "is_notebook_context": False,
                "profile_name": "botify",
            },
        )

    def test_resolver_matches_requested_and_final_guided_urls(self):
        requested_url = "https://app.example.com/project/page?analysis=1"
        final_url = requested_url + "&context=24h"

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            cache_dir = (
                root
                / "browser_cache"
                / "looking_at"
                / "app.example.com"
                / "%2Fproject%2Fpage--0123456789abcdef"
            )
            cache_dir.mkdir(parents=True)
            (cache_dir / "headers.json").write_text(
                json.dumps({
                    "url": requested_url,
                    "final_url": final_url,
                    "source_provenance": "wire",
                }),
                encoding="utf-8",
            )
            (cache_dir / "source.html").write_text(
                "<html>wire source</html>",
                encoding="utf-8",
            )
            (cache_dir / "hydrated_dom.html").write_text(
                "<html>hydrated</html>",
                encoding="utf-8",
            )
            (cache_dir / "network_log.jsonl").write_text(
                '{"method":"Network.requestWillBeSent"}\n',
                encoding="utf-8",
            )
            (cache_dir / "seo.md").write_text(
                "# Captured page",
                encoding="utf-8",
            )

            with patch.object(prompt_foo, "REPO_ROOT", str(root)):
                requested_result = prompt_foo.resolve_prompt_foo_cache(
                    requested_url
                )
                final_result = prompt_foo.resolve_prompt_foo_cache(final_url)

            self.assertTrue(requested_result["guided"])
            self.assertTrue(final_result["guided"])
            self.assertEqual(
                Path(requested_result["cache_dir"]),
                cache_dir,
            )
            self.assertEqual(
                Path(final_result["cache_dir"]),
                cache_dir,
            )
            self.assertEqual(
                requested_result["artifacts"]["network_log"],
                str(cache_dir / "network_log.jsonl"),
            )
            self.assertEqual(
                requested_result["final_url"],
                final_url,
            )

    def test_resolver_falls_back_to_legacy_prompt_foo_cache(self):
        target_url = "https://example.com/a/b?variant=1"

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch.object(prompt_foo, "REPO_ROOT", str(root)):
                result = prompt_foo.resolve_prompt_foo_cache(target_url)

            self.assertFalse(result["guided"])
            self.assertEqual(
                Path(result["cache_dir"]),
                root / "browser_cache" / "example.com" / "%2Fa%2Fb",
            )
            self.assertEqual(result["domain"], "example.com")


    def test_guided_capture_refuses_an_explicit_non_tty_stream(self):
        # PINS THE IDENTITY GUARD in guided_browser_capture's pre-launch gate.
        # The gate prefers /dev/tty when it was handed the REAL sys.stdin, so a
        # piped `curl | bash` can still reach a human at the CAPTURE prompt. An
        # EXPLICIT stream -- this one -- must NEVER get that second look: if it
        # did, this test on a developer's terminal would sail past the gate and
        # then block forever waiting for someone to type CAPTURE. Refusal here
        # is the entire contract, and it must hold in every lane.
        # Imports are function-local on purpose: the browser stack (selenium,
        # undetected-chromedriver, loguru) stays out of the import path for the
        # schema and resolver tests, which are pure and should stay cheap.
        import asyncio
        import io
        from tools.scraper_tools import guided_browser_capture
        result = asyncio.run(
            guided_browser_capture(
                {
                    "headless": False,
                    "persistent": True,
                    "override_cache": True,
                },
                stdin=io.StringIO(),
            )
        )
        self.assertFalse(result["success"])
        self.assertIn("TTY on stdin before browser launch", result["error"])
        self.assertEqual(result["looking_at_files"], {})
if __name__ == "__main__":
    unittest.main()
