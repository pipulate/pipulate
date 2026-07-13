#!/usr/bin/env python3
"""
facet_allowlist.py — strategic uncanonicalization pipeline.

build-facets   : crawl {domain}/products.json (paginated) into facet_dim
import-demand  : load a GSC / Botify RealKeywords CSV into demand_fact,
                 parsing handle and variant_id out of the page URL
allowlist      : variant_ids whose demand clears thresholds (the paste-ready
                 selective-canonical list)
latent         : size/color-token queries landing on BASE urls — demand the
                 variant URLs haven't captured yet

Stdlib only. Facet parsing mirrors the PageWorkers v2.1 buildSuffix policy:
color / band+cup combined / any *size* option; unknown names skipped.
"""
import argparse
import csv
import json
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request

DDL = """
CREATE TABLE IF NOT EXISTS facet_dim (
    variant_id   INTEGER PRIMARY KEY,
    handle       TEXT NOT NULL,
    product_title TEXT,
    option_shape TEXT,
    color        TEXT,
    band         TEXT,
    cup          TEXT,
    size_raw     TEXT,
    size_norm    TEXT,
    available    INTEGER,
    price        REAL
);
CREATE INDEX IF NOT EXISTS idx_facet_handle ON facet_dim(handle);

CREATE TABLE IF NOT EXISTS demand_fact (
    date_window  TEXT,
    page_url     TEXT,
    query        TEXT,
    impressions  INTEGER DEFAULT 0,
    clicks       INTEGER DEFAULT 0,
    position     REAL,
    handle       TEXT,
    variant_id   INTEGER
);
CREATE INDEX IF NOT EXISTS idx_demand_variant ON demand_fact(variant_id);
CREATE INDEX IF NOT EXISTS idx_demand_handle ON demand_fact(handle);
"""

SIZE_TOKEN = re.compile(r'\b\d{2}\s?[A-N]{1,3}\b', re.IGNORECASE)


def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.executescript(DDL)
    return conn


def parse_page_url(url):
    """Return (handle, variant_id) from any product URL, else (None, None)."""
    m = re.search(r'/products/([^/?#]+)', url or '')
    handle = m.group(1) if m else None
    variant_id = None
    try:
        qs = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        if 'variant' in qs and qs['variant'][0].isdigit():
            variant_id = int(qs['variant'][0])
    except (ValueError, AttributeError, TypeError):
        pass
    return handle, variant_id


def classify_options(options, variant):
    """Mirror of PageWorkers v2.1 buildSuffix name policy."""
    color = band = cup = size_raw = None
    for i, opt in enumerate(options):
        name = (opt.get('name') or '').lower()
        val = variant.get('option%d' % opt.get('position', i + 1))
        if not val or val == 'Default Title':
            continue
        if name in ('color', 'colour'):
            color = val
        elif name == 'band size':
            band = val
        elif name == 'cup size':
            cup = val
        elif 'size' in name and size_raw is None:
            size_raw = val
    if band and cup:
        size_norm = band + cup
    elif band or cup:
        size_norm = band or cup
    else:
        size_norm = size_raw
    return color, band, cup, size_raw, size_norm


