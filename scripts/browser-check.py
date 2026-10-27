"""Optional end-to-end checks. Requires an installed Playwright and Chromium."""
from pathlib import Path, PurePosixPath
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlsplit, unquote, parse_qs
from threading import Thread
from datetime import datetime, timezone, timedelta
import base64, json, sys, traceback
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
    def list_directory(self,path):
        self.send_error(404,'Directory listings are unavailable')
        return None
    def copyfile(self,source,outputfile):
        try:super().copyfile(source,outputfile)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass

def record(label):checks.append(label);print('PASS: '+label,flush=True)

class PublicServer(ThreadingHTTPServer):
    # Browser navigations/lazy artwork can briefly open many parallel connections.
    request_queue_size=128

def run():
    validate_dist(PUBLIC);record('Public allowlist, references, dates, evidence states and privacy scan')
    server=PublicServer(('127.0.0.1',0),PublicHandler)
    Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}{PREFIX}'
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            context=browser.new_context(viewport={'width':1280,'height':900},locale='ko-KR',has_touch=True)
            # Keep local regression checks independent of thumbnail CDN availability.
            thumbnail=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGP4DwQACfsD/fteaysAAAAASUVORK5CYII=')
            context.route('https://i.ytimg.com/**',lambda route:route.fulfill(body=thumbnail,content_type='image/png'))
            page=context.new_page();errors=[];bad_requests=[]
            # Stable reference date; do not depend on the machine running this check.
            page.clock.set_fixed_time(datetime(2026,10,20,3,tzinfo=timezone.utc))
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
                page.evaluate("() => { document.activeElement?.blur(); window.scrollTo({top:0,behavior:'instant'}); }")
                page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
                page.screenshot(path=str(OUT/name),full_page=True)
            def check_unit_media():
                events=json.loads((PUBLIC/'data/unit-performances.json').read_text(encoding='utf-8'))
                expected={event['id']:event['media'] for event in events}
                for width in [320,375,390,768,1280]:
                    page.set_viewport_size({'width':width,'height':900});go('unit.html')
                    for event_id,media in expected.items():
                        card=page.locator(f'#{event_id}')
                        images=card.locator('.unit-media img')
                        assert images.count()==len(media)
                        for img,item in zip(images.all(),media):
                            img.evaluate("i => { i.loading='eager'; return i.decode(); }")
                            assert img.get_attribute('data-original-src')==item['path']
                            assert img.get_attribute('alt')==item['label']
                            assert unquote(urlsplit(img.get_attribute('src')).path)==item['path']
                            assert img.get_attribute('loading')=='eager'  # forced only for this check
                            assert img.get_attribute('decoding')=='async'
                            assert img.evaluate('(i)=>[i.naturalWidth,i.naturalHeight]')==[item['width'],item['height']]
                            assert [int(img.get_attribute(k)) for k in ['width','height']]==[item['width'],item['height']]
                            assert img.evaluate('(i)=>getComputedStyle(i).objectFit')=='contain'
                            box=img.bounding_box()
                            assert abs(box['height']-box['width']*item['height']/item['width'])<1
                        buttons=card.locator('.unit-media-grid').first.locator('.unit-media-button')
                        if buttons.count()==2:
                            first,second=[button.bounding_box() for button in buttons.all()]
                            if width>=600:
                                assert second['x']>first['x'] and abs(second['y']-first['y'])<1
                            else:
                                assert second['y']>=first['y']+first['height']
                    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth+1')
                    poster=page.locator('#sunset-20261024 .unit-poster').bounding_box()
                    info=page.locator('#sunset-20261024 .unit-copy').bounding_box()
                    assert poster['y']>=info['y']+info['height']
                    assert page.locator('#sunset-20261024 .pill').inner_text()=='공연 완료'
                    assert page.locator('#sunset-20261024 .unit-media-heading').all_text_contents()==['현장 스케치','공연 포스터']
                    if width in [375,1280]:capture(f'small-stages-media-{width}.png')
                record('Seven original images: exact event/path/alt, decoded dimensions, uncropped ratios, 320/375/390/768/1280px gallery and poster layouts')
                page.set_viewport_size({'width':375,'height':900});go('unit.html')
                button=page.locator('#wedding-20251207 .unit-media-button').first
                button.focus();page.keyboard.press('Enter')
                assert page.locator('#media-dialog').evaluate('(d)=>d.open')
                assert page.locator('#media-title').inner_text()=='첫 번째 결혼축가 현장 스케치 1'
                page.locator('#media-content img').evaluate('(i)=>i.decode()')
                page.keyboard.press('Escape')
                assert not page.locator('#media-dialog').evaluate('(d)=>d.open')
                assert button.evaluate('(b)=>b===document.activeElement')
                poster_button=page.locator('#sunset-20261024 .unit-poster .unit-media-button')
                poster_button.click();page.locator('#close-dialog').click()
                assert poster_button.evaluate('(b)=>b===document.activeElement')
                record('Sketch and poster reuse the modal with keyboard/touch opening, Escape/close and focus return')
                reordered=list(reversed(events))
                page.route('**/data/unit-performances.json',lambda route:route.fulfill(json=reordered))
                go('unit.html')
                for event_id,media in expected.items():
                    assert page.locator(f'#{event_id} .unit-media img').first.get_attribute('data-original-src')==media[0]['path']
                page.unroute('**/data/unit-performances.json')
                empty=[{key:value for key,value in event.items() if key!='media'} for event in events]
                page.route('**/data/unit-performances.json',lambda route:route.fulfill(json=empty))
                go('unit.html')
                assert page.locator('.unit-media, .unit-card .image-placeholder').count()==0
                page.unroute('**/data/unit-performances.json')
                broken_path=expected['wedding-20251207'][0]['path']
                def broken_match(url):return unquote(urlsplit(url).path).endswith('/'+broken_path)
                page.route(broken_match,lambda route:route.abort())
                go('unit.html')
                broken=page.locator('#wedding-20251207 .unit-media-button').first
                broken.scroll_into_view_if_needed()
                page.wait_for_function('() => document.querySelector("#wedding-20251207 .unit-media-button").disabled')
                assert broken.locator('img').count()==0
                assert broken.locator('.image-placeholder').count()==1
                assert '불러오지 못했습니다' in broken.inner_text()
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth+1')
                page.unroute(broken_match)
                go('index.html')
                assert page.locator('#small-stages img, #small-stages .unit-media').count()==0
                assert page.locator('.stat b').all_text_contents()==['7','1','26']
                record('Reordered events keep their own images; absent media is omitted, failed images show a stable text fallback, home preview remains compact')
                page.set_viewport_size({'width':1280,'height':900})
            if '--unit-preview' in sys.argv:
                check_unit_media()
                for width in [375,1280]:
                    page.set_viewport_size({'width':width,'height':900})
                    go('unit.html')
                    assert page.locator('.unit-hero h1').bounding_box()['y']>page.locator('.site-header').bounding_box()['height']
                    assert page.locator('.unit-hero .eyebrow').is_visible()
                    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                    capture(f'small-stages-{width}.png')
                record('Small-stage desktop/mobile previews have an unobscured hero and no horizontal overflow')
                browser.close()
                return
            check_unit_media()
            checked_links=set()
            for path in ['index.html','archive.html?year=2025','archive.html?year=2026','unit.html','repertoire.html','members.html','about.html']:
                go(path)
                assert page.locator('.site-header .brand-logo').get_attribute('src')=='image/dokbaek_logo_horizontal.png'
                assert page.locator('.footer-logo').count()==1
                assert page.locator('a[href="https://www.youtube.com/@dokback-u4l"]').count()==1
                assert page.locator('a[href="https://www.instagram.com/stringband.dokbaek/"]').count()==1
                assert page.locator('#footer-links .channel-icon').count()==2
                assert page.locator('.footer-inquiry').count()==1
                assert page.locator('.footer-inquiry').get_attribute('href').startswith('mailto:uuincity@naver.com?')
                for venue in page.locator('.venue-link').all():
                    assert venue.get_attribute('href')=='https://naver.me/xMni5Yd6'
                    assert venue.get_attribute('target')=='_blank'
                    assert venue.get_attribute('rel')=='noopener noreferrer'
                assert page.locator('a a').count()==0
                assert page.locator('#main h1').count()==1
                assert page.locator('#main-nav a[href="unit.html"]').count()==1
                assert page.locator('.footer-nav a[href="unit.html"]').count()==1
                for anchor in page.locator('a[href]').all():
                    href=anchor.get_attribute('href')
                    if not href or href.startswith(('http:','https:','mailto:')):continue
                    target=base+href.split('#')[0] if not href.startswith('#') else page.url.split('#')[0]
                    if target not in checked_links:
                        response=context.request.get(target)
                        assert response.ok,f'Broken internal link {href}'
                        checked_links.add(target)
            record('Seven page routes, small-stage header/footer navigation and generated links load under /dokbaek/')
            go('unit.html')
            assert page.locator('h1').inner_text()=='독백의 작은 무대'
            assert page.locator('#main-nav a[aria-current="page"]').inner_text()=='작은 무대'
            assert page.locator('#unit-upcoming .unit-card').count()==0
            assert page.locator('#unit-past .unit-card').count()==3
            assert page.locator('#unit-past .unit-card').first.get_attribute('id')=='sunset-20261024'
            assert page.locator('#wedding-20251207 .unit-count').inner_text()=='3명 참여 · 2곡'
            assert page.locator('#wedding-20251227 .unit-count').inner_text()=='5명 참여 · 2곡'
            assert page.locator('#sunset-20261024 .unit-count').inner_text()=='2명 참여 · 1곡'
            assert page.locator('.unit-card img').count()==7
            assert page.locator('.unit-card video, .unit-card .image-placeholder').count()==0
            assert page.locator('.unit-date').first.get_attribute('datetime')=='2026-10-24'
            summary=page.locator('#wedding-20251207 summary')
            summary.focus();page.keyboard.press('Enter')
            assert page.locator('#wedding-20251207 details').get_attribute('open') is not None
            assert '기타 · 멜로디언' in page.locator('#wedding-20251207 .unit-program').inner_text()
            assert page.locator('#wedding-20251207 .unit-program>ol>li').count()==2
            assert page.locator('#wedding-20251207 .unit-program>ol>li').nth(1).locator('.unit-performers>li').count()==3
            capture('small-stages-desktop.png')
            page.clock.set_fixed_time(datetime(2027,1,1,3,tzinfo=timezone.utc))
            go('unit.html')
            assert page.locator('#unit-past #sunset-20261024 .pill').inner_text()=='공연 완료'
            page.clock.set_fixed_time(datetime(2026,10,20,3,tzinfo=timezone.utc))
            go('index.html')
            assert page.locator('#small-stages .unit-card').count()==2
            assert page.locator('#small-stages .unit-card').first.get_attribute('data-unit-id')=='sunset-20261024'
            assert page.locator('#small-stages .unit-card').last.get_attribute('data-unit-id')=='wedding-20251227'
            assert page.locator('#small-stages').bounding_box()['y']>page.locator('#past-shows').bounding_box()['y']
            record('Small stages: 3 events / 5 songs, exact members and roles, keyboard details, preview ordering and explicit status after 2026')
            go('index.html')
            assert page.locator('.stat b').all_text_contents()==['7','1','26']
            assert page.locator('.year-card').count()==2
            poster_path='2026/포스터/포스터_수녀원 음악회(20261108)_5.png'
            assert page.locator('.upcoming-poster img').get_attribute('data-original-src')==poster_path
            assert page.locator('.upcoming-feature').get_attribute('data-concert-id')=='2026-11-08-convent'
            assert '2026년 11월 8일(일)' in page.locator('.show-date').inner_text()
            assert page.locator('#past-shows .concert-preview').first.locator('.preview-main').get_attribute('href').endswith('#2026-10-18-gallery')
            assert page.locator('#past-shows .concert-preview').first.locator('.pill').inner_text()=='종료 공연'
            assert page.locator('#past-shows .section-head a').get_attribute('href')=='archive.html?year=2026'
            assert page.locator('.upcoming-copy .button').last.get_attribute('href').endswith('#2026-11-08-convent-program')
            assert page.locator('.upcoming-program li').count()==11
            assert page.locator('.upcoming-poster').bounding_box()['x']>page.locator('.upcoming-copy').bounding_box()['x']
            assert page.locator('.home-hero .group-art img').get_attribute('data-original-src')=='image/집단적독백밴드 전체사진3.png'
            assert 'Gowun Batang' in page.locator('h1').evaluate('e=>getComputedStyle(e).fontFamily')
            assert page.locator('#upcoming').bounding_box()['y'] < page.locator('.music-highlights').bounding_box()['y']
            assert page.locator('meta[property="og:image"]').get_attribute('content').startswith('https://uincity.github.io/dokbaek/')
            card=page.locator('.performance-inquiry')
            assert page.locator('#main>section:last-child').get_attribute('id')=='performance-inquiry'
            assert card.bounding_box()['y']>page.locator('.music-highlights').bounding_box()['y']
            mail=urlsplit(card.locator('.inquiry-send').get_attribute('href'))
            assert mail.scheme=='mailto' and mail.path=='uuincity@naver.com'
            query=parse_qs(mail.query)
            assert query['subject']==['[집단적독백] 공연 초청 문의']
            expected_body='안녕하세요. 집단적독백 공연 초청을 문의드립니다.\n\n1. 문의자 / 단체명:\n2. 연락 가능한 이메일:\n3. 공연 희망 날짜 및 시간:\n4. 공연 장소:\n5. 행사 성격 및 예상 관객:\n6. 기타 요청사항:\n\n감사합니다.'
            assert query['body']==[expected_body]
            assert not card.locator('#inquiry-status').text_content()
            page.evaluate("Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>{window.copiedInquiry=text}}})")
            card.locator('.inquiry-copy').click()
            page.wait_for_function("document.querySelector('#inquiry-status').textContent.includes('복사했습니다')")
            assert page.evaluate('window.copiedInquiry')=='uuincity@naver.com'
            page.evaluate("Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async()=>{throw new Error('denied')}}})")
            card.locator('.inquiry-copy').click()
            page.wait_for_function("document.querySelector('#inquiry-status').textContent.includes('직접 선택')")
            assert card.locator('#inquiry-status').get_attribute('role')=='status'
            assert card.locator('#inquiry-address').evaluate('(e)=>e===document.activeElement && e.readOnly && e.selectionEnd-e.selectionStart===e.value.length')
            record('Inquiry is last in home content; exact mailto recipient/subject/body, clipboard success/failure feedback and manual selection fallback')
            go('index.html')
            capture('home-desktop.png')
            record('Home statistics show recorded concerts, upcoming concerts and 26 member repertoire songs')
            go('archive.html?year=2025')
            assert page.locator('.concert-timeline .timeline-link').count()==5
            assert page.locator('.year-calendar').get_attribute('open') is None
            page.locator('.year-calendar>summary').click()
            assert page.locator('.calendar .month').count()==12
            assert page.locator('.calendar .month').nth(10).locator('a').count()==2
            assert '2025년 1월 ·' not in page.locator('[id="2025-01-family"]').inner_text()
            assert page.locator('[id="2025-11-02-gallery"] .set-item').count()==12
            assert page.locator('[id="2025-11-22-workshop"] .set-item').count()==11
            assert not page.locator('[id="2025-11-22-workshop"]').inner_text().count('시 「선물」 낭송')
            assert page.locator('.video-button').count()==20 and page.locator('iframe').count()==0
            assert page.locator('.video-card .video-thumbnail').count()==20
            assert page.locator('.rehearsal-video a').get_attribute('href')=='https://www.youtube.com/watch?v=x-biPXwf0p4'
            preludio=page.locator('[id="2025-11-02-gallery-item-07"]')
            assert preludio.locator('.video-thumbnail').get_attribute('href').endswith('Ti47YVDMfYk&t=68s')
            preludio.locator('.video-button').click()
            assert page.locator('iframe').get_attribute('src').endswith('Ti47YVDMfYk?start=68')
            page.keyboard.press('Escape')
            page.locator('.month a').filter(has_text='꿈꾸는').click()
            assert page.url.endswith('#2025-11-22-workshop')
            record('Independent November calendar links, month-only date and separate event/encore records')
            go('archive.html?year=2025#2025-11-02-gallery-item-07')
            anchor_y=page.locator('[id="2025-11-02-gallery-item-07"]').bounding_box()['y']
            assert page.locator('.site-header').bounding_box()['height']<=anchor_y<page.viewport_size['height']
            go('archive.html?year=2026')
            assert page.locator('[id="2026-10-18-gallery"] .set-item').count()==11
            assert '15:00' in page.locator('[id="2026-10-18-gallery"] .concert-heading').inner_text()
            assert page.locator('.stat b').all_text_contents()==['2','1','11']
            assert page.locator('[data-status="scheduled"] .concert-section').count()==1
            assert page.locator('[data-status="completed"] .concert-section').count()==2
            assert page.locator('[id="2026-11-08-convent"] .set-item').count()==11
            assert page.locator('[id="2026-10-18-gallery"] .pill').filter(has_text='진행 계획').count()==0
            assert page.locator('[id="2026-11-08-convent"] .pill').filter(has_text='진행 계획').count()==11
            assert page.locator('[id="2026-10-18-gallery"] .concert-info .pill').inner_text()=='종료 공연'
            assert '공연 예정' not in page.locator('[id="2026-10-18-gallery"]').inner_text()
            capture('archive-2026-desktop.png')
            record('2026: No.4 completed with 11 confirmed performed songs; No.5 remains scheduled with 11 planned songs')
            go('archive.html?year=1900')
            assert '아직 기록되지 않은 해' in page.locator('h1').inner_text()
            go('repertoire.html')
            assert page.locator('.song-card').count()==26
            assert page.locator('#hua-kai-gu-ren-lai, #ave-maria-gounod').count()==0
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
            assert page.locator('.song-card').count()==26
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
            assert page.locator('#member-detail .history').count()==7
            assert page.locator('#member-detail .empty-state').count()==0
            record('Seven original member characters, direct member hash and seven manager song participations including small stages')
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
            fixture_next=json.loads((PUBLIC/'data/concerts-2026.json').read_text(encoding='utf-8'))
            for c in fixture+fixture_next:
                for entry in c['setlist']:
                    entry['credits']=[cr for cr in entry['credits'] if cr['memberId']!='member-manager']
            fixture[0]['setlist'][1]['credits']=[{'memberId':'member-manager','role':'기타'}]
            fixture[0]['setlist'][1]['guestCredits']=[]
            fixture[0]['setlist'][1]['creditsStatus']='confirmed'
            page.route('**/data/concerts-2025.json',lambda route:route.fulfill(json=fixture))
            page.route('**/data/concerts-2026.json',lambda route:route.fulfill(json=fixture_next))
            page.route('**/data/unit-performances.json',lambda route:route.fulfill(json=[]))
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
            page.unroute('**/data/concerts-2026.json')
            page.unroute('**/data/unit-performances.json')
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
            # Shared metadata must agree in every performance and repertoire view.
            song_info={s['id']:s for s in json.loads((PUBLIC/'data/songs.json').read_text(encoding='utf-8'))}
            for year in [2025,2026]:
                go(f'archive.html?year={year}')
                for c in json.loads((PUBLIC/f'data/concerts-{year}.json').read_text(encoding='utf-8')):
                    for e in c['setlist']:
                        if e['kind']!='song':continue
                        s=song_info[e['songId']]
                        info=page.locator(f'[id="{e["id"]}"] .song-information')
                        assert info.locator('.composer').text_content()=='작곡가(가수) · '+s['artistCredit']
                        assert info.locator('.song-genre').text_content()=='장르 · '+s['genre']
                        assert info.locator('.song-description').text_content()==s['note']
            go('repertoire.html')
            member_song_ids={e['songId'] for year in [2025,2026] for c in json.loads((PUBLIC/f'data/concerts-{year}.json').read_text(encoding='utf-8')) for e in c['setlist'] if e['kind']=='song' and e['credits']}
            assert len(member_song_ids)==26 and {'hua-kai-gu-ren-lai','ave-maria-gounod'}.isdisjoint(member_song_ids)
            for song_id in member_song_ids:
                s=song_info[song_id]
                info=page.locator(f'#{song_id} .song-information')
                assert info.locator('.composer').text_content()=='작곡가(가수) · '+s['artistCredit']
                assert info.locator('.song-genre').text_content()=='장르 · '+s['genre']
                assert info.locator('.song-description').text_content()==s['note']
            record(f'All concert song stories and {len(member_song_ids)} member repertoire entries share the exact credit, genre and description')
            for width in [320,360,375,390,430,768,1024,1280]:
                page.set_viewport_size({'width':width,'height':900})
                for path in ['index.html','archive.html?year=2025','archive.html?year=2026','unit.html','repertoire.html','members.html','about.html']:
                    go(path)
                    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth+1'),(width,path)
                    if path=='repertoire.html':
                        assert all(float(field.evaluate('e=>getComputedStyle(e).fontSize').replace('px',''))>=16 for field in page.locator('input,select').all())
                    if path=='index.html':
                        assert page.locator('.inquiry-send').bounding_box()['height']>=44
                        assert page.locator('.inquiry-copy').bounding_box()['height']>=44
                        assert float(page.locator('#inquiry-address').evaluate('e=>getComputedStyle(e).fontSize').replace('px',''))>=16
                    if path=='unit.html':
                        for summary in page.locator('.unit-program>summary').all():
                            summary.click()
                        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth+1'),(width,'unit details')
                        assert all(control.bounding_box()['height']>=44 for control in page.locator('.unit-program>summary, .unit-members a, .unit-performers a').all())
                        if width==375:capture('small-stages-mobile-375.png')
                    if width==360:
                        page.locator('.menu-toggle').click()
                        assert page.locator('#main-nav a').count()==6 and page.locator('#main-nav').is_visible()
                        page.keyboard.press('Escape')
                        assert page.locator('.menu-toggle').get_attribute('aria-expanded')=='false'
                if width==360:
                    go('index.html');capture('home-mobile-360.png')
                    go('members.html');capture('members-mobile-360.png')
            record('320/360/375/390/430/768/1024/1280px: all pages fit, forms use 16px text, mobile menu stays accessible')
            page.set_viewport_size({'width':360,'height':800});go('index.html')
            assert page.locator('.upcoming-feature .button').first.bounding_box()['y']<800
            page.locator('.menu-toggle').click()
            page.locator('.home-hero h1').click()
            assert page.locator('.menu-toggle').get_attribute('aria-expanded')=='false'
            capture('home-mobile-360.png')
            for width in [390,768]:
                page.set_viewport_size({'width':width,'height':844});go('index.html');capture(f'home-{width}.png')
            for width in [360,390,768,1280]:
                page.set_viewport_size({'width':width,'height':900});go('index.html')
                assert page.locator('.upcoming-poster img').evaluate("i=>getComputedStyle(i).objectFit==='contain'")
                page.locator('.upcoming-program summary').tap()
                upcoming=next(c for c in json.loads((PUBLIC/'data/concerts-2026.json').read_text(encoding='utf-8')) if c['id']=='2026-11-08-convent')
                expected=[entry['title'] for entry in upcoming['setlist']]
                assert page.locator('.upcoming-program li a').all_text_contents()==expected
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                page.locator('.upcoming-poster').tap()
                original=page.locator('#media-content img')
                original.evaluate('i=>i.decode()')
                assert unquote(original.get_attribute('src'))==poster_path
                assert original.get_attribute('alt').startswith(upcoming['title']+' · 2026년 11월 8일(일)')
                page.locator('#close-dialog').tap()
                assert not page.locator('#media-dialog').evaluate('d=>d.open')
                assert page.locator('.upcoming-poster').evaluate('b=>b===document.activeElement')
                page.locator('.upcoming-copy .button').last.tap()
                page.wait_for_function("()=>document.getElementById('2026-11-08-convent-program')!==null")
                target=page.locator('[id="2026-11-08-convent-program"]')
                assert target.bounding_box()['y']>=page.locator('.site-header').bounding_box()['height']-1
                assert target.locator('.set-item').count()==11
            record('Upcoming program preview/order, full original poster URL/alt, touch open/close/focus return and program deep links at 360/390/768/1280px')
            # Display classification follows Seoul dates; song evidence stays unchanged.
            # Check regular concerts separately; small stages keep their editorial status.
            page.route('**/data/unit-performances.json',lambda route:route.fulfill(json=[]))
            page.clock.set_fixed_time(datetime(2027,1,1,3,tzinfo=timezone.utc));go('index.html')
            assert page.locator('.upcoming-feature').count()==0
            assert '다음 공연을 준비 중' in page.locator('#upcoming').inner_text()
            assert page.locator('.schedule-pending').count()==0
            assert page.locator('#past-shows .concert-preview').count()==2
            assert page.locator('#past-shows .concert-preview').first.locator('.preview-main').get_attribute('href').endswith('#2026-11-08-convent')
            assert page.locator('.stat b').all_text_contents()==['5','0','26']
            page.clock.set_fixed_time(datetime(2026,11,8,14,59,59,tzinfo=timezone.utc));go('index.html')
            assert page.locator('.upcoming-feature').count()==1
            page.clock.set_fixed_time(datetime(2026,11,8,15,tzinfo=timezone.utc));go('archive.html?year=2026')
            assert page.locator('[data-status="scheduled"]').count()==0
            assert page.locator('[data-status="completed"] .concert-section').count()==2
            assert page.locator('.concert-section').first.get_attribute('id')=='2026-11-08-convent'
            assert page.locator('[id="2026-11-08-convent"] .pill').filter(has_text='진행 계획').count()==11
            page.clock.set_fixed_time(datetime(2026,10,20,3,tzinfo=timezone.utc))
            page.unroute('**/data/unit-performances.json')
            record('360×800 upcoming CTA, outside-click menu close, restored group artwork and serif headings, consistent branding/channels, static sharing metadata and expired schedule fallback')
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
                    card_records={(a.get_attribute('data-entry-id'),a.get_attribute('href'),a.locator('small').text_content() if a.locator('small').count() else '') for a in cards.locator('li a').all()}
                    table_records={(a.get_attribute('data-entry-id'),a.get_attribute('href'),a.text_content().removeprefix('수록').strip(' ·')) for a in page.locator('.repertoire-comparison td a').all()}
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
                assert materials.evaluate('(d)=>d.open')
                b=materials.locator('.print-button').first;b.click()
                page.keyboard.press('Escape');assert b.evaluate('(b)=>b===document.activeElement')
                materials.locator('summary').click()
                assert not b.is_visible()
                page.locator('.timeline-link[href="#2025-11-22-workshop"]').click()
                assert page.url.endswith('#2025-11-22-workshop')
                go('archive.html?year=2025#2025-11-02-gallery-item-07')
                target=page.locator('[id="2025-11-02-gallery-item-07"]')
                assert target.bounding_box()['y']>=page.locator('.site-header').bounding_box()['height']
            record('Mobile quick links above fold, timeline, closed calendar/story/media with keyboard toggles and modal focus return')
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
            fixture[0]['setlist'][0]['guestCredits']=[]
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
            record('Only the two explicitly requested posters are released from original year folders; directory listings, drafts, instructions and private notes stay unavailable')
            for response_body in [None, '{broken json', '[{"id":"broken"}]']:
                def fail_unit(route, request, body=response_body):
                    route.fulfill(status=503 if body is None else 200, body=body or 'Unavailable', content_type='application/json')
                page.route('**/data/unit-performances.json',fail_unit)
                for path in ['index.html','unit.html']:
                    go(path)
                    assert page.locator('.unit-error[role="alert"]').count()==1
                    assert page.locator('#footer-links .channel-icon').count()==2
                    if path=='index.html':
                        assert page.locator('.stat b').all_text_contents()==['4','1','26']
                        assert page.locator('#past-shows .concert-preview').count()==2
                page.unroute('**/data/unit-performances.json',fail_unit)
            record('Missing, malformed and invalid small-stage JSON shows an accessible error while official home/archive data remains available')
            assert not errors,errors
            browser.close()
    finally:server.shutdown();server.server_close()

if __name__=='__main__':
    try:
        run()
        checked_date=datetime.now(timezone(timedelta(hours=9))).date().isoformat()
        report_name='unit-visual.md' if '--unit-preview' in sys.argv else 'validation.md'
        (OUT/report_name).write_text(f'# 검증 결과\n\n{checked_date} · Chromium / Playwright · 로컬 공개 산출물\n\n'+'\n'.join('- PASS: '+s for s in checks)+'\n\n영상 썸네일 CDN은 시험용 이미지로 대체했습니다.\n미검증: 실제 GitHub Actions/Pages 배포, 외부 CDN·공식 채널의 로그인·게시물 접근, 미확인 원본 내용.\n',encoding='utf-8')
        print(f'PASS: {len(checks)} browser and data checks. Screenshots and report: test-results/')
    except Exception:
        (OUT/'validation.md').write_text('# 검증 진행 결과\n\n'+'\n'.join('- PASS: '+s for s in checks)+'\n\n실패 또는 환경 제약:\n```\n'+traceback.format_exc()+'\n```\n',encoding='utf-8')
        raise
