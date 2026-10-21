"""Regression checks for worksheet grouping, role parsing and safe re-imports."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path
from unit_data import validate_units
from validate import ROOT, approved_files

spec = importlib.util.spec_from_file_location('unit_importer', Path(__file__).with_name('import-unit-performances.py'))
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)


class UnitChecks(unittest.TestCase):
    def setUp(self):
        self.songs = json.loads((ROOT / 'data/songs.json').read_text(encoding='utf-8'))
        self.members = json.loads((ROOT / 'data/members.json').read_text(encoding='utf-8'))
        self.events = json.loads((ROOT / 'data/unit-performances.json').read_text(encoding='utf-8'))
        self.rows = [list(importer.HEADERS)]
        for event in self.events:
            for song in event['songs']:
                self.rows.append([event['source_category'], song['source_title'], song['source_performers'], event['source_venue'], event['date']])

    def build(self, rows=None, previous=None, approved=()):
        return importer.build_events(rows or self.rows, self.songs, self.members, self.events if previous is None else previous, approved_files()+list(approved))

    def test_actual_workbook_matches_checked_in_json(self):
        import openpyxl
        book = openpyxl.load_workbook(ROOT / '레파토리목록.xlsx', data_only=True, read_only=True)
        try:
            events = self.build(list(book['파일럿공연'].values))
        finally:
            book.close()
        self.assertEqual(events, self.events)

    def test_three_events_five_rows_and_unique_members(self):
        events = self.build(previous=[])
        self.assertEqual(len(events), 3)
        self.assertEqual(sum(len(e['songs']) for e in events), 5)
        self.assertEqual([len({p['member_id'] for s in e['songs'] for p in s['performers']}) for e in events], [3, 5, 2])
        self.assertEqual([e['status'] for e in events], ['completed', 'completed', 'scheduled'])

    def test_media_stays_bound_to_each_event_and_survives_reimport(self):
        expected = {
            'wedding-20251207': ['image/첫 번째 결혼축가1.png', 'image/첫 번째 결혼축가2.png'],
            'wedding-20251227': ['image/두 번째 결혼축가1.png', 'image/두 번째 결혼축가2.png'],
            'sunset-20261024': ['2026/포스터/포스터_노을음악회_20261024.jpg'],
        }
        for event in self.build(previous=list(reversed(self.events))):
            self.assertEqual([m['path'] for m in event['media']], expected[event['id']])
            self.assertTrue(all(m['width'] > 0 and m['height'] > 0 for m in event['media']))

    def test_invalid_media_usage_or_dimensions_rejected(self):
        for change in [{'usage': 'unreviewed'}, {'width': 0}, {'height': None}, {'width': True}]:
            events = copy.deepcopy(self.events)
            events[0]['media'][0].update(change)
            with self.assertRaises(ValueError):
                validate_units(events, self.songs, self.members, approved_files())

    def test_role_commas_keep_one_person_and_workbook_melodion(self):
        players = importer.parse_performers('베키짱(노래), 로나짱(기타,아코디언),유니뀨짱(기타)', self.members)
        self.assertEqual(len(players), 3)
        self.assertEqual(players[1]['roles'], ['기타', '아코디언'])
        self.assertEqual(self.events[0]['songs'][1]['performers'][1]['roles'], ['기타', '멜로디언'])

    def test_title_prefix_alias_and_raw_title_preservation(self):
        song = self.build()[0]['songs'][0]
        self.assertEqual(song['title'], 'Bésame Mucho')
        self.assertEqual(song['song_id'], 'besame-mucho')
        self.assertEqual(song['formats'], ['중주'])
        self.assertEqual(song['source_title'], '01. (중주) 05.Besame mucho ')
        self.assertEqual(self.build()[0]['songs'][1]['song_id'], 'fly-me-to-the-moon')

    def test_manual_status_media_notes_and_stable_ids_survive(self):
        old = copy.deepcopy(self.events)
        old[-1].update(status='completed', notes='개최 확인', description='음악의 기록', id='stable-sunset')
        old[-1]['media'] = [{'type': 'image', 'path': 'public-media/reviewed.jpg', 'label': '승인된 활동 사진', 'reviewed': True}]
        output = self.build(previous=old, approved=['public-media/reviewed.jpg'])
        for key in ('status', 'notes', 'description', 'id', 'media'):
            self.assertEqual(output[-1][key], old[-1][key])
        self.assertEqual(self.build(previous=old, approved=['public-media/reviewed.jpg']), output)

    def test_conflicting_event_date_or_venue_rejected(self):
        for column, value in [(3, '다른 장소'), (4, '2025.12.8.')]:
            rows = copy.deepcopy(self.rows)
            rows[2][column] = value
            with self.assertRaisesRegex(ValueError, 'conflicting date/venue'):
                self.build(rows)

    def test_missing_or_malformed_cells_rejected(self):
        for column, value in [(1, ''), (1, '01. (중주)'), (2, '(기타)'), (2, '로나짱(기타),'), (2, '로나짱(기타) 유니뀨짱(기타)'), (4, '2025.02.30')]:
            rows = copy.deepcopy(self.rows)
            rows[1][column] = value
            with self.assertRaises(ValueError):
                self.build(rows)

    def test_duplicate_ids_bad_status_missing_names_and_unapproved_media_rejected(self):
        changes = [lambda e: e[1].update(id=e[0]['id']), lambda e: e[0].update(status='automatic'),
                   lambda e: e[0]['songs'][0]['performers'][0].update(name=''),
                   lambda e: e[0].update(media=[{'type': 'image', 'label': '미승인', 'path': 'public-media/unreviewed.jpg', 'reviewed': False}])]
        for change in changes:
            events = copy.deepcopy(self.events)
            change(events)
            with self.assertRaises(ValueError):
                validate_units(events, self.songs, self.members, approved_files())

    def test_removed_event_needs_explicit_resolution(self):
        with self.assertRaisesRegex(ValueError, 'removed existing events'):
            self.build(self.rows[:-1])

    def test_unknown_song_uses_standalone_title_without_new_id(self):
        rows = copy.deepcopy(self.rows)
        rows[-1][1] = '01.새로운 곡'
        song = self.build(rows)[-1]['songs'][0]
        self.assertEqual(song['title'], '새로운 곡')
        self.assertIsNone(song['song_id'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
