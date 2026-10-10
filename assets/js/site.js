const main = document.querySelector('#main');
const page = document.body.dataset.page;
const params = new URLSearchParams(location.search);
let site, members, songs, concerts, memberMap, songMap, sourceMap;
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
function pill(text, color='') { return el('span',text,`pill ${color}`); }
function safeMedia(path) {
  return typeof path === 'string' && /^(image|public-media)\//.test(path) && !path.split('/').includes('..') && !/[\\?#]/.test(path);
}
function image(path, alt, className='', eager=false) {
  const wrap = el('span',null,`image-wrap ${className}`);
  const fallback = () => { wrap.replaceChildren(el('span', '이미지 준비 중', 'image-placeholder')); };
  if (!safeMedia(path)) { fallback(); return wrap; }
  const img = el('img'); img.alt = alt; img.loading = eager ? 'eager' : 'lazy'; img.decoding = 'async';
  img.addEventListener('error',fallback,{once:true}); img.src = path;
  wrap.append(img); return wrap;
}
function dateText(c) {
  if (!c.date) return '날짜 확인 중';
  const [year,month,day] = c.date.split('-').map(Number);
  return `${year}년 ${month}월${c.datePrecision === 'day' ? ` ${day}일` : ''}${c.time ? ` · ${c.time}` : ''}`;
}
function concertLink(c, entry=null) { return `archive.html?year=${c.year}#${entry?.id || c.id}`; }
function ordered(list) { return [...list].sort((a,b)=>(a.date || '').localeCompare(b.date || '') || a.id.localeCompare(b.id)); }
function occurrences(songId, list=concerts) {
  return ordered(list).flatMap(c=>c.setlist.filter(e=>e.kind==='song' && e.songId===songId).map(e=>({c,e})));
}
function stats(list) {
  const complete = list.filter(c=>c.status==='completed').length;
  const upcoming = list.filter(c=>c.status==='scheduled').length;
  const confirmed = new Set(list.flatMap(c=>c.setlist.filter(e=>e.kind==='song' && e.evidenceStatus==='confirmed').map(e=>e.songId))).size;
  const box = el('div',null,'stats');
  for (const [n,label,note] of [[complete,'기록된 공연','공연 기록 기준'],[upcoming,'예정 공연','완료 기록과 별도'],[confirmed,'연주 곡','계획·이벤트 제외']]) {
    box.append(add(el('div',null,'stat'),el('b',n),el('span',label),el('small',note)));
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
  const a=link('',concertLink(c),'concert-preview');
  add(a,el('p',dateText(c),'preview-date'),pill(c.status==='scheduled' ? '공연 예정' : c.no ? `No.${c.no}` : '공연 기록',c.status==='scheduled'?'red':''),
    el('h3',c.title),el('p',c.venue || '장소 확인 중'),el('small',c.story));
  return a;
}
function home() {
  const hero=heading('서로 다른 소리,\n함께 쓰는 음악.','DOKBAEK · CONCERT ARCHIVE',site.description);
  hero.classList.add('home-hero');
  const art=image(site.groupImage,'집단적독백 일곱 멤버의 단체 캐릭터','group-art',true);
  hero.append(art);
  const actions=add(el('div',null,'actions'),link('공연 기록 읽기 ↗',`archive.html?year=${site.years[0].year}`,'button primary'),link('곡으로 찾아보기','repertoire.html','button'));
  hero.append(add(el('div',null,'hero-bottom'),el('small','일곱 사람의 이야기 · 클래식 기타 밴드'),actions));
  add(main,hero,stats(concerts));
  const years=section('한 해씩, 한 장씩.'); const grid=el('div',null,'year-grid');
  for (const y of site.years) {
    const card=link('',`archive.html?year=${y.year}`,'year-card');
    add(card,el('span',y.year,'year-number'),el('span','↗','arrow'),el('h3',y.title),el('p',y.phrase)); grid.append(card);
  }
  years.append(grid); main.append(years);
  const planned=ordered(concerts.filter(c=>c.status==='scheduled' && c.visibility==='public'));
  const upcoming=section('다음 무대');
  upcoming.append(planned.length ? add(el('div',null,'card-grid'),...planned.map(preview)) : el('p','새로운 공개 공연이 정해지면 이곳에 기록합니다.','muted')); main.append(upcoming);
  const recent=section('지난 무대의 기록',link('아카이브 보기 ↗',`archive.html?year=${site.years[0].year}`));
  recent.append(add(el('div',null,'card-grid'),...ordered(concerts.filter(c=>c.status==='completed')).reverse().slice(0,2).map(preview))); main.append(recent);
}
function repertoireTable(list) {
  const songIds=[...new Set(list.flatMap(c=>c.setlist.filter(e=>e.kind==='song').map(e=>e.songId)))];
  const wrap=el('div',null,'table-wrap'); wrap.tabIndex=0; wrap.setAttribute('aria-label','공연별 레퍼토리 비교표, 가로 스크롤 가능');
  const table=el('table'); const caption=el('caption','프로그램에 기록된 레퍼토리'); caption.className='sr-only';
  const head=el('thead'); const tr=el('tr'); add(tr,el('th','곡'));
  for (const c of list) { const th=el('th',c.no ? `No.${c.no}` : c.venue); th.scope='col'; tr.append(th); }
  head.append(tr); const body=el('tbody');
  for (const id of songIds) {
    const row=el('tr'); const title=el('th'); title.scope='row'; title.append(link(songMap.get(id).title,`repertoire.html#${id}`)); row.append(title);
    for (const c of list) {
      const td=el('td'); const entries=c.setlist.filter(e=>e.kind==='song' && e.songId===id);
      for (const e of entries) { const label=[evidenceText(e) || '수록', c.status==='scheduled'?'공연 예정':''].filter(Boolean).join(' · '); const a=link(label,concertLink(c,e)); a.dataset.entryId=e.id; td.append(a); }
      if (!entries.length) td.textContent='—'; row.append(td);
    }
    body.append(row);
  }
  add(table,caption,head,body); wrap.append(table); return wrap;
}
function repertoireViews(list) {
  const view=el('div',null,'repertoire-views');
  const cards=el('div',null,'repertoire-mobile');
  const ids=[...new Set(list.flatMap(c=>c.setlist.filter(e=>e.kind==='song').map(e=>e.songId)))];
  for(const id of ids) {
    const card=el('article',null,'repertoire-mini');card.dataset.songId=id;
    add(card,add(el('h3'),link(songMap.get(id).title,`repertoire.html#${id}`)));
    const records=el('ul');
    for(const {c,e} of occurrences(id,list)) {
      const a=link('',concertLink(c,e));a.dataset.entryId=e.id;
      const label=[evidenceText(e),c.status==='scheduled'?'공연 예정':''].filter(Boolean).join(' · ');
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
  add(b,image(media.path,`${c.venue} ${media.label}`,'print-image'),add(el('span',null,'print-caption'),el('span',media.label),el('span','확대 ↗')));
  b.addEventListener('click',()=>openDialog(`${c.venue} · ${media.label}`,image(media.path,`${c.venue} ${media.label}`,'',true),b));return b;
}
function concertSection(c, list, index) {
  const s=el('section',null,'concert-section'); s.id=c.id;
  const number=add(el('div',null,'concert-number'),el('small',c.no ? 'NO.' : 'LIVE'),el('span',c.no || '♪'));
  const info=el('div',null,'concert-info');
  add(info,pill(c.status==='scheduled'?'공연 예정':c.visibility==='public-summary'?'사적 공연 · 요약 기록':'공연 기록',c.status==='scheduled'?'red':''),el('h2',c.title),el('p',dateText(c)),el('p',c.venue || '장소 확인 중'));
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
      b.addEventListener('click',()=>openDialog(`${c.venue} · ${m.label}`,image(m.path,`${c.venue} ${m.label}`,'',true),b));buttons.append(b);
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
    materials.open=true;
    const grid=el('div',null,'print-grid');
    media.forEach(m=>grid.append(printButton(c,m)));materials.append(grid);s.append(materials);
  }
  s.append(el('h3','무대에 담은 곡들'));
  const setlist=el('ol',null,'setlist');
  for (const entry of [...c.setlist].sort((a,b)=>a.order-b.order)) {
    const li=el('li',null,`set-item ${entry.kind==='event'?'event':''}`); li.id=entry.id;
    const body=el('div'); const song=songMap.get(entry.songId);
    const h=el('h3'); h.append(song ? link(entry.title || song.title,`repertoire.html#${song.id}`) : el('span',entry.title));
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
      if(song?.composer)story.append(el('p',`작곡 · ${song.composer}`,'composer'));
      if(song?.note)story.append(el('p',song.note));
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
  for(let i=0;i<6;i++)shape('line',{x1:'5',y1:103+i*9,x2:'282',y2:103+i*9,stroke:'var(--brass)','stroke-width':'.85'});
  return svg;
}
function jumpLabel(c) {return `${c.no?`No.${c.no} · `:''}${c.venue || c.title}`;}
function timeline(list) {
  const items=el('ol',null,'concert-timeline');
  for(const c of list) {
    const a=link('',`#${c.id}`,'timeline-link');
    add(a,el('span',dateText(c),'timeline-date'),add(el('span',null,'timeline-copy'),el('small',c.no?`No.${c.no}`:'공연'),el('strong',c.title),el('span',c.venue||'장소 확인 중')),el('span',c.status==='scheduled'?'공연 예정':'공연 기록','timeline-status'),el('span','↗','timeline-arrow'));
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
  const list=ordered(concerts.filter(c=>c.year===year));
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
    for(const c of inMonth) box.append(link(`${c.no ? `No.${c.no} · ` : ''}${c.venue}${c.status==='scheduled'?' (예정)':''}`,`#${c.id}`));
    grid.append(box);
  }
  add(cal,grid,el('p','공연을 선택해 그날의 기록을 펼쳐 보세요.','calendar-caption'));navigation.append(cal);main.append(navigation);
  list.forEach((c,i)=>main.append(concertSection(c,list,i)));
  const rep=section(`${year} 레퍼토리`,link('전체 곡 찾아보기 ↗',`repertoire.html?year=${year}`));
  add(rep,repertoireViews(list),el('p','인쇄 프로그램과 진행 계획은 별도로 표시합니다. 낭송·낭독 이벤트는 곡 수에 포함하지 않습니다.','table-legend'));main.append(rep);
}
function history(c,e) {
  const h=el('div',null,'history');
  add(h,link(`${c.year} · ${c.no?`No.${c.no} · `:''}${c.venue}`,concertLink(c,e)),el('p',dateText(c)),evidenceLabels[e.evidenceStatus] ? pill(evidenceLabels[e.evidenceStatus],'navy') : null);
  if(e.title) h.append(el('p',e.title));
  if(c.status==='scheduled')h.append(pill('공연 예정','red'));
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
    for(const song of songs) {
      if(q && ![song.title,...song.aliases].some(t=>normalize(t).includes(q))) continue;
      const rows=occurrences(song.id).filter(({c,e})=>matches(c,e));if(!rows.length)continue;n++;
      const card=el('details',null,'song-card');card.id=song.id;
      const title=add(el('span'),el('strong',song.title),el('small',song.composer || '작곡 정보 확인 중'));
      add(card,add(el('summary'),title,el('span',`${rows.length}개 기록`,'history-count')),
        add(el('div',null,'song-body'),el('p',song.note,'song-description'),...rows.map(({c,e})=>history(c,e))));
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
  main.append(heading('독백이 모여, 하나의 음악으로.','ABOUT DOKBAEK','클래식 기타를 사랑하는 사람들이 모여 서로의 소리를 듣습니다.'));
  const prose=el('div',null,'prose');
  add(prose,el('h2','이름에 담은 이야기'),el('p','‘집단적 독백’은 여럿이 함께 있어도 각자 자기 이야기를 하는 모습을 가리킵니다. 밴드의 대화도 종종 그렇게 흘러갑니다.'),el('p','하지만 연주할 때는 다릅니다. 서로 다른 소리와 표현을 듣고 맞추며, 하나의 음악을 만들어 갑니다. 집단적독백이라는 이름에는 그 즐거움이 담겨 있습니다.'),el('h2','우리가 남기는 기록'),el('p','작은 가족음악회에서 공개 무대까지, 기타와 노래에 짧은 낭송을 더하며 공연을 준비합니다. 이곳에는 공연의 이야기와 프로그램, 곡마다 이어지는 무대의 이력을 모읍니다.'),el('p','확인된 연주와 인쇄 프로그램, 진행 계획을 구분해 기록합니다. 멤버는 닉네임으로 소개하며, 아직 확인되지 않은 내용은 천천히 채워 갑니다.'),el('p','서로 다른 소리, 함께 쓰는 음악.','about-signature'),el('h2','공식 채널'));
  const channels=el('div',null,'channel-list');site.channels.forEach(c=>channels.append(external(c.label+' ↗',c.url)));prose.append(channels);
  prose.append(el('p','Instagram은 외부 링크로 연결합니다. 게시물을 이곳에서 수집하거나 자동으로 불러오지 않습니다.','source-note'));main.append(prose);
}
function hashId() { try{return decodeURIComponent(location.hash.slice(1));}catch{return '';} }
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
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&menu.getAttribute('aria-expanded')==='true'){menu.setAttribute('aria-expanded','false');document.querySelector('#main-nav').classList.remove('is-open');menu.focus();}});
document.querySelectorAll('#main-nav a').forEach(a=>{if(a.getAttribute('href').split(/[.?]/)[0]===page)a.setAttribute('aria-current','page');});
async function load(path) { const response=await fetch(path);if(!response.ok)throw new Error(`자료를 불러오지 못했습니다 (${response.status})`);return response.json(); }
try {
  [site,members,songs]=await Promise.all(['data/site.json','data/members.json','data/songs.json'].map(load));
  concerts=(await Promise.all(site.years.map(y=>load(y.file)))).flat().filter(c=>['public','public-summary'].includes(c.visibility));
  memberMap=new Map(members.map(m=>[m.id,m]));songMap=new Map(songs.map(s=>[s.id,s]));sourceMap=new Map(site.sources.map(s=>[s.id,s]));
  main.replaceChildren();
  ({index:home,archive,repertoire,members:memberPage,about}[page] || home)();
  for(const c of site.channels)document.querySelector('#footer-links').append(external(c.label,c.url));
  revealHash();
} catch(error) {
  main.replaceChildren(add(el('div',null,'error'),el('h1','기록을 불러오지 못했습니다.'),el('p',location.protocol==='file:'?'로컬 서버로 사이트를 열어 주세요. README의 실행 방법을 참고하세요.':'잠시 후 새로고침해 주세요. 자료 파일을 확인해야 할 수 있습니다.'),link('다시 열기',location.href,'button')));
  console.error(error);
}
