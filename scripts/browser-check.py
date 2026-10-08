"""Optional end-to-end checks. Requires an installed Playwright and Chromium."""
from pathlib import Path, PurePosixPath
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlsplit, unquote
from threading import Thread
import json, sys, traceback
from playwright.sync_api import sync_playwright
from validate import ROOT, validate_dist

sys.stdout.reconfigure(encoding='utf-8')
OUT=ROOT/'test-results';OUT.mkdir(exist_ok=True)
PUBLIC=ROOT/'dist'
PREFIX='/dokbaek/'
checks=[]

class PublicHandler(SimpleHTTPRequestHandler):
    def translate_path(self,path):
        path=unquote(urlsplit(path).path)
        if not path.startswith(PREFIX):return str(PUBLIC/'.missing')
        pieces=PurePosixPath(path[len(PREFIX):]).parts
        if any(p in ('..','.') for p in pieces):return str(PUBLIC/'.missing')
        result=PUBLIC.joinpath(*pieces).resolve()
        if not result.is_relative_to(PUBLIC.resolve()):return str(PUBLIC/'.missing')
        return str(result)
    def log_message(self,*args):pass
    def copyfile(self,source,outputfile):
        try:super().copyfile(source,outputfile)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass

def record(label):checks.append(label);print('PASS: '+label,flush=True)

