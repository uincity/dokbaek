"""Verify small stages appear once in shared concert and member histories."""
import copy
import importlib.util
import json
from datetime import datetime, timezone
from threading import Thread
from playwright.sync_api import sync_playwright
from validate import ROOT, validate_dist

spec=importlib.util.spec_from_file_location('browser_check',ROOT/'scripts/browser-check.py')
shared=importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)

def run():
    validate_dist(ROOT/'dist')
    units=json.loads((ROOT/'dist/data/unit-performances.json').read_text(encoding='utf-8'))
    members=json.loads((ROOT/'dist/data/members.json').read_text(encoding='utf-8'))
    server=shared.PublicServer(('127.0.0.1',0),shared.PublicHandler)
    Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page()
            page.clock.set_fixed_time(datetime(2026,10,20,3,tzinfo=timezone.utc))
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            def go(path):
                page.goto(f'http://127.0.0.1:{server.server_port}/dokbaek/'+path,wait_until='networkidle')
                page.wait_for_function("!document.querySelector('#main .loading')")
            for width in (390,1280):
                page.set_viewport_size({'width':width,'height':900})
                go('index.html')
                assert page.locator('.stat b').all_text_contents()==['6','2','26']
                assert page.locator('.upcoming-feature').get_attribute('data-concert-id')=='unit-sunset-20261024'
                for year in (2025,2026):
                    go(f'archive.html?year={year}')
                    for event in units:
                        if not event['date'].startswith(str(year)):continue
                        card=page.locator('#unit-'+event['id'])
                        assert card.count()==1
                        assert card.locator('.set-item').count()==len(event['songs'])
                        for song in event['songs']:
                            item=card.locator(f'#unit-{event["id"]}-song-{song["order"]}')
                            for person in song['performers']:
                                assert item.locator(f'.credit[href="members.html#{person["member_id"]}"]').count()==1
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                for member in members:
                    go('members.html#'+member['id'])
                    records=page.locator('#member-detail .history')
                    for event in units:
                        expected=sum(any(person['member_id']==member['id'] for person in song['performers']) for song in event['songs'])
                        actual=records.filter(has=page.locator(f'a[href*="#unit-{event["id"]}-song-"]'))
                        assert actual.count()==expected,(member['id'],event['id'],expected,actual.count())
                        previews=page.locator(f'#member-detail .preview-main[href$="#unit-{event["id"]}"]')
                        assert previews.count()==int(expected>0)
                go('repertoire.html?year=2025#besame-mucho')
                assert page.locator('#besame-mucho .history a[href*="#unit-wedding-"]').count()==2
                go('concert.html?year=2025&id=unit-wedding-20251207')
                assert page.locator('.set-item').count()==2
                assert page.locator('.essay-cover-photo,.essay-scenes .essay-photo').count()==2
                for img in page.locator('.essay-photo-image img').all():
                    img.evaluate("async i=>{i.loading='eager';await i.decode();}")
            page.clock.set_fixed_time(datetime(2027,1,1,3,tzinfo=timezone.utc))
            go('archive.html?year=2026')
            assert page.locator('[data-status="scheduled"] #unit-sunset-20261024').count()==1
            # Unregistered songs remain visible in the performer's history.
            fixture=copy.deepcopy(units)
            fixture[0]['songs'][0].update(song_id=None,title='Standalone unit song')
            page.route('**/data/unit-performances.json',lambda route:route.fulfill(json=fixture))
            go('members.html#member-rona')
            record=page.locator('.history').filter(has=page.locator('a[href$="#unit-wedding-20251207-song-1"]'))
            assert 'Standalone unit song' in record.inner_text()
            assert record.locator('a[href*="#null"]').count()==0
            page.unroute('**/data/unit-performances.json')
            page.route('**/data/unit-performances.json',lambda route:route.fulfill(status=503,body='Unavailable'))
            go('index.html')
            go('members.html#member-rona')
            assert page.locator('.unit-error[role="alert"]').count()==1
            assert page.locator('#member-detail .history').count()>0
            assert not errors,errors
            browser.close()
    finally:
        server.shutdown();server.server_close()
    print('PASS: statistics, archives, exact member credits, repertoire, detail images, editorial status, unknown songs and load failure')

if __name__=='__main__':run()
