"""Photo essay regression checks; fixtures exist only in intercepted HTTP responses."""
import copy
import importlib.util
import json
import struct
import traceback
import zlib
from threading import Thread
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright
from validate import ROOT, validate_dist

spec=importlib.util.spec_from_file_location('browser_check',ROOT/'scripts/browser-check.py')
shared=importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)
OUT=ROOT/'test-results'
checks=[]
DETAIL='concert.html?year=2026&id=2026-10-18-gallery'

def record(message):
    checks.append(message)
    print('PASS: '+message,flush=True)

def png(width,height):
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+
            chunk(b'IDAT',zlib.compress((b'\0'+b'\xb5\x98\x76'*width)*height))+chunk(b'IEND',b''))

def run():
    validate_dist(ROOT/'dist')
    original=json.loads((ROOT/'data/concerts-2026.json').read_text(encoding='utf-8'))
    source_original=copy.deepcopy(original)
    # Keep synthetic count cases independent of photographs registered by the operator.
    for concert in original:
        concert['media']=[m for m in concert['media'] if m.get('usage')!='performance-photo']
    server=shared.PublicServer(('127.0.0.1',0),shared.PublicHandler)
    Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}/dokbaek/'
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            context=browser.new_context(viewport={'width':390,'height':900},has_touch=True)
            page=context.new_page()
            page.clock.set_fixed_time(datetime(2026,10,22,3,tzinfo=timezone.utc))
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            requested=[]
            def photo_response(route):
                requested.append(route.request.url)
                portrait=int(route.request.url.rsplit('-',1)[-1].split('.')[0])%3==0
                route.fulfill(body=png(40,60) if portrait else png(60,40),content_type='image/png')
            page.route('**/public-media/photo-check/**',photo_response)
            def go(path=DETAIL):
                page.goto(base+path,wait_until='networkidle')
                page.wait_for_selector('.concert-essay' if path==DETAIL else '#main h1')
                assert not page.locator('#main .error').count()
            fixture=copy.deepcopy(original)
            page.route('**/data/concerts-2026.json',lambda route:route.fulfill(json=fixture))
            for n in [0,1,3,8,16,35,60]:
                fixture=copy.deepcopy(original)
                photo_media=[{'type':'image','usage':'performance-photo','path':f'public-media/photo-check/scene-{i}.png',
                              'label':f'Fixture {i}','alt':f'Test geometric scene {i}', 'caption':f'Test caption {i}',
                              'reviewed':True,'order':i,'width':40 if i%3==0 else 60,'height':60 if i%3==0 else 40}
                             for i in range(1,n+1)]
                # A selected cover later in the ordered list must not change viewer order.
                if n:photo_media[-1]['placement']='cover'
                fixture[0]['media']+=list(reversed(photo_media))
                for width in [360,390,768,1280]:
                    page.set_viewport_size({'width':width,'height':900})
                    requested.clear();go()
                    assert page.locator('.set-item').count()==11
                    assert page.locator('.print-button').count()==2
                    assert page.locator('.photo-button').count()==min(n,17)
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),(n,width)
                    if n==0:
                        assert page.locator('.essay-cover-photo,.essay-scenes,.essay-gallery,.image-placeholder').count()==0
                        assert page.locator('.essay-photo-count').is_hidden()
                    else:
                        assert page.locator('.essay-photo-count').inner_text()==f'현장 사진 {n}장'
                        assert len(set(requested))<=min(n,17)
                        assert page.locator('.essay-cover-photo img').get_attribute('loading')=='eager'
                        assert all(i.get_attribute('loading')=='lazy' for i in page.locator('.essay-photo img').all())
                        opener=page.locator('.photo-button').first
                        opener.click()
                        box=page.locator('#media-dialog').bounding_box()
                        assert box['x']>=0 and box['x']+box['width']<=width+1
                        assert page.locator('.photo-controls button').first.bounding_box()['height']>=44
                        assert page.locator('.photo-controls button').last.bounding_box()['height']>=44
                        page.keyboard.press('Escape')
                        assert opener.evaluate('(b)=>document.activeElement===b')
                    seen=page.locator('figure[data-photo-path]').evaluate_all('(fs)=>fs.map(f=>f.dataset.photoPath)')
                    while page.get_by_role('button',name='사진 더 보기',exact=True).is_visible():
                        before=len(seen)
                        page.get_by_role('button',name='사진 더 보기',exact=True).click()
                        current=page.locator('figure[data-photo-path]').evaluate_all('(fs)=>fs.map(f=>f.dataset.photoPath)')
                        assert current[:before]==seen
                        assert 0<len(current)-before<=12
                        seen=current
                    assert len(seen)==n and len(set(seen))==n
                    if n in [8,35] and width in [390,1280]:
                        for img in page.locator('#main img').all():
                            img.evaluate("i=>{i.loading='eager';return i.decode();}")
                        page.screenshot(path=str(OUT/f'photo-essay-{n}-{width}.png'),full_page=True)
                if n:
                    # Open before expanding the gallery, then traverse all photos by keyboard.
                    go();trigger=page.locator('.photo-button').first
                    trigger.focus();page.keyboard.press('Enter')
                    assert page.locator('#media-dialog').evaluate('(d)=>d.open')
                    assert page.locator('.photo-position').inner_text()==f'{n} / {n}'
                    assert page.locator('.photo-controls button:disabled').count()==(2 if n==1 else 0)
                    if n>1:
                        for i in range(1,n+1):
                            page.keyboard.press('ArrowRight')
                            assert page.locator('.photo-position').inner_text()==f'{i} / {n}'
                            assert page.locator('.photo-viewer img').get_attribute('alt')==f'Test geometric scene {i}'
                        page.keyboard.press('ArrowLeft')
                        assert page.locator('.photo-position').inner_text()==f'{n-1} / {n}'
                        page.get_by_role('button',name='다음 →',exact=True).click()
                        assert page.locator('.photo-position').inner_text()==f'{n} / {n}'
                    page.locator('#close-dialog').focus();page.keyboard.press('Shift+Tab')
                    assert page.locator('#media-dialog').evaluate('(d)=>d.contains(document.activeElement)')
                    page.keyboard.press('Escape')
                    assert trigger.evaluate('(b)=>document.activeElement===b')
                record(f'{n} photos: 360/390/768/1280px, counts, lazy batches, no duplicates, full viewer order and focus')
            # Mixed approval and visibility flags must not expose photos or change print media.
            fixture=copy.deepcopy(original)
            bad=copy.deepcopy(photo_media[:5])
            bad[0]['reviewed']=False
            bad[1]['visibility']='private'
            bad[2]['path']='../private.png'
            bad[3]['alt']=''
            bad[4]['type']='video'
            fixture[0]['media']+=bad
            go();assert page.locator('.photo-button').count()==0
            fixture[0]['media']=original[0]['media']+copy.deepcopy(photo_media[:3])
            fixture[0]['mediaVisibility']='withheld'
            go();assert page.locator('.photo-button,.print-button').count()==0
            fixture[0]['mediaVisibility']='reviewed-only';fixture[0]['visibility']='public-summary'
            go();assert page.locator('.photo-button').count()==0
            record('Unreviewed/private/unsafe/missing-alt/video/withheld/summary photographs excluded')
            fixture=copy.deepcopy(original)
            fixture[0]['media']+=copy.deepcopy(photo_media[:3])
            page.route('**/public-media/photo-check/scene-1.png',lambda route:route.fulfill(status=404,body='Missing'))
            go()
            page.wait_for_function("document.querySelector('.essay-photo-count').textContent==='현장 사진 2장'")
            assert page.locator('.photo-button').count()==2
            assert page.locator('.image-placeholder').count()==0
            assert page.locator('.set-item').count()==11
            trigger=page.locator('.photo-button').first;trigger.click()
            assert page.locator('.photo-position').inner_text()=='1 / 2'
            page.locator('#close-dialog').click()
            assert trigger.evaluate('(b)=>document.activeElement===b')
            record('404 photograph removed; remaining photos, counts, viewer and all 11 songs remain available')
            page.unroute('**/public-media/photo-check/scene-1.png')
            page.set_viewport_size({'width':390,'height':900})
            fixture=copy.deepcopy(original)
            fixture[0]['media']+=copy.deepcopy(photo_media)
            go();page.locator('.photo-button').first.click()
            page.locator('.photo-viewer-frame').evaluate("""f=>{
                const touch=(x,y)=>new Touch({identifier:1,target:f,clientX:x,clientY:y});
                f.dispatchEvent(new TouchEvent('touchstart',{touches:[touch(250,100)]}));
                f.dispatchEvent(new TouchEvent('touchend',{changedTouches:[touch(80,105)]}));
            }""")
            assert page.locator('.photo-position').inner_text()=='1 / 60'
            page.keyboard.press('Escape')
            page.emulate_media(reduced_motion='reduce')
            page.evaluate("document.documentElement.style.fontSize='200%'")
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            page.locator('.photo-button').first.click()
            box=page.locator('#media-dialog').bounding_box()
            assert box['x']>=0 and box['x']+box['width']<=page.viewport_size['width']+1
            page.keyboard.press('Escape')
            record('Touch swipe, 200% text, reduced motion and bounded mobile dialog')
            fixture=copy.deepcopy(original)
            go('archive.html?year=2026#2026-10-18-gallery')
            assert page.locator('[id="2026-10-18-gallery"]').count()==1
            assert page.get_by_role('link',name='그날의 사진과 이야기 ↗',exact=True).count()==1
            page.get_by_role('link',name='그날의 사진과 이야기 ↗',exact=True).click()
            page.wait_for_selector('.concert-essay')
            assert page.locator('h1').inner_text()==original[0]['title']
            assert fixture==original
            assert json.loads((ROOT/'data/concerts-2026.json').read_text(encoding='utf-8'))==source_original
            assert original[1]['id']=='2026-11-08-convent' and original[1]['status']=='scheduled'
            page.goto(base+'concert.html?year=2026&id=missing',wait_until='networkidle')
            assert page.locator('#main h1').inner_text()=='공연을 찾을 수 없습니다.'
            record('Legacy archive anchor, detail link, unchanged source records, No.5 scheduled status and invalid URL')
            assert not errors,errors
            browser.close()
    finally:
        server.shutdown();server.server_close()
    validate_dist(ROOT/'dist')
    record('Release allowlist unchanged by memory-only fixtures; no test images or data in dist')

if __name__=='__main__':
    try:
        run()
    except Exception:
        (OUT/'photo-validation.md').write_text('# Photo essay checks\n\n'+'\n'.join('- PASS: '+c for c in checks)+'\n\n'+traceback.format_exc(),encoding='utf-8')
        raise
    (OUT/'photo-validation.md').write_text('# Photo essay checks\n\n'+'\n'.join('- PASS: '+c for c in checks)+'\n\nFixtures were served from memory only. No publication was performed.\n',encoding='utf-8')
