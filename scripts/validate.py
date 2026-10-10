"""Validate public data and release boundaries, using Python's standard library."""
from pathlib import Path
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
import json, re, sys, struct

ROOT=Path(__file__).resolve().parents[1]
PAGES={'index.html','archive.html','repertoire.html','members.html','about.html'}
SOURCE_KEYS={'id','label','type'}
MEMBER_KEYS={'id','nickname','avatar','roles','rolesStatus','characterRole','sourceIds'}
SONG_KEYS={'id','title','composer','composerStatus','aliases','note','sourceIds','fieldEvidence'}
CONCERT_KEYS={'id','year','no','date','datePrecision','time','title','venue','story','status','visibility','mediaVisibility','participants','setlist','media','rehearsalVideo','moments','sourceIds','fieldEvidence','notes'}
ENTRY_KEYS={'id','order','songId','kind','originalTitle','title','formats','evidenceStatus','isEncore','credits','guestCredits','creditsStatus','videoUrl','sourceIds','additionalEvents'}
EVIDENCE={'confirmed','planned','program'}
STATUSES={'confirmed','needs-confirmation'}

def require(condition,message):
    if not condition: raise ValueError(message)

def load(base,path):
    return json.loads((base/path).read_text(encoding='utf-8'))

def local_path(path):
    require(isinstance(path,str) and path and not re.search(r'[\\?#:]',path) and not path.startswith('/'),'Unsafe local path')
    require(all(p not in ('','..','.') for p in path.split('/')),'Unsafe local path segments')
    return path

def keys(obj,allowed,label):
    require(isinstance(obj,dict),f'{label}: expected object')
    require(not set(obj)-allowed,f'{label}: unsupported fields {set(obj)-allowed}')

