/* Service Worker: lưu offline theo lô, tự động khi bạn đọc tới. */
const PHIEN_BAN = 'vctd-tracuu-v2';
const VO = `${PHIEN_BAN}-vo`;      // khung app: html, css, js
const DU_LIEU = `${PHIEN_BAN}-du-lieu`;  // data/*

const KHUNG = ['./', './index.html', './app.css', './app.js'];

// Dữ liệu lõi (~2,5 MB): mục lục, chỉ mục, tóm tắt, wiki. Lưu ngay từ lần mở
// đầu tiên, vì thiếu chúng thì tra cứu và wiki chết hẳn khi mất mạng — còn các
// lô chương thì nặng nên vẫn để đọc tới đâu lưu tới đó.
const LOI = [
  './data/chapters.json', './data/index.json.gz', './data/summaries.json.gz',
  './data/cooc.json.gz', './data/quotes.json.gz', './data/clean-log.json.gz',
];

self.addEventListener('install', e => {
  e.waitUntil((async () => {
    const vo = await caches.open(VO);
    await vo.addAll(KHUNG);
    const du = await caches.open(DU_LIEU);
    // từng file một: thiếu một file không được làm hỏng cả lần cài
    await Promise.all(LOI.map(u => du.add(u).catch(() => {})));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    for(const k of await caches.keys()){
      if(!k.startsWith(PHIEN_BAN)) await caches.delete(k);   // dọn bản cũ
    }
    await self.clients.claim();
  })());
});

self.addEventListener('message', e => {
  if(e.data === 'xoa-cache'){
    e.waitUntil(caches.keys().then(ks => Promise.all(ks.map(k => caches.delete(k)))));
  }
});

async function tuoi_truoc(req, ten){
  // Khung app: ưu tiên mạng để sửa code là thấy ngay, mất mạng thì dùng bản lưu.
  const cache = await caches.open(ten);
  try{
    const res = await fetch(req);
    if(res.ok) cache.put(req, res.clone());
    return res;
  }catch(err){
    const cu = await cache.match(req);
    if(cu) return cu;
    throw err;
  }
}

async function cache_truoc(req, ten){
  // Dữ liệu: trả từ cache ngay cho nhanh, rồi lặng lẽ làm mới ở nền.
  const cache = await caches.open(ten);
  const cu = await cache.match(req);
  const mang = fetch(req).then(res => {
    if(res.ok) cache.put(req, res.clone());
    return res;
  }).catch(() => null);
  if(cu){ mang; return cu; }
  const res = await mang;
  if(res) return res;
  return new Response('Chưa tải lô này khi còn mạng.', {status: 504});
}

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if(e.request.method !== 'GET' || url.origin !== location.origin) return;
  if(url.pathname.includes('/data/')) e.respondWith(cache_truoc(e.request, DU_LIEU));
  else e.respondWith(tuoi_truoc(e.request, VO));
});
