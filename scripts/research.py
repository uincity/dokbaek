"""Local source inspection; results are NEVER part of the public build."""
from pathlib import Path
import sys
import struct, subprocess, email, email.policy, re, base64

ROOT = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding='utf-8')
OUT = ROOT / 'private-notes' / 'extracted'
OUT.mkdir(parents=True, exist_ok=True)

def hwp_preview(path):
    b = path.read_bytes()
    if b[:8] != bytes.fromhex('d0cf11e0a1b11ae1'):
        raise ValueError('Unsupported HWP container')
    size = 1 << struct.unpack_from('<H', b, 30)[0]
    sector = lambda n: b[(n+1)*size:(n+2)*size]
    difat = list(struct.unpack_from('<109I', b, 76))
    if struct.unpack_from('<I', b, 72)[0]:
        raise ValueError('Extended DIFAT not supported')
    fat = []
    for n in difat:
        if n < 0xfffffffa:
            fat.extend(struct.unpack('<'+'I'*(size//4), sector(n)))
    def chain(n, table, read):
        out, seen = [], set()
        while n < 0xfffffffa:
            if n in seen or n >= len(table):
                raise ValueError('Invalid sector chain')
            seen.add(n); out.append(read(n)); n = table[n]
        return b''.join(out)
    directory = chain(struct.unpack_from('<I',b,48)[0],fat,sector)
    entries = []
    for offset in range(0,len(directory),128):
        row=directory[offset:offset+128]
        name=row[:max(0,struct.unpack_from('<H',row,64)[0]-2)].decode('utf-16le',errors='replace')
        entries.append((name, row[66], struct.unpack_from('<I',row,116)[0], struct.unpack_from('<Q',row,120)[0]))
    root=next(e for e in entries if e[1]==5)
    mini=chain(root[2],fat,sector)[:root[3]]
    mini_fat_b=chain(struct.unpack_from('<I',b,60)[0],fat,sector)
    mini_fat=struct.unpack('<'+'I'*(len(mini_fat_b)//4),mini_fat_b)
    e=next(e for e in entries if e[0]=='PrvText')
    data=(chain(e[2],mini_fat,lambda n:mini[n*64:(n+1)*64]) if e[3]<4096 else chain(e[2],fat,sector))[:e[3]]
    return data.decode('utf-16le',errors='replace')

report=[]
for folder in ('2025','2026'):
    for p in sorted((ROOT/folder).rglob('*')):
        if not p.is_file(): continue
        rel=p.relative_to(ROOT).as_posix()
        try:
            if p.suffix.lower()=='.pdf':
                result=subprocess.run(['pdftotext','-enc','UTF-8',str(p),'-'],capture_output=True,timeout=30)
                if result.returncode: raise ValueError(result.stderr.decode(errors='replace')[:160])
                content=result.stdout.decode('utf-8')
            elif p.suffix.lower()=='.hwp': content=hwp_preview(p)
            elif p.suffix.lower()=='.txt': content=p.read_text(encoding='utf-8')
            elif p.suffix.lower()=='.eml':
                msg=email.message_from_bytes(p.read_bytes(),policy=email.policy.default)
                content='\n'.join(part.get_content() for part in msg.walk() if part.get_content_type()=='text/plain')
            else:
                report.append(rel+' — image: visual review required'); continue
            target=OUT/(rel.replace('/','__')+'.txt')
            target.write_text(content,encoding='utf-8')
            report.append(rel+' — '+('HWP preview only (may be truncated)' if p.suffix=='.hwp' else 'text extracted'))
        except Exception as exc: report.append(rel+' — unable to extract: '+str(exc))
(OUT.parent/'source-inventory.md').write_text('\n'.join(report),encoding='utf-8')
# Extract the draft images for review only, without publishing them.
draft=(ROOT/'2025-archive.html').read_text(encoding='utf-8')
for i,match in enumerate(re.finditer(r'data:image/(jpeg|png);base64,([^"\s]+)',draft)):
    (OUT/f'draft-{i}.{match[1]}').write_bytes(base64.b64decode(match[2]))
print('\n'.join(report))
