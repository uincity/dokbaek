import imageSources from './image-sources.js';
const main = document.querySelector('#main');
const page = document.body.dataset.page;
const params = new URLSearchParams(location.search);
const inquiryEmail='uuincity@naver.com';
const inquirySubject='[집단적독백] 공연 초청 문의';
const inquiryBody='안녕하세요. 집단적독백 공연 초청을 문의드립니다.\n\n1. 문의자 / 단체명:\n2. 연락 가능한 이메일:\n3. 공연 희망 날짜 및 시간:\n4. 공연 장소:\n5. 행사 성격 및 예상 관객:\n6. 기타 요청사항:\n\n감사합니다.';
const inquiryMailto=`mailto:${inquiryEmail}?subject=${encodeURIComponent(inquirySubject)}&body=${encodeURIComponent(inquiryBody)}`;
let site, members, songs, concerts, memberMap, songMap, sourceMap;
let unitPerformances=[], unitError=null;
const evidenceLabels = {confirmed:'', planned:'진행 계획', program:'인쇄 프로그램'};
function evidenceText(entry) {
  return [evidenceLabels[entry.evidenceStatus], entry.isEncore ? '앵콜' : ''].filter(Boolean).join(' · ');
}

// All text from JSON, queries and hashes enters the DOM as text, never HTML.
function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function add(parent, ...nodes) { parent.append(...nodes.filter(Boolean)); return parent; }
function link(text, href, className) { const a = el('a', text, className); a.href = href; return a; }
function external(text, url) {
  const a = link(text, url); a.target = '_blank'; a.rel = 'noopener noreferrer';
  a.setAttribute('aria-label', `${text} (새 창)`); return a;
}
function venueLink(venue) {
  const maps={'고덕우갤러리':'https://naver.me/xMni5Yd6','꿈꾸는공작소':'https://naver.me/xMni5Yd6'};
  const url=maps[(venue || '').replace(/\s/g,'')];
  if(!url)return el('span',venue || '장소 확인 중');
  const a=external(venue,url);a.className='venue-link';
  a.setAttribute('aria-label',`${venue} 네이버지도 (새 창)`);return a;
}
function pill(text, color='') { return el('span',text,`pill ${color}`); }
function safeMedia(path) {
  const reviewedPoster='2026/포스터/포스터_수녀원 음악회(20261108).png';
  return typeof path === 'string' && (/^(image|public-media)\//.test(path) || path===reviewedPoster) && !path.split('/').includes('..') && !/[\\?#]/.test(path);
}
function image(path, alt, className='', eager=false, fullResolution=false) {
  const wrap = el('span',null,`image-wrap ${className}`);
  const fallback = () => { wrap.replaceChildren(el('span', '이미지 준비 중', 'image-placeholder')); };
  if (!safeMedia(path)) { fallback(); return wrap; }
  const img = el('img'); img.alt = alt; img.loading = eager ? 'eager' : 'lazy'; img.decoding = 'async';
  img.dataset.originalSrc=path;
  const info=imageSources[path];
  if(info){img.width=info.width;img.height=info.height;}
  if(eager && !fullResolution)img.fetchPriority='high';
  img.addEventListener('error',fallback,{once:true});
  if(info && !fullResolution){
    img.sizes=className==='credit-avatar' ? '68px' : className==='print-image' ? '(min-width:768px) 240px, 45vw' : className==='group-art' ? '(min-width:1200px) 1120px, calc(100vw - 40px)' : page==='members' ? '(min-width:1000px) 140px, (min-width:431px) 28vw, 42vw' : eager ? '(min-width:1200px) 1120px, calc(100vw - 40px)' : 'auto, (min-width:1200px) 1120px, calc(100vw - 40px)';
    img.srcset=info.variants.map(([src,width])=>`${src} ${width}w`).join(', ');
    img.src=info.variants.at(-1)[0];
  }else img.src=path.split('/').map(encodeURIComponent).join('/');
  wrap.append(img); return wrap;
}
function dateText(c) {
  if (!c.date) return '날짜 확인 중';
  const [year,month,day] = c.date.split('-').map(Number);
  const weekday=c.datePrecision==='day' ? `(${['일','월','화','수','목','금','토'][new Date(Date.UTC(year,month-1,day)).getUTCDay()]})` : '';
  return `${year}년 ${month}월${c.datePrecision === 'day' ? ` ${day}일${weekday}` : ''}${c.time ? ` · ${c.time}` : ''}`;
}
function concertLink(c, entry=null) { return `archive.html?year=${c.year}#${entry?.id || c.id}`; }
function ordered(list) { return [...list].sort((a,b)=>(a.date || '').localeCompare(b.date || '') || a.id.localeCompare(b.id)); }
function occurrences(songId, list=concerts) {
  return ordered(list).flatMap(c=>c.setlist.filter(e=>e.kind==='song' && e.songId===songId).map(e=>({c,e})));
}
function memberRepertoireIds(list=concerts) {
  return new Set(list.flatMap(c=>c.setlist.filter(e=>e.kind==='song' && e.credits?.length).map(e=>e.songId)));
}
function stats(list, showNotes=true, useMemberRepertoire=false) {
  const complete = list.filter(c=>concertStatus(c)==='completed').length;
  const upcoming = list.filter(c=>concertStatus(c)==='scheduled').length;
  const songCount = useMemberRepertoire
    ? memberRepertoireIds(list).size
    : new Set(list.flatMap(c=>c.setlist.filter(e=>e.kind==='song' && e.evidenceStatus==='confirmed').map(e=>e.songId))).size;
  const box = el('div',null,'stats');
  const songNote=useMemberRepertoire ? '멤버 참여곡 기준' : '계획·이벤트 제외';
  for (const [n,label,note] of [[complete,'기록된 공연','공연 기록 기준'],[upcoming,'예정 공연','완료 기록과 별도'],[songCount,'연주 곡',songNote]]) {
    box.append(add(el('div',null,'stat'),el('b',n),el('span',label),showNotes ? el('small',note) : null));
  }
  return box;
}
function heading(title, eyebrow, description, phrase=null) {
  const hero = el('section',null,'hero');
  hero.append(el('p',eyebrow,'eyebrow'));
  if (phrase) {
    const line = el('div',null,'manuscript'); line.setAttribute('aria-label',phrase);
    for (const char of phrase) { const cell = el('span',char === ' ' ? '\u00a0' : char); cell.setAttribute('aria-hidden','true'); cell.style.setProperty('--i',line.childElementCount); line.append(cell); }
    hero.append(line);
  }
  add(hero,el('h1',title),el('p',description,'lede')); return hero;
}
function section(title, more=null) {
  const s=el('section',null,'section'); add(s,add(el('div',null,'section-head'),el('h2',title),more)); return s;
}
function sources(ids) { return (ids || []).map(id=>sourceMap.get(id)?.label).filter(Boolean).join(' · '); }
function disclosure(label, className='') {
  const d=el('details',null,className);d.append(el('summary',label));return d;
}
function songInformation(song) {
  const info=el('div',null,'song-information');
  if(song.artistCredit || song.composer)info.append(el('p',`작곡가(가수) · ${song.artistCredit || song.composer}`,'composer'));
  if(song.genre)info.append(el('p',`장르 · ${song.genre}`,'song-genre'));
  if(song.note)info.append(el('p',song.note,'song-description'));
  const ids=[...new Set(['artistCredit','genre','note'].flatMap(field=>song.fieldEvidence?.[field]?.sourceIds || []))];
  if(ids.length)info.append(el('p',`곡 정보 · ${sources(ids)}`,'source-note'));
  return info;
}
// These original portraits were visually checked; other artwork stays uncropped.
const facePortraits=new Set(['매니저(열심남).png','로나짱.png','베리짱.png','베키짱(기타).png','유니뀨짱.png','쿠르짱.png','세뉴짱.png'].map(n=>'image/'+n));
function credits(entry) {
  const box = el('div',null,'credits');
  const grouped=new Map();
  for (const credit of entry.credits || []) {
    const member = memberMap.get(credit.memberId);
    if (!member) continue;
    if(!grouped.has(member.id))grouped.set(member.id,{member,roles:new Set()});
    grouped.get(member.id).roles.add(credit.role);
  }
  for(const {member,roles} of grouped.values()) {
    const a = link('',`members.html#${member.id}`,'credit');
    const avatar=image(member.avatar,'','credit-avatar');
    if(facePortraits.has(member.avatar)){avatar.classList.add('face-crop');avatar.dataset.memberId=member.id;}
    add(a,avatar,add(el('span',null,'credit-text'),el('strong',member.nickname),el('span',[...roles].join(' · '))));box.append(a);
  }
  for(const guest of entry.guestCredits || []) {
    box.append(add(el('span',null,'credit'),add(el('span',null,'credit-text'),el('strong',guest.name),el('span',guest.role))));
  }
  if (!box.childElementCount || entry.creditsStatus !== 'confirmed') box.append(el('small',`${entry.formats?.includes('합주') ? '합주 · 참여 멤버' : '연주자'} 확인 중`));
  return box;
}
const dialog=document.querySelector('#media-dialog');
let returnFocus=null;
function openDialog(title,content,trigger) {
  returnFocus=trigger; document.querySelector('#media-title').textContent=title;
  document.querySelector('#media-content').replaceChildren(content); dialog.showModal();
}
document.querySelector('#close-dialog').addEventListener('click',()=>dialog.close());
dialog.addEventListener('close',()=>{ document.querySelector('#media-content').replaceChildren(); returnFocus?.focus(); });
dialog.addEventListener('keydown',event=>{
  if(event.key!=='Tab')return;
  const focusable=[...dialog.querySelectorAll('button, a[href], input, select, textarea, iframe, [tabindex]:not([tabindex="-1"])')].filter(node=>node.getClientRects().length);
  const first=focusable[0], last=focusable.at(-1);
  if(!first){event.preventDefault();return;}
  if(event.shiftKey && document.activeElement===first){event.preventDefault();last.focus();}
  else if(!event.shiftKey && document.activeElement===last){event.preventDefault();first.focus();}
});
dialog.addEventListener('click',event=>{ if(event.target===dialog) { const r=dialog.getBoundingClientRect(); if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom) dialog.close(); } });
function video(entry) {
  if (!entry.videoUrl) return null;
  const url = new URL(entry.videoUrl);
  let id=null;
  if (url.hostname==='youtu.be') id=url.pathname.slice(1);
  if (['www.youtube.com','youtube.com'].includes(url.hostname)) id=url.searchParams.get('v');
  if (!id || !/^[\w-]{11}$/.test(id)) return null;
  const title=entry.title || songMap.get(entry.songId)?.title || entry.originalTitle || '공연';
  const card=el('div',null,'video-card');
  const thumbnail=external(`${title} · YouTube에서 보기`,entry.videoUrl);thumbnail.className='video-thumbnail';
  const img=el('img');img.src=`https://i.ytimg.com/vi/${id}/hqdefault.jpg`;img.alt=`${title} 공연 영상 썸네일`;img.loading='lazy';img.decoding='async';
  img.addEventListener('error',()=>img.remove(),{once:true});
  thumbnail.replaceChildren(img,el('span','YouTube에서 보기 ↗','video-caption'));
  card.append(thumbnail);
  const b=el('button','공연 영상 보기','button video-button');
  b.addEventListener('click',()=>{
    const frame=el('iframe'); frame.src=`https://www.youtube-nocookie.com/embed/${id}`;
    const start=url.searchParams.get('t') || url.searchParams.get('start');
    if(start && /^\d+s?$/.test(start))frame.src+=`?start=${parseInt(start,10)}`;
    frame.title='집단적독백 공연 영상'; frame.allow='fullscreen'; frame.referrerPolicy='strict-origin-when-cross-origin';
    openDialog('공연 영상',frame,b);
  }); card.append(b);return card;
}
function preview(c) {
  const card=el('article',null,'concert-preview');
  const a=link('',concertLink(c),'preview-main');
  const scheduled=concertStatus(c)==='scheduled';
  add(a,el('p',dateText(c),'preview-date'),pill(scheduled ? '공연 예정' : '종료 공연',scheduled?'red':''),el('h3',c.title));
  add(card,a,add(el('p'),venueLink(c.venue)),el('small',c.story));return card;
}
function unitParticipants(event) {
  return [...new Map(event.songs.flatMap(song=>song.performers).map(p=>[p.member_id,p])).values()];
}
// Small stages use editorial status only, even after the scheduled date passes.
function unitSchedule(list) {
  return {
    upcoming:ordered(list.filter(event=>event.status==='scheduled')),
    past:ordered(list.filter(event=>event.status==='completed')).reverse()
  };
}
function checkUnitData(events) {
  if(!Array.isArray(events))throw new Error('작은 무대 자료는 행사 목록이어야 합니다.');
  const ids=new Set();
  for(const event of events) {
    if(!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(event.id) || ids.has(event.id) ||
       !['scheduled','completed'].includes(event.status) || !/^\d{4}-\d{2}-\d{2}$/.test(event.date) ||
       !event.title?.trim() || !event.venue?.trim() || !Array.isArray(event.songs) || !event.songs.length)
      throw new Error('작은 무대 행사 정보가 올바르지 않습니다.');
    ids.add(event.id);
    for(const song of event.songs) {
      if(!song.title?.trim() || !Array.isArray(song.performers) || !song.performers.length ||
         song.performers.some(p=>!memberMap.has(p.member_id) || !p.name?.trim() || !Array.isArray(p.roles) || !p.roles.length || p.roles.some(role=>!role?.trim())))
        throw new Error(`작은 무대 프로그램 정보가 올바르지 않습니다 (${event.id}).`);
    }
  }
  return events;
}
function unitLoadNotice() {
  const box=el('div',null,'notice unit-error');box.setAttribute('role','alert');
  return add(box,el('p','작은 무대 기록을 불러오지 못했습니다. 잠시 후 다시 열어 주세요.'),link('다시 열기',location.href,'button'));
}
function unitCard(event, compact=false) {
  const card=el('article',null,`unit-card${compact?' unit-compact':''}`);
  card.dataset.unitId=event.id;
  if(!compact)card.id=event.id;
  const [year,month,day]=event.date.split('-');
  const stamp=el('time',null,'unit-date');stamp.dateTime=event.date;
  stamp.setAttribute('aria-label',`${year}년 ${Number(month)}월 ${Number(day)}일`);
  add(stamp,el('span',`${Number(month)}월`),el('strong',Number(day)),el('small',year));
  const body=el('div',null,'unit-copy');
  const title=el('h3');title.append(compact?link(event.title,`unit.html#${event.id}`):document.createTextNode(event.title));
  const participants=unitParticipants(event);
  add(body,pill(event.status==='scheduled'?'공연 예정':'공연 완료',event.status==='scheduled'?'red':''),title,
    el('p',event.venue,'unit-venue'));
  if(event.description && !compact)body.append(el('p',event.description,'unit-description'));
  if(!compact && event.status==='scheduled')body.append(el('p','함께 나눌 음악을 준비하고 있습니다.','unit-description'));
  const names=el('ul',null,'unit-members');names.setAttribute('aria-label','참여 멤버');
  for(const person of participants)names.append(add(el('li'),link(person.name,`members.html#${person.member_id}`)));
  add(body,el('p',`${participants.length}명 참여 · ${event.songs.length}곡`,'unit-count'),names);
  if(compact)body.append(el('p',event.songs.map(song=>song.title).join(' · '),'unit-song-preview'));
  else {
    const summary=el('p',event.songs.map(song=>song.title).join(' · '),'unit-song-preview');
    const detail=disclosure('프로그램 자세히 보기','unit-program');
    const list=el('ol');
    for(const song of [...event.songs].sort((a,b)=>a.order-b.order)) {
      const item=el('li');
      const songTitle=el('h4');songTitle.append(song.song_id && songMap.has(song.song_id)?link(song.title,`repertoire.html#${song.song_id}`):document.createTextNode(song.title));
      item.append(songTitle);
      if(song.formats.length)item.append(el('small',song.formats.join(' · '),'unit-format'));
      const players=el('ul',null,'unit-performers');
      for(const person of song.performers)players.append(add(el('li'),link(person.name,`members.html#${person.member_id}`),el('span',person.roles.join(' · '))));
      item.append(players);list.append(item);
    }
    detail.append(list);add(body,summary,detail);
    const approved=(event.media || []).filter(media=>media.reviewed===true && safeMedia(media.path));
    if(approved.length) {
      const mediaList=el('div',null,'unit-media');
      for(const media of approved) {
        if(media.type==='image')mediaList.append(image(media.path,media.label));
        if(media.type==='video') {
          const player=el('video');player.controls=true;player.preload='none';player.src=media.path;player.setAttribute('aria-label',media.label);mediaList.append(player);
        }
      }
      body.append(mediaList);
    }
  }
  add(card,stamp,body);return card;
}
function unitHomePreview() {
  const preview=section('독백의 작은 무대',link('작은 무대 전체 보기 ↗','unit.html'));preview.id='small-stages';
  preview.append(el('p','때로는 둘이서, 때로는 함께.','unit-intro'));
  if(unitError)preview.append(unitLoadNotice());
  else {
    const schedule=unitSchedule(unitPerformances);
    const selected=schedule.upcoming.length?[schedule.upcoming[0],...(schedule.past.length?[schedule.past[0]]:schedule.upcoming.slice(1,2))]:schedule.past.slice(0,2);
    if(!selected.length)return null;
    preview.append(add(el('div',null,'unit-grid'),...selected.map(event=>unitCard(event,true))));
  }
  return preview;
}
function unitPage() {
  const hero=heading('독백의 작은 무대','SMALL STAGES · UNIT SESSIONS','때로는 둘이서, 때로는 함께.');hero.classList.add('unit-hero');
  hero.append(el('p','정식 공연의 무대 밖에서도 집단적독백의 음악은 계속됩니다. 결혼식의 축복을 전하는 노래부터 누군가의 하루를 위로하는 작은 음악회까지. 멤버들이 다양한 조합으로 만들어가는 특별한 음악의 순간을 기록합니다.','unit-hero-copy'));
  main.append(hero);
  if(unitError){main.append(unitLoadNotice());return;}
  const schedule=unitSchedule(unitPerformances);
  for(const [title,id,events,empty] of [
    ['예정된 작은 무대','unit-upcoming',schedule.upcoming,'새로운 작은 무대를 준비하면 이곳에서 전하겠습니다.'],
    ['지나온 작은 무대','unit-past',schedule.past,'작은 무대의 기록을 차곡차곡 모읍니다.']]) {
    const group=section(title);group.id=id;
    group.append(events.length?add(el('div',null,'unit-grid'),...events.map(event=>unitCard(event))):el('p',empty,'empty-state'));
    main.append(group);
  }
}
function performanceInquiry() {
  const card=el('section',null,'performance-inquiry');card.id='performance-inquiry';
  const title=el('h2','집단적독백을 초대하고 싶으신가요?');title.id='inquiry-title';
  card.setAttribute('aria-labelledby',title.id);
  add(card,el('p','공연 초청 및 문의','eyebrow'),title,
    el('p','집단적독백은 음악을 함께 나누는 즐거움을 소중하게 생각하는 아마추어 기타 밴드입니다. 기본적으로 무료 공연을 지향하며, 작은 음악회부터 지역 행사, 문화공간의 공연까지 다양한 무대를 함께하고 싶습니다. 공연 초청이나 협업 제안은 이메일로 문의해주세요. 일정과 공연 내용은 사전 협의를 통해 결정합니다.'),
    el('p','담당 · 집단적독백 매니저','inquiry-manager'));
  const controls=el('div',null,'inquiry-controls');
  const send=link('공연 문의 이메일 보내기',inquiryMailto,'button primary inquiry-send');
  const label=el('label','문의 이메일');label.htmlFor='inquiry-address';
  const address=el('input');address.id='inquiry-address';address.type='text';address.readOnly=true;address.value=inquiryEmail;
  address.setAttribute('aria-describedby','inquiry-status');label.append(address);
  const copy=el('button','이메일 주소 복사','button inquiry-copy');copy.type='button';
  const status=el('p','','inquiry-status');status.id='inquiry-status';status.setAttribute('role','status');status.setAttribute('aria-live','polite');status.setAttribute('aria-atomic','true');
  copy.addEventListener('click',async()=>{
    copy.disabled=true;status.textContent='';
    try {
      await navigator.clipboard.writeText(inquiryEmail);
      status.textContent='이메일 주소를 복사했습니다.';
    } catch {
      status.textContent='자동 복사를 사용할 수 없습니다. 위 이메일 주소를 직접 선택해 복사해주세요.';
      address.focus();address.select();
    } finally {copy.disabled=false;}
  });
  add(controls,send,label,copy);add(card,controls,status,
    el('p','버튼을 누르면 기본 메일 앱에서 편지를 작성합니다. 발송은 메일 앱에서 직접 진행해주세요.','source-note'));
  return card;
}
function home() {
  const hero=heading('기타로 만나, 함께 웃고, 무대에서 만납니다.','DOKBAEK · ACOUSTIC CLUB','익숙한 노래부터 재즈와 영화음악, 작은 소품곡까지. 클래식 기타로 함께 음악을 즐기는 사람들, 집단적독백입니다.');
  hero.classList.add('home-hero');
  hero.append(add(el('div',null,'actions'),link('공연소식 보기','#upcoming','button primary'),link('지난 공연 보기','#past-shows','button')));
  hero.append(image(site.groupImage,'집단적독백 일곱 멤버의 단체 캐릭터','group-art',true));
  main.append(hero);
  const schedule=homeSchedule(concerts);
  const upcoming=section('다음 공연');upcoming.id='upcoming';upcoming.classList.add('upcoming-section');
  if(schedule.upcoming.length) {
    const [first,...rest]=schedule.upcoming;
    const feature=el('article',null,'upcoming-feature');feature.dataset.concertId=first.id;
    const copy=el('div',null,'upcoming-copy');
    add(copy,pill('공연 예정','red'),el('h3',first.title),el('p',dateText(first),'show-date'),add(el('p',null,'show-venue'),venueLink(first.venue)),link('공연 상세 보기 ↗',concertLink(first),'button primary'),el('p',first.story,'show-story'));
    if(first.address)copy.querySelector('.show-venue').after(el('p',first.address,'show-address'));
    const entries=[...first.setlist].sort((a,b)=>a.order-b.order);
    if(entries.length){
      copy.querySelector('.button').after(link('프로그램 보기 ↗',`${concertLink(first)}-program`,'button'));
      const program=disclosure(`프로그램 미리보기 · ${entries.length}곡`,'upcoming-program');
      const list=el('ol');
      for(const e of entries)list.append(add(el('li'),link(e.title || songMap.get(e.songId)?.title || e.originalTitle,concertLink(first,e))));
      program.append(list);copy.append(program);
    }
    feature.append(copy);
    const poster=first.visibility==='public' && first.mediaVisibility!=='withheld'
      ? (first.media || []).find(m=>m.reviewed && m.type==='image' && m.label.includes('포스터')) : null;
    if(poster){feature.classList.add('has-poster');feature.append(printButton(first,poster,'upcoming-poster'));}
    upcoming.append(feature);
    if(rest.length)upcoming.append(add(el('div',null,'card-grid'),...rest.map(preview)));
  } else upcoming.append(add(el('div',null,'schedule-empty'),el('p','다음 공연을 준비 중입니다.'),link('레퍼토리 살펴보기 ↗','repertoire.html','button')));
  if(schedule.pending.length) {
    const d=disclosure('일정 확인 중','schedule-pending');
    for(const c of schedule.pending)d.append(add(el('p'),link(`${c.title} · ${dateText(c)}`,concertLink(c))));
    upcoming.append(d);
  }
  main.append(upcoming);
  const music=section('우리가 연주하는 음악',link('레퍼토리 살펴보기 ↗','repertoire.html'));
  const highlights=el('div',null,'music-highlights');
  for(const [title,copy] of [['익숙한 노래','함께 흥얼거릴 수 있는 멜로디.'],['재즈와 보사노바','기타로 나누는 가벼운 리듬.'],['영화음악과 소품','짧은 선율에 담긴 장면들.'],['클래식 기타의 매력','여섯 줄이 들려주는 다양한 소리.']])highlights.append(add(el('article'),el('h3',title),el('p',copy)));
  music.append(highlights);main.append(music);
  const together=section('함께 만드는 시간');together.classList.add('together-section');
  add(together,el('p','연습하고 이야기하고, 다시 기타를 잡습니다. 함께 소리를 맞추고 무대를 준비하는 시간도 우리가 음악을 즐기는 방법입니다.'),link('집단적독백 이야기 ↗','about.html','button'));main.append(together);
  const recent=section('지난 공연',link('아카이브 보기 ↗',`archive.html?year=${schedule.past[0]?.year || site.years[0].year}`));recent.id='past-shows';
  recent.append(add(el('div',null,'card-grid'),...schedule.past.slice(0,2).map(preview)));main.append(recent);
  add(main,unitHomePreview());
  const years=section('한 해씩, 한 장씩'); const grid=el('div',null,'year-grid');
  for (const y of site.years) {
    const card=link('',`archive.html?year=${y.year}`,'year-card');
    add(card,el('span',y.year,'year-number'),el('span','↗','arrow'),el('h3',y.title),el('p',y.phrase)); grid.append(card);
  }
  years.append(grid); add(main,years,stats(concerts,false,true),performanceInquiry());
}
function seoulToday(now=new Date()) {
  const parts=new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now);
  const value=type=>parts.find(p=>p.type===type).value;
  return `${value('year')}-${value('month')}-${value('day')}`;
}
function hasConcertDay(c) { return c.datePrecision==='day' && /^\d{4}-\d{2}-\d{2}$/.test(c.date || ''); }
function concertStatus(c, today=seoulToday()) {
  // Display classification only; elapsed time never confirms a song's performance.
  return c.status==='scheduled' && hasConcertDay(c) && c.date<today ? 'completed' : c.status;
}
function homeSchedule(list, today=seoulToday()) {
  const publicList=list.filter(c=>['public','public-summary'].includes(c.visibility));
  const scheduled=ordered(publicList.filter(c=>concertStatus(c,today)==='scheduled'));
  return {
    upcoming:scheduled.filter(hasConcertDay),
    past:ordered(publicList.filter(c=>concertStatus(c,today)==='completed')).reverse(),
    pending:scheduled.filter(c=>!hasConcertDay(c))
  };
}
function repertoireTable(list) {
  const songIds=[...memberRepertoireIds(list)];
  const wrap=el('div',null,'table-wrap'); wrap.tabIndex=0; wrap.setAttribute('aria-label','공연별 레퍼토리 비교표, 가로 스크롤 가능');
  const table=el('table'); const caption=el('caption','프로그램에 기록된 레퍼토리'); caption.className='sr-only';
  const head=el('thead'); const tr=el('tr'); add(tr,el('th','곡'));
  for (const c of list) { const th=el('th',c.no ? `No.${c.no}` : c.venue); th.scope='col'; tr.append(th); }
  head.append(tr); const body=el('tbody');
  for (const id of songIds) {
    const row=el('tr'); const title=el('th'); title.scope='row'; title.append(link(songMap.get(id).title,`repertoire.html#${id}`)); row.append(title);
    for (const c of list) {
      const td=el('td'); const entries=c.setlist.filter(e=>e.kind==='song' && e.songId===id);
      for (const e of entries) { const label=[evidenceText(e) || '수록', concertStatus(c)==='scheduled'?'공연 예정':''].filter(Boolean).join(' · '); const a=link(label,concertLink(c,e)); a.dataset.entryId=e.id; td.append(a); }
      if (!entries.length) td.textContent='—'; row.append(td);
    }
    body.append(row);
  }
  add(table,caption,head,body); wrap.append(table); return wrap;
}
function repertoireViews(list) {
  const view=el('div',null,'repertoire-views');
  const cards=el('div',null,'repertoire-mobile');
  const ids=[...memberRepertoireIds(list)];
  for(const id of ids) {
    const card=el('article',null,'repertoire-mini');card.dataset.songId=id;
    add(card,add(el('h3'),link(songMap.get(id).title,`repertoire.html#${id}`)));
    const records=el('ul');
    for(const {c,e} of occurrences(id,list)) {
      const a=link('',concertLink(c,e));a.dataset.entryId=e.id;
      const label=[evidenceText(e),concertStatus(c)==='scheduled'?'공연 예정':''].filter(Boolean).join(' · ');
      add(a,el('span',`${c.no?`No.${c.no} · `:''}${c.venue}`),label ? el('small',label) : null);
      records.append(add(el('li'),a));
    }
    card.append(records);cards.append(card);
  }
  const compare=disclosure('공연별 비교표 보기','repertoire-comparison');
  compare.append(repertoireTable(list));
  // The same table is open on desktop and explicitly expandable on mobile.
  // display:none removes the alternative card view from focus and accessibility.
  const mq=window.matchMedia('(max-width:760px)');
  const updateCards=()=>{cards.hidden=!mq.matches || compare.open;};
  const sync=()=>{compare.open=!mq.matches;updateCards();};
  sync();mq.addEventListener('change',sync);compare.addEventListener('toggle',updateCards);
  add(view,compare,cards);return view;
}
function printButton(c,media,className='') {
  const b=el('button',null,`print-button ${className}`);b.type='button';
  b.setAttribute('aria-label',`${c.venue} ${media.label} 크게 보기`);
  const alt=`${c.title} · ${dateText(c)} · ${c.venue} ${media.label}`;
  add(b,image(media.path,alt,'print-image'),add(el('span',null,'print-caption'),el('span',media.label),el('span','확대 ↗')));
  b.addEventListener('click',()=>openDialog(`${c.venue} · ${media.label}`,image(media.path,alt,'',true,true),b));return b;
}
function concertSection(c, list, index) {
  const s=el('section',null,'concert-section'); s.id=c.id;
  const number=add(el('div',null,'concert-number'),el('small',c.no ? 'NO.' : 'LIVE'),el('span',c.no || '♪'));
  const info=el('div',null,'concert-info');
  const scheduled=concertStatus(c)==='scheduled';
  add(info,pill(scheduled?'공연 예정':c.visibility==='public-summary'?'사적 공연 · 요약 기록':'종료 공연',scheduled?'red':''),el('h2',c.title),el('p',dateText(c)),add(el('p'),venueLink(c.venue)));
  if(c.address)info.append(el('p',c.address,'show-address'));
  const cover=el('div',null,'concert-cover');
  const copy=el('div',null,'concert-cover-copy');
  add(copy,add(el('div',null,'concert-heading'),number,info),el('p',c.story,'concert-story'));
  const media=c.mediaVisibility==='withheld'?[]:(c.media||[]).filter(m=>m.reviewed && m.type==='image');
  const poster=media.find(m=>m.label.includes('포스터'));
  if(poster)cover.append(printButton(c,poster,'cover-poster'));else cover.classList.add('without-poster');
  if(media.length) {
    const buttons=el('div',null,'cover-print-actions');
    for(const m of media.filter(m=>m!==poster)) {
      const b=el('button',`${m.label.includes('프로그램')?'프로그램 보기':m.label+' 보기'} ↗`,'button');b.type='button';
      b.addEventListener('click',()=>openDialog(`${c.venue} · ${m.label}`,image(m.path,`${c.venue} ${m.label}`,'',true,true),b));buttons.append(b);
    }
    copy.append(buttons);
  }
  cover.append(copy);s.append(cover);
  if(c.rehearsalVideo) {
    const rehearsal=c.rehearsalVideo;
    const card=el('div',null,'rehearsal-video');
    const a=external(rehearsal.title,rehearsal.url);a.className='video-thumbnail';
    a.replaceChildren(image(rehearsal.thumbnail,rehearsal.title),el('span',`${rehearsal.title} · YouTube에서 보기 ↗`,'video-caption'));
    card.append(a);s.append(card);
  }
  if (c.notes?.length) s.append(add(el('div',null,'notice'),...c.notes.map(n=>el('p',n))));
  if(media.length) {
    const materials=disclosure('포스터·프로그램 보기','concert-media');
    // Mobile readers reach the songs before choosing to open the printed material.
    materials.open=false;
    const grid=el('div',null,'print-grid');
    media.forEach(m=>grid.append(printButton(c,m)));materials.append(grid);s.append(materials);
  }
  s.append(el('h3','무대에 담은 곡들'));
  const setlist=el('ol',null,'setlist');setlist.id=`${c.id}-program`;
  for (const entry of [...c.setlist].sort((a,b)=>a.order-b.order)) {
    const li=el('li',null,`set-item ${entry.kind==='event'?'event':''}`); li.id=entry.id;
    const body=el('div'); const song=songMap.get(entry.songId);
    const h=el('h3');
    h.append(song && memberRepertoireIds().has(song.id) ? link(entry.title || song.title,`repertoire.html#${song.id}`) : el('span',entry.title || song?.title));
    body.append(h);
    const badges=el('div');
    for(const format of entry.formats || []) badges.append(pill(format));
    if(entry.isEncore) badges.append(pill('앵콜','red'));
    if(evidenceLabels[entry.evidenceStatus]) badges.append(pill(evidenceLabels[entry.evidenceStatus],'navy'));
    body.append(badges);
    add(body,credits(entry),video(entry));
    const extraSources=(entry.sourceIds||[]).filter(id=>!(c.sourceIds||[]).includes(id));
    if(song || entry.additionalEvents?.length) {
      const story=disclosure('곡 이야기','song-story');
      if(song)story.append(songInformation(song));
      if(entry.originalTitle && entry.originalTitle!==song?.title)story.append(el('p',`자료의 표기 · ${entry.originalTitle}`,'source-note'));
      for(const extra of entry.additionalEvents||[])story.append(el('p',`함께 담은 이야기 · ${extra.title}${evidenceLabels[extra.evidenceStatus] ? ` (${evidenceLabels[extra.evidenceStatus]})` : ''}`));
      if(extraSources.length)story.append(el('p',`곡별 근거 · ${sources(entry.sourceIds)}`,'source-note'));
      body.append(story);
    } else if(extraSources.length) {
      const evidence=disclosure('곡별 근거','song-story');evidence.append(el('p',sources(entry.sourceIds),'source-note'));body.append(evidence);
    }
    add(li,el('span',entry.kind==='event'?'—':entry.isEncore?'EN':String(entry.order).padStart(2,'0'),'set-number'),body); setlist.append(li);
  }
  s.append(setlist);
  if(c.moments?.length) {
    s.append(el('h3','무대에 담은 이야기'));
    s.append(add(el('div',null,'moments'),...c.moments.map(m=>el('p',m,'moment'))));
  }
  s.append(el('p',c.mediaVisibility==='withheld'?'이 공연은 요약 기록만 공개합니다.':c.setlist.some(e=>e.videoUrl)?'곡별 썸네일을 누르면 YouTube에서 공연 영상을 볼 수 있습니다.':'공개가 확인된 현장 사진과 영상은 아직 없습니다.','media-note'));
  const evidence=disclosure('기록의 근거','concert-evidence');
  const evidenceIds=[...new Set([...(c.sourceIds||[]),...c.setlist.flatMap(e=>e.sourceIds||[])])];
  const sourceList=el('ul');evidenceIds.forEach(id=>{const src=sourceMap.get(id);if(src)sourceList.append(el('li',src.label));});
  add(evidence,sourceList,el('p','인쇄 프로그램과 진행 계획은 실제 곡별 연주 여부와 구분해 기록합니다.','source-note'));s.append(evidence);
  const nav=el('nav',null,'concert-pagination'); nav.setAttribute('aria-label',`${c.venue} 이전 다음 공연`);
  if(index>0) nav.append(link(`← ${list[index-1].venue}`,`#${list[index-1].id}`)); else nav.append(el('span'));
  if(index<list.length-1) nav.append(link(`${list[index+1].venue} →`,`#${list[index+1].id}`));
  s.append(nav); return s;
}
function guitarDecoration() {
  const ns='http://www.w3.org/2000/svg';
  const svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 320 250');svg.setAttribute('aria-hidden','true');svg.setAttribute('focusable','false');svg.classList.add('guitar-decoration');
  function shape(tag,attrs){const node=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>node.setAttribute(k,v));svg.append(node);}
  shape('path',{d:'M320 12 C270 6 259 45 221 52 C176 57 175 4 120 14 C70 24 45 72 56 122 C44 178 74 235 126 238 C179 241 183 194 221 201 C260 209 265 249 320 240 Z',fill:'var(--wood-light)',stroke:'var(--brass)', 'stroke-width':'1'});
  [65,61,56].forEach(r=>shape('circle',{cx:'167',cy:'125',r,fill:r===56?'var(--walnut)':'none',stroke:'var(--brass)','stroke-width':r===61?'3':'1'}));
  shape('circle',{cx:'167',cy:'125',r:'51',fill:'var(--ink)',opacity:'.85'});
  shape('rect',{x:'271',y:'81',width:'12',height:'88',rx:'2',fill:'var(--walnut)'});
  for(let i=0;i<6;i++)shape('line',{class:`guitar-string guitar-string-${i+1}`,x1:'5',y1:103+i*9,x2:'282',y2:103+i*9,stroke:'var(--brass)','stroke-width':'.85'});
  return svg;
}
function jumpLabel(c) {return `${c.no?`No.${c.no} · `:''}${c.venue || c.title}`;}
function timeline(list) {
  const items=el('ol',null,'concert-timeline');
  for(const c of list) {
    const a=link('',`#${c.id}`,'timeline-link');
    add(a,el('span',dateText(c),'timeline-date'),add(el('span',null,'timeline-copy'),el('small',c.no?`No.${c.no}`:'공연'),el('strong',c.title),el('span',c.venue||'장소 확인 중')),el('span',concertStatus(c)==='scheduled'?'공연 예정':'종료 공연','timeline-status'),el('span','↗','timeline-arrow'));
    items.append(add(el('li'),a));
  }
  return items;
}
function archive() {
  const year=Number(params.get('year') || site.years[0].year);
  const tabs=el('nav',null,'year-tabs'); tabs.setAttribute('aria-label','아카이브 연도');
  for(const y of site.years) { const a=link(y.year,`archive.html?year=${y.year}`); if(y.year===year)a.setAttribute('aria-current','page'); tabs.append(a); }
  main.append(tabs);
  const y=site.years.find(y=>y.year===year);
  if(!y) { main.append(heading('아직 기록되지 않은 해','ARCHIVE','위에서 기록이 있는 연도를 선택해 주세요.')); return; }
  document.title=`${year}, ${y.title} · 집단적독백`;
  const schedule=homeSchedule(concerts.filter(c=>c.year===year));
  const list=[...schedule.upcoming,...schedule.past,...schedule.pending];
  const album=el('section',null,'album-cover');
  const title=heading(`${year},\n${y.title}`,`${year} · CONCERT ARCHIVE`,y.description);
  const jumps=el('nav',null,'concert-jumps');jumps.setAttribute('aria-label','공연 바로가기');
  list.forEach(c=>jumps.append(link(jumpLabel(c),`#${c.id}`)));title.append(jumps);
  const motif=el('div',null,'album-art');motif.setAttribute('aria-hidden','true');
  add(motif,guitarDecoration(),el('p',y.phrase,'album-phrase'));
  add(album,title,motif,stats(list));main.append(album);
  if(y.historicalLineup) main.append(el('p',`${year}년에는 기타 ${y.historicalLineup.guitars}명과 매니저 ${y.historicalLineup.manager}명이 함께했습니다.`,'historical-note'));
  const navigation=section('그해의 무대');navigation.classList.add('year-navigation');navigation.append(timeline(list));
  const cal=disclosure('한 해 전체 보기','year-calendar');const grid=el('div',null,'calendar');
  for(let month=1;month<=12;month++) {
    const inMonth=list.filter(c=>c.date && Number(c.date.split('-')[1])===month);
    const box=el('div',null,`month ${inMonth.length?'':'empty'}`); box.append(el('span',String(month).padStart(2,'0'),'month-number'));
    for(const c of inMonth) box.append(link(`${c.no ? `No.${c.no} · ` : ''}${c.venue}${concertStatus(c)==='scheduled'?' (예정)':''}`,`#${c.id}`));
    grid.append(box);
  }
  add(cal,grid,el('p','공연을 선택해 그날의 기록을 펼쳐 보세요.','calendar-caption'));navigation.append(cal);main.append(navigation);
  for(const [items,label,status] of [[schedule.upcoming,'예정 공연','scheduled'],[schedule.past,'지난 공연','completed'],[schedule.pending,'일정 확인 중','pending']]){
    if(!items.length)continue;
    const group=section(label);group.classList.add('archive-group');group.dataset.status=status;
    items.forEach(c=>group.append(concertSection(c,list,list.indexOf(c))));main.append(group);
  }
  const rep=section(`${year} 레퍼토리`,link('전체 곡 찾아보기 ↗',`repertoire.html?year=${year}`));
  add(rep,repertoireViews(list),el('p','인쇄 프로그램과 진행 계획은 별도로 표시합니다. 낭송·낭독 이벤트는 곡 수에 포함하지 않습니다.','table-legend'));main.append(rep);
}
function history(c,e) {
  const h=el('div',null,'history');
  add(h,link(`${c.year} · ${c.no?`No.${c.no} · `:''}${c.venue}`,concertLink(c,e)),el('p',dateText(c)),evidenceLabels[e.evidenceStatus] ? pill(evidenceLabels[e.evidenceStatus],'navy') : null);
  const map=venueLink(c.venue);if(map.tagName==='A')h.append(map);
  if(e.title) h.append(el('p',e.title));
  if(concertStatus(c)==='scheduled')h.append(pill('공연 예정','red'));
  if(e.isEncore)h.append(pill('앵콜','red'));
  add(h,el('p',(e.formats || []).join(' · ')),credits(e),video(e));
  if(e.originalTitle && e.originalTitle!==songMap.get(e.songId)?.title)h.append(el('small',`자료의 표기 · ${e.originalTitle}`));
  for(const extra of e.additionalEvents || [])h.append(el('p',`부가 이벤트 · ${extra.title}`));
  h.append(el('p',`근거 · ${sources(e.sourceIds)}`,'source-note')); return h;
}
function repertoire() {
  main.append(heading('곡에서 시작하는 기록.','REPERTOIRE','한 곡이 여러 무대를 이어갑니다. 곡을 열어 공연마다 달랐던 편성과 이야기를 찾아보세요.'));
  const form=el('form',null,'filters'); form.setAttribute('role','search'); form.addEventListener('submit',e=>e.preventDefault());
  const query=el('input'); query.type='search'; query.id='song-query'; query.placeholder='곡명 또는 원본 표기'; query.value=params.get('q')||'';
  const searchLabel=el('label','곡 찾기'); searchLabel.htmlFor=query.id; searchLabel.append(query); form.append(searchLabel);
  function select(label,name,options) {
    const s=el('select');s.id=`filter-${name}`;s.name=name;
    for(const [value,text] of [['','전체'],...options]) { const o=el('option',text);o.value=value;s.append(o); }
    s.value=params.get(name)||''; const l=el('label',label);l.htmlFor=s.id;l.append(s);form.append(l);return s;
  }
  const year=select('연도','year',site.years.map(y=>[String(y.year),String(y.year)]));
  const member=select('참여 멤버','member',members.map(m=>[m.id,m.nickname]));
  const formats=[...new Set(concerts.flatMap(c=>c.setlist.filter(e=>e.kind==='song').flatMap(e=>e.formats || [])))].sort();
  const format=select('편성','format',formats.map(f=>[f,f]));
  const bar=el('div',null,'filter-bottom');const count=el('p'); count.setAttribute('role','status');count.setAttribute('aria-live','polite');
  const reset=el('button','필터 초기화','text-button');reset.type='button';add(bar,count,reset);
  const results=el('div');results.id='song-results';
  add(main,form,bar,results);
  main.append(el('p','멤버 필터는 제공된 공연별 목록에서 닉네임 연결이 확인된 참여를 보여줍니다. 일부 출연진은 확인 중입니다.','source-note'));
  const normalize=s=>String(s).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase().trim();
  function matches(c,e) {
    return (!year.value || c.year===Number(year.value)) && (!member.value || e.credits.some(cr=>cr.memberId===member.value)) && (!format.value || e.formats.includes(format.value));
  }
  function render(updateUrl=false) {
    results.replaceChildren();let n=0;const q=normalize(query.value);
    for(const song of songs.filter(s=>memberRepertoireIds().has(s.id))) {
      if(q && ![song.title,...song.aliases].some(t=>normalize(t).includes(q))) continue;
      const rows=occurrences(song.id).filter(({c,e})=>matches(c,e));if(!rows.length)continue;n++;
      const card=el('details',null,'song-card');card.id=song.id;
      const title=add(el('span'),el('strong',song.title),el('small',song.artistCredit || song.composer || '작곡 정보 확인 중'));
      add(card,add(el('summary'),title,el('span',`${rows.length}개 기록`,'history-count')),
        add(el('div',null,'song-body'),songInformation(song),...rows.map(({c,e})=>history(c,e))));
      results.append(card);
    }
    count.textContent=`${n}곡 · 선택한 조건의 공연 기록`;
    if(!n)results.append(el('p','조건에 맞는 곡이 없습니다. 검색어나 필터를 바꿔 주세요.','empty-state'));
    if(updateUrl) {
      const next=new URLSearchParams();for(const [k,v] of [['q',query.value],['year',year.value],['member',member.value],['format',format.value]])if(v)next.set(k,v);
      window.history.replaceState(null,'',`repertoire.html${next.size?'?'+next:''}${location.hash}`);
    }
    revealHash(false);
  }
  query.addEventListener('input',()=>render(true));[year,member,format].forEach(s=>s.addEventListener('change',()=>render(true)));
  reset.addEventListener('click',()=>{query.value='';year.value='';member.value='';format.value='';render(true);query.focus();});
  render();
}
function memberPage() {
  const roleText=m=>m.roles.join(', ');
  main.append(heading('일곱 사람, 서로 다른 이야기.','OUR MEMBERS','각자의 닉네임으로 만나는 집단적독백. 참여 기록은 멤버별로 차곡차곡 이어집니다.'));
  const grid=el('div',null,'member-grid');
  for(const m of members) {
    const a=link('',`#${m.id}`,'member-card');a.dataset.member=m.id;
    add(a,image(m.avatar,''),el('h3',m.nickname),el('p',roleText(m)));grid.append(a);
  }
  main.append(grid);
  const detail=el('section',null,'member-detail');detail.id='member-detail';detail.setAttribute('aria-live','polite');main.append(detail);
  function choose() {
    const m=memberMap.get(hashId());
    grid.querySelectorAll('a').forEach(a=>a.setAttribute('aria-current',String(a.dataset.member===m?.id)));
    detail.replaceChildren();
    if(!m) { add(detail,el('h2','멤버의 기록 찾아보기'),el('p','멤버를 선택하면 참여 공연과 곡을 볼 수 있습니다.','muted'));return; }
    add(detail,el('h2',`${m.nickname}의 무대`),el('p',roleText(m),'muted'));
    const found=ordered(concerts).flatMap(c=>c.setlist.filter(e=>e.kind==='song' && e.credits.some(cr=>cr.memberId===m.id)).map(e=>({c,e})));
    if(!found.length)detail.append(el('p','닉네임으로 확인된 참여 기록이 아직 없습니다.','empty-state'));
    for(const {c,e} of found) { const box=history(c,e);box.prepend(link(e.title || songMap.get(e.songId).title,`repertoire.html?member=${m.id}#${e.songId}`));detail.append(box); }
    const participantConcerts=concerts.filter(c=>c.participants.some(p=>p.memberId===m.id));
    if(participantConcerts.length)detail.append(add(el('div',null,'card-grid'),...participantConcerts.map(preview)));
    detail.append(link(`${m.nickname} 참여곡 찾아보기 ↗`,`repertoire.html?member=${m.id}`,'button'));
    detail.scrollIntoView({block:'nearest'});
  }
  window.addEventListener('hashchange',choose); choose();
}
function about() {
  main.append(heading('기타를 함께 즐기는 사람들.','ABOUT DOKBAEK','익숙한 노래와 재즈, 영화음악과 작은 소품곡. 클래식 기타를 매개로 만나 음악을 즐기는 밴드입니다.'));
  const moment=(path,alt,caption,eager=false)=>add(el('figure',null,'about-moment'),image(path,alt,'',eager),el('figcaption',caption));
  main.append(moment('image/따뜻한 기타 앙상블 리허설.png','연습실에서 함께 클래식 기타를 연주하는 다섯 사람의 일러스트','서로의 소리에 귀 기울이며, 함께 맞춰 가는 시간.',true));
  const prose=el('div',null,'prose');
  add(prose,el('h2','이름에 담은 이야기'),el('p','‘집단적 독백’은 여럿이 함께 있어도 각자 자기 이야기를 하는 모습을 가리킵니다. 밴드의 대화도 종종 그렇게 흘러갑니다.'),el('p','하지만 연주할 때는 다릅니다. 서로 다른 소리와 표현을 듣고 맞추며, 하나의 음악을 만들어 갑니다. 집단적독백이라는 이름에는 그 즐거움이 담겨 있습니다.'),el('h2','우리가 남기는 기록'),el('p','작은 가족음악회에서 공개 무대까지, 기타와 노래에 짧은 낭송을 더하며 공연을 준비합니다. 이곳에는 공연의 이야기와 프로그램, 곡마다 이어지는 무대의 이력을 모읍니다.'),el('p','확인된 연주와 인쇄 프로그램, 진행 계획을 구분해 기록합니다. 멤버는 닉네임으로 소개하며, 아직 확인되지 않은 내용은 천천히 채워 갑니다.'),el('p','서로 다른 소리, 함께 쓰는 음악.','about-signature'));
  const moments=el('div',null,'about-moments');
  add(moments,
    moment('image/카페에서 함께한 따뜻한 셀카.png','카페에 모여 음료와 디저트를 즐기는 멤버들의 단체 셀카 일러스트','음악 밖에서도 이어지는, 우리의 이야기.'),
    moment('image/따뜻한 음악실 단체 셀카.png','기타와 악보가 있는 음악실에서 함께 웃는 멤버들의 단체 셀카 일러스트','기타와 웃음이 함께하는 연습실.'),
    moment('image/따뜻한 한식당 단체 셀카.png','한식당에서 음식을 나누며 함께 웃는 멤버들의 단체 셀카 일러스트','함께 먹고 웃으며, 또 하나의 추억을 쌓습니다.'));
  prose.insertBefore(moments,prose.querySelectorAll('h2')[1]);
  main.append(prose);
}
function hashId() { try{return decodeURIComponent(location.hash.slice(1));}catch{return '';} }
function initArchiveMotion() {
  if(page!=='archive')return;
  const album=main.querySelector('.album-cover'), timeline=main.querySelector('.concert-timeline');
  if(!album || !timeline)return;
  const art=album.querySelector('.album-art');
  const rows=[...timeline.children];
  const pending=new Set();
  const controller=new AbortController();
  const options={signal:controller.signal};
  let observer;
  // Visibility is never conditional on the observer: animate only upon entry.
  // A failed setup, hash jump, restored page or preference change stays readable.
  const stop=()=>{
    observer?.disconnect();controller.abort();pending.clear();
    album.classList.remove('cover-entering');art.classList.remove('strings-playing');
    timeline.classList.remove('timeline-drawing');
    rows.forEach(row=>row.classList.remove('timeline-entering'));
  };
  try {
    const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
    const restored=performance.getEntriesByType('navigation')[0]?.type==='back_forward';
    if(reduced.matches || location.hash || restored)return;
    reduced.addEventListener('change',stop,options);
    window.addEventListener('pagehide',stop,options);
    window.addEventListener('hashchange',stop,options);
    const playStrings=()=>{
      if(!reduced.matches && !art.classList.contains('strings-playing'))art.classList.add('strings-playing');
    };
    art.addEventListener('animationend',event=>{
      if(event.target===art && event.animationName==='cover-enter')album.classList.remove('cover-entering');
      if(event.target.classList.contains('guitar-string-6'))art.classList.remove('strings-playing');
    },options);
    if(window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
      art.addEventListener('pointerenter',playStrings,options);
      // Keep the decoration out of the tab order; existing cover links can trigger it.
      album.addEventListener('focusin',playStrings,options);
    }
    album.classList.add('cover-entering');playStrings();
    if(!('IntersectionObserver' in window))return;
    const visibleNow=node=>{
      const rect=node.getBoundingClientRect();
      return rect.top<innerHeight && rect.bottom>0;
    };
    if(!visibleNow(timeline))pending.add(timeline);
    rows.forEach(row=>{if(!visibleNow(row))pending.add(row);});
    observer=new IntersectionObserver(entries=>{
      try {
        let animated=0;
        for(const entry of entries) {
          if(!entry.isIntersecting || !pending.has(entry.target))continue;
          pending.delete(entry.target);observer.unobserve(entry.target);
          // Skip delayed deliveries/fast jumps near the top; cap work per frame.
          if(performance.now()-entry.time>160 || entry.boundingClientRect.top<innerHeight*.2)continue;
          if(entry.target===timeline)timeline.classList.add('timeline-drawing');
          else if(animated++<4)entry.target.classList.add('timeline-entering');
        }
        if(!pending.size)observer.disconnect();
      } catch {stop();}
    },{threshold:0,rootMargin:'0px 0px -24px 0px'});
    pending.forEach(node=>observer.observe(node));
    timeline.addEventListener('focusin',event=>{
      const row=event.target.closest('li');
      if(row){row.classList.remove('timeline-entering');pending.delete(row);observer.unobserve(row);}
    },options);
    timeline.addEventListener('animationend',event=>{
      if(event.animationName==='timeline-enter')event.target.classList.remove('timeline-entering');
      if(event.animationName==='timeline-line')timeline.classList.remove('timeline-drawing');
    },options);
  } catch {stop();}
}
function revealHash(scroll=true) {
  if(page==='members')return;
  const target=document.getElementById(hashId());if(!target)return;
  if(target.tagName==='DETAILS')target.open=true;
  if(scroll)requestAnimationFrame(()=>target.scrollIntoView({block:'start',behavior:'instant'}));
}
window.addEventListener('hashchange',()=>revealHash());
const menu=document.querySelector('.menu-toggle');
// Reserve the actual sticky header height, including enlarged text or an open menu.
const headerObserver=new ResizeObserver(([entry])=>{
  document.documentElement.style.setProperty('--header-offset',`${entry.target.getBoundingClientRect().height+16}px`);
});
headerObserver.observe(document.querySelector('.site-header'));
menu.addEventListener('click',()=>{const expanded=menu.getAttribute('aria-expanded')!=='true';menu.setAttribute('aria-expanded',String(expanded));document.querySelector('#main-nav').classList.toggle('is-open',expanded);});
function closeMenu(focus=false) {
  menu.setAttribute('aria-expanded','false');document.querySelector('#main-nav').classList.remove('is-open');
  if(focus)menu.focus();
}
document.addEventListener('click',event=>{if(menu.getAttribute('aria-expanded')==='true' && !event.target.closest('.site-header'))closeMenu();});
document.querySelector('#main-nav').addEventListener('click',event=>{if(event.target.closest('a'))closeMenu();});
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&menu.getAttribute('aria-expanded')==='true'){menu.setAttribute('aria-expanded','false');document.querySelector('#main-nav').classList.remove('is-open');menu.focus();}});
document.querySelectorAll('#main-nav a').forEach(a=>{if(a.getAttribute('href').split(/[.?]/)[0]===page)a.setAttribute('aria-current','page');});
async function load(path) { const response=await fetch(path);if(!response.ok)throw new Error(`자료를 불러오지 못했습니다 (${response.status})`);return response.json(); }
const footerInquiry=link(`공연 문의 · ${inquiryEmail}`,inquiryMailto,'footer-inquiry');
document.querySelector('.site-footer').insertBefore(footerInquiry,document.querySelector('.site-footer>small'));
try {
  [site,members,songs]=await Promise.all(['data/site.json','data/members.json','data/songs.json'].map(load));
  concerts=(await Promise.all(site.years.map(y=>load(y.file)))).flat().filter(c=>['public','public-summary'].includes(c.visibility));
  memberMap=new Map(members.map(m=>[m.id,m]));songMap=new Map(songs.map(s=>[s.id,s]));sourceMap=new Map(site.sources.map(s=>[s.id,s]));
  if(['index','unit'].includes(page)) {
    try {unitPerformances=checkUnitData(await load('data/unit-performances.json'));}
    catch(error){unitError=error;console.error('작은 무대 데이터 로드 실패:',error);}
  }
  main.replaceChildren();
  ({index:home,archive,unit:unitPage,repertoire,members:memberPage,about}[page] || home)();
  const channelIcons={YouTube:'image/youtube.png',Instagram:'image/instagram.png'};
  for(const c of site.channels){
    const channelLink=external(c.label,c.url);
    if(channelIcons[c.label]){
      const icon=el('img');icon.src=channelIcons[c.label];icon.alt=c.label;icon.width=32;icon.height=32;icon.className='channel-icon';
      channelLink.replaceChildren(icon);
      channelLink.setAttribute('aria-label',`${c.label} 공식 채널 (새 창)`);
    }
    document.querySelector('#footer-links').append(channelLink);
  }
  revealHash();
  initArchiveMotion();
} catch(error) {
  main.replaceChildren(add(el('div',null,'error'),el('h1','기록을 불러오지 못했습니다.'),el('p',location.protocol==='file:'?'로컬 서버로 사이트를 열어 주세요. README의 실행 방법을 참고하세요.':'잠시 후 새로고침해 주세요. 자료 파일을 확인해야 할 수 있습니다.'),link('다시 열기',location.href,'button')));
  console.error(error);
}
