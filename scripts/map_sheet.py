#!/usr/bin/env python3
"""Scaffold a human-reviewable Google Sheet-to-API mapping artifact.

Input is the timestamped, sentinel-fenced TSV emitted by
scripts/connectors/sheets.py STACK mode. Suggestions are never confirmations:
the JSON must be reviewed before downstream automation or QA may use it.
"""

import argparse
import csv
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse

START_RE = re.compile(
    r'^--- START: TAB "(?P<name>.*)" '
    r'\((?P<rows>\d+) rows x (?P<cols>\d+) cols\) ---$'
)
END_RE = re.compile(r'^--- END: TAB "(?P<name>.*)" ---$')
SHEET_RE = re.compile(
    r'^# (?P<title>.*?)\s+\[spreadsheetId: (?P<sid>[^\]]+)\]\s+'
    r'(?:-|\u2014)\s+(?P<detail>.*)$'
)
STAMP_RE = re.compile(r'^# acquired_at_utc:\s*(?P<stamp>\S+)\s*$')
NUMBER_RE = re.compile(r'^[-+]?[$€£]?\d[\d,]*(?:\.\d+)?%?$')
HEADER_TERMS = {
    'url', 'product', 'variant', 'metric', 'category', 'impression',
    'impressions', 'click', 'clicks', 'position', 'change', 'diff', 'current',
    'prior', 'tracked', 'indexed', 'products', 'rows', 'note', 'period',
}
DERIVED_TERMS = {'diff', 'change', 'delta', 'prior', 'previous'}
STOP_TERMS = {'avg', 'average', 'count', 'current', 'metric', 'period', 'total'}


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace(
        '+00:00', 'Z'
    )


def normalize(value):
    value = unicodedata.normalize('NFKD', str(value))
    value = value.encode('ascii', 'ignore').decode('ascii').casefold()
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', value).split())


def words(value):
    return set(normalize(value).split())


def excel_column(index):
    result = []
    while index:
        index, remainder = divmod(index - 1, 26)
        result.append(chr(65 + remainder))
    return ''.join(reversed(result))


def row_width(row):
    row = list(row)
    while row and not str(row[-1]).strip():
        row.pop()
    return len(row)


def blank(row):
    return not any(str(cell).strip() for cell in row)


def is_number(value):
    return bool(NUMBER_RE.match(str(value).strip()))


def is_url(value):
    parsed = urlparse(str(value).strip())
    return parsed.scheme in {'http', 'https'} and bool(parsed.netloc)


def parse_stack(text):
    source = {
        'spreadsheet_id': None,
        'spreadsheet_title': None,
        'acquired_at_utc': None,
        'stack_detail': None,
    }
    tabs = []
    current = None

    for line in text.splitlines():
        if current is None:
            match = SHEET_RE.match(line)
            if match and source['spreadsheet_id'] is None:
                source.update({
                    'spreadsheet_id': match.group('sid'),
                    'spreadsheet_title': match.group('title'),
                    'stack_detail': match.group('detail'),
                })
                continue
            match = STAMP_RE.match(line)
            if match:
                source['acquired_at_utc'] = match.group('stamp')
                continue
            match = START_RE.match(line)
            if match:
                current = {
                    'name': match.group('name'),
                    'declared_rows': int(match.group('rows')),
                    'declared_cols': int(match.group('cols')),
                    'url': None,
                    'rows': [],
                }
                continue
        else:
            if END_RE.match(line):
                tabs.append(current)
                current = None
                continue
            if current['url'] is None and line.startswith('# http'):
                current['url'] = line[2:].strip()
                continue
            if line != '(empty tab)':
                current['rows'].append(
                    next(csv.reader([line], delimiter='\t'))
                )

    if current is not None:
        raise ValueError(f'Unclosed tab sentinel for {current["name"]!r}')
    if not tabs:
        raise ValueError('No sentinel-fenced tabs found in input')
    return source, tabs


def header_score(rows, index):
    row = rows[index]
    values = [str(cell).strip() for cell in row if str(cell).strip()]
    if len(values) < 2:
        return None

    width = row_width(row)
    text_ratio = sum(
        not is_number(value) and not is_url(value) for value in values
    ) / len(values)
    value_ratio = sum(
        is_number(value) or is_url(value) for value in values
    ) / len(values)
    keyword_hits = sum(bool(words(value) & HEADER_TERMS) for value in values)
    uniqueness = len({normalize(value) for value in values}) / len(values)

    following = [row for row in rows[index + 1:index + 9] if not blank(row)]
    compatible = sum(
        max(2, width - 1) <= row_width(row) <= width + 1
        for row in following
    )
    compatibility = compatible / len(following) if following else 0.0

    return round(
        min(len(values), 8) * 0.35
        + text_ratio * 1.2
        + uniqueness * 1.4
        + min(keyword_hits, 4) * 0.55
        + compatibility * 2.0
        - value_ratio * 1.5,
        3,
    )


