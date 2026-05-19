const CACHE_NAME = '787-perf-v7';
const ASSETS = [
    '/787-LDG-Perf/',
    '/787-LDG-Perf/index.html',
    '/787-LDG-Perf/manifest.json',
    '/787-LDG-Perf/taf.json'
];

self.addEventListener('install', e => {
    e.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS))
    );
    self.skipWaiting();
});

self.addEventListener('activate', e => {
    e.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', e => {
    const url = new URL(e.request.url);

    // 外部APIはネットワーク優先
    if (url.hostname === 'api.open-meteo.com' || url.hostname === 'aviationweather.gov') {
        e.respondWith(fetch(e.request).catch(() => new Response('', { status: 503 })));
        return;
    }

    // HTMLファイルはネットワーク優先（更新を即反映）、失敗時のみキャッシュ
    if (url.pathname.endsWith('.html') || url.pathname.endsWith('/')) {
        e.respondWith(
            fetch(e.request)
                .then(res => {
                    const clone = res.clone();
                    caches.open(CACHE_NAME).then(c => c.put(e.request, clone));
                    return res;
                })
                .catch(() => caches.match(e.request))
        );
        return;
    }

    // その他（taf.json等）はキャッシュ優先、バックグラウンドで更新
    e.respondWith(
        caches.match(e.request).then(cached => {
            const fetchPromise = fetch(e.request).then(res => {
                caches.open(CACHE_NAME).then(c => c.put(e.request, res.clone()));
                return res;
            });
            return cached || fetchPromise;
        })
    );
});
