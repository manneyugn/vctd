/* VCTĐ Tra cứu — toàn bộ chạy trong trình duyệt, không cần máy chủ ứng dụng. */
'use strict';

const DATA = 'data/';
const LS = 'vctd:';
const KIND_LABEL = {
  nhan_vat:'Nhân vật', the_luc:'Thế lực', dia_danh:'Địa danh',
  cong_phap:'Công pháp', bao_vat:'Bảo vật', canh_gioi:'Cảnh giới', khac:'Khác'
};

const S = {
  meta:null, byNum:new Map(), index:null, entities:null, cooc:null,
  quotes:null, cleanLog:null, summaries:null, shards:new Map(), lookup:null,
  cur:1, route:'doc', wikiKind:'', wikiNguong:50, chat:[], daTaiTruoc:new Set()
};

const $  = (s,r=document)=>r.querySelector(s);
const $$ = (s,r=document)=>[...r.querySelectorAll(s)];
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const norm = s => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/đ/g,'d');
const titleCase = s => s.replace(/(^|\s)(\p{L})/gu, (m,a,b)=>a+b.toUpperCase());
const fmt = n => n.toLocaleString('vi-VN');

/* ---------- tải dữ liệu ---------- */
function showLoad(text, pct){
  const el = $('#loading');
  el.hidden = false;
  $('#loading-text').textContent = text;
  $('#loading-bar').style.width = (pct ?? 0) + '%';
}
const hideLoad = () => { $('#loading').hidden = true; };

async function fetchGz(url){
  const res = await fetch(url);
  if(!res.ok) throw new Error(url + ' → ' + res.status);
  // Nhiều CDN thấy đuôi .gz là tự gắn Content-Encoding: gzip, trình duyệt giải
  // nén sẵn — giải thêm lần nữa sẽ hỏng. Nên thử giải, hỏng thì đọc thẳng.
  const buf = await res.arrayBuffer();
  const laGzip = new Uint8Array(buf.slice(0, 2));
  if(laGzip[0] === 0x1f && laGzip[1] === 0x8b && typeof DecompressionStream === 'function'){
    try{
      const ds = new DecompressionStream('gzip');
      const st = new Blob([buf]).stream().pipeThrough(ds);
      return await new Response(st).json();
    }catch(e){ /* rơi xuống đọc thẳng */ }
  }
  return JSON.parse(new TextDecoder().decode(buf));
}

const once = {};
function lazy(key, loader){
  if(!once[key]) once[key] = loader();
  return once[key];
}
const needIndex   = () => lazy('index',  async()=>{ S.index  = await fetchGz(DATA+'index.json.gz');  buildLookup(); });
const needEnts    = () => lazy('ents',   async()=>{ S.entities = (await fetchGz(DATA+'entities.json.gz')).entities; });
const needCooc    = () => lazy('cooc',   async()=>{ S.cooc   = await fetchGz(DATA+'cooc.json.gz'); });
const needQuotes  = () => lazy('quotes', async()=>{ S.quotes = await fetchGz(DATA+'quotes.json.gz'); });
const needClean   = () => lazy('clean',  async()=>{ S.cleanLog = await fetchGz(DATA+'clean-log.json.gz'); });
// tóm tắt là tuỳ chọn: chưa chạy summarize.py thì app vẫn chạy bình thường
const needSummaries = () => lazy('sum', async()=>{
  try { S.summaries = await fetchGz(DATA+'summaries.json.gz'); }
  catch(e){ S.summaries = {}; }
});

function buildLookup(){
  S.lookup = new Map();
  for(const [name, v] of Object.entries(S.index)){
    S.lookup.set(norm(name), name);
    for(const a of (v.a||[])) S.lookup.set(norm(a), name);
  }
}

async function getChapter(n){
  const ch = S.byNum.get(n);
  if(!ch) return null;
  if(!S.shards.has(ch.s)){
    showLoad(`Đang tải lô chương ${ch.s*S.meta.shardSize+1}–${(ch.s+1)*S.meta.shardSize}…`, 40);
    try{
      S.shards.set(ch.s, await fetchGz(DATA+`shard-${String(ch.s).padStart(3,'0')}.json.gz`));
    } finally { hideLoad(); }
  }
  return { ...ch, paras: S.shards.get(ch.s)[String(n)] || [] };
}

