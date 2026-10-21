"""Import the 파일럿공연 worksheet, preserving editorial status and approved media."""
from pathlib import Path
from datetime import date, datetime
import argparse
import hashlib
import json
import re
import sys
import unicodedata
from unit_data import require, validate_units

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = {
    '결혼축가1': ('wedding-20251207', '첫 번째 결혼축가', 'wedding', 'completed'),
    '결혼축가2': ('wedding-20251227', '두 번째 결혼축가', 'wedding', 'completed'),
    '노을음악회': ('sunset-20261024', '노을음악회', 'outreach', 'scheduled'),
}
HEADERS = ('구분', '곡명', '연주자(역할)', '장소', '일시')


def normalize(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFC', value)).casefold()


def parse_title(raw):
    title, formats = raw.strip(), []
    while True:
        prefix = re.match(r'^(?:\d+\s*\.\s*|\(([^()]+)\)\s*)', title)
        if not prefix:
            break
        if prefix[1]:
            formats.append(prefix[1].strip())
        title = title[prefix.end():].strip()
    require(bool(title), 'Empty song title after removing program prefixes')
    return title, formats


def parse_performers(raw, members):
    names = {m['nickname']: m['id'] for m in members}
    performers, end = [], 0
    for match in re.finditer(r'([^(),]+)\(([^()]+)\)', raw):
        gap = raw[end:match.start()]
        require(not gap.strip() if end == 0 else gap.strip() == ',', f'Malformed performer separator: {raw}')
        name = match[1].strip()
        require(name in names, f'Unknown public member nickname: {name}; register in data/members.json first')
        roles = [role.strip() for role in re.split(r'[,·]', match[2])]
        require(all(roles), f'Missing performer role: {raw}')
        performers.append({'member_id': names[name], 'name': name, 'roles': roles})
        end = match.end()
    require(performers and not raw[end:].strip(), f'Missing/malformed performer name or roles: {raw}')
    return performers


def parse_date(value):
    if isinstance(value, (datetime, date)):
        return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
    match = re.fullmatch(r'\s*(\d{4})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})\.?\s*', str(value))
    require(match is not None, f'Invalid date: {value}')
    return date(*map(int, match.groups())).isoformat()


def build_events(rows, songs, members, previous, approved_media=()):
    validate_units(previous, songs, members, approved_media)
    headers = [str(v).strip() if v is not None else '' for v in rows[0]]
    require(all(headers.count(h) == 1 for h in HEADERS), f'Expected worksheet headers: {HEADERS}')
    positions = [headers.index(h) for h in HEADERS]
    aliases = {}
    for song in songs:
        for title in [song['title'], *song.get('aliases', [])]:
            aliases.setdefault(normalize(title), {})[song['id']] = song
    old = {e['source_category']: e for e in previous}
    events = {}
    for row_number, row in enumerate(rows[1:], 2):
        if not any(value is not None and str(value).strip() for value in row):
            continue
        values = [row[p] if p < len(row) else None for p in positions]
        require(all(v is not None and str(v).strip() for v in values), f'Worksheet row {row_number}: missing required cell')
        category, raw_title, raw_performers, raw_venue, raw_date = values
        category, raw_venue = str(category).strip(), str(raw_venue).strip()
        event_date = parse_date(raw_date)
        if category not in events:
            event_id, title, kind, status = DEFAULTS.get(category, (
                f'unit-{event_date.replace("-", "")}-{hashlib.sha256(category.encode()).hexdigest()[:8]}', category, 'other', 'scheduled'))
            event = {'id': event_id, 'source_category': category, 'title': title, 'type': kind,
                     'date': event_date, 'venue': raw_venue.replace('(ONN닥터TV홀)', ' ONN닥터TV홀'),
                     'source_venue': raw_venue, 'status': status, 'songs': []}
            if category in old:
                # Keep stable IDs and all manually curated fields, including explicit status.
                event.update({k: v for k, v in old[category].items() if k not in {'source_category', 'date', 'venue', 'source_venue', 'songs'}})
            events[category] = event
        event = events[category]
        require(event['date'] == event_date and event['source_venue'] == raw_venue,
                f'Worksheet row {row_number}: conflicting date/venue within {category}')
        title, formats = parse_title(str(raw_title))
        matches = list(aliases.get(normalize(title), {}).values())
        require(len(matches) <= 1, f'Ambiguous existing song title: {title}')
        match = matches[0] if matches else None
        if not match:
            print(f'WARNING: no existing song ID for {title}; retaining standalone title', file=sys.stderr)
        event['songs'].append({'order': len(event['songs']) + 1,
            'title': match['title'] if match else title, 'song_id': match['id'] if match else None,
            'source_title': str(raw_title), 'source_performers': str(raw_performers),
            'formats': formats, 'performers': parse_performers(str(raw_performers), members)})
    require(not set(old) - set(events), f'Worksheet removed existing events: {set(old) - set(events)}; resolve explicitly before importing')
    result = sorted(events.values(), key=lambda e: (e['date'], e['id']))
    validate_units(result, songs, members, approved_media)
    return result


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbook', type=Path, default=ROOT / '레파토리목록.xlsx')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/unit-performances.json')
    args = parser.parse_args()
    # openpyxl is optional for importing; the site/build use only static JSON.
    import openpyxl
    from validate import approved_files, scan_text
    workbook = openpyxl.load_workbook(args.workbook, data_only=True, read_only=True)
    try:
        require('파일럿공연' in workbook.sheetnames, 'Missing 파일럿공연 worksheet; output was not changed')
        rows = list(workbook['파일럿공연'].values)
    finally:
        workbook.close()
    require(bool(rows), 'Empty worksheet')
    songs = json.loads((ROOT / 'data/songs.json').read_text(encoding='utf-8'))
    members = json.loads((ROOT / 'data/members.json').read_text(encoding='utf-8'))
    previous = json.loads(args.output.read_text(encoding='utf-8')) if args.output.exists() else []
    events = build_events(rows, songs, members, previous, approved_files())
    content = json.dumps(events, ensure_ascii=False, indent=2) + '\n'
    scan_text(content)
    temporary = args.output.with_suffix('.json.tmp')
    temporary.write_text(content, encoding='utf-8')
    temporary.replace(args.output)
    print(f'PASS: imported {len(events)} small stages / {sum(len(e["songs"]) for e in events)} songs; editorial status/media preserved')


if __name__ == '__main__':
    try:
        run()
    except (ValueError, KeyError, TypeError, OSError, ImportError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        sys.exit(1)
