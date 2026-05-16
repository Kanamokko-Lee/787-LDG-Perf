const CACHE_NAME = '787-perf-v1';
const ASSETS = ['/', '/index.html', '/manifest.json'];

// インストール時にアプリ本体をキャッシュ
self.addEventListener('install', e => {
    e.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS))
    );
    self.skipWaiting();
});

// 古いキャッシュを削除
self.addEventListener('activate', e => {
    e.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        )
    );
    self.clients.claim();
});

// リクエスト処理：アプリ本体はキャッシュ優先、天気APIはネットワーク優先
self.addEventListener('fetch', e => {
    const url = new URL(e.request.url);

    // 天気APIはネットワーク優先（失敗してもOK、localStorageのキャッシュを使う）
    if (url.hostname === 'api.open-meteo.com') {
        e.respondWith(fetch(e.request).catch(() => new Response('', { status: 503 })));
        return;
    }

    // アプリ本体はキャッシュ優先
    e.respondWith(
        caches.match(e.request).then(cached => cached || fetch(e.request))
    );
});