def header_candidates(rows, scan_rows):
    candidates = []
    for index in range(min(len(rows), scan_rows)):
        score = header_score(rows, index)
        if score is not None:
            candidates.append({
                'row': index + 1,
                'score': score,
                'values': rows[index],
            })
    return sorted(candidates, key=lambda item: (-item['score'], item['row']))


def layout_diagnostics(rows, header_index, width):
    following = [row for row in rows[header_index + 1:] if not blank(row)]
    if not following:
        return ['no_data_rows_after_header']

    compatible = 0
    single_cell = 0
    compatible_run = 0
    mixed_after_table = False
    for row in following:
        width_now = row_width(row)
        if max(2, width - 1) <= width_now <= width + 1:
            compatible += 1
            compatible_run += 1
        elif width_now == 1:
            single_cell += 1
            mixed_after_table |= compatible_run >= 2

    diagnostics = []
    if compatible < 2:
        diagnostics.append('too_few_table_shaped_rows')
    if mixed_after_table and single_cell / len(following) >= 0.2:
        diagnostics.append('mixed_layout_after_table')
    return diagnostics


def columns_from(header):
    return [
        {
            'index': index,
            'letter': excel_column(index),
            'name': str(name),
            'normalized_name': normalize(name),
        }
        for index, name in enumerate(header, start=1)
    ]


def suggest_lookup(columns, rows, header_index):
    ranked = []
    for column in columns:
        terms = words(column['name'])
        if 'url' not in terms:
            continue
        offset = column['index'] - 1
        samples = [
            str(row[offset]).strip()
            for row in rows[header_index + 1:header_index + 26]
            if offset < len(row) and str(row[offset]).strip()
        ]
        ratio = (
            sum(is_url(value) for value in samples) / len(samples)
            if samples else 0.0
        )
        if ratio < 0.5:
            continue
        score = ratio * 10 + (4 if terms == {'url'} else 0)
        score += 2 if terms & {'product', 'variant'} else 0
        ranked.append((score, column))

    if not ranked:
        return {
            'status': 'unmapped',
            'column_index': None,
            'column_name': None,
            'normalized_name': None,
        }
    ranked.sort(key=lambda item: (-item[0], item[1]['index']))
    column = ranked[0][1]
    return {
        'status': 'suggested',
        'column_index': column['index'],
        'column_name': column['name'],
        'normalized_name': column['normalized_name'],
    }


def api_leaf(field):
    leaf = re.split(r'[./]', field)[-1]
    return normalize(re.sub(r'^count[_ -]+', '', leaf, flags=re.IGNORECASE))


def match_score(label, field):
    left = words(label) - STOP_TERMS
    right = words(api_leaf(field)) - STOP_TERMS
    if not left or not right:
        return 0.0
    overlap = len(left & right) / len(left | right)
    sequence = SequenceMatcher(
        None, ' '.join(sorted(left)), ' '.join(sorted(right))
    ).ratio()
    return round(overlap * 0.7 + sequence * 0.3, 3)


def suggest_qa(columns, api_fields, threshold):
    suggestions = []
    for column in columns:
        if words(column['name']) & DERIVED_TERMS:
            continue
        ranked = sorted(
            ((match_score(column['name'], field), field) for field in api_fields),
            key=lambda item: (-item[0], item[1]),
        )
        ranked = [item for item in ranked if item[0] >= threshold][:3]
        if ranked:
            suggestions.append({
                'sheet_column_index': column['index'],
                'sheet_column_name': column['name'],
                'status': 'suggested',
                'api_candidates': [
                    {'field': field, 'score': score}
                    for score, field in ranked
                ],
            })
    return suggestions


def collect_fields(value):
    found = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(child, str) and (
                '.' in child
                or any(
                    term in normalize(key)
                    for term in ('field', 'dimension', 'metric')
                )
            ):
                found.add(child)
            found.update(collect_fields(child))
    elif isinstance(value, list):
        for child in value:
            found.update(collect_fields(child))
    elif isinstance(value, str) and '.' in value:
        found.add(value)
    return found


def load_api_fields(schema_paths, explicit, prefixes):
    fields = set(explicit)
    for path in schema_paths:
        payload = json.loads(Path(path).read_text(encoding='utf-8'))
        fields.update(collect_fields(payload))
    fields = sorted(field.strip() for field in fields if field.strip())
    if prefixes:
        fields = [
            field for field in fields
            if any(field.startswith(prefix) for prefix in prefixes)
        ]
    return fields


