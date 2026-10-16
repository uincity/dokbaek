"""Regenerate reviewed responsive assets. Requires Pillow only when regenerating."""
from pathlib import Path
import hashlib
import json
import re
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
manifest_path = ROOT / 'scripts/public-files.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
originals = [p for p in manifest['images'] + manifest['media'] if not p.startswith('image/optimized/')]
output = ROOT / 'image/optimized'
output.mkdir(exist_ok=True)
sources = {}
generated = []
original_bytes = optimized_bytes = 0
for path in originals:
    with Image.open(ROOT / path) as source:
        picture = ImageOps.exif_transpose(source).convert('RGBA' if 'A' in source.getbands() else 'RGB')
        width, height = picture.size
        # ASCII names avoid whitespace ambiguity in srcset candidates.
        name = hashlib.sha256(path.encode('utf-8')).hexdigest()[:16]
        variants = []
        for size in sorted({min(width, size) for size in (160, 480, 800, 1200)}):
            rel = f'image/optimized/{name}-{size}.webp'
            resized = picture.resize((size, max(1, round(height * size / width))), Image.Resampling.LANCZOS)
            resized.save(ROOT / rel, 'WEBP', quality=82, method=6)
            variants.append([rel, size])
            generated.append(rel)
        sources[path] = {'width': width, 'height': height, 'variants': variants}
        original_bytes += (ROOT / path).stat().st_size
        optimized_bytes += (ROOT / variants[-1][0]).stat().st_size

manifest['images'] = [p for p in manifest['images'] if not p.startswith('image/optimized/')] + generated
module = 'assets/js/image-sources.js'
if module not in manifest['assets']:
    manifest['assets'].append(module)
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(ROOT / module).write_text('export default ' + json.dumps(sources, ensure_ascii=False, indent=2) + ';\n', encoding='utf-8')

def responsive_logo(match):
    tag = match.group(0)
    path = re.search(r'src="([^"]+)"', tag).group(1)
    info = sources.get(path)
    if not info:
        return tag
    tag = re.sub(r' (?:srcset|sizes|decoding)="[^"]*"', '', tag)
    sizes = '(max-width:350px) 160px, (max-width:760px) 174px, (max-width:767px) 195px, 240px' if 'brand-logo' in tag else '(max-width:767px) 72px, 88px'
    srcset = ', '.join(f'{p} {w}w' for p, w in info['variants'])
    return tag[:-1] + f' srcset="{srcset}" sizes="{sizes}" decoding="async">'

for page in manifest['html']:
    p = ROOT / page
    p.write_text(re.sub(r'<img\b[^>]*class="(?:brand-logo|footer-logo)"[^>]*>', responsive_logo, p.read_text(encoding='utf-8')), encoding='utf-8')
print(f'Generated {len(generated)} WebP variants; largest variants: {original_bytes:,} -> {optimized_bytes:,} bytes ({100 * (1 - optimized_bytes / original_bytes):.1f}% smaller).')
