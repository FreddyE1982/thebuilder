self.addEventListener('install', event => {
  event.waitUntil(
    caches.open('builder-cache').then(cache => cache.add('/'))
  );
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (url.pathname === '/workouts') {
    event.respondWith(
      fetch(event.request)
        .then(resp => {
          const clone = resp.clone();
          caches.open('workouts-cache').then(c => c.put(event.request, clone));
          resp.clone().json().then(data => {
            caches.open('workouts-index').then(ic => {
              ic.put('/workouts-index', new Response(JSON.stringify(data)));
            });
          });
          return resp;
        })
        .catch(() => caches.match(event.request))
    );
  } else if (url.pathname === '/offline_search') {
    event.respondWith(
      caches.open('workouts-index')
        .then(c => c.match('/workouts-index'))
        .then(r => r ? r.json() : [])
        .then(data => {
          const q = url.searchParams.get('q') || '';
          const res = data.filter(w => (w.notes || '').toLowerCase().includes(q.toLowerCase()));
          return new Response(JSON.stringify(res), {headers: {'Content-Type': 'application/json'}});
        })
    );
  } else {
    event.respondWith(
      caches.match(event.request).then(resp => resp || fetch(event.request))
    );
  }
});
