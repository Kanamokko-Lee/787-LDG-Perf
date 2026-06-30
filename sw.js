const CACHE_NAME = '787-perf-v9';
const ASSETS = [
    '/787-LDG-Perf/',
    '/787-LDG-Perf/index.html',
    '/787-LDG-Perf/manifest.json',
    '/787-LDG-Perf/taf.json'
];

self.addEventListener('install', e => {
    e.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            // 1つの取得失敗で install 全体が失敗しないよう個別にcatchする
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

// レスポンスが「本物のOK」か判定する。
// 社内プロキシ等が200を返しつつ別内容（認証ページ等）を差し込んでくるケースを
// 弾くため、ステータスに加えcontent-typeも軽くチェックする。
function isGoodResponse(res, expectHtml) {
    if (!res || !res.ok) return false;
    if (expectHtml) {
        const ct = res.headers.get('content-type') || '';
        // HTMLを期待しているのに全く違うtypeが返る場合は弾く（プロキシ差し込み対策）
        if (ct && !ct.includes('text/html') && !ct.includes('text/plain') && ct !== '') {
            // ct が完全に無関係 (image/png 等) ならNG。ただしcontent-type無しは許容。
            if (!ct.includes('html')) return false;
        }
    }
    return true;
}

self.addEventListener('fetch', e => {
    if (e.request.method !== 'GET') return; // POST等はそのまま素通し
    const url = new URL(e.request.url);

    // 外部APIはネットワーク優先、失敗時は空レスポンス（呼び出し側のtry-catchで処理）
    if (url.hostname === 'api.open-meteo.com' || url.hostname === 'aviationweather.gov') {
        e.respondWith(
            fetch(e.request).catch(() => new Response('', { status: 503 }))
        );
        return;
    }

    // HTMLファイルはネットワーク優先、失敗 or 不正応答時はキャッシュにフォールバック
    if (url.pathname.endsWith('.html') || url.pathname.endsWith('/')) {
        e.respondWith(
            fetch(e.request)
                .then(res => {
                    if (!isGoodResponse(res, true)) {
                        // プロキシブロック等で200だが内容が不正 → キャッシュ優先
                        return caches.match(e.request).then(cached => cached || res);
                    }
                    const clone = res.clone();
                    caches.open(CACHE_NAME).then(c => c.put(e.request, clone));
                    return res;
                })
                .catch(() =>
                    caches.match(e.request).then(cached => {
                        if (cached) return cached;
                        // キャッシュにも無い場合の最終フォールバック（真っ白防止用の簡易画面）
                        return new Response(
                            `<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
                            <meta name="viewport" content="width=device-width, initial-scale=1.0">
                            <title>787 Perf Tool Pro - Offline</title>
                            <style>
                                body{background:#0a0a0a;color:#fff;font-family:sans-serif;
                                     display:flex;align-items:center;justify-content:center;
                                     height:100vh;margin:0;text-align:center;padding:20px;}
                                .box{max-width:320px;}
                                h1{color:#00b4d8;font-size:18px;}
                                p{color:#a0a0a0;font-size:13px;line-height:1.6;}
                                button{margin-top:16px;background:#1a1a1a;border:1px solid #00b4d8;
                                       color:#00b4d8;padding:10px 20px;border-radius:6px;
                                       font-size:13px;cursor:pointer;}
                            </style></head>
                            <body><div class="box">
                                <h1>オフライン / 接続不可</h1>
                                <p>ネットワークに接続できないか、必要な通信がブロックされています。<br>
                                キャッシュされたデータも見つかりませんでした。<br>
                                Wi-Fi環境を確認するか、一度オンライン環境で本アプリを開いてキャッシュを作成してください。</p>
                                <button onclick="location.reload()">再読み込み</button>
                            </div></body></html>`,
                            { status: 200, headers: { 'Content-Type': 'text/html; charset=UTF-8' } }
                        );
                    })
                )
        );
        return;
    }

    // その他（taf.json, manifest.json等）はキャッシュ優先、バックグラウンドで更新
    e.respondWith(
        caches.match(e.request).then(cached => {
            const fetchPromise = fetch(e.request)
                .then(res => {
                    if (res && res.ok) {
                        caches.open(CACHE_NAME).then(c => c.put(e.request, res.clone()));
                        return res;
                    }
                    // 不正応答（プロキシブロック等）はキャッシュを優先
                    return cached || res;
                })
                .catch(() => cached || new Response('{}', {
                    status: 200,
                    headers: { 'Content-Type': 'application/json' }
                }));
            return cached || fetchPromise;
        })
    );
});