/* ---------- định tuyến ---------- */
function parseHash(){
  const h = location.hash.replace(/^#/, '');
  const [route, ...rest] = h.split('/');
  return { route: route || 'doc', arg: decodeURIComponent(rest.join('/') || '') };
}

async function route(){
  const { route:r, arg } = parseHash();
  S.route = r;
  $$('#tabs button').forEach(b => b.setAttribute('aria-current', String(b.dataset.route === r)));
  $$('.view').forEach(v => v.classList.toggle('on', v.id === 'view-' + r));
  window.scrollTo(0,0);
  if(r === 'doc')         await openChapter(arg ? +arg : S.cur);
  else if(r === 'muc-luc')  renderTOC();
  else if(r === 'tra-cuu')  { await needIndex(); if(arg){ $('#q-input').value = titleCase(arg); await showEntity(arg); } else renderSamples(); }
  else if(r === 'wiki')     { await needIndex(); if(arg) await showEntity(arg, '#wiki-list'); else renderWiki(); }
  else if(r === 'hieu-dinh')await renderClean();
}

/* ---------- đọc truyện ---------- */
// Mọi cách đổi chương (nút trước/sau, phím ← →, ô nhảy chương) đều về đầu chương mới.
// Cuộn SAU khi nội dung mới đã hiện, để không nháy lên đầu chương cũ lúc đang tải lô.
async function openChapter(n){
  await hienChuong(n);
  window.scrollTo({top: 0, behavior: 'instant'});
}
async function hienChuong(n){
  n = Math.min(Math.max(1, n|0), S.meta.chapters.length);
  S.cur = n;
  localStorage.setItem(LS+'last', n);
  const el = $('#chapter');

  if(S.meta.mode === 'tra-cuu'){
    // Bản công khai không kèm nguyên văn: chỉ hiện tóm tắt.
    await needSummaries();
    const meta = S.byNum.get(n) || {};
    const sum = S.summaries?.[String(n)];
    el.innerHTML = `<span class="ch-no">Chương ${n} / ${S.meta.chapters.length}</span>`
      + `<h1>${esc(meta.t || '')}</h1>`
      + (sum ? `<div class="summary"><span>Tóm tắt</span>${esc(sum)}</div>`
             : `<p class="muted">Chương này chưa có tóm tắt.</p>`);
    $('#jump-input').value = n;
    if(location.hash !== '#doc/'+n) history.replaceState(null,'','#doc/'+n);
    document.title = `C.${n} ${meta.t || ''} · VCTĐ`;
    return;
  }

  let ch = null;
  try{
    ch = await getChapter(n);
  }catch(err){
    // Mất mạng và lô chương này chưa được lưu: phải nói rõ, không để màn hình
    // đứng nguyên ở chương cũ làm người đọc tưởng app treo.
    const meta = S.byNum.get(n);
    const lo = meta ? `${meta.s*S.meta.shardSize+1}–${(meta.s+1)*S.meta.shardSize}` : '';
    el.innerHTML = `<span class="ch-no">Chương ${n}</span>`
      + `<h1>Chưa tải được chương này</h1>`
      + `<p class="muted">${navigator.onLine
          ? 'Không tải được dữ liệu chương. Thử lại sau giây lát.'
          : `Bạn đang offline và lô chương ${lo} chưa được lưu. Kết nối mạng rồi mở lại chương này là nó sẽ được lưu cho lần sau.`}</p>`
      + `<p><button id="thu-lai" class="card" style="width:auto;padding:.45rem .9rem">Thử lại</button></p>`;
    $('#thu-lai').onclick = () => openChapter(n);
    document.title = `C.${n} · VCTĐ`;
    return;
  }
  if(!ch){ el.innerHTML = '<p class="muted">Không tìm thấy chương.</p>'; return; }
  el.innerHTML =
    `<span class="ch-no">Chương ${ch.n} / ${S.meta.chapters.length}</span>` +
    `<h1>${esc(ch.t)}</h1>` +
    ch.paras.map(p => `<p>${esc(p)}</p>`).join('');
  $('#jump-input').value = n;
  taiTruocLo(ch.s);
  if(location.hash !== '#doc/'+n) history.replaceState(null,'','#doc/'+n);
  document.title = `C.${n} ${ch.t} · VCTĐ`;
  needSummaries().then(()=>{
    const sum = S.summaries?.[String(n)];
    if(!sum || S.cur !== n || $('#chapter .summary')) return;
    const box = document.createElement('div');
    box.className = 'summary';
    box.innerHTML = `<span>Tóm tắt</span>${esc(sum)}`;
    $('#chapter h1').after(box);
  });
}
const go = d => openChapter(S.cur + d);

/* ---------- mục lục ---------- */
function renderTOC(){
  const q = norm($('#toc-filter').value.trim());
  const list = S.meta.chapters.filter(c => !q || norm(c.t).includes(q) || String(c.n) === q);
  $('#toc-count').textContent = `${fmt(list.length)} chương`;
  const frag = document.createDocumentFragment();
  for(const c of list.slice(0, 1200)){
    const a = document.createElement('a');
    a.href = '#doc/' + c.n;
    a.innerHTML = `<b>${c.n}</b><span>${esc(c.t)}</span>`;
    frag.append(a);
  }
  if(list.length > 1200){
    const d = document.createElement('div');
    d.className = 'row'; d.innerHTML = `<span class="muted">… còn ${fmt(list.length-1200)} chương, hãy lọc để thu hẹp.</span>`;
    frag.append(d);
  }
  $('#toc-list').replaceChildren(frag);
}

/* ---------- tra cứu ---------- */
const SAMPLES = ['trương nhược trần','trì dao','côn lôn giới','bất tử huyết tộc','thiên đình','địa ngục giới'];
function renderSamples(){
  $('#q-samples').innerHTML = SAMPLES.map(s=>`<button data-q="${esc(s)}">${esc(titleCase(s))}</button>`).join('');
  $('#q-results').innerHTML = '';
  $('#entity-detail').innerHTML = '';
}

function searchEntities(q, limit=40){
  const nq = norm(q.trim());
  if(!nq) return [];
  const hits = [];
  for(const [name, v] of Object.entries(S.index)){
    const nn = norm(name);
    let score = 0;
    if(nn === nq) score = 1000;
    else if(nn.startsWith(nq)) score = 500;
    else if(nn.includes(nq)) score = 200;
    else if((v.a||[]).some(a => norm(a).includes(nq))) score = 150;
    if(score) hits.push([score + Math.log(v.n), name, v]);
  }
  return hits.sort((a,b)=>b[0]-a[0]).slice(0, limit);
}

function cardHTML(name, v){
  return `<button class="card" data-ent="${esc(name)}">
    <div class="nm">${esc(titleCase(name))}</div>
    <div class="meta">
      <span class="tag ${v.k}">${KIND_LABEL[v.k]}</span>
      <span>${fmt(v.n)} lần nhắc</span>
      <span>chương ${v.f}–${v.l}</span>
      ${(v.a||[]).length ? `<span>bí danh: ${esc(v.a.map(titleCase).join(', '))}</span>` : ''}
    </div></button>`;
}

async function runSearch(){
  const q = $('#q-input').value.trim();
  $('#entity-detail').innerHTML = '';
  if(!q){ renderSamples(); return; }
  await needIndex();
  const hits = searchEntities(q);
  $('#q-samples').innerHTML = '';
  $('#q-results').innerHTML = hits.length
    ? hits.map(([,n,v]) => cardHTML(n,v)).join('')
    : `<p class="muted">Không có thực thể nào khớp “${esc(q)}”. Chỉ mục chỉ chứa tên riêng xuất hiện đủ nhiều trong truyện.</p>`;
}

/* ---------- chi tiết thực thể ---------- */
async function showEntity(name, scrollTo){
  await Promise.all([needIndex(), needCooc(), needQuotes(), needSummaries()]);
  const canon = S.index[name] ? name : (S.lookup.get(norm(name)) || name);
  const v = S.index[canon];
  const host = S.route === 'wiki' ? $('#wiki-list') : $('#entity-detail');
  if(!v){ host.innerHTML = `<p class="muted">Không có dữ liệu cho “${esc(name)}”.</p>`; return; }

  const total = S.meta.chapters.length;
  const BUCKETS = 60, buckets = new Array(BUCKETS).fill(0);
  for(const [c,k] of v.c) buckets[Math.min(BUCKETS-1, Math.floor((c-1)/total*BUCKETS))] += k;
  const peak = Math.max(...buckets, 1);
  const top = [...v.c].sort((a,b)=>b[1]-a[1]).slice(0,24).sort((a,b)=>a[0]-b[0]);
  const rel = (S.cooc[canon]||[]).filter(n => S.index[n]);
  const qs  = S.quotes[canon] || [];
  const moc = chonMoc(v, canon);

  host.innerHTML = `<div class="detail">
    <h3>${esc(titleCase(canon))} <span class="tag ${v.k}">${KIND_LABEL[v.k]}</span></h3>
    ${(v.a||[]).length ? `<div class="aliases">Cũng gọi là: ${esc(v.a.map(titleCase).join(' · '))}</div>` : ''}
    <div class="stat-row">
      <div class="stat"><b>${fmt(v.n)}</b><span>lần được nhắc</span></div>
      <div class="stat"><b>${fmt(v.c.length)}</b><span>chương có mặt</span></div>
      <div class="stat"><b>${v.f}</b><span>xuất hiện đầu</span></div>
      <div class="stat"><b>${v.l}</b><span>xuất hiện cuối</span></div>
    </div>
    <h4>Mật độ xuất hiện theo mạch truyện</h4>
    <div class="spark">${buckets.map((b,i)=>{
      const from = Math.floor(i/BUCKETS*total)+1, to = Math.floor((i+1)/BUCKETS*total);
      return `<i style="height:${Math.round(b/peak*100)}%" title="chương ${from}–${to}: ${fmt(b)} lần"></i>`;
    }).join('')}</div>
    <div class="spark-x"><span>chương 1</span><span>chương ${total}</span></div>
    <h4>Chương tập trung nhất</h4>
    <div class="ch-links">${top.map(([c,k])=>`<a href="#doc/${c}">c.${c}<span class="muted"> ·${k}</span></a>`).join('')}</div>
    ${moc.length ? `<h4>Dòng thời gian</h4><ol class="moc">${moc.map(m =>
      `<li><a href="#doc/${m.n}">c.${m.n}</a><span>${esc(m.t)}</span></li>`).join('')}</ol>` : ''}
    ${rel.length ? `<h4>Thường đi cùng</h4><div class="pill-list">${
      rel.map(n=>`<button data-ent="${esc(n)}">${esc(titleCase(n))}</button>`).join('')}</div>` : ''}
    ${qs.length ? `<h4>Trích dẫn trong truyện</h4>${
      qs.map(q=>`<div class="quote">${esc(q.t)}<br><a href="#doc/${q.n}">→ chương ${q.n}</a></div>`).join('')}` : ''}
  </div>`;
  if(scrollTo) host.scrollIntoView({behavior:'smooth', block:'start'});
}

/* ---------- dòng thời gian dựng từ tóm tắt ---------- */
const MOC = 9;                      // số mốc tối đa trên một dòng thời gian

function tachCau(text){
  return text.split(/(?<=[.!?…])\s+/).map(s => s.trim()).filter(Boolean);
}

/**
 * Tên có trong câu không — KHÔNG dùng norm() ở đây.
 * Bỏ dấu làm "bắt Tử" trùng với "Bất Tử", còn chữ hoa thường thì vô hại,
 * nên so sánh giữ nguyên dấu và chỉ hạ chữ hoa, kèm ranh giới từ.
 */
const LA_CHU = /\p{L}/u;
function chuaTen(cau, ten){
  const c = cau.toLowerCase(), t = ten.toLowerCase();
  for(let i = c.indexOf(t); i !== -1; i = c.indexOf(t, i + 1)){
    const truoc = c[i - 1], sau = c[i + t.length];
    if(!(truoc && LA_CHU.test(truoc)) && !(sau && LA_CHU.test(sau))) return true;
  }
  return false;
}

/** Câu trong tóm tắt chương `n` có nhắc tới thực thể này. */
function cauNhacToi(n, ten, biDanh){
  const sum = S.summaries?.[String(n)];
  if(!sum) return null;
  const keys = [ten, ...biDanh];
  const hit = tachCau(sum).filter(c => keys.some(k => chuaTen(c, k)));
  if(!hit.length) return null;
  let t = hit.slice(0, 2).join(' ');
  if(t.length > 300) t = t.slice(0, 297).trimEnd() + '…';
  return t;
}

/**
 * Chọn các mốc trải đều suốt mạch truyện: chia khoảng xuất hiện của thực thể
 * thành MOC đoạn, mỗi đoạn lấy chương được nhắc nhiều nhất MÀ tóm tắt có nói tới nó.
 * Luôn giữ chương đầu và chương cuối vì đó là hai mốc có ý nghĩa nhất.
 */
function chonMoc(v, ten){
  const biDanh = v.a || [];
  const co = v.c.filter(([c]) => S.summaries?.[String(c)]);
  if(!co.length) return [];
  const dau = co[0][0], cuoi = co[co.length - 1][0];
  const rong = Math.max(1, cuoi - dau + 1);
  const thung = new Map();
  for(const [c, k] of co){
    const i = Math.min(MOC - 1, Math.floor((c - dau) / rong * MOC));
    const cu = thung.get(i);
    if(!cu || k > cu[1]) thung.set(i, [c, k]);
  }
  const ds = [...new Set([dau, ...[...thung.values()].map(x => x[0]), cuoi])].sort((a, b) => a - b);
  const out = [];
  for(const c of ds){
    const t = cauNhacToi(c, ten, biDanh);
    if(t) out.push({ n: c, t });
  }
  return out.slice(0, MOC + 2);
}

/* ---------- wiki ---------- */
async function renderWiki(){
  await needIndex();
  const kinds = ['', ...Object.keys(KIND_LABEL)];
  $('#wiki-kinds').innerHTML = kinds.map(k =>
    `<button data-kind="${k}" aria-pressed="${S.wikiKind===k}">${k ? KIND_LABEL[k] : 'Tất cả'}</button>`).join('');
  // Nửa dưới chỉ mục là mảnh vụn tần suất thấp, nên mặc định chỉ hiện mục nổi bật.
  // Tab Tra cứu vẫn tìm được tất cả, ngưỡng này chỉ áp cho việc duyệt wiki.
  const NGUONG = [[50,'Nổi bật'],[200,'Chủ chốt'],[0,'Tất cả']];
  $('#wiki-nguong').innerHTML = NGUONG.map(([n,t]) =>
    `<button data-nguong="${n}" aria-pressed="${S.wikiNguong===n}">${t}${n?` <span class="muted">≥${n}</span>`:''}</button>`).join('');
  const q = norm($('#wiki-filter').value.trim());
  let rows = Object.entries(S.index);
  if(S.wikiNguong) rows = rows.filter(([,v]) => v.n >= S.wikiNguong);
  if(S.wikiKind) rows = rows.filter(([,v]) => v.k === S.wikiKind);
  if(q) rows = rows.filter(([n,v]) => norm(n).includes(q) || (v.a||[]).some(a=>norm(a).includes(q)));
  rows.sort((a,b)=>b[1].n-a[1].n);
  const tong = Object.keys(S.index).length;
  $('#wiki-count').textContent = `${fmt(rows.length)} thực thể`
    + (S.wikiNguong && !q ? ` · ẩn ${fmt(tong - Object.values(S.index).filter(v=>v.n>=S.wikiNguong).length)} mục hiếm` : '');
  $('#wiki-list').innerHTML = rows.slice(0,200).map(([n,v]) => cardHTML(n,v)).join('')
    + (rows.length>200 ? `<p class="muted small">… còn ${fmt(rows.length-200)} mục, hãy lọc để thu hẹp.</p>` : '');
}

/* ---------- hiệu đính ---------- */
const CLEAN_LABEL = {
  quote_spacing:'Khoảng trắng quanh ngoặc kép', punct_spacing:'Dấu câu dính chữ',
  ellipsis:'Dấu ba chấm kéo dài', junk_links:'Link rác / watermark', whitespace:'Khoảng trắng thừa',
  dau_cau:'Dấu câu kiểu Trung (「」《》、。)', rac:'Lời tác giả / converter', chu_han:'Chữ Hán sót',
  ten_rieng:'Tên riêng gõ sai', chinh_ta:'Lỗi chính tả', ngoac_kep:'Khoảng trắng trong ngoặc kép',
  viet_hoa_ten:'Viết hoa tên riêng / thuật ngữ', viet_hoa_dau_cau:'Viết hoa đầu câu', noi_doan:'Nối đoạn bị cắt giữa câu'
};
async function renderClean(){
  await needClean();
  const t = S.cleanLog.totals;
  $('#clean-stats').innerHTML =
    `<div class="stat"><b>${fmt(S.cleanLog.chapters.length)}</b><span>chương được sửa</span></div>` +
    `<div class="stat"><b>${fmt(Object.values(t).reduce((a,b)=>a+b,0))}</b><span>vị trí đã sửa</span></div>` +
    Object.entries(t).map(([k,v])=>`<div class="stat"><b>${fmt(v)}</b><span>${CLEAN_LABEL[k]||k}</span></div>`).join('');
  drawCleanList();
}
function drawCleanList(){
  const q = $('#clean-filter').value.trim();
  const rows = S.cleanLog.chapters.filter(r => !q || String(r.n).startsWith(q));
  $('#clean-list').innerHTML = rows.slice(0,400).map(r =>
    `<a href="#doc/${r.n}"><b>${r.n}</b><span>${
      Object.entries(r.fixes).map(([k,v])=>`${CLEAN_LABEL[k]||k}: ${v}`).join(' · ')}</span></a>`).join('')
    + (rows.length>400 ? `<div class="row"><span class="muted">… còn ${fmt(rows.length-400)} chương.</span></div>` : '');
}

/* ---------- chat: tra cứu 6 bước rồi mới nhờ AI diễn giải ---------- */
const cfg = {
  get provider(){ return localStorage.getItem(LS+'provider') || 'gemini'; },
  get key(){ return localStorage.getItem(LS+(this.provider==='gemini'?'key':'key2')) || ''; },
  get model(){ return localStorage.getItem(LS+(this.provider==='gemini'?'model':'model2'))
                 || (this.provider==='gemini' ? 'gemini-3.5-flash-lite' : ''); },
  get base(){ return localStorage.getItem(LS+'base') || ''; },
  get sanSang(){ return this.provider==='openai' ? !!(this.base && this.model) : !!this.key; }
};

/* --- ① nhận diện thực thể --- */
function nhanDienThucThe(text){
  const found = [];
  for(const [name, v] of Object.entries(S.index)){
    for(const k of [name, ...(v.a||[])]){
      if(k.length >= 5 && chuaTen(text, k)){ found.push(name); break; }
    }
  }
  return [...new Set(found)]
    .sort((a,b) => S.index[b].n - S.index[a].n)
    .slice(0, 6);
}

/* --- ③ xếp hạng chương: ưu tiên chương có NHIỀU thực thể cùng xuất hiện --- */
function xepHangChuong(ents, limit=8){
  const diem = new Map(), soThucThe = new Map();
  for(const e of ents){
    for(const [c,k] of S.index[e].c){
      diem.set(c, (diem.get(c)||0) + k);
      soThucThe.set(c, (soThucThe.get(c)||0) + 1);
    }
  }
  for(const [c,n] of soThucThe) if(n > 1) diem.set(c, diem.get(c) * (1 + n));
  return [...diem].sort((a,b)=>b[1]-a[1]).slice(0, limit).map(([c])=>c);
}

/* --- ⑤ bằng chứng: tóm tắt trước (rẻ, phủ cả 4211 chương), nguyên văn sau --- */
async function thuThapBangChung(chapters, ents){
  const tomTat = chapters.map(n => ({ n, s: S.summaries?.[String(n)] })).filter(x => x.s);
  const nguyenVan = [];
  for(const n of (S.meta.mode === 'tra-cuu' ? [] : chapters.slice(0, 2))){           // chỉ 2 chương sát nhất mới nạp toàn văn
    let ch = null;
    try { ch = await getChapter(n); } catch(e){ continue; }
    if(!ch) continue;
    const keep = ch.paras.filter(p => ents.some(e => chuaTen(p, e))).slice(0, 3);
    if(keep.length) nguyenVan.push({ n, t: ch.t, text: keep.join('\n').slice(0, 1800) });
  }
  return { tomTat, nguyenVan };
}

function dungPrompt(q, ents, moc, bc, lichSu){
  const thucThe = ents.map(e => {
    const v = S.index[e];
    return `- ${titleCase(e)} (${KIND_LABEL[v.k]}): ${fmt(v.n)} lần nhắc, xuất hiện c.${v.f}–c.${v.l}`
      + ((v.a||[]).length ? `, còn gọi là ${v.a.map(titleCase).join(', ')}` : '');
  }).join('\n');
  return `Bạn trả lời câu hỏi về tiểu thuyết "Vạn Cổ Thần Đế" (Phi Thiên Ngư) DỰA HOÀN TOÀN vào tư liệu dưới đây.

QUY TẮC
- Chỉ dùng thông tin trong tư liệu. Không suy đoán, không bịa.
- Mỗi ý phải ghi nguồn dạng c.<số chương>.
- Nếu tư liệu không đủ để trả lời, nói thẳng là không đủ căn cứ và cho biết nên đọc chương nào.
- Trả lời bằng tiếng Việt, ngắn gọn, đi thẳng vào câu hỏi.

THỰC THỂ NHẬN RA
${thucThe || '(không có)'}

DÒNG THỜI GIAN
${moc.length ? moc.map(m => `- c.${m.n}: ${m.t}`).join('\n') : '(không có)'}

TÓM TẮT CÁC CHƯƠNG LIÊN QUAN NHẤT
${bc.tomTat.map(x => `[c.${x.n}] ${x.s}`).join('\n') || '(không có)'}

TRÍCH NGUYÊN VĂN
${bc.nguyenVan.map(e => `[c.${e.n} — ${e.t}]\n${e.text}`).join('\n\n') || '(không có)'}
${lichSu ? `\nHỘI THOẠI TRƯỚC ĐÓ\n${lichSu}` : ''}
CÂU HỎI: ${q}`;
}

/* --- ⑥ gọi AI: Gemini hoặc máy chủ OpenAI-compatible của bạn --- */
async function goiAI(prompt){
  if(cfg.provider === 'openai'){
    const r = await fetch(cfg.base.replace(/\/$/,'') + '/v1/chat/completions', {
      method:'POST',
      headers: Object.assign({'Content-Type':'application/json'},
                             cfg.key ? {'Authorization':'Bearer '+cfg.key} : {}),
      body: JSON.stringify({ model: cfg.model, messages:[{role:'user',content:prompt}],
                             temperature:0.3, max_tokens:8000 })
    });
    if(!r.ok) throw new Error(`Máy chủ trả lỗi ${r.status}. ${await r.text().catch(()=>'')}`.slice(0,300));
    const j = await r.json();
    const m = j.choices?.[0]?.message || {};
    const txt = (m.content || '').replace(/<think>[\s\S]*?<\/think>/g,'').trim();
    if(!txt) throw new Error('Model trả về rỗng — nhiều khả năng hết max_tokens khi đang "nghĩ".');
    return txt;
  }
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${cfg.model}:generateContent?key=${encodeURIComponent(cfg.key)}`;
  const r = await fetch(url, { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ contents:[{parts:[{text:prompt}]}],
      generationConfig:{temperature:0.3, maxOutputTokens:1600} }) });
  if(r.status === 429) throw new Error('Hết hạn mức hôm nay (429). Đổi sang model lite trong ⚙ Cài đặt.');
  if(!r.ok) throw new Error('Gemini trả lỗi ' + r.status + '. Kiểm tra lại API key trong ⚙ Cài đặt.');
  const j = await r.json();
  return j.candidates?.[0]?.content?.parts?.map(p=>p.text).join('') || '(không có nội dung trả về)';
}

function pushMsg(cls, html){
  const d = document.createElement('div');
  d.className = 'msg ' + cls;
  d.innerHTML = html;
  $('#chat-log').append(d);
  d.scrollIntoView({behavior:'smooth', block:'end'});
  return d;
}
const linkCites = s => esc(s).replace(/c\.(\d{1,4})/g, (m,n)=>`<a href="#doc/${n}">c.${n}</a>`);

async function sendChat(){
  const q = $('#chat-input').value.trim();
  if(!q) return;
  $('#chat-input').value = ''; $('#chat-input').style.height = 'auto';
  pushMsg('me', esc(q));
  const bubble = pushMsg('ai', '<div class="steps">① Đang nhận diện thực thể…</div>');
  const buoc = t => { const e = bubble.querySelector('.steps'); if(e) e.textContent = t; };

  try{
    await Promise.all([needIndex(), needQuotes(), needSummaries()]);
    const ents = nhanDienThucThe(q);
    if(!ents.length){
      bubble.innerHTML = 'Mình không nhận ra tên riêng nào trong câu hỏi. Hãy nhắc tên nhân vật, thế lực hoặc địa danh cụ thể — ví dụ <em>“Trương Nhược Trần gặp Trì Dao lần đầu ở chương nào?”</em>';
      return;
    }
    buoc(`② Tra chỉ mục: ${ents.map(titleCase).join(', ')}`);
    const chapters = xepHangChuong(ents);
    buoc(`③ Xếp hạng chương → ${chapters.slice(0,5).map(c=>'c.'+c).join(', ')}…`);
    const moc = chonMoc(S.index[ents[0]], ents[0]);
    buoc(`④ Dòng thời gian: ${moc.length} mốc`);
    const bc = await thuThapBangChung(chapters, ents);
    buoc(`⑤ Bằng chứng: ${bc.tomTat.length} tóm tắt + ${bc.nguyenVan.length} trích nguyên văn`);

    if(!cfg.sanSang){
      bubble.innerHTML = `<div class="steps">Chưa cấu hình AI — đây là kết quả tra cứu thuần chỉ mục:</div>`
        + `<b>Thực thể</b><br>${ents.map(e=>`${esc(titleCase(e))} — c.${S.index[e].f}–${S.index[e].l}, ${fmt(S.index[e].n)} lần`).join('<br>')}`
        + (moc.length ? `<br><br><b>Dòng thời gian</b><ol class="moc">${moc.map(m=>`<li><a href="#doc/${m.n}">c.${m.n}</a><span>${esc(m.t)}</span></li>`).join('')}</ol>` : '')
        + `<br><b>Chương liên quan nhất</b><div class="cites ch-links">${chapters.map(c=>`<a href="#doc/${c}">c.${c}</a>`).join('')}</div>`
        + `<p class="muted small">${cfg.provider==='openai'
             ? 'Điền Base URL và tên model của máy chủ bạn trong ⚙ Cài đặt'
             : 'Thêm Gemini API key trong ⚙ Cài đặt'} để bước ⑥ tổng hợp bằng AI.</p>`;
      S.chat.push({q, a:'(tra cứu thuần)'});
      return;
    }
    buoc(`⑥ ${cfg.provider==='openai' ? cfg.model : cfg.model} đang tổng hợp…`);
    const lichSu = S.chat.slice(-3).map(t => `Hỏi: ${t.q}\nĐáp: ${t.a}`).join('\n');
    const ans = await goiAI(dungPrompt(q, ents, moc, bc, lichSu));
    S.chat.push({q, a: ans.slice(0, 600)});
    bubble.innerHTML = `<div class="steps">Nguồn: ${bc.tomTat.map(x=>'c.'+x.n).join(', ')} · ${cfg.model}</div>`
      + linkCites(ans).replace(/\n/g,'<br>');
  }catch(err){
    bubble.innerHTML = `<span class="muted">${esc(err.message)}</span>`;
  }
}

/* ---------- tuỳ chỉnh hiển thị ---------- */
const prefs = {
  fs: +localStorage.getItem(LS+'fs') || 19,
  lh: +localStorage.getItem(LS+'lh') || 1.8,
  w:  +localStorage.getItem(LS+'w')  || 42,
  font: localStorage.getItem(LS+'font') || 'serif',
  // chưa từng chọn: theo hệ điều hành; đã chọn: nhớ lựa chọn
  theme: localStorage.getItem(LS+'theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'toi' : 'sang'),
  lastLight: null
};
function applyPrefs(){
  const r = document.documentElement.style;
  r.setProperty('--fs', prefs.fs+'px');
  r.setProperty('--lh', prefs.lh);
  r.setProperty('--w', prefs.w+'rem');
  document.body.dataset.font = prefs.font;
  document.body.dataset.theme = prefs.theme;
  $('#fs-val').textContent = prefs.fs;
  $('#lh-val').textContent = prefs.lh.toFixed(1);
  $('#w-val').textContent = prefs.w;
  $$('[data-font]').forEach(b=>b.setAttribute('aria-pressed', String(b.dataset.font===prefs.font)));
  $$('.sheet [data-theme]').forEach(b=>b.setAttribute('aria-pressed', String(b.dataset.theme===prefs.theme)));
  for(const k of ['fs','lh','w','font','theme']) localStorage.setItem(LS+k, prefs[k]);
  veThemeIcon();
}

/* ---------- nút chuyển sáng/tối trên header ---------- */
const ICO_SUN  = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32 1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41m11.32-11.32 1.41-1.41"/></svg>';
const ICO_MOON = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
function veThemeIcon(){
  const b = $('#btn-theme');
  if(!b) return;
  const toi = prefs.theme === 'toi';
  b.innerHTML = toi ? ICO_SUN : ICO_MOON;
  b.title = toi ? 'Chuyển sang chế độ sáng' : 'Chuyển sang chế độ tối';
  b.setAttribute('aria-pressed', String(toi));
}
// tối ⇄ nền sáng trước đó (sang hoặc giay), để không giẫm lên chủ đề giấy
function dapTheme(){
  if(prefs.theme === 'toi') prefs.theme = prefs.lastLight || 'sang';
  else { prefs.lastLight = prefs.theme; prefs.theme = 'toi'; }
  applyPrefs();
}

/* ---------- header tự ẩn khi cuộn xuống ---------- */
function autoHideTop(){
  const bar = $('.top');
  if(!bar) return;
  let lastY = scrollY, que = false;
  addEventListener('scroll', () => {
    if(que) return;   // gom vào rAF: nhiều sự kiện cuộn trong một khung hình
    que = true;
    requestAnimationFrame(() => {
      que = false;
      const y = scrollY, d = y - lastY;
      if(Math.abs(d) < 8) return;   // ngưỡng nhỏ để khỏi giật
      const xuong = d > 0;
      lastY = y;
      bar.classList.toggle('hide', y < 24 ? false : xuong);
    });
  }, {passive:true});
}

/* ---------- lưu offline theo lô ---------- */
function dangKySW(){
  if(!('serviceWorker' in navigator)) return;
  navigator.serviceWorker.register('sw.js').catch(()=>{});
}

/** Lô kế tiếp được tải ngầm khi rảnh, nên đọc liên tục không chạm mạng. */
function taiTruocLo(sid){
  if(S.meta.mode === 'tra-cuu') return;
  const tong = Math.ceil(S.meta.chapters.length / S.meta.shardSize);
  const ran = cb => (window.requestIdleCallback || (f=>setTimeout(f,1200)))(cb);
  for(const k of [sid+1, sid-1]){
    if(k < 0 || k >= tong || S.daTaiTruoc.has(k)) continue;
    S.daTaiTruoc.add(k);
    ran(()=> fetch(DATA+`shard-${String(k).padStart(3,'0')}.json.gz`).catch(()=>{}));
  }
}

/** Đã lưu được bao nhiêu lô — hiện trong ⚙ Cài đặt. */
async function demLoDaLuu(){
  if(!('caches' in window)) return null;
  try{
    const ten = (await caches.keys()).find(k => k.endsWith('-du-lieu'));
    if(!ten) return 0;
    const ks = await (await caches.open(ten)).keys();
    return ks.filter(r => /shard-\d+\.json\.gz$/.test(r.url)).length;
  }catch(e){ return null; }
}

/* ---------- khởi động ---------- */
(async function boot(){
  applyPrefs();
  dangKySW();
  showLoad('Đang tải mục lục…', 20);
  S.meta = await (await fetch(DATA+'chapters.json')).json();
  S.meta.chapters.forEach(c => S.byNum.set(c.n, c));
  hideLoad();
  S.cur = +localStorage.getItem(LS+'last') || 1;
  $('#api-provider').value = cfg.provider;
  $('#api-key').value    = localStorage.getItem(LS+'key')    || '';
  $('#api-model').value  = localStorage.getItem(LS+'model')  || 'gemini-3.5-flash-lite';
  $('#api-base').value   = cfg.base;
  $('#api-model2').value = localStorage.getItem(LS+'model2') || '';
  $('#api-key2').value   = localStorage.getItem(LS+'key2')   || '';
  $('#cfg-gemini').hidden = cfg.provider !== 'gemini';
  $('#cfg-openai').hidden = cfg.provider !== 'openai';

  addEventListener('hashchange', route);
  autoHideTop();
  $('#btn-theme').onclick = dapTheme;
  $('#tabs').onclick = e => { const b = e.target.closest('button'); if(b) location.hash = '#'+b.dataset.route; };

  $('#prev-ch').onclick = $('#prev-ch2').onclick = () => go(-1);
  $('#next-ch').onclick = $('#next-ch2').onclick = () => go(1);
  $('#to-top').onclick = () => scrollTo({top:0, behavior:'smooth'});
  $('#jump-go').onclick = () => openChapter(+$('#jump-input').value);
  $('#jump-input').onkeydown = e => { if(e.key==='Enter') openChapter(+e.target.value); };

  $('#toc-filter').oninput = renderTOC;
  $('#wiki-filter').oninput = renderWiki;
  $('#clean-filter').oninput = drawCleanList;
  $('#q-input').oninput = debounce(runSearch, 160);
  $('#wiki-kinds').onclick = e => { const b=e.target.closest('button'); if(b){ S.wikiKind=b.dataset.kind; renderWiki(); } };
  $('#wiki-nguong').onclick = e => { const b=e.target.closest('button'); if(b){ S.wikiNguong=+b.dataset.nguong; renderWiki(); } };

  document.body.addEventListener('click', e => {
    const s = e.target.closest('[data-q]');
    if(s){ $('#q-input').value = titleCase(s.dataset.q); runSearch(); return; }
    const b = e.target.closest('[data-ent]');
    if(b){ showEntity(b.dataset.ent, true); }
  });

  const sheet = $('#typo-sheet');
  $('#btn-typo').onclick = () => { sheet.hidden = !sheet.hidden; };
  $('#typo-close').onclick = () => { sheet.hidden = true; };
  // Màn chạm không có hover: chạm ra ngoài hộp cũng phải đóng được
  addEventListener('pointerdown', e => {
    if(!sheet.hidden && !sheet.contains(e.target) && !e.target.closest('#btn-typo')) sheet.hidden = true;
  }, {passive:true});
  $('#typo-sheet').onclick = e => {
    const b = e.target.closest('button'); if(!b) return;
    const t = b.dataset.typo;
    if(t==='fs+') prefs.fs = Math.min(30, prefs.fs+1);
    if(t==='fs-') prefs.fs = Math.max(14, prefs.fs-1);
    if(t==='lh+') prefs.lh = Math.min(2.6, prefs.lh+0.1);
    if(t==='lh-') prefs.lh = Math.max(1.2, prefs.lh-0.1);
    if(t==='w+')  prefs.w  = Math.min(70, prefs.w+2);
    if(t==='w-')  prefs.w  = Math.max(26, prefs.w-2);
    if(b.dataset.font)  prefs.font  = b.dataset.font;
    if(b.dataset.theme) prefs.theme = b.dataset.theme;
    applyPrefs();
  };

  const veOffline = async () => {
    const n = await demLoDaLuu();
    const tong = Math.ceil(S.meta.chapters.length / S.meta.shardSize);
    $('#offline-trangthai').textContent = n === null
      ? 'Trình duyệt này không hỗ trợ lưu offline.'
      : `Đã lưu ${n}/${tong} lô chương (${(n*100/tong).toFixed(0)}%). Đọc tới đâu tự lưu tới đó.`;
  };
  $('#btn-settings').onclick = () => { $('#settings').showModal(); veOffline(); };
  $('#offline-xoa').onclick = async () => {
    navigator.serviceWorker?.controller?.postMessage('xoa-cache');
    setTimeout(veOffline, 600);
  };
  $('#settings-close').onclick = () => $('#settings').close();
  const veProvider = () => {
    const p = $('#api-provider').value;
    $('#cfg-gemini').hidden = p !== 'gemini';
    $('#cfg-openai').hidden = p !== 'openai';
  };
  $('#api-provider').onchange = veProvider;
  $('#settings-save').onclick = () => {
    localStorage.setItem(LS+'provider', $('#api-provider').value);
    localStorage.setItem(LS+'key',    $('#api-key').value.trim());
    localStorage.setItem(LS+'model',  $('#api-model').value);
    localStorage.setItem(LS+'base',   $('#api-base').value.trim());
    localStorage.setItem(LS+'model2', $('#api-model2').value.trim());
    localStorage.setItem(LS+'key2',   $('#api-key2').value.trim());
    $('#settings').close();
  };

  $('#chat-send').onclick = sendChat;
  $('#chat-input').onkeydown = e => {
    if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); sendChat(); }
  };
  $('#chat-input').oninput = e => { e.target.style.height='auto'; e.target.style.height=e.target.scrollHeight+'px'; };

  addEventListener('keydown', e => {
    if(e.key==='Escape' && !sheet.hidden){ sheet.hidden = true; return; }
    if(/^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) || e.metaKey || e.ctrlKey) return;
    if(S.route==='doc' && e.key==='ArrowLeft')  go(-1);
    if(S.route==='doc' && e.key==='ArrowRight') go(1);
    if(e.key==='m'||e.key==='M') location.hash='#muc-luc';
    if(e.key==='a'||e.key==='A') $('#btn-typo').click();
  });

  await route();
})();

function debounce(fn, ms){ let t; return (...a)=>{ clearTimeout(t); t=setTimeout(()=>fn(...a), ms); }; }