def build_facets(args):
    conn = connect(args.db)
    page, total = 1, 0
    while True:
        url = 'https://%s/products.json?limit=250&page=%d' % (args.domain, page)
        req = urllib.request.Request(url, headers={
            'User-Agent': ('Mozilla/5.0 (X11; Linux x86_64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/126.0.0.0 Safari/537.36'),
            'Accept': 'application/json',
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            products = json.load(resp).get('products', [])
        if not products:
            break
        for p in products:
            shape = json.dumps([o.get('name') for o in p.get('options', [])])
            for v in p.get('variants', []):
                color, band, cup, size_raw, size_norm = classify_options(
                    p.get('options', []), v)
                conn.execute(
                    """INSERT OR REPLACE INTO facet_dim
                       (variant_id, handle, product_title, option_shape,
                        color, band, cup, size_raw, size_norm, available, price)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (v['id'], p['handle'], p.get('title'), shape,
                     color, band, cup, size_raw, size_norm,
                     1 if v.get('available') else 0,
                     float(v['price']) if v.get('price') else None))
                total += 1
        conn.commit()
        print('page %d: %d products (running variant total: %d)'
              % (page, len(products), total))
        if len(products) < 250:
            break
        page += 1
        time.sleep(args.delay)
    print('facet_dim built: %d variants' % total)


def import_demand(args):
    conn = connect(args.db)

    def norm(h):
        return (h or '').strip().lower().replace(' ', '_')

    def num(row, col, cast):
        raw = (row.get(col) or '').replace(',', '').replace('%', '').strip()
        try:
            return cast(raw)
        except (ValueError, TypeError):
            return 0 if cast is int else None

    # Idempotent by window: re-importing the same window replaces its rows
    # instead of appending duplicates (the exact failure behind the doubled
    # 491,232-row demand_fact and the inflated 9,639-variant allowlist).
    conn.execute('DELETE FROM demand_fact WHERE date_window = ?', (args.window,))
    conn.commit()
    inserted = 0
    with open(args.csv, newline='', encoding='utf-8-sig') as f:
        # Excel-dialect exports (Botify) lead with a 'sep=,' hint line that
        # would otherwise be consumed as the header row -- the exact failure
        # behind '0 rows imported'. Honor it for the delimiter, then skip it.
        first = f.readline()
        delim = ','
        if first.lower().startswith('sep='):
            delim = first.strip()[4:] or ','
        else:
            f.seek(0)
        reader = csv.DictReader(f, delimiter=delim)
        reader.fieldnames = [norm(h) for h in reader.fieldnames]
        print('normalized headers: %s' % reader.fieldnames)
        missing = [c for c in (norm(args.url_col), norm(args.query_col))
                   if c not in reader.fieldnames]
        if missing:
            print('ERROR: column(s) %s not found in headers %s.\n'
                  'Pass the matching --url-col / --query-col (and metric-col) '
                  'flags using the normalized names printed above.'
                  % (missing, reader.fieldnames), file=sys.stderr)
            sys.exit(1)
        for row in reader:
            url = row.get(norm(args.url_col), '')
            handle, variant_id = parse_page_url(url)
            if not handle:
                continue
            conn.execute(
                """INSERT INTO demand_fact
                   (date_window, page_url, query, impressions, clicks,
                    position, handle, variant_id)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (args.window, url, row.get(norm(args.query_col), ''),
                 num(row, norm(args.impressions_col), int),
                 num(row, norm(args.clicks_col), int),
                 num(row, norm(args.position_col), float),
                 handle, variant_id))
            inserted += 1
    conn.commit()
    print('demand_fact: %d rows imported for window %s' % (inserted, args.window))


def allowlist(args):
    conn = connect(args.db)
    rows = conn.execute(
        """SELECT d.variant_id, f.handle, f.color, f.size_norm,
                  SUM(d.impressions) AS imp, SUM(d.clicks) AS clk,
                  MIN(d.position)   AS best_pos
           FROM demand_fact d
           JOIN facet_dim f ON f.variant_id = d.variant_id
           WHERE d.variant_id IS NOT NULL
           GROUP BY d.variant_id
           HAVING SUM(d.impressions) >= ? OR SUM(d.clicks) >= ?
           ORDER BY imp DESC""",
        (args.min_impressions, args.min_clicks)).fetchall()
    print('variant_id\thandle\tcolor\tsize\timpressions\tclicks\tbest_pos')
    for r in rows:
        print('\t'.join(str(x) if x is not None else '' for x in r))
    print('-- %d variants clear thresholds (imp>=%d or clicks>=%d)'
          % (len(rows), args.min_impressions, args.min_clicks), file=sys.stderr)


def latent(args):
    conn = connect(args.db)
    rows = conn.execute(
        """SELECT handle, query, SUM(impressions) AS imp, SUM(clicks) AS clk
           FROM demand_fact
           WHERE variant_id IS NULL
           GROUP BY handle, query
           ORDER BY imp DESC""").fetchall()
    print('handle\tquery\timpressions\tclicks\t(size-token match)')
    shown = 0
    for handle, query, imp, clk in rows:
        m = SIZE_TOKEN.search(query or '')
        if m:
            print('%s\t%s\t%s\t%s\t%s' % (handle, query, imp, clk, m.group(0)))
            shown += 1
    print('-- %d base-URL queries carry size tokens (latent variant demand)'
          % shown, file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)

    b = sub.add_parser('build-facets')
    b.add_argument('--domain', required=True)
    b.add_argument('--db', default='facets.db')
    b.add_argument('--delay', type=float, default=0.5)
    b.set_defaults(func=build_facets)

    i = sub.add_parser('import-demand')
    i.add_argument('--db', default='facets.db')
    i.add_argument('--csv', required=True)
    i.add_argument('--window', default='unspecified')
    i.add_argument('--url-col', default='page')
    i.add_argument('--query-col', default='query')
    i.add_argument('--impressions-col', default='impressions')
    i.add_argument('--clicks-col', default='clicks')
    i.add_argument('--position-col', default='position')
    i.set_defaults(func=import_demand)

    a = sub.add_parser('allowlist')
    a.add_argument('--db', default='facets.db')
    a.add_argument('--min-impressions', type=int, default=50)
    a.add_argument('--min-clicks', type=int, default=3)
    a.set_defaults(func=allowlist)

    lat = sub.add_parser('latent')
    lat.add_argument('--db', default='facets.db')
    lat.set_defaults(func=latent)

    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