def map_tab(tab, api_fields, scan_rows, threshold):
    rows = tab['rows']
    candidates = header_candidates(rows, scan_rows)
    result = {
        'tab_name': tab['name'],
        'tab_url': tab['url'],
        'declared_extent': {
            'rows': tab['declared_rows'],
            'columns': tab['declared_cols'],
        },
        'mapping_status': 'needs_human',
        'header': {
            'status': 'unmapped',
            'row': None,
            'suggested_row': None,
            'candidates': candidates[:5],
        },
        'columns': [],
        'lookup_key': {
            'status': 'unmapped',
            'column_index': None,
            'column_name': None,
            'normalized_name': None,
        },
        'qa_fields': [],
        'diagnostics': [],
    }
    if not candidates:
        result['diagnostics'].append('no_plausible_header_row')
        return result

    best = candidates[0]
    header_index = best['row'] - 1
    width = row_width(rows[header_index])
    diagnostics = layout_diagnostics(rows, header_index, width)
    if len(candidates) > 1 and best['score'] - candidates[1]['score'] < 0.75:
        diagnostics.append('competing_header_candidates')

    columns = columns_from(rows[header_index][:width])
    result.update({
        'mapping_status': 'needs_human' if diagnostics else 'ready_for_review',
        'header': {
            'status': 'needs_human' if diagnostics else 'suggested',
            'row': None if diagnostics else best['row'],
            'suggested_row': best['row'],
            'candidates': candidates[:5],
        },
        'columns': columns,
        'lookup_key': suggest_lookup(columns, rows, header_index),
        'qa_fields': suggest_qa(columns, api_fields, threshold),
        'diagnostics': diagnostics,
    })
    return result


def main():
    parser = argparse.ArgumentParser(
        description='Scaffold a human-reviewable SheetApiMapping JSON artifact.'
    )
    parser.add_argument(
        'stack',
        nargs='?',
        default='-',
        help='sheets.py STACK output file, or - for stdin.',
    )
    parser.add_argument(
        '-o',
        '--output',
        default='-',
        help='Destination JSON, or - for stdout.',
    )
    parser.add_argument(
        '--api-schema',
        action='append',
        default=[],
        help='JSON schema/discovery file; repeatable.',
    )
    parser.add_argument(
        '--api-field',
        action='append',
        default=[],
        help='Known API field candidate; repeatable.',
    )
    parser.add_argument(
        '--api-prefix',
        action='append',
        default=[],
        help='Keep API fields with this prefix; repeatable.',
    )
    parser.add_argument('--scan-rows', type=int, default=25)
    parser.add_argument('--match-threshold', type=float, default=0.58)
    args = parser.parse_args()

    try:
        if args.stack == '-':
            text, input_name = sys.stdin.read(), 'stdin'
        else:
            path = Path(args.stack)
            text, input_name = path.read_text(encoding='utf-8'), str(path)
        source, tabs = parse_stack(text)
        api_fields = load_api_fields(
            args.api_schema, args.api_field, args.api_prefix
        )
        source.update({
            'input_name': input_name,
            'input_has_acquisition_timestamp': bool(source['acquired_at_utc']),
        })
        payload = {
            'type': 'SheetApiMapping',
            'schema_version': 1,
            'generated_at_utc': utc_now(),
            'status': 'draft_requires_human_confirmation',
            'source': source,
            'api_catalog': {
                'schema_files': args.api_schema,
                'prefix_filters': args.api_prefix,
                'field_count': len(api_fields),
            },
            'tabs': [
                map_tab(
                    tab,
                    api_fields,
                    max(1, args.scan_rows),
                    min(max(args.match_threshold, 0.0), 1.0),
                )
                for tab in tabs
            ],
            'confirmation_contract': {
                'rule': (
                    'No downstream automation or QA may treat suggested '
                    'mappings as confirmed.'
                ),
                'required_actions': [
                    'Confirm or correct each tab header row.',
                    'Confirm or correct the lookup key by index and name.',
                    'Confirm each sheet-column to API-field correspondence.',
                ],
            },
        }
        rendered = json.dumps(payload, indent=2, ensure_ascii=False) + '\n'
        if args.output == '-':
            sys.stdout.write(rendered)
        else:
            destination = Path(args.output)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(rendered, encoding='utf-8')
            print(
                f'Wrote draft mapping artifact: {destination}',
                file=sys.stderr,
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f'map_sheet.py: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
