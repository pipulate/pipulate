#!/usr/bin/env python3
"""
Regression tests for apply.py's autolink contamination airlock.

Verifies that self-referential markdown autolinks -- the shape a chat renderer
produces from a bare www-prefixed host between the compiler and the model --
are refused before disk mutation on non-.md targets, while the deliberate .md
exemption is preserved.

Every forbidden signature is assembled at runtime from fragments so this file
never contains the literal shape apply.py refuses. Otherwise the patch that
creates this file would be refused by the very airlock it tests.
"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import apply


def _make_autolink_www(domain="probe.invalid", scheme="https"):
    prefix = "www."
    host = prefix + domain
    return f"[{host}]({scheme}://{host})"


def _make_autolink_scheme(domain="probe.invalid", scheme="https"):
    url = f"{scheme}://{domain}"
    return f"[{url}]({url})"


def _build_search_replace_payload(target, search, replace):
    s_tag = "[" * 3 + "SEARCH" + "]" * 3
    d_tag = "[" * 3 + "DIVIDER" + "]" * 3
    r_tag = "[" * 3 + "REPLACE" + "]" * 3
    return f"Target: {target}\n{s_tag}\n{search}\n{d_tag}\n{replace}\n{r_tag}\n"


def _build_write_file_payload(target, content):
    w_tag = "[" * 3 + "WRITE_FILE" + "]" * 3
    e_tag = "[" * 3 + "END_WRITE_FILE" + "]" * 3
    return f"Target: {target}\n{w_tag}\n{content}\n{e_tag}\n"


class TestApplyAutolinkAirlock(unittest.TestCase):
    def _apply(self, payload):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return apply.apply_search_replace_patch(payload)

    def test_ordinary_search_replace_succeeds(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "module.py"
            target.write_text("x = 1\n", encoding="utf-8")
            payload = _build_search_replace_payload(target, "x = 1", "x = 2")
            self.assertTrue(self._apply(payload))
            self.assertEqual(target.read_text(encoding="utf-8"), "x = 2\n")

    def test_contaminated_search_replace_refuses_and_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "module.py"
            target.write_text("y = 3\n", encoding="utf-8")
            bad_link = _make_autolink_www("airlock-test.invalid")
            payload = _build_search_replace_payload(
                target, "y = 3", f"# {bad_link}\ny = 4"
            )
            self.assertFalse(self._apply(payload))
            self.assertEqual(target.read_text(encoding="utf-8"), "y = 3\n")

    def test_clean_write_file_creation_succeeds(self):
        # POSITIVE CONTROL for the WRITE_FILE lane. Without it, the two
        # contaminated-WRITE_FILE tests below go green both when the airlock
        # refuses AND when WRITE_FILE parsing silently breaks -- the
        # no-blocks-found path also returns False and writes nothing. This
        # test fails independently if the WRITE_FILE lane stops parsing, which
        # is what lets the refusals below indict the airlock rather than a
        # parse miss. Sibling of the constitution's SUCCESS-ONLY WITNESS: the
        # WRITE_FILE success branch was otherwise unobserved.
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "fresh_module.py"
            payload = _build_write_file_payload(target, "created = True\n")
            self.assertTrue(self._apply(payload))
            self.assertTrue(target.exists())
            self.assertEqual(target.read_text(encoding="utf-8"), "created = True\n")

    def test_contaminated_write_file_creation_refuses_and_creates_no_target(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "new_module.py"
            bad_link = _make_autolink_www("airlock-create.invalid")
            payload = _build_write_file_payload(target, f"# {bad_link}\nz = 10\n")
            self.assertFalse(self._apply(payload))
            self.assertFalse(target.exists())

    def test_contaminated_write_file_overwrite_refuses_and_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "existing_module.py"
            target.write_text("status = 'unmodified'\n", encoding="utf-8")
            bad_link = _make_autolink_www("airlock-overwrite.invalid")
            payload = _build_write_file_payload(
                target, f"# {bad_link}\nstatus = 'corrupted'\n"
            )
            self.assertFalse(self._apply(payload))
            self.assertEqual(
                target.read_text(encoding="utf-8"), "status = 'unmodified'\n"
            )

    def test_both_regex_alternatives_are_refused(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target_www = Path(temp_dir) / "alt_www.py"
            target_www.write_text("val = 100\n", encoding="utf-8")
            link_www = _make_autolink_www("branch-one.invalid")
            payload_www = _build_search_replace_payload(
                target_www, "val = 100", f"# {link_www}\nval = 101"
            )

            target_scheme = Path(temp_dir) / "alt_scheme.py"
            target_scheme.write_text("val = 200\n", encoding="utf-8")
            link_scheme = _make_autolink_scheme("branch-two.invalid")
            payload_scheme = _build_search_replace_payload(
                target_scheme, "val = 200", f"# {link_scheme}\nval = 201"
            )

            self.assertFalse(self._apply(payload_www))
            self.assertFalse(self._apply(payload_scheme))
            self.assertEqual(target_www.read_text(encoding="utf-8"), "val = 100\n")
            self.assertEqual(target_scheme.read_text(encoding="utf-8"), "val = 200\n")

    def test_markdown_files_are_deliberately_exempt(self):
        # The .md exemption is intentional: self-referential markdown links are
        # legitimate in articles and documentation, so a blanket refusal there
        # would make normal .md files uneditable. A green here requires the
        # airlock to SKIP the check for .md, so the exemption is witnessed, not
        # merely assumed.
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "document.md"
            target.write_text("# Documentation\n\nOriginal draft.\n", encoding="utf-8")
            link_md = _make_autolink_www("doc-reference.invalid")
            payload = _build_search_replace_payload(
                target, "Original draft.", f"Updated draft with reference: {link_md}"
            )
            self.assertTrue(self._apply(payload))
            self.assertIn(link_md, target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
