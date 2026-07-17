const CACHE_NAME = '787-perf-v10';
const ASSETS = [
    '/787-LDG-Perf/',
    '/787-LDG-Perf/index.html',
    '/787-LDG-Perf/manifest.json',
    '/787-LDG-Perf/taf.json'
];

// ネットワーク試行にタイムアウトをかけるヘルパー
function fetchWithTimeout(request, ms) {
    return new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error('timeout')), ms);
        fetch(request).then(
            res => { clearTimeout(timer); resolve(res); },
            err => { clearTimeout(timer); reject(err); }
        );
    });
}

self.addEventListener('install', e => {
    e.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            // 1ファイルの取得失敗でinstall全体が失敗しないよう個別にcatch
            return Promise.all(
                ASSETS.map(url =>
                    cache.add(url).catch(err => {
                        console.warn('[SW] cache.add failed:', url, err);
                    })
                )
            );
        })
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
    if (e.request.method !== 'GET') return;
    const url = new URL(e.request.url);

    // 外部API：2秒タイムアウト、失敗は503で返す（呼び出し側try-catchで処理）
    if (url.hostname === 'api.open-meteo.com' ||
        url.hostname === 'aviationweather.gov' ||
        url.hostname === 'corsproxy.io') {
        e.respondWith(
            fetchWithTimeout(e.request, 2000)
                .catch(() => new Response('', { status: 503 }))
        );
        return;
    }

    // 自ドメインのHTML・JSON・その他すべて：キャッシュ優先
    // キャッシュがあれば即返し、バックグラウンドで更新を試みる（Stale While Revalidate）
    e.respondWith(
        caches.match(e.request).then(cached => {
            // バックグラウンドで最新を取りにいく（2秒タイムアウト）
            const revalidate = fetchWithTimeout(e.request, 2000)
                .then(res => {
                    if (res && res.ok) {
                        caches.open(CACHE_NAME).then(c => c.put(e.request, res.clone()));
                    }
                    return res;
                })
                .catch(() => null); // 失敗は無視

            if (cached) {
                // キャッシュがある → 即返す（バックグラウンドで更新）
                e.waitUntil(revalidate);
                return cached;
            }

            // キャッシュなし → ネットワークを待つ（失敗時はオフライン画面）
            return revalidate.then(res => {
                if (res && res.ok) return res;
                // 最終フォールバック：オフライン案内画面（真っ黒防止）
                if (url.pathname.endsWith('.html') || url.pathname.endsWith('/')) {
                    return new Response(
                        `<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <title>787 Perf Tool Pro - Offline</title>
                        <style>
                            body{background:#0a0a0a;color:#fff;font-family:sans-serif;
                                 display:flex;align-items:center;justify-content:center;
                                 height:100vh;margin:0;text-align:center;padding:20px;box-sizing:border-box;}
                            .box{max-width:340px;}
                            h1{color:#00b4d8;font-size:18px;margin-bottom:12px;}
                            p{color:#a0a0a0;font-size:13px;line-height:1.7;margin:0 0 20px;}
                            button{background:#1a1a1a;border:1px solid #00b4d8;color:#00b4d8;
                                   padding:10px 24px;border-radius:6px;font-size:13px;cursor:pointer;}
                        </style></head>
                        <body><div class="box">
                            <h1>⚡ 787 Perf Tool Pro</h1>
                            <p>現在のネットワーク環境ではアクセスできません。<br>
                            一度オンライン環境（機内モードOFF・通常Wi-Fi）で<br>
                            アプリを開いてキャッシュを作成してください。</p>
                            <button onclick="location.reload()">再読み込み</button>
                        </div></body></html>`,
                        { status: 200, headers: { 'Content-Type': 'text/html; charset=UTF-8' } }
                    );
                }
                return new Response('', { status: 503 });
            });
        })
    );
});
