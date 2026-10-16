"""Check actual responsive selection and image requests on mobile and desktop."""
import importlib.util
from pathlib import Path
from threading import Thread
from urllib.parse import unquote, urlsplit
from playwright.sync_api import sync_playwright

spec = importlib.util.spec_from_file_location('browser_checks', Path(__file__).with_name('browser-check.py'))
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)

server = checks.PublicServer(('127.0.0.1', 0), checks.PublicHandler)
Thread(target=server.serve_forever, daemon=True).start()
base = f'http://127.0.0.1:{server.server_port}/dokbaek/'
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for width, density in [(390, 1), (390, 3), (1280, 1)]:
            context = browser.new_context(viewport={'width': width, 'height': 844}, device_scale_factor=density)
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('response', lambda response: errors.append(response.url) if response.status >= 400 else None)
            for route in ['index.html', 'about.html', 'members.html', 'archive.html?year=2026']:
                page.goto(base + route, wait_until='networkidle')
                page.wait_for_selector('#main h1')
                for image in page.locator('#main img[data-original-src]').all():
                    image.evaluate("async i => {i.loading='eager'; await i.decode();}")
                    assert image.evaluate('i => i.naturalWidth > 0'), (route, image.get_attribute('data-original-src'))
                    assert image.evaluate("i => i.currentSrc.includes('/image/optimized/')"), image.get_attribute('src')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), route
                if route == 'about.html':
                    images = page.locator('.about-moment img')
                    assert images.count() == 4
                    selected = images.first.evaluate('i => i.currentSrc')
                    rel = unquote(urlsplit(selected).path).removeprefix('/dokbaek/')
                    size = (checks.PUBLIC / rel).stat().st_size
                    assert size < 250_000, size
                    if density == 1 and width == 390:
                        assert selected.endswith('-480.webp'), selected
                    print(f'PASS: {width}px DPR {density}: about lead {size:,} bytes; all images decode')
                    if density == 1:
                        page.screenshot(path=str(checks.OUT / f'images-about-{width}.png'), full_page=True)
                if route.startswith('archive'):
                    if width < 768:
                        page.locator('.concert-media summary').first.click()
                    page.locator('.print-button:visible').first.click()
                    image = page.locator('#media-content img')
                    image.evaluate('i => i.decode()')
                    assert image.get_attribute('src') == image.get_attribute('data-original-src')
                    page.locator('#close-dialog').click()
            assert not errors, errors
            context.close()
        browser.close()
finally:
    server.shutdown()
