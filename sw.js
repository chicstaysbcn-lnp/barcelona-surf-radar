const CACHE_NAME = 'bcn-surf-radar-shell-v1.1';
const ASSETS = ['./', './index.html', './styles.css', './app.js', './manifest.webmanifest', './data/spot_profiles.json', './assets/icon.svg'];
self.addEventListener('install', event => {event.waitUntil(caches.open(CACHE_NAME).then(cache=>cache.addAll(ASSETS)).then(()=>self.skipWaiting()));});
self.addEventListener('activate', event => {event.waitUntil(caches.keys().then(names=>Promise.all(names.filter(name=>name!==CACHE_NAME).map(name=>caches.delete(name)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch', event => {
  if(event.request.method!=='GET')return;
  const url = new URL(event.request.url);
  if(url.origin!==self.location.origin)return;
  if(url.pathname.endsWith('/data/latest.json')){
    event.respondWith(fetch(event.request).then(res=>{
      if(res.ok){const copy=res.clone();caches.open(CACHE_NAME).then(c=>c.put('./data/latest.json',copy));}
      return res;
    }).catch(()=>caches.match('./data/latest.json').then(cached=>cached||Response.error())));
    return;
  }
  event.respondWith(caches.match(event.request).then(res=>res||fetch(event.request)));
});
