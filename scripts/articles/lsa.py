#!/usr/bin/env python3
"""
lsa.py (List All Articles)

A unified utility merging the fast-streaming, copy-paste-friendly output of ls2.py
with the deep structural sort_order analysis of list_articles.py.
Dynamically routed via targets.json.
"""

import os
import sys
import yaml
import json
import argparse
import shutil
from datetime import datetime
from collections import defaultdict
from pathlib import Path

# Gracefully handle tiktoken — LAZILY (banked 2026-07-19). The import is
# deferred into the first count_tokens() call, so warm all-hit runs (where
# the fm and token memo tables answer everything) never reach it at all.
# The import cost isn't reduced; it's made UNREACHABLE on the hot path.
# Graceful degradation preserved: unavailable -> whitespace word count.
_TIKTOKEN = None  # None = not yet attempted; False = attempted, unavailable

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    global _TIKTOKEN
    if _TIKTOKEN is None:
        try:
            import tiktoken as _tk
            _TIKTOKEN = _tk
        except ImportError:
            _TIKTOKEN = False
    if _TIKTOKEN:
        try:
            encoding = _TIKTOKEN.encoding_for_model(model)
            return len(encoding.encode(text))
        except Exception:
            return len(text.split())
    return len(text.split())

# Gracefully handle rich for the gaps report
try:
    from rich.console import Console
    from rich.table import Table
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

CONFIG_DIR = Path.home() / ".config" / "pipulate"
TARGETS_FILE = CONFIG_DIR / "blogs.json"

DEFAULT_TARGETS = {
    "1": {
        "name": "Local Project (Default)",
        "path": "./_posts"
    }
}

class MtimeMemo:
    """THE SENTINEL CACHE, UNIFIED (DRY car, banked 2026-07-19).

    Filesystem-as-hash-table memo: {path: [mtime, *values]} in one JSON
    file, invalidated per-entry on mtime change. A thin wrapper over the
    EXACT on-disk shape both existing caches already use (json.dump,
    indent=2), so adopting it invalidates nothing. Load fails soft to
    empty; save is a no-op unless at least one entry missed — a warm
    run never touches the file, which is the format-stability proof.
    Validity policies (e.g. the token cache's anti-swallow guard) stay
    at call sites: this class does mechanics, not judgment.
    """

    def __init__(self, cache_file):
        self.cache_file = cache_file
        self.table = {}
        self.updated = False
        self.hits = 0
        self.misses = 0
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as cf:
                    self.table = json.load(cf)
            except Exception:
                self.table = {}

    def lookup(self, path, mtime):
        """Return cached values (list, mtime stripped) or None on staleness."""
        entry = self.table.get(path)
        if entry and entry[0] == mtime:
            self.hits += 1
            return entry[1:]
        self.misses += 1
        return None

    def store(self, path, mtime, values):
        self.table[path] = [mtime] + list(values)
        self.updated = True

    def save(self):
        if not self.updated:
            return
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as cf:
                json.dump(self.table, cf, indent=2)
        except Exception:
            pass

