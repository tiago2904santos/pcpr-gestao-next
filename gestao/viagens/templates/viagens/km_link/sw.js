{% load static %}// Service worker do link de km (fluxo 10-4). Escopo: só a página deste link.
// - Página: rede primeiro; sem rede, a última cópia (o que ainda não foi enviado está no
//   localStorage, não aqui). 404/410 da rede = link revogado ou vencido: a cópia é apagada.
// - Arquivos estáticos: a cópia primeiro (os nomes têm hash do conteúdo).
// - POST (lançamentos) nunca passa pelo cache.
// - Dois caches: a página deste link (um por link) e os estáticos, UM por versão publicada e
//   compartilhado entre links; a versão anterior dos estáticos é apagada ao ativar (sem isso
//   cada link novo guardava outra cópia inteira no aparelho).
const CACHE = "pcpr-km-{{ link_id|escapejs }}";
const VERSAO = "{% static 'js/componentes/km-offline.js' %}";
const CACHE_ESTATICOS = `pcpr-km-estaticos:${VERSAO}`;
const PAGINA = "{{ base|escapejs }}";
const ESTATICOS = "{% get_static_prefix %}";
const PRECACHE = [
  "{% static 'css/tokens.css' %}", "{% static 'css/base.css' %}", "{% static 'css/layout.css' %}",
  "{% static 'css/components.css' %}",
  "{% static 'css/publica.css' %}", "{% static 'css/formulario.css' %}",
  "{% static 'css/documento.css' %}", "{% static 'js/app.js' %}",
  "{% static 'js/componentes/shell.js' %}", "{% static 'js/componentes/menu.js' %}",
  "{% static 'js/componentes/dialogo.js' %}", "{% static 'js/componentes/toasts.js' %}",
  "{% static 'js/componentes/comandos.js' %}", "{% static 'js/componentes/acao.js' %}",
  "{% static 'js/componentes/km-offline.js' %}", "{% static 'vendor/htmx.min.js' %}",
  "{% static 'icons/sprite.svg' %}", "{% static 'img/brasao-pcpr-96.webp' %}",
  "{% static 'img/favicon-32.png' %}", "{% static 'fonts/inter-latin-wght-normal.woff2' %}",
];

self.addEventListener("install", (evento) => {
  evento.waitUntil(Promise.all([
    caches.open(CACHE).then((cache) => cache.add(PAGINA)).catch(() => undefined),
    caches.open(CACHE_ESTATICOS)
      .then((cache) => Promise.allSettled(PRECACHE.map((url) => cache.add(url)))),
  ]).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(caches.keys()
    .then((nomes) => Promise.all(nomes
      .filter((n) => n.startsWith("pcpr-km-estaticos:") && n !== CACHE_ESTATICOS)
      .map((n) => caches.delete(n))))
    .then(() => self.clients.claim()));
});

async function pagina(pedido) {
  try {
    const resposta = await fetch(pedido);
    const cache = await caches.open(CACHE);
    if (resposta.ok) await cache.put(PAGINA, resposta.clone());
    else if (resposta.status === 404 || resposta.status === 410) await caches.delete(CACHE);
    return resposta;
  } catch {
    const copia = await caches.match(PAGINA);
    return copia || Response.error();
  }
}

async function estatico(pedido) {
  const copia = await caches.match(pedido);
  if (copia) return copia;
  const resposta = await fetch(pedido);
  if (resposta.ok) (await caches.open(CACHE_ESTATICOS)).put(pedido, resposta.clone());
  return resposta;
}

self.addEventListener("fetch", (evento) => {
  const pedido = evento.request;
  if (pedido.method !== "GET") return;
  const url = new URL(pedido.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname === PAGINA) evento.respondWith(pagina(pedido));
  else if (url.pathname.startsWith(ESTATICOS)) evento.respondWith(estatico(pedido));
});
