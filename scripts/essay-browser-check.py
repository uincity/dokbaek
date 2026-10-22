"""Check the published narrative essay against its approved text and images."""
import importlib.util
import json
from threading import Thread
from playwright.sync_api import sync_playwright
from validate import ROOT, validate_dist

spec=importlib.util.spec_from_file_location('browser_check',ROOT/'scripts/browser-check.py')
shared=importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)

def run():
    validate_dist(ROOT/'dist')
    concert=next(c for c in json.loads((ROOT/'dist/data/concerts-2026.json').read_text(encoding='utf-8')) if c['id']=='2026-10-18-gallery')
    essay=concert['photoEssay']
    cover=next(m for m in concert['media'] if m.get('placement')=='cover')
    assert cover['path'].endswith('sketch-06.webp')
    server=shared.PublicServer(('127.0.0.1',0),shared.PublicHandler)
    Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page()
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            for width in (390,768,1280):
                page.set_viewport_size({'width':width,'height':900})
                page.goto(f'http://127.0.0.1:{server.server_port}/dokbaek/concert.html?year=2026&id=2026-10-18-gallery',wait_until='networkidle')
                page.wait_for_selector('.narrative-essay')
                assert page.locator('h1').inner_text()==essay['title']
                assert page.locator('.hero .eyebrow').inner_text()==essay['subtitle']
                assert page.locator('.essay-introduction').inner_text()==essay['introduction']
                assert page.locator('.essay-cover-photo img').get_attribute('data-original-src')==cover['path']
                chapters=page.locator('.essay-chapter')
                assert chapters.count()==8
                for scene,chapter in zip(chapters.all(),essay['chapters']):
                    assert scene.locator('h2').inner_text()==chapter['title']
                    assert scene.locator('.essay-chapter-text').inner_text()==chapter['text']
                    img=scene.locator('img')
                    assert img.get_attribute('data-original-src')==chapter['photo']
                    img.evaluate("async i => { i.loading='eager'; await i.decode(); }")
                    assert img.evaluate('i=>Math.abs(i.clientWidth/i.clientHeight-i.naturalWidth/i.naturalHeight)<0.02')
                assert page.locator('.essay-closing strong').inner_text()==essay['closing']['lead']
                assert page.locator('.essay-closing em').inner_text()==essay['closing']['emphasis']
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                page.locator('.essay-cover-photo button').click()
                assert page.locator('.photo-position').inner_text()=='6 / 8'
                page.keyboard.press('ArrowRight')
                assert page.locator('.photo-position').inner_text()=='7 / 8'
                page.keyboard.press('Escape')
                assert page.locator('.essay-cover-photo button').evaluate('b=>b===document.activeElement')
                assert page.locator('.set-item').count()==len(concert['setlist'])
                if width in (390,1280):
                    page.evaluate("window.scrollTo({top:0,behavior:'instant'})")
                    page.screenshot(path=str(ROOT/f'test-results/essay-{width}.png'),full_page=True)
            assert not errors,errors
            browser.close()
    finally:
        server.shutdown();server.server_close()
    print('PASS: cover 6, eight illustrated chapters, exact copy, aspect ratios, mobile layout and viewer navigation')

if __name__=='__main__':run()
