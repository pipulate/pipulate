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

# prompt_foo is imported inside the two resolver tests (2026-10-04), so the
# trail tests below load neither the compiler nor the browser stack.
import walk


class MotherCatRep2Tests(unittest.TestCase):
    def test_public_walk_yaml_is_the_default_trail(self):
        # THREE WALKS (2026-10-04): the PageWorkers trail this test once read
        # was purged with five others; it pinned a trail's shape, never the
        # Rep 2 witness. The bundled trail is public_walk, YAML since that day.
        # Its JSON twin stays out of this test, so removing the twin moves no line.
        self.assertEqual(walk.DEFAULT_TRAIL.name, "public_walk.yaml")
        trail = walk.load_trail(walk.DEFAULT_TRAIL)

        self.assertEqual(trail["schema_version"], 1)
        self.assertEqual(trail["name"], "public_walk")
        self.assertEqual(
            [stop["name"] for stop in trail["stops"]],
            ["the_word", "the_receipt", "the_two_pages"],
        )
        self.assertNotIn("introduction", trail)
        self.assertEqual(
            {
                "headless": trail["defaults"]["headless"],
                "persistent": trail["defaults"]["persistent"],
                "override_cache": trail["defaults"]["override_cache"],
                "profile_name": trail["defaults"]["profile_name"],
            },
            {
                "headless": False,
                "persistent": True,
                "override_cache": True,
                "profile_name": "default",
            },
        )

    def test_introduction_is_optional_and_shares_the_walk_namespace(self):
        # THE INTRODUCTION IS SKIPPED BY DEFAULT (2026-10-04): an optional list
        # of stops, validated like the walk's own; a name is unique across both
        # lists, because both land in one capture archive.
        import yaml

        raw = yaml.safe_load(walk.DEFAULT_TRAIL.read_text(encoding="utf-8"))
        first = raw["stops"][0]
        fresh = dict(first, name="first_look", target_slot="first_slot")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "intro.yaml"
            path.write_text(
                yaml.safe_dump(dict(raw, introduction=[fresh])), encoding="utf-8"
            )
            trail = walk.load_trail(path)
            self.assertEqual(
                [stop["name"] for stop in trail["introduction"]], ["first_look"]
            )
            self.assertEqual(len(trail["stops"]), 3)
            path.write_text(
                yaml.safe_dump(dict(raw, introduction=[first])), encoding="utf-8"
            )
            with self.assertRaisesRegex(walk.TrailError, "must be unique"):
                walk.load_trail(path)

    def test_resolver_matches_requested_and_final_guided_urls(self):
        import prompt_foo

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
        import prompt_foo

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
