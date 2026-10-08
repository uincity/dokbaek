"""Regression checks for evidence integrity and public-information boundaries."""
import copy, json, struct, unittest, zlib
from unittest.mock import patch
import validate
from build import strip_metadata

class PublicDataChecks(unittest.TestCase):
    def setUp(self):
        files=validate.validate_data()['files']+['scripts/public-files.json']
        self.data={f:validate.load(validate.ROOT,f) for f in files}
    def check_invalid(self,change):
        change(self.data)
        with patch.object(validate,'load',side_effect=lambda base,path:copy.deepcopy(self.data[path])):
            with self.assertRaises((ValueError,KeyError)):validate.validate_data()
    def test_unknown_song(self):
        self.check_invalid(lambda d:d['data/concerts-2025.json'][0]['setlist'][0].update(songId='unknown-song'))
    def test_unknown_member(self):
        self.check_invalid(lambda d:d['data/concerts-2025.json'][0]['setlist'][0].update(credits=[{'memberId':'unknown','role':'기타'}]))
    def test_duplicate_entry(self):
        self.check_invalid(lambda d:d['data/concerts-2025.json'][0]['setlist'].append(copy.deepcopy(d['data/concerts-2025.json'][0]['setlist'][0])))
    def test_month_precision_cannot_invent_day(self):
        self.check_invalid(lambda d:d['data/concerts-2025.json'][0].update(date='2025-01-01'))
    def test_upcoming_does_not_confirm_performance(self):
        self.check_invalid(lambda d:d['data/concerts-2026.json'][0]['setlist'][0].update(evidenceStatus='confirmed'))
    def test_real_name_field_not_allowed(self):
        self.check_invalid(lambda d:d['data/members.json'][0].update(realName='private person'))
    def test_unreviewed_media_not_allowed(self):
        self.check_invalid(lambda d:d['data/concerts-2025.json'][1]['media'][0].update(reviewed=False))
    def test_document_path_not_allowed(self):
        self.check_invalid(lambda d:d['scripts/public-files.json']['media'].append('2025/private.hwp'))
    def test_poem_not_counted_as_song(self):
        self.check_invalid(lambda d:next(e for e in d['data/concerts-2025.json'][1]['setlist'] if e['kind']=='event').update(songId='misty'))
    def test_contact_and_machine_path_detection(self):
        for text in ['private@example.com','010-1234-5678','C:/Users/private/file','D:\\private\\file']:
            with self.assertRaises(ValueError):validate.scan_text(text)
        validate.scan_text('https://www.youtube.com/@dokback-u4l')
    def test_png_removes_metadata_without_changing_pixels(self):
        def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
        pixels=zlib.compress(b'\x00\x12\x34\x56')
        header=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))
        clean=header+chunk(b'IDAT',pixels)+chunk(b'IEND',b'')
        original=header+chunk(b'tEXt',b'Author\x00Private person')+chunk(b'eXIf',b'private EXIF')+chunk(b'IDAT',pixels)+chunk(b'IEND',b'')
        self.assertEqual(strip_metadata(original,'.png'),clean)

if __name__=='__main__':unittest.main(verbosity=2)