def load_targets():
    if TARGETS_FILE.exists():
        try:
            with open(TARGETS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ Warning: {TARGETS_FILE} is corrupt. Using defaults.", file=sys.stderr)
    return DEFAULT_TARGETS

def fast_get_sort_order(filepath):
    """Reads only the YAML frontmatter to extract sort_order extremely fast."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            first_line = f.readline()
            if not first_line.startswith('---'):
                return 0, ''
            
            yaml_content = []
            for line in f:
                if line.startswith('---'):
                    break
                yaml_content.append(line)
                
            fm = yaml.safe_load(''.join(yaml_content)) or {}
            return int(fm.get('sort_order', 0)), (fm.get('permalink') or '')
    except Exception:
        return 0, ''

def analyze_sort_order_contiguity(metadata):
    """Analyzes sort_order for gaps, duplicates, and late starts."""
    anomalies = []
    posts_by_day = defaultdict(list)

    for item in metadata:
        posts_by_day[item['date']].append(item['sort_order'])

    for date, orders in sorted(posts_by_day.items()):
        unique_orders = sorted(list(set(orders)))

        # Duplicates
        if len(orders) != len(unique_orders):
            dupes = sorted([o for o in unique_orders if orders.count(o) > 1])
            anomalies.append({
                "date": date, "type": "Duplicate",
                "details": f"Duplicate value(s): {dupes}", "sequence": str(orders)
            })

        # Starts Late
        if unique_orders and unique_orders[0] != 1:
            anomalies.append({
                "date": date, "type": "Starts Late",
                "details": f"Sequence starts at {unique_orders[0]} instead of 1.", "sequence": str(orders)
            })

        # Gaps
        if unique_orders:
            expected_sequence = set(range(1, unique_orders[-1] + 1))
            gaps = sorted(list(expected_sequence - set(unique_orders)))
            if gaps:
                anomalies.append({
                    "date": date, "type": "Gap",
                    "details": f"Missing value(s): {gaps}", "sequence": str(orders)
                })

    return anomalies

def print_contiguity_report(anomalies):
    if not RICH_AVAILABLE:
        print("\n=== Sort Order Contiguity Report ===")
        if not anomalies:
            print("✅ All Clear! Sort order is contiguous.")
            return
        for a in anomalies:
            print(f"[{a['date']}] {a['type']}: {a['details']} | Seq: {a['sequence']}")
        return

    console = Console()
    console.print("\n" + "="*50)
    console.print("[bold bright_blue]Sort Order Contiguity Report[/bold bright_blue]")
    console.print("="*50)

    if not anomalies:
        console.print("✅ [bold green]All Clear![/bold green] Sort order is contiguous and correct for all days.")
        return

    table = Table(box=box.ROUNDED, show_lines=True)
    table.add_column("Date", style="magenta", justify="left")
    table.add_column("Anomaly Type", style="cyan", justify="left")
    table.add_column("Details", style="white", justify="left")
    table.add_column("Observed Sequence", style="yellow", justify="left")

    for a in anomalies:
        table.add_row(str(a["date"]), a["type"], a["details"], a["sequence"])
    console.print(table)


def parse_slice_arg(arg_str: str):
    """Parses a string like '[-5:]' into a valid Python slice object."""
    if not arg_str or not arg_str.startswith('[') or not arg_str.endswith(']'): return None
    content = arg_str[1:-1].strip()
    if ':' in content:
        parts = content.split(':', 1)
        start = int(parts[0].strip()) if parts[0].strip() else None
        end = int(parts[1].strip()) if parts[1].strip() else None
        return slice(start, end)
    elif content: return int(content)
    return slice(None, None)


def print_shard_header(filepath: str, prefix: str = "#   "):
    """Interleaves the holographic shard (keywords + summary) for a post.

    Looks for _context/<stem>.json beside the post. Degrades silently:
    missing shards produce no output and no error. Orphaned shards
    (shards whose post was renamed or deleted) are never looked up,
    so they cannot poison this path.
    """
    p = Path(filepath)
    json_path = p.parent / "_context" / f"{p.stem}.json"
    if not json_path.exists():
        return
    try:
        with open(json_path, 'r', encoding='utf-8') as jf:
            shard = json.load(jf)
    except Exception:
        return
    kw = ", ".join(shard.get('kw', []))
    summary = (shard.get('s') or '').replace('\n', ' ').strip()
    if kw:
        print(f"{prefix}kw: {kw}", flush=True)
    if summary:
        print(f"{prefix}sum: {summary}", flush=True)


def print_hit_regions(filepath: str, terms, around: int, max_regions: int = 5, prefix: str = "#   "):
    """Prints ±around lines of context for case-insensitive fixed-string hits.

    Overlapping windows are merged. Output is capped at max_regions per
    file to protect the token budget; a truncation note reports the rest.
    All output lines are prefixed as comments so downstream path-parsing
    consumers (e.g. --stdin round-trips) skip them cleanly.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.read().split('\n')
    except Exception:
        return
    needles = [t.lower() for t in terms if t]
    if not needles:
        return
    lowered = [ln.lower() for ln in lines]
    hits = [i for i, ln in enumerate(lowered) if any(n in ln for n in needles)]
    if not hits:
        return
    windows = []
    for i in hits:
        start, end = max(0, i - around), min(len(lines) - 1, i + around)
        if windows and start <= windows[-1][1] + 1:
            windows[-1][1] = max(windows[-1][1], end)
        else:
            windows.append([start, end])
    total = len(windows)
    for w_idx, (start, end) in enumerate(windows[:max_regions]):
        print(f"{prefix}-- region {w_idx + 1}/{total} (lines {start + 1}-{end + 1}) --", flush=True)
        for li in range(start, end + 1):
            print(f"{prefix}{li + 1:5d}: {lines[li]}", flush=True)
    if total > max_regions:
        print(f"{prefix}... {total - max_regions} more region(s) truncated", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Unified Article Lister & Analyzer")
    parser.add_argument('-t', '--target', type=str, help="Target ID from blogs.json (e.g., '1', '4')")
    parser.add_argument('-g', '--gaps', action='store_true', help="Run and display the sort_order contiguity gap report")
    parser.add_argument('-r', '--reverse', action='store_true', help="Reverse the sorting order")
    parser.add_argument('-a', '--article', type=str, help="Generate a prompt_foo.py command for a slice of articles (e.g., '[-5:]')")
    parser.add_argument('--top', type=int, default=None, metavar='N', help="Limit output to the first N results (after sorting)")
    parser.add_argument('--last', type=int, default=None, metavar='N', help="Keep only the N most recent articles (chronologically), preserving display order")
    parser.add_argument('--match', type=str, default=None, metavar='TERMS', help="Filter articles whose filename contains all whitespace-separated terms (case-insensitive)")
    parser.add_argument('--tokens-under', type=int, default=None, metavar='N', dest='tokens_under', help="Exclude articles with token count >= N (requires reading each file)")
    parser.add_argument('--fmt', type=str, default='full', choices=['full', 'paths', 'slugs', 'dated-slugs'], help="Output format: 'full' (default, with comments), 'paths' (bare absolute paths), or 'slugs' (concept slug only, no date prefix)")
    parser.add_argument('--slugs', nargs='+', default=None, metavar='SLUG', help="Select articles by exact slug match (space-separated, no date prefix needed)")
    parser.add_argument('--clear-cache', action='store_true', help="Purge the token cache file before processing")
    parser.add_argument('--stdin', action='store_true', help="Read file paths or filenames from standard input instead of scanning the directory")
    parser.add_argument('--shards', action='store_true', help="Interleave each article's holographic shard (keywords + summary) from _context/ beneath its listing line (full format only)")
    parser.add_argument('--around', type=int, default=None, metavar='N', help="With --terms, print ±N lines of context around each case-insensitive hit (full format only)")
    parser.add_argument('--terms', nargs='+', default=None, metavar='TERM', help="Search terms for --around hit-region extraction (case-insensitive fixed strings)")
    args = parser.parse_args()

    targets = load_targets()
    target_key = args.target

    if not target_key:
        print("\nSelect Target Repo for Listing:")
        for k, v in targets.items():
            print(f"  [{k}] {v['name']} ({v['path']})")
        target_key = input("Enter choice (default 1): ").strip() or "1"

    if target_key not in targets:
        print(f"❌ Invalid target key: {target_key}", file=sys.stderr)
        sys.exit(1)

    target_dir = Path(targets[target_key]['path']).expanduser().resolve()
    if not target_dir.is_dir():
        print(f"❌ Directory not found: {target_dir}", file=sys.stderr)
        sys.exit(1)

    # Determine the sort description based on the reverse flag
    sort_desc = "Newest First" if args.reverse else "Oldest First"
    
    # Suppress header for machine-readable output formats
    if args.fmt not in ('paths', 'slugs', 'dated-slugs'):
        print(f"# 🎯 Target: {targets[target_key]['name']} [{sort_desc}]\n", flush=True)

    # THE FRONTMATTER MEMO TABLE (30-and-3 winner #5, banked 2026-07-19):
    # (path, mtime) -> [sort_order, permalink]. Served by the shared
    # MtimeMemo helper since the DRY car (2026-07-19); on-disk format
    # and per-entry mtime invalidation are unchanged.
    fm_memo = MtimeMemo(CONFIG_DIR / "fm_cache.json")

    metadata = []
    # --- PASS 1: FAST METADATA EXTRACTION ---
    if args.stdin:
        source_paths = []
        for raw_line in sys.stdin:
            raw_path = raw_line.strip().split("  # ", 1)[0]
            if not raw_path:
                continue

            candidate = Path(raw_path).expanduser()
            if candidate.is_absolute():
                resolved = candidate
            else:
                cwd_candidate = (Path.cwd() / candidate).resolve()
                target_candidate = (target_dir / candidate.name).resolve()
                resolved = cwd_candidate if cwd_candidate.exists() else target_candidate

            source_paths.append(str(resolved))
    else:
        source_paths = [os.path.join(target_dir, filename) for filename in os.listdir(target_dir)]

    for filepath in source_paths:
        filename = os.path.basename(filepath)
        if not os.path.isfile(filepath) or not filename.endswith(('.md', '.markdown')):
            continue
            
        try:
            date_str = filename[:10]
            post_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            fm_mtime = os.path.getmtime(filepath)
            cached_fm = fm_memo.lookup(filepath, fm_mtime)
            if cached_fm is not None:
                sort_order, permalink = cached_fm[0], cached_fm[1]
            else:
                sort_order, permalink = fast_get_sort_order(filepath)
                fm_memo.store(filepath, fm_mtime, [sort_order, permalink])
            
            metadata.append({
                'path': filepath,
                'date': post_date,
                'sort_order': sort_order,
                'permalink': permalink
            })
        except (ValueError, TypeError):
            continue
            
    fm_memo.save()
    # GATED (banked 2026-07-19): silence = all-hits, and that silence is
    # falsifiable via the warm-run timing receipt (~0.27s warm floor,
    # CPU-bound: real ≈ user+sys per the 2026-07-19 receipt; the earlier
    # ~0.13s reading was the unreproduced outlier). Staleness
    # events self-announce with their exact recount; success says nothing.
    if fm_memo.misses:
        print(f"# fm cache: {fm_memo.hits} hits, {fm_memo.misses} misses", file=sys.stderr)

    # Sort first by date, then by the YAML sort_order
    metadata.sort(key=lambda p: (p['date'], p['sort_order']), reverse=args.reverse)

    # --- PASS 1.5: FILTERING ---
    # --slugs: exact slug selection (free, no I/O)
    if args.slugs:
        import re as _re
        wanted = set(args.slugs)
        def _stem_to_slug(path):
            stem = os.path.splitext(os.path.basename(path))[0]
            return _re.sub(r'^\d{4}-\d{2}-\d{2}-', '', stem)
        metadata = [item for item in metadata if _stem_to_slug(item['path']) in wanted]

    # --match: substring filter on filename (free, no I/O)
    if args.match:
        terms = args.match.lower().split()
        metadata = [item for item in metadata if all(t in item['path'].lower() for t in terms)]

    # --last: keep only the N most recent, preserving the chosen display order.
    # Default sort is oldest-first, so "most recent" is the tail; with
    # --reverse (newest-first) it is the head.
    if args.last is not None and args.last > 0:
        if args.reverse:
            metadata = metadata[:args.last]
        else:
            metadata = metadata[-args.last:]

    # --top: limit after sort+filter
    if args.top is not None:
        metadata = metadata[:args.top]

    # --tokens-under: expensive filter, read each file
    if args.tokens_under is not None:
        filtered = []
        for item in metadata:
            try:
                with open(item['path'], 'r', encoding='utf-8') as f:
                    content = f.read()
                if count_tokens(content) < args.tokens_under:
                    filtered.append(item)
            except Exception:
                filtered.append(item)  # keep on error
        metadata = filtered

    # --- PASS 2: OUTPUT GENERATION (REPORT OR COMMAND) ---
    cache_file = CONFIG_DIR / "token_cache.json"
    
    if args.clear_cache and cache_file.exists():
        try:
            cache_file.unlink()
            print("✨ Token cache file purged successfully.", file=sys.stderr)
        except Exception:
            pass

    token_memo = MtimeMemo(cache_file)

    def _get_metrics(path):
        try:
            mtime = os.path.getmtime(path)
            # Anti-swallow guard: Local files can be locked during git stash pops.
            # Only trust the cache if the file timestamp matches AND the token count is > 0.
            cached = token_memo.lookup(path, mtime)
            if cached is not None and cached[0] > 0:
                return cached[0], cached[1]
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            t_cnt = count_tokens(content)
            b_cnt = len(content.encode('utf-8'))
            if t_cnt > 0:
                token_memo.store(path, mtime, [t_cnt, b_cnt])
            return t_cnt, b_cnt
        except Exception:
            return 0, 0

    if args.article:
        # Executable Telemetry Mode: Generate the prompt_foo.py command
        slice_obj = parse_slice_arg(args.article)
        if slice_obj is not None:
            sliced_metadata = metadata[slice_obj] if isinstance(slice_obj, slice) else [metadata[slice_obj]]
            
            if not sliced_metadata:
                print("# No articles matched the provided slice.", file=sys.stderr)
            else:
                # Build the multiline command safely
                command_lines = ["python prompt_foo.py -l [:] --no-tree \\"]
                for i, item in enumerate(sliced_metadata):
                    # Add the continuation backslash to all but the last item
                    line = f"  --decanter {item['path']}"
                    if i < len(sliced_metadata) - 1:
                        line += " \\"
                    command_lines.append(line)
                
                print("\n".join(command_lines))
        else:
            print(f"❌ Invalid slice format: {args.article}. Use format like '[-5:]'", file=sys.stderr)
    else:
        # Standard Mode: Heavy Lifting & Streaming Output
        if args.fmt == 'paths':
            for item in metadata:
                print(item['path'], flush=True)
        elif args.fmt == 'slugs':
            import re
            for item in metadata:
                stem = os.path.splitext(os.path.basename(item['path']))[0]
                slug = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', stem)
                print(slug, flush=True)
        elif args.fmt == 'dated-slugs':
            import re
            target_config = targets[target_key]
            base_url = target_config.get('base_url', 'https://mikelev.in').rstrip('/')
            # THE BUDGET MAP: per-article token size PLUS a running Σ cumulative.
            # Newest-first (--reverse) means Σ answers "take the N newest -> this
            # many tokens." Scan the Σ column top-down; cut where it crosses your
            # context budget. Reversible: this whole block is one SEARCH/REPLACE.
            run_tokens = 0
            run_bytes = 0
            shown = 0
            for item in metadata:
                stem = os.path.splitext(os.path.basename(item['path']))[0]
                slug = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', stem)
                tokens, bytes_count = _get_metrics(item['path'])
                # OPTIMIZATION: Complete hypermedia routing parity with fully qualified absolute URLs.
                # Leverages YAML frontmatter permalinks falling back to default route structures.
                permalink = item.get('permalink', '').rstrip('/')
                if not permalink:
                    permalink = f"/futureproof/{slug}"
                url_target = f"{base_url}{permalink}/index.md"
                if tokens > 0:
                    run_tokens += tokens
                    run_bytes += bytes_count
                    shown += 1
                    # .1f kills the misleading [0k]; sub-1k now reads e.g. [  0.7k].
                    print(f"{item['date']} [{tokens/1000:5.1f}k Σ{run_tokens/1000:8.1f}k] {url_target}", flush=True)
                else:
                    print(f"{item['date']} [  ?  k Σ{run_tokens/1000:8.1f}k] {url_target}", flush=True)
            # THE FOOTER: the summed selection budget (respects --last/--match/--slugs).
            # Comment-prefixed so downstream --stdin / path parsers skip it cleanly.
            print(
                f"# ── selection: {shown} articles | {run_tokens:,} tokens"
                f" | {run_bytes:,} bytes (Σ{run_tokens/1000:.1f}k)",
                flush=True,
            )
        else:
            for idx, item in enumerate(metadata, start=1):
                filepath = item['path']
                tokens, bytes_count = _get_metrics(filepath)
                if tokens > 0:
                    order = item['sort_order']
                    print(f"{filepath}  # [Idx: {idx} | Order: {order} | Tokens: {tokens:,} | Bytes: {bytes_count:,}]", flush=True)
                    if args.shards:
                        print_shard_header(filepath)
                    if args.around is not None and args.terms:
                        print_hit_regions(filepath, args.terms, args.around)
                else:
                    print(f"# Error processing {filepath}", file=sys.stderr)

    token_memo.save()


def get_holographic_article_data(target_dir: str) -> list[dict]:
    """
    The Universal Semantic Extractor.
    Reads Jekyll Markdown and associated JSON shards to create dense context objects.
    """
    target_path = Path(target_dir).expanduser().resolve()
    context_dir = target_path / "_context"
    
    metadata = []
    
    for filename in os.listdir(target_path):
        filepath = target_path / filename
        if not filepath.is_file() or not filename.endswith(('.md', '.markdown')):
            continue
            
        try:
            # 1. Fast YAML Extraction
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if not content.startswith('---'):
                continue
                
            parts = content.split('---', 2)
            if len(parts) < 3:
                continue
                
            fm = yaml.safe_load(parts[1]) or {}
            
            # 2. Basic Metadata
            date_str = filename[:10]
            post_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            sort_order = int(fm.get('sort_order', 0))
            
            # 3. Holographic JSON Shard Extraction (The Flattener logic)
            stem = filepath.stem
            json_path = context_dir / f"{stem}.json"
            
            kw_str, sub_str, sum_str = "", "", ""
            if json_path.exists():
                try:
                    with open(json_path, 'r', encoding='utf-8') as jf:
                        shard = json.load(jf)
                        kw_str = ", ".join(shard.get('kw', []))
                        sub_str = ", ".join(shard.get('sub', []))
                        sum_str = shard.get('s', '').replace('\n', ' ').strip()
                except Exception:
                    pass

            metadata.append({
                'path': str(filepath),
                'filename': filename,
                'date': post_date,
                'sort_order': sort_order,
                'title': fm.get('title', 'Untitled'),
                'permalink': fm.get('permalink', ''),
                'summary': fm.get('meta_description', fm.get('description', '')),
                'shard_kw': kw_str,
                'shard_sub': sub_str,
                'shard_sum': sum_str,
                # We defer expensive token/byte counting until needed by the caller
            })
            
        except Exception:
            continue
            
    # Sort first by date (newest first), then by the YAML sort_order
    metadata.sort(key=lambda p: (p['date'], p['sort_order']), reverse=True)
    return metadata

if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        import os
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        sys.exit(0)