def run():
    validate_dist(PUBLIC);record('Public allowlist, references, dates, evidence states and privacy scan')
    server=ThreadingHTTPServer(('127.0.0.1',0),PublicHandler)
    Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}{PREFIX}'
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            context=browser.new_context(viewport={'width':1280,'height':900},locale='ko-KR')
            page=context.new_page();errors=[];bad_requests=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('response',lambda res:bad_requests.append(res.url) if res.status>=400 else None)
            def go(path):
                page.goto(base+path,wait_until='networkidle')
                page.wait_for_function("() => !document.querySelector('#main .loading')")
                assert not page.locator('h1').inner_text().startswith('기록을 불러오지 못'),path
            def capture(name):
                # Full-page capture does not trigger off-screen lazy loads by itself.
                for img in page.locator('#main img').all():
                    img.evaluate("i => { i.loading='eager'; return i.decode(); }")
                page.evaluate("window.scrollTo({top:0,behavior:'instant'})")
                page.screenshot(path=str(OUT/name),full_page=True)
            for path in ['index.html','archive.html?year=2025','archive.html?year=2026','repertoire.html','members.html','about.html']:
                go(path)
                assert page.locator('#main h1').count()==1
                for anchor in page.locator('a[href]').all():
                    href=anchor.get_attribute('href')
                    if not href or href.startswith(('http:','https:')):continue
                    response=context.request.get(base+href.split('#')[0] if not href.startswith('#') else page.url.split('#')[0])
                    assert response.ok,f'Broken internal link {href}'
            record('Six page routes and all generated internal links load under /dokbaek/')
            go('index.html')
            assert page.locator('.stat b').all_text_contents()==['3','1','13']
            assert page.locator('.year-card').count()==2
            assert page.locator('.concert-preview').first.inner_text().find('15:00')>=0
            capture('home-desktop.png')
            record('Home statistics separate recorded concerts, upcoming concerts and confirmed songs')
            go('archive.html?year=2025')
            assert page.locator('.concert-timeline .timeline-link').count()==3
            assert page.locator('.year-calendar').get_attribute('open') is None
            page.locator('.year-calendar>summary').click()
            assert page.locator('.calendar .month').count()==12
            assert page.locator('.calendar .month').nth(10).locator('a').count()==2
            assert '2025년 1월 ·' not in page.locator('[id="2025-01-family"]').inner_text()
            assert page.locator('[id="2025-11-02-gallery"] .set-item').count()==12
            assert page.locator('[id="2025-11-22-workshop"] .set-item').count()==11
            assert not page.locator('[id="2025-11-22-workshop"]').inner_text().count('시 「선물」 낭송')
            assert page.locator('.video-button').count()==0 and page.locator('iframe').count()==0
            page.locator('.month a').filter(has_text='꿈꾸는').click()
            assert page.url.endswith('#2025-11-22-workshop')
            record('Independent November calendar links, month-only date and separate event/encore records')
            go('archive.html?year=2025#2025-11-02-gallery-item-07')
            assert abs(page.locator('[id="2025-11-02-gallery-item-07"]').bounding_box()['y'])<250
            go('archive.html?year=2026')
            assert page.locator('[id="2026-10-18-gallery"] .set-item').count()==11
            assert '15:00' in page.locator('.concert-heading').inner_text()
            assert page.locator('.stat b').all_text_contents()==['0','1','0']
            capture('archive-2026-desktop.png')
            record('2026 scheduled concert: poster time, ten printed songs and added closing song')
            go('archive.html?year=1900')
            assert '아직 기록되지 않은 해' in page.locator('h1').inner_text()
            go('repertoire.html')
            assert page.locator('.song-card').count()==24
            page.locator('#song-query').fill('fly')
            assert page.locator('.song-card').count()==1
            page.locator('#filter-year').select_option('2025')
            page.locator('#filter-format').select_option('노래')
            assert page.locator('.song-card').count()==1
            page.locator('summary').click()
            assert page.locator('.history').count()==3
            page.locator('#filter-member').select_option('member-manager')
            assert page.locator('.empty-state').count()==1
            page.get_by_role('button',name='필터 초기화').click()
            assert page.locator('.song-card').count()==24
            page.locator('#song-query').fill('<img src=x onerror=alert(1)>')
            assert page.locator('.empty-state').count()==1 and page.locator('#song-results img').count()==0
            record('Combined search/year/member/format filters, reset, no results and safe query text')
            go('repertoire.html?year=2025#preludio-triston')
            assert page.locator('#preludio-triston').get_attribute('open') is not None
            page.locator('#preludio-triston .history>a').first.click()
            page.wait_for_function("() => document.getElementById('2025-11-02-gallery-item-07') !== null")
            assert '#2025-11-02-gallery-item-07' in page.url
            record('Direct song hash opens history and links to the specific concert song')
            go('members.html#member-manager')
            assert page.locator('.member-card').count()==7
            assert '매니저의 무대' in page.locator('#member-detail').inner_text()
            assert page.locator('#member-detail .empty-state').count()==1
            record('Seven original member characters, direct member hash and unconfirmed participation state')
            go('members.html#member-berry')
            assert page.locator('#member-detail .history').count()>10
            go('repertoire.html?member=member-berry#beloved')
            assert page.locator('#beloved .history').count()==2
            assert page.locator('#beloved .credit').filter(has_text='베리짱').count()==2
            page.locator('#beloved .history>a').first.click()
            page.wait_for_function("() => document.getElementById('2025-11-02-gallery-item-01') !== null")
            assert page.locator('[id="2025-11-02-gallery-item-01"] .credit').count()==2
            record('Imported repertoire: actual member participation, two Beloved histories and concert credits')
            # Exercise confirmed credits with an isolated, in-browser fixture. No source data is changed.
            fixture=json.loads((PUBLIC/'data/concerts-2025.json').read_text(encoding='utf-8'))
            fixture[0]['setlist'][1]['credits']=[{'memberId':'member-manager','role':'기타'}]
            fixture[0]['setlist'][1]['creditsStatus']='confirmed'
            page.route('**/data/concerts-2025.json',lambda route:route.fulfill(json=fixture))
            # Force a document navigation, rather than staying on the same hash URL.
            go('index.html')
            go('members.html#member-manager')
            assert page.locator('#member-detail .history').count()==1
            go('repertoire.html?member=member-manager')
            assert page.locator('.song-card').count()==1
            page.locator('summary').click()
            assert page.locator('.credit').count()==1
            page.locator('.credit').click()
            page.wait_for_function("() => document.querySelector('#member-detail .history') !== null")
            assert 'members.html#member-manager' in page.url
            page.unroute('**/data/concerts-2025.json')
            record('Confirmed member → song → concert and credit → member flow using a test-only fixture')
            go('archive.html?year=2026')
            first=page.locator('.print-button').first
            first.focus();page.keyboard.press('Enter')
            assert page.locator('#media-dialog').evaluate('(d)=>d.open')
            page.keyboard.press('Tab')
            assert page.evaluate("document.querySelector('#media-dialog').contains(document.activeElement)")
            page.keyboard.press('Escape')
            assert not page.locator('#media-dialog').evaluate('(d)=>d.open')
            assert first.evaluate('(b)=>b===document.activeElement')
            first.click();page.locator('#close-dialog').click()
            assert first.evaluate('(b)=>b===document.activeElement')
            record('Keyboard poster modal: Enter, focus containment, Escape, close button and focus return')
            # Load all reviewed public artwork, including lazy images.
            for path in ['index.html','members.html','archive.html?year=2025','archive.html?year=2026']:
                go(path)
                for img in page.locator('#main img').all():
                    img.evaluate("i=>{i.loading='eager'}")
                    img.evaluate('(i)=>i.decode()')
                    assert img.evaluate('(i)=>i.complete && i.naturalWidth>0')
            record('All original member images, group artwork and reviewed posters/programs decode successfully')
            assert not errors,errors
            assert not bad_requests,bad_requests
            record('Normal page flows have no JavaScript exceptions or failed HTTP responses')
            for width in [360,390,768,1280]:
                page.set_viewport_size({'width':width,'height':900})
                for path in ['index.html','archive.html?year=2025','archive.html?year=2026','repertoire.html','members.html','about.html']:
                    go(path)
                    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth+1'),(width,path)
                    if path=='repertoire.html':
                        assert all(float(field.evaluate('e=>getComputedStyle(e).fontSize').replace('px',''))>=16 for field in page.locator('input,select').all())
                    if width==360:
                        page.locator('.menu-toggle').click()
                        assert page.locator('#main-nav a').count()==5 and page.locator('#main-nav').is_visible()
                        page.keyboard.press('Escape')
                        assert page.locator('.menu-toggle').get_attribute('aria-expanded')=='false'
                if width==360:
                    go('index.html');capture('home-mobile-360.png')
                    go('members.html');capture('members-mobile-360.png')
            record('360/390/768/1280px: all pages fit, forms use 16px text, mobile menu stays accessible')
            # Program-book design: mobile disclosures, alternate repertoire views and sticky anchors.
            for width in [360,390]:
                page.set_viewport_size({'width':width,'height':900})
                for year in [2025,2026]:
                    go(f'archive.html?year={year}')
                    assert page.locator('.concert-jumps a').last.bounding_box()['y']<850
                    assert not page.locator('.year-calendar').evaluate('(d)=>d.open')
                    assert all(not d.evaluate('(d)=>d.open') for d in page.locator('.concert-media').all())
                    assert page.locator('.concert-jumps a').count()==page.locator('.timeline-link').count()
                    assert page.locator('.album-art').bounding_box()['y']>page.locator('.concert-jumps').bounding_box()['y']
                    cards=page.locator('.repertoire-mobile')
                    assert cards.is_visible()
                    card_records={(a.get_attribute('data-entry-id'),a.get_attribute('href'),a.locator('small').text_content()) for a in cards.locator('li a').all()}
                    table_records={(a.get_attribute('data-entry-id'),a.get_attribute('href'),a.text_content()) for a in page.locator('.repertoire-comparison td a').all()}
                    assert card_records==table_records
                    compare=page.locator('.repertoire-comparison')
                    compare.locator('summary').click()
                    page.wait_for_function("() => document.querySelector('.repertoire-mobile').hidden")
                    assert not cards.is_visible()
                    assert compare.locator('.table-wrap').is_visible()
                    assert compare.locator('.table-wrap').evaluate('(e)=>e.scrollWidth>e.clientWidth')
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                    compare.locator('summary').click()
                    page.wait_for_function("() => !document.querySelector('.repertoire-mobile').hidden")
                go('archive.html?year=2025')
                story=page.locator('.song-story').first
                assert not story.evaluate('(d)=>d.open') and not story.locator('.composer').is_visible()
                story.locator('summary').focus();page.keyboard.press('Enter')
                assert story.locator('.composer').is_visible()
                page.keyboard.press('Space');assert not story.evaluate('(d)=>d.open')
                materials=page.locator('.concert-media').first
                materials.locator('summary').focus();page.keyboard.press('Enter')
                b=materials.locator('.print-button').first;b.click()
                page.keyboard.press('Escape');assert b.evaluate('(b)=>b===document.activeElement')
                materials.locator('summary').click()
                assert not b.is_visible()
                page.locator('.timeline-link').last.click()
                assert page.url.endswith('#2025-11-22-workshop')
                go('archive.html?year=2025#2025-11-02-gallery-item-07')
                target=page.locator('[id="2025-11-02-gallery-item-07"]')
                assert target.bounding_box()['y']>=page.locator('.site-header').bounding_box()['height']
            record('Mobile quick links above fold, timeline, closed calendar/media/story, keyboard disclosures and modal focus return')
            record('Mobile repertoire cards and table have identical entry IDs, links and evidence; inactive view has no focus targets')
            record('Concert/song deep links remain visible below the measured sticky header at 360px and 390px')
            # Enlarge root/body text to 200%, keeping the viewport narrow.
            go('archive.html?year=2025')
            page.evaluate("() => {document.documentElement.style.fontSize='200%';document.body.style.fontSize='32px'}")
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            go('repertoire.html')
            page.evaluate("() => {document.documentElement.style.fontSize='200%';document.body.style.fontSize='32px';document.querySelectorAll('input,select').forEach(e=>e.style.fontSize='32px')}")
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            record('200% root/body text and enlarged form fields fit the narrow viewport')
            page.set_viewport_size({'width':1280,'height':960});go('archive.html?year=2025')
            page.screenshot(path=str(OUT/'archive-2025-desktop.png'))
            page.set_viewport_size({'width':390,'height':900});go('archive.html?year=2025')
            page.screenshot(path=str(OUT/'archive-2025-mobile.png'))
            page.set_viewport_size({'width':1280,'height':900})
            page.emulate_media(reduced_motion='reduce')
            go('archive.html?year=2025')
            assert page.locator('.guitar-decoration').get_attribute('aria-hidden')=='true'
            assert page.evaluate("getComputedStyle(document.documentElement).scrollBehavior")=='auto'
            record('Decorative guitar is hidden from assistive technology; reduced motion disables smooth scrolling')
            # Local fixture only: verify all reviewed avatar focal positions and lazy video loading.
            fixture=json.loads((PUBLIC/'data/concerts-2025.json').read_text(encoding='utf-8'))
            fixture[0]['setlist'][0]['credits']=[{'memberId':m['id'],'role':'기타'} for m in json.loads((PUBLIC/'data/members.json').read_text(encoding='utf-8'))]
            fixture[0]['setlist'][0]['credits'].append({'memberId':'member-manager','role':'노래'})
            fixture[0]['setlist'][0]['creditsStatus']='confirmed'
            fixture[0]['setlist'][0]['videoUrl']='https://www.youtube.com/watch?v=TESTVIDEO01'
            page.route('**/data/concerts-2025.json',lambda route:route.fulfill(json=fixture))
            page.route('https://www.youtube-nocookie.com/**',lambda route:route.fulfill(body='<html><body>Test-only video frame</body></html>',content_type='text/html'))
            go('index.html')
            go('archive.html?year=2025#2025-01-family-item-01')
            entry=page.locator('[id="2025-01-family-item-01"]')
            assert entry.locator('.credit').count()==7
            assert all(40<=a.bounding_box()['width']<=44 for a in entry.locator('.credit-avatar').all())
            assert entry.locator('.credit').first.locator('img').get_attribute('alt')==''
            assert page.locator('iframe').count()==0
            for img in entry.locator('img').all():img.evaluate('(i)=>i.decode()')
            entry.screenshot(path=str(OUT/'avatar-focus-fixture.png'))
            entry.locator('.video-button').click()
            assert 'autoplay' not in page.locator('iframe').get_attribute('src')
            page.keyboard.press('Escape')
            page.wait_for_function("() => !document.querySelector('iframe')")
            page.unroute('**/data/concerts-2025.json');page.unroute('https://www.youtube-nocookie.com/**')
            record('Seven reviewed 44px face crops, combined roles, decorative avatar alt and click-only video using a test fixture')
            page.route('**/image/**',lambda route:route.abort())
            go('members.html')
            page.locator('.member-card').last.scroll_into_view_if_needed()
            page.wait_for_function("() => document.querySelectorAll('.member-card .image-placeholder').length===7")
            assert all(item.bounding_box()['height']>=100 for item in page.locator('.member-card .image-wrap').all())
            page.unroute('**/image/**')
            record('Missing images show a neutral placeholder with preserved dimensions')
            # Original documents are not served by the preview server or present in the release.
            for path in ['2025/','2026/','private-notes/','2025-archive.html','dokbaek_archive_codex_prompt.md']:
                assert context.request.get(base+path).status==404
            record('Original year folders, draft, instructions and private notes are unavailable in public output')
            browser.close()
    finally:server.shutdown();server.server_close()

if __name__=='__main__':
    try:
        run()
        (OUT/'validation.md').write_text('# 검증 결과\n\n2026-10-08 · Chromium / Playwright · 로컬 공개 산출물\n\n'+'\n'.join('- PASS: '+s for s in checks)+'\n\n미검증: 실제 GitHub Actions/Pages 배포, 외부 공식 채널의 로그인·게시물 접근, 미확인 원본 내용.\n',encoding='utf-8')
        print(f'PASS: {len(checks)} browser and data checks. Screenshots and report: test-results/')
    except Exception:
        (OUT/'validation.md').write_text('# 검증 진행 결과\n\n'+'\n'.join('- PASS: '+s for s in checks)+'\n\n실패 또는 환경 제약:\n```\n'+traceback.format_exc()+'\n```\n',encoding='utf-8')
        raise
