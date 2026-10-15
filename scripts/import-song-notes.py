"""Import only the explicitly requested song-information sheet; never publish the workbook.

Optional maintenance command requiring openpyxl; the normal build has no dependency on it.
"""
from pathlib import Path
import json
import unicodedata
import openpyxl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'member-song-notes'


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text).casefold() if c.isalnum())


def import_notes():
    workbook = openpyxl.load_workbook(ROOT/'레파토리목록.xlsx', read_only=True, data_only=True)
    try:
        rows = list(workbook['곡설명'].iter_rows(values_only=True))
    finally:
        workbook.close()
    if tuple(rows[0][:4]) != ('곡명', '작곡가(가수)', '장르', '곡설명'):
        raise ValueError('Unexpected song-information columns')
    songs_path = ROOT/'data/songs.json'
    songs = json.loads(songs_path.read_text(encoding='utf-8'))
    names = {}
    for song in songs:
        for title in [song['title'], *song['aliases']]:
            key = normalize(title)
            if key in names and names[key] != song['id']:
                raise ValueError('Ambiguous song title')
            names[key] = song['id']
    # Reviewed title variants; no fuzzy or row-position matching.
    variants = {
        'Romance D´amour (Spanish Romance)': 'romance-damour',
        '곁에 있어도 될까 (Gently, by Your Side)': 'gently-by-your-side',
        '산골 소년의 사랑이야기': 'sangol-boy',
        'Trot Medley (돌아와요 부산항에, 사랑밖엔 난 몰라, 낭만에 대하여)': 'trot-medley',
    }
    names.update({normalize(k): v for k, v in variants.items()})
    by_id = {song['id']: song for song in songs}
    seen = set()
    for row in rows[1:]:
        if not any(value is not None for value in row):
            continue
        if len(row) < 4 or any(not isinstance(v, str) or not v.strip() for v in row[:4]):
            raise ValueError('Incomplete song information')
        title, credit, genre, note = [v.strip() for v in row[:4]]
        song_id = names.get(normalize(title))
        if song_id not in by_id or song_id in seen:
            raise ValueError(f'Unmatched or duplicate song: {title}')
        seen.add(song_id)
        song = by_id[song_id]
        # Preserve composer-only evidence separately: this cell may also name singers.
        song.update(artistCredit=credit, genre=genre, note=note)
        if SOURCE not in song['sourceIds']:
            song['sourceIds'].append(SOURCE)
        for field in ['artistCredit', 'genre', 'note']:
            song['fieldEvidence'][field] = {'status': 'confirmed', 'sourceIds': [SOURCE]}
    if seen != set(by_id):
        raise ValueError(f'Missing song notes: {sorted(set(by_id)-seen)}')
    site_path = ROOT/'data/site.json'
    site = json.loads(site_path.read_text(encoding='utf-8'))
    if not any(s['id'] == SOURCE for s in site['sources']):
        site['sources'].append({'id': SOURCE, 'label': '멤버 제공 곡설명', 'type': 'member-record'})
    # All mappings have succeeded before either data file is written.
    site_path.write_text(json.dumps(site, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    songs_path.write_text(json.dumps(songs, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'PASS: imported {len(seen)} song notes; workbook and concert records preserved.')


if __name__ == '__main__':
    import_notes()