def unique(records,label):
    ids=[r['id'] for r in records]
    require(len(ids)==len(set(ids)),f'{label}: duplicate IDs')
    require(all(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',i) for i in ids),f'{label}: unsafe ID')
    return set(ids)

def approved_files(base=ROOT):
    manifest=load(base,'scripts/public-files.json')
    require(set(manifest)=={'html','assets','images','media','fonts'},'Unexpected manifest category')
    require(set(manifest['html'])==PAGES,'Only the five public pages may be released')
    for group,prefix,extensions in [('assets','assets/',{'.css','.js'}),('images','image/',{'.png','.jpg','.jpeg','.webp'}),('media','public-media/',{'.png','.jpg','.jpeg','.webp'}),('fonts','assets/fonts/',{'.woff2','.txt','.md'})]:
        for path in manifest[group]:
            local_path(path)
            require(path.startswith(prefix) and Path(path).suffix.lower() in extensions,'Unexpected public file type')
    paths=[p for group in manifest.values() for p in group]
    require(len(paths)==len(set(paths)),'Duplicate allowlist path')
    return paths

def validate_data(base=ROOT, manifest_base=ROOT):
    site=load(base,'data/site.json'); members=load(base,'data/members.json'); songs=load(base,'data/songs.json')
    keys(site,{'name','description','groupImage','channels','years','sources'},'site')
    allowed=set(approved_files(manifest_base))
    source_ids=unique(site['sources'],'sources')
    for s in site['sources']: keys(s,SOURCE_KEYS,'source')
    def refs(obj):
        require('sourceIds' in obj and isinstance(obj['sourceIds'],list),'Missing evidence sources')
        require(set(obj['sourceIds'])<=source_ids,'Unknown source ID')
    def fields(obj):
        for name,ev in obj.get('fieldEvidence',{}).items():
            require(name in obj,'Evidence refers to absent field')
            keys(ev,{'status','sourceIds'},'field evidence'); refs(ev)
            require(ev['status'] in STATUSES,'Invalid field evidence status')
            require(ev['status']!='confirmed' or ev['sourceIds'],'Confirmed field needs evidence')
    member_ids=unique(members,'members'); song_ids=unique(songs,'songs')
    require(site['groupImage'] in allowed,'Group artwork needs allowlist review')
    for m in members:
        keys(m,MEMBER_KEYS,'member');refs(m)
        require(m['avatar'] in allowed and m['avatar'].startswith('image/'),'Member avatar needs allowlist review')
        require(m['rolesStatus'] in STATUSES,'Invalid roles status')
        require(not m['roles'] or m['rolesStatus']=='confirmed','Unconfirmed member roles must remain empty')
    for s in songs:
        keys(s,SONG_KEYS,'song'); refs(s); fields(s)
        require(s['composerStatus'] in STATUSES,'Invalid composer status')
        require((s['composer'] is not None)==(s['composerStatus']=='confirmed'),'Composer confirmation mismatch')
    years=[y['year'] for y in site['years']]
    require(len(years)==len(set(years)),'Duplicate years')
    concerts=[]; data_files=['data/site.json','data/members.json','data/songs.json']
    for y in site['years']:
        keys(y,{'year','title','phrase','description','file','historicalLineup'},'year')
        require(isinstance(y['year'],int) and 1900<=y['year']<=2200,'Invalid year')
        require(y['file']==f'data/concerts-{y["year"]}.json','Unexpected concert data path')
        if y.get('historicalLineup'):
            keys(y['historicalLineup'],{'guitars','manager','sourceId'},'historical lineup')
            require(y['historicalLineup']['sourceId'] in source_ids,'Unknown lineup source')
        data_files.append(y['file']); cs=load(base,y['file'])
        require(all(c['year']==y['year'] for c in cs),'Year and concert file mismatch'); concerts.extend(cs)
    concert_ids=unique(concerts,'concerts')
    all_entries=[e for c in concerts for e in c['setlist']]
    entry_ids=unique(all_entries,'setlist')
    require(not concert_ids & entry_ids and not song_ids & entry_ids,'Hash ID collision')
    numbers=[c['no'] for c in concerts if c['no'] is not None]
    require(len(numbers)==len(set(numbers)),'Band-wide concert number repeated')
    def credit_check(credit):
        keys(credit,{'memberId','role'},'credit')
        require(credit.get('memberId') in member_ids,'Unknown credited member')
        require(isinstance(credit.get('role'),str) and credit['role'],'Missing credit role')
    for c in concerts:
        keys(c,CONCERT_KEYS,'concert'); refs(c); fields(c)
        require(c['status'] in {'completed','scheduled'},'Invalid concert status')
        require(c['visibility'] in {'public','public-summary','private'},'Invalid visibility')
        require(c['mediaVisibility'] in {'withheld','reviewed-only'},'Invalid media visibility')
        require(c['no'] is None or isinstance(c['no'],int) and c['no']>0,'Invalid official number')
        if c['datePrecision']=='month':
            require(re.fullmatch(r'\d{4}-\d{2}',c['date'] or '') is not None,'Month date must not invent a day'); date.fromisoformat(c['date']+'-01')
        elif c['datePrecision']=='day': date.fromisoformat(c['date'])
        elif c['datePrecision']=='unknown': require(c['date'] is None,'Unknown dates must be null')
        else: raise ValueError('Invalid date precision')
        if c['date']:require(c['date'].startswith(str(c['year'])+'-'),'Date year mismatch')
        require(c['time'] is None or re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',c['time']),'Invalid time')
        for participant in c['participants']: credit_check(participant)
        for m in c['media']:
            keys(m,{'type','label','path','sourceIds','reviewed'},'media');refs(m)
            require(m['type']=='image' and m['reviewed'] is True and m['path'] in allowed,'Unreviewed public media')
            require(m['path'].startswith('public-media/'),'Media must be a reviewed public copy')
        require(c['mediaVisibility']!='withheld' or not c['media'],'Withheld media cannot be released')
        if c.get('rehearsalVideo'):
            rehearsal=c['rehearsalVideo']
            keys(rehearsal,{'title','url','thumbnail'},'rehearsal video')
            url=urlsplit(rehearsal['url'])
            require(url.scheme=='https' and url.hostname in {'youtube.com','www.youtube.com','youtu.be'},'Rehearsal video must be a YouTube link')
            require(rehearsal['thumbnail'] in allowed,'Rehearsal thumbnail needs allowlist review')
        orders=[e['order'] for e in c['setlist']];require(len(orders)==len(set(orders)),'Duplicate setlist order')
        for e in c['setlist']:
            keys(e,ENTRY_KEYS,'entry');refs(e)
            require(e['kind'] in {'song','event'},'Invalid entry kind')
            require(e['evidenceStatus'] in EVIDENCE and e['creditsStatus'] in STATUSES,'Invalid entry evidence status')
            require(c['status']!='scheduled' or e['evidenceStatus']!='confirmed','Upcoming concert cannot confirm performance')
            require(isinstance(e['order'],(float,int)) and e['order']>0,'Invalid entry order')
            require(isinstance(e['isEncore'],bool),'Encore must be boolean')
            require(e['kind']!='song' or e['songId'] in song_ids,'Unknown song reference')
            require(e['kind']!='event' or e['songId'] is None,'Events must not count as songs')
            for cr in e['credits']:credit_check(cr)
            for guest in e.get('guestCredits',[]):
                keys(guest,{'name','role'},'guest credit')
                require(isinstance(guest.get('name'),str) and guest['name'],'Missing guest name')
                require(isinstance(guest.get('role'),str) and guest['role'],'Missing guest role')
            for ev in e['additionalEvents']:
                keys(ev,{'title','kind','evidenceStatus','sourceIds'},'additional event');refs(ev)
                require(ev['kind']=='event' and ev['evidenceStatus'] in EVIDENCE,'Invalid additional event')
            if e['videoUrl']:
                url=urlsplit(e['videoUrl']);require(url.scheme=='https' and url.hostname in {'youtube.com','www.youtube.com','youtu.be'},'Video must be a reviewed YouTube link')
    for channel in site['channels']:
        keys(channel,{'label','url'},'channel');url=urlsplit(channel['url'])
        require(url.scheme=='https' and url.hostname in {'www.youtube.com','www.instagram.com'},'Unexpected channel URL')
    for p in allowed | set(data_files):require((base/p).is_file(),f'Missing public file: {p}')
    for relative in load(manifest_base,'scripts/public-files.json')['fonts']:
        path=base/relative
        if path.suffix=='.woff2':
            content=path.read_bytes()
            require(len(content)>=48 and content[:4]==b'wOF2','Invalid WOFF2 font')
            require(int.from_bytes(content[8:12],'big')==len(content),'Truncated WOFF2 font')
    # Catch private fields in arbitrary nested data as well.
    text='\n'.join((base/p).read_text(encoding='utf-8') for p in data_files)
    scan_text(text)
    return {'files':data_files,'concerts':concerts,'songs':songs,'members':members}

def scan_text(text):
    for pattern in [r'(?<![A-Za-z])[A-Za-z]:[\\/]',r'/(?:Users|home)/',r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b',r'\b01[016789][ -]?\d{3,4}[ -]?\d{4}\b',r'private-notes',r'큐시트[^\n]*\.hwp',r'cloudflareinsights',r'googletagmanager',r'google-analytics',r'"(?:realName|email|phone|privatePath|stageDirections)"\s*:']:
        require(not re.search(pattern,text,re.I),'Private information or tracking pattern found')
    terms_file=ROOT/'private-notes'/'privacy-terms.json'
    if terms_file.exists():
        for term in json.loads(terms_file.read_text(encoding='utf-8')):
            require(term not in text,'A private identity term was found')

class References(HTMLParser):
    def __init__(self):super().__init__();self.paths=[]
    def handle_starttag(self,tag,attrs):
        for name,value in attrs:
            if name in {'src','href'} and value:self.paths.append(value)

def validate_dist(base):
    info=validate_data(base)
    expected=set(approved_files()) | set(info['files']) | {'.nojekyll'}
    actual={p.relative_to(base).as_posix() for p in base.rglob('*') if p.is_file()}
    require(actual==expected,f'Release boundary mismatch: extra={actual-expected}, missing={expected-actual}')
    for rel in actual:
        p=base/rel
        if p.suffix in {'.html','.js','.css','.json'}:
            content=p.read_text(encoding='utf-8');scan_text(content)
            if p.suffix=='.css':
                for target in re.findall(r'url\([\x22\x27]?([^\x22\x27)]+)[\x22\x27]?\)',content):
                    url=urlsplit(target)
                    if not url.scheme:
                        require(not url.path.startswith('/'),'Domain-root CSS URL breaks project Pages URLs')
                        resolved=(p.parent/unquote(url.path)).resolve()
                        require(resolved.is_relative_to(base.resolve()) and resolved.is_file(),'Broken local CSS resource')
            if p.suffix=='.html':
                parser=References();parser.feed(content)
                for target in parser.paths:
                    url=urlsplit(target)
                    if not url.scheme and url.path:
                        require(not url.path.startswith('/'),'Domain-root reference breaks project Pages URLs')
                        require((p.parent/unquote(url.path)).is_file(),'Broken HTML reference')
        elif p.suffix.lower()=='.png':
            b=p.read_bytes();off=8
            while off<len(b):
                length=struct.unpack_from('>I',b,off)[0];kind=b[off+4:off+8]
                require(kind not in {b'tEXt',b'zTXt',b'iTXt',b'eXIf'},'Image metadata not stripped');off+=length+12
        elif p.suffix.lower() in {'.jpg','.jpeg'}:
            # Scan metadata bytes as UTF-8/UTF-16; release writer strips private metadata segments.
            scan_text(p.read_bytes()[:4096].decode('utf-8',errors='ignore'))
    return info

if __name__=='__main__':
    try:
        target=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT
        info=validate_dist(target) if target!=ROOT else validate_data()
        print(f'PASS: {len(info["concerts"])} concerts, {len(info["songs"])} songs, {len(info["members"])} members; references and public boundaries valid.')
    except (ValueError,KeyError,TypeError) as exc:
        print(f'FAIL: {exc}',file=sys.stderr);sys.exit(1)
