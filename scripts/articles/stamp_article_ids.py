#!/usr/bin/env python3
"""
stamp_article_ids.py

Idempotent, self-healing monotonic `article_id` stamper for Jekyll `_posts/`.
- Existing unique positive integer `article_id` values are NEVER renumbered,
  so moving or deleting a historical post never shifts downstream IDs.
- Unstamped posts are sorted deterministically by `(YYYY-MM-DD, sort_order, filename)`
  and assigned `high_water + 1 .. high_water + K`.
- Duplicate `article_id` claims (e.g., copied draft templates) fail closed by
  default unless `--heal-duplicates` reassigns newer copies.
- Uses `common.stamp_frontmatter_value(..., preserve_mtime=True)` so only one
  YAML line changes and mtime-sensitive adapters (`googledocizer.py`) stay calm.
"""

import argparse
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

_DATED_MD_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-.+\.(?:md|markdown)$")
_AID_LINE_RE = re.compile(rf"^{re.escape(common.ARTICLE_ID_KEY)}\s*:\s*(.*?)\s*$")
_SORT_LINE_RE = re.compile(r"^\s*sort_order\s*:\s*['\"]?(-?\d+)['\"]?\s*(?:#.*)?$")


def _is_valid_dated_post(path: Path) -> str | None:
    if not path.is_file():
        return None
    m = _DATED_MD_RE.match(path.name)
    if not m:
        return None
    date_s = m.group(1)
    try:
        datetime.strptime(date_s, "%Y-%m-%d")
    except ValueError:
        return None
    return date_s


def scan_target_posts(posts_dir: Path) -> list[dict]:
    """Scan dated posts in posts_dir reading only the leading YAML frontmatter block."""
    posts_path = Path(posts_dir).expanduser().resolve()
    if not posts_path.is_dir():
        return []
    rows = []
    for name in sorted(os.listdir(posts_path)):
        p = posts_path / name
        date_s = _is_valid_dated_post(p)
        if not date_s:
            continue
        has_fm = False
        aid_val = None
        invalid_aid = None
        sort_order = 0
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                first = f.readline()
                if first.strip() == "---":
                    for line in f:
                        if line.strip() == "---":
                            has_fm = True
                            break
                        clean = line.rstrip("\r\n")
                        m_aid = _AID_LINE_RE.match(clean)
                        if m_aid and aid_val is None and invalid_aid is None:
                            raw_v = m_aid.group(1).split("#", 1)[0].strip().strip("'\"")
                            if re.fullmatch(r"[1-9]\d*", raw_v):
                                aid_val = int(raw_v)
                            else:
                                invalid_aid = raw_v or "<empty>"
                        m_so = _SORT_LINE_RE.match(clean)
                        if m_so:
                            sort_order = int(m_so.group(1))
        except OSError:
            has_fm = False
        rows.append({
            "path": p,
            "filename": name,
            "date": date_s,
            "sort_order": sort_order,
            "has_frontmatter": has_fm,
            "article_id": aid_val,
            "invalid_aid": invalid_aid,
        })
    rows.sort(key=lambda r: (r["date"], r["sort_order"], r["filename"]))
    return rows


def plan_article_ids(posts_dir: Path, heal_duplicates: bool = False) -> dict:
    """Compute a read-only monotonic stamping plan for posts_dir."""
    rows = scan_target_posts(posts_dir)
    day_order_counts = Counter((r["date"], r["sort_order"]) for r in rows)
    same_day_ties = sum(1 for c in day_order_counts.values() if c > 1)
    no_frontmatter = [r["path"] for r in rows if not r["has_frontmatter"]]
    invalid_ids = [(r["path"], r["invalid_aid"]) for r in rows if r["invalid_aid"] is not None]

    by_id: dict[int, list[dict]] = {}
    unstamped: list[dict] = []
    for r in rows:
        if not r["has_frontmatter"] or r["invalid_aid"] is not None:
            continue
        if r["article_id"] is not None:
            by_id.setdefault(r["article_id"], []).append(r)
        else:
            unstamped.append(r)

    kept_ids: set[int] = set()
    duplicates: dict[int, list[Path]] = {}
    healed_queue: list[dict] = []
    for aid, claimants in sorted(by_id.items()):
        kept_ids.add(aid)
        if len(claimants) > 1:
            if heal_duplicates:
                healed_queue.extend(claimants[1:])
            else:
                duplicates[aid] = [c["path"] for c in claimants]

    high_water = max(kept_ids, default=0)
    gaps = [i for i in range(1, high_water + 1) if i not in kept_ids]
    to_assign = sorted(
        [(r, "NEW") for r in unstamped] + [(r, "HEAL_DUP") for r in healed_queue],
        key=lambda item: (item[0]["date"], item[0]["sort_order"], item[0]["filename"]),
    )
    assignments = [
        (high_water + offset, item["path"], reason)
        for offset, (item, reason) in enumerate(to_assign, start=1)
    ]
    return {
        "posts_dir": str(Path(posts_dir).expanduser().resolve()),
        "total_posts": len(rows),
        "already_stamped": len(kept_ids),
        "unstamped_count": len(unstamped),
        "healed_duplicates": len(healed_queue),
        "high_water": high_water,
        "next_high_water": high_water + len(assignments),
        "gaps": gaps,
        "same_day_ties": same_day_ties,
        "no_frontmatter": no_frontmatter,
        "invalid_ids": invalid_ids,
        "duplicates": duplicates,
        "assignments": assignments,
    }


