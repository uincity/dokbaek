"""Optional motion regression checks against dist; uses installed Playwright only."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import json
import sys
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'test-results'
checks = []
sys.stdout.reconfigure(encoding='utf-8')


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def copyfile(self, source, outputfile):
        try:
            super().copyfile(source, outputfile)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # Rapid navigation legitimately cancels pending asset responses.


def record(text):
    checks.append(text)
    print('PASS: ' + text, flush=True)


TRACK = """(() => {
  window.motionEvents=[];window.motionCLS=0;
  document.addEventListener('animationstart',e=>motionEvents.push({
    name:e.animationName, target:e.target.className.baseVal ?? e.target.className,
    row:e.target.closest('li')?.querySelector('a')?.hash, time:performance.now()
  }));
  new PerformanceObserver(list=>list.getEntries().forEach(e=>{
    if(!e.hadRecentInput)motionCLS+=e.value;
  })).observe({type:'layout-shift',buffered:true});
})()"""
STATIC = """() => [...document.querySelectorAll(
  '.album-cover h1,.album-cover .lede,.album-art,.concert-timeline li'
)].every(e=>getComputedStyle(e).opacity==='1' && getComputedStyle(e).transform==='none')"""


def run():
    OUT.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(ROOT / 'dist')))
    Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}/'
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(viewport={'width':390,'height':420})
            context.add_init_script(TRACK)
            # External video thumbnails are unrelated to local motion checks.
            context.route('https://**/*', lambda route: route.abort())
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))

            def go(year=2025, suffix=''):
                page.goto(f'{base}archive.html?year={year}{suffix}', wait_until='domcontentloaded')
                page.wait_for_selector('.concert-timeline')

            def finish():
                page.wait_for_timeout(1400)
                assert page.evaluate(STATIC)
                assert page.evaluate("document.getAnimations().length===0")

            for width in (360, 390, 768, 1280):
                page.set_viewport_size({'width':width,'height':420})
                for year in (2025, 2026):
                    go(year)
                    assert page.locator('.guitar-string').count() == 6
                    page.wait_for_timeout(350)
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                    # Exclude pre-existing font swaps and lazy-media loading from motion CLS.
                    page.evaluate("async () => {await document.fonts.ready;await Promise.all([...document.images].map(i=>{i.loading='eager';return i.decode().catch(()=>{})}));}")
                    page.evaluate('motionCLS=0')
                    finish()
                    strings = page.evaluate("motionEvents.filter(e=>e.name==='guitar-pluck')")
                    assert len(strings) == 6, strings
                    assert strings[-1]['time'] - strings[0]['time'] >= 250
                    assert page.locator('.album-art').get_attribute('aria-hidden') == 'true'
                    assert page.locator('.album-art').get_attribute('tabindex') is None
                    # Reveal each row near the bottom, then revisit without replay.
                    for row in page.locator('.concert-timeline li').all():
                        row.evaluate("e=>e.scrollIntoView({block:'end',behavior:'instant'})")
                        page.wait_for_timeout(700)
                    events = page.evaluate("motionEvents.filter(e=>e.name==='timeline-enter')")
                    assert len({e['row'] for e in events}) == len(events)
                    assert events, (width, year)
                    assert page.evaluate("motionEvents.some(e=>e.name==='timeline-line')")
                    count = len(events)
                    page.evaluate("scrollTo({top:0,behavior:'instant'})")
                    page.locator('.concert-timeline').evaluate("e=>e.scrollIntoView({behavior:'instant'})")
                    page.wait_for_timeout(700)
                    assert page.evaluate("motionEvents.filter(e=>e.name==='timeline-enter').length") == count
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                    assert page.evaluate('motionCLS') < .01
                    page.screenshot(path=str(OUT / f'motion-{year}-{width}.png'))
            record('Both years at 360/390/768/1280px: six sequential finite plucks, one-time rows/line, no horizontal overflow or motion CLS')

            page.set_viewport_size({'width':1280,'height':900})
            go();finish()
            page.locator('.album-art').hover();finish()
            assert page.evaluate("motionEvents.filter(e=>e.name==='guitar-pluck').length") == 12
            page.locator('.concert-jumps a').first.focus();finish()
            assert page.evaluate("motionEvents.filter(e=>e.name==='guitar-pluck').length") == 18
            record('Desktop pointer and existing cover-link focus replay once without adding decorative focus targets')

            page.emulate_media(reduced_motion='reduce')
            for year in (2025, 2026):
                go(year)
                assert page.evaluate(STATIC)
                assert page.evaluate('document.getAnimations().length===0')
                assert page.evaluate("getComputedStyle(document.documentElement).scrollBehavior==='auto'")
            page.emulate_media(reduced_motion='no-preference')
            go();page.emulate_media(reduced_motion='reduce')
            assert page.evaluate(STATIC)
            assert page.evaluate('document.getAnimations().length===0')
            record('Reduced motion at load and live preference change immediately reveal all content and stop animations')
            page.emulate_media(reduced_motion='no-preference')

            for year in (2025, 2026):
                data = json.loads((ROOT / 'dist' / 'data' / f'concerts-{year}.json').read_text(encoding='utf-8'))
                for concert in data:
                    go(year, '#' + concert['id'])
                    assert page.evaluate(STATIC)
                    target = page.locator('[id="' + concert['id'] + '"]')
                    page.wait_for_function("id=>Math.abs(document.getElementById(id).getBoundingClientRect().top)<250", arg=concert['id'])
                    assert target.bounding_box()['y'] >= page.locator('.site-header').bounding_box()['height']
                go(year, '#' + data[0]['setlist'][0]['id'])
                assert page.evaluate(STATIC)
            go()
            page.locator('.concert-jumps a').first.focus()
            page.keyboard.press('Enter')
            page.wait_for_function("location.hash.length>1")
            assert page.evaluate(STATIC)
            page.locator('.year-tabs a').filter(has_text='2026').click()
            page.wait_for_selector('h1:text("2026")')
            page.go_back(wait_until='domcontentloaded')
            page.wait_for_selector('.concert-timeline')
            assert page.evaluate(STATIC)
            record('All concert and representative song deep links, keyboard quick links, year tabs and browser back preserve readable targets')

            for setup in (
                'delete window.IntersectionObserver',
                "window.IntersectionObserver=class {constructor(){throw Error('test')}}",
                "window.IntersectionObserver=class {observe(){throw Error('test')} disconnect(){}}",
            ):
                fallback = context.new_page();fallback.add_init_script(setup)
                fallback.goto(base + 'archive.html?year=2025')
                fallback.wait_for_selector('.concert-timeline')
                assert fallback.locator('.concert-timeline li').count() == 3
                assert fallback.evaluate("() => [...document.querySelectorAll('.concert-timeline li')].every(e=>getComputedStyle(e).opacity==='1')")
                fallback.close()
            record('Absent observer, constructor failure and observe failure keep every concert visible')

            page.set_viewport_size({'width':360,'height':900})
            go();finish()
            page.evaluate("document.documentElement.style.fontSize='200%';document.body.style.fontSize='32px'")
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            page.locator('.concert-jumps a').first.click()
            page.wait_for_function("location.hash.length>1")
            assert page.evaluate(STATIC)
            go();page.evaluate("dispatchEvent(new PageTransitionEvent('pagehide'))")
            assert page.evaluate(STATIC)
            assert page.evaluate('document.getAnimations().length===0')
            assert not errors, errors
            record('200% text with functional anchors; pagehide cleanup; no uncaught browser errors')
            browser.close()
    finally:
        server.shutdown();server.server_close()


if __name__ == '__main__':
    run()
    (OUT / 'motion-validation.md').write_text(
        '# 모션 검증\n\n2026-10-11 · Chromium / Playwright · 로컬 dist\n\n' +
        '\n'.join('- PASS: ' + item for item in checks) +
        '\n\n실제 GitHub Pages 배포 및 Safari/Firefox 실기기 검증은 미실행.\n', encoding='utf-8')