def apply_article_id_plan(
    posts_dir: Path,
    heal_duplicates: bool = False,
    preserve_mtime: bool = True,
) -> dict:
    """Execute monotonic article_id stamping if all preflight invariants hold."""
    plan = plan_article_ids(posts_dir, heal_duplicates=heal_duplicates)
    if plan["no_frontmatter"]:
        return {**plan, "ok": False, "error": "NO_FRONTMATTER", "stamped": 0, "unchanged_writes": 0}
    if plan["invalid_ids"]:
        return {**plan, "ok": False, "error": "INVALID_IDS", "stamped": 0, "unchanged_writes": 0}
    if plan["duplicates"]:
        return {**plan, "ok": False, "error": "DUPLICATE_IDS", "stamped": 0, "unchanged_writes": 0}

    stamped = 0
    unchanged_writes = 0
    for new_id, md_path, _ in plan["assignments"]:
        verdict = common.stamp_frontmatter_value(
            md_path,
            common.ARTICLE_ID_KEY,
            str(new_id),
            preserve_mtime=preserve_mtime,
        )
        if verdict in ("ADDED", "UPDATED"):
            stamped += 1
        else:
            unchanged_writes += 1
    return {
        **plan,
        "ok": True,
        "error": None,
        "stamped": stamped,
        "unchanged_writes": unchanged_writes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit or stamp permanent monotonic `article_id` values in Jekyll `_posts/`."
    )
    common.add_standard_arguments(parser)
    parser.add_argument("--posts-dir", type=str, default=None, help="Explicit `_posts` directory override.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Read-only audit and assignment preview (default).")
    mode.add_argument("--check", action="store_true", help="Exit 0 iff every dated post has a valid unique article_id.")
    mode.add_argument("--apply", action="store_true", help="Surgically stamp missing article_id values in place.")
    parser.add_argument(
        "--heal-duplicates",
        action="store_true",
        help="Keep oldest claimant on duplicate article_id values and reassign newer copies.",
    )
    parser.add_argument(
        "--touch-mtime",
        action="store_true",
        help="Update file mtime instead of preserving mtime on stamped posts.",
    )
    args = parser.parse_args(argv)
    posts_dir = Path(args.posts_dir).expanduser() if args.posts_dir else common.get_target_path(args)

    if args.apply:
        res = apply_article_id_plan(
            posts_dir,
            heal_duplicates=args.heal_duplicates,
            preserve_mtime=not args.touch_mtime,
        )
        if not res["ok"]:
            print(f"❌ Refused to stamp {res['posts_dir']} ({res['error']}):")
            for p in res["no_frontmatter"][:5]:
                print(f"   • Missing frontmatter: {p.name}")
            for p, raw in res["invalid_ids"][:5]:
                print(f"   • Invalid {common.ARTICLE_ID_KEY}={raw!r}: {p.name}")
            for aid, paths in list(res["duplicates"].items())[:5]:
                joined = ", ".join(x.name for x in paths)
                print(f"   • Duplicate {common.ARTICLE_ID_KEY}={aid}: {joined} (pass --heal-duplicates to reassign newer copy)")
            return 1
        if res["stamped"] == 0:
            print(
                f"✅ Article IDs verified ({res['total_posts']} posts, max #{res['next_high_water']}, "
                f"gaps={len(res['gaps'])}, 0 changes needed)."
            )
        else:
            first_id, first_p, _ = res["assignments"][0]
            last_id, last_p, _ = res["assignments"][-1]
            print(
                f"🔢 Stamped {common.ARTICLE_ID_KEY} on {res['stamped']} post(s) "
                f"(#{first_id} {first_p.name} .. #{last_id} {last_p.name}; "
                f"{res['already_stamped']} existing untouched)."
            )
        return 0

    plan = plan_article_ids(posts_dir, heal_duplicates=args.heal_duplicates)
    mode_lbl = "CHECK" if args.check else "DRY RUN"
    print(
        f"🔢 Article ID Audit [{mode_lbl}] ({plan['posts_dir']}): "
        f"total={plan['total_posts']} | stamped={plan['already_stamped']} | "
        f"unstamped={plan['unstamped_count']} | max=#{plan['high_water']} -> #{plan['next_high_water']} | "
        f"gaps={len(plan['gaps'])} | same_day_ties={plan['same_day_ties']} | "
        f"dupes={len(plan['duplicates'])} | no_fm={len(plan['no_frontmatter'])}"
    )
    if plan["assignments"]:
        head = plan["assignments"][:3]
        tail = plan["assignments"][-3:] if len(plan["assignments"]) > 3 else []
        for aid, p, reason in head:
            print(f"   + #{aid:4d} [{reason}] {p.name}")
        if len(plan["assignments"]) > 6:
            print(f"   ... ({len(plan['assignments']) - 6} middle assignment(s)) ...")
        for aid, p, reason in tail:
            if (aid, p, reason) not in head:
                print(f"   + #{aid:4d} [{reason}] {p.name}")
    if args.check:
        clean = (
            plan["unstamped_count"] == 0
            and not plan["duplicates"]
            and not plan["invalid_ids"]
            and not plan["no_frontmatter"]
        )
        return 0 if clean else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
