{% load static %}// Service worker do link de km (fluxo 10-4). Escopo: só a página deste link.
// - Página: rede primeiro; sem rede, a última cópia (o que ainda não foi enviado está no
//   localStorage, não aqui). 404/410 da rede = link revogado ou vencido: a cópia é apagada.
// - Arquivos estáticos: a cópia primeiro (os nomes têm hash do conteúdo).
// - POST (lançamentos) nunca passa pelo cache.
// - Dois caches: a página deste link (um por link) e os estáticos, UM por versão publicada e
//   compartilhado entre links. Cada cópia de página guarda (em `MARCA`) a versão dos
//   estáticos que o HTML dela referencia; ao ativar, uma versão anterior só é apagada se
//   nenhuma página de link ainda válida a usa (o Cache Storage é um só para a origem: apagar
//   tudo quebrava o uso offline de outro link aberto antes da publicação). Sem isso, cada
//   link novo guardava outra cópia inteira no aparelho.
// - O link vence: a cópia da página deixa de abrir offline depois de `EXPIRA` e é apagada
//   (num aparelho perdido ou compartilhado, roteiro e km não ficam acessíveis para sempre).
//   O nome do cache leva o vencimento, e qualquer cache de página vencido é apagado ao ativar.
//   No lugar dela entra `VENCIDO` (km_link/vencido.html, que vem DENTRO deste arquivo: não
//   depende de cache): sem nada da viagem, só o `km-vencido.js`, que lê do localStorage o
//   que ficou pendente neste aparelho para a pessoa copiar e mandar ao setor.
const EXPIRA = {{ expira_ms|default:0 }};
const CACHE = `pcpr-km-pagina:{{ link_id|escapejs }}:${EXPIRA}`;
const VERSAO = "{% static 'js/componentes/km-offline.js' %}|{% static 'js/componentes/km-vencido.js' %}";
const VENCIDO = "{{ vencido|escapejs }}";
const CSP_VENCIDO = "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
  + "font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'";
const CACHE_ESTATICOS = `pcpr-km-estaticos:${VERSAO}`;
const PAGINA = "{{ base|escapejs }}";
// A mesma chave em toda cópia de página (cada cache de página é de um link só); nunca é
// pedida à rede: guarda só o nome do cache de estáticos que o HTML daquela cópia usa.
const MARCA = "/__pcpr-km-estaticos";
const ESTATICOS = "{% get_static_prefix %}";
const PRECACHE = [
  "{% static 'css/tokens.css' %}", "{% static 'css/base.css' %}", "{% static 'css/layout.css' %}",
  "{% static 'css/components.css' %}",
  "{% static 'css/publica.css' %}", "{% static 'css/formulario.css' %}",
  "{% static 'css/documento.css' %}", "{% static 'js/app.js' %}",
  "{% static 'js/componentes/shell.js' %}", "{% static 'js/componentes/menu.js' %}",
  "{% static 'js/componentes/dialogo.js' %}", "{% static 'js/componentes/toasts.js' %}",
  "{% static 'js/componentes/comandos.js' %}", "{% static 'js/componentes/acao.js' %}",
  "{% static 'js/componentes/km-offline.js' %}", "{% static 'js/componentes/km-vencido.js' %}",
  "{% static 'vendor/htmx.min.js' %}",
  "{% static 'icons/sprite.svg' %}", "{% static 'img/brasao-pcpr-96.webp' %}",
  "{% static 'img/favicon-32.png' %}", "{% static 'fonts/inter-latin-wght-normal.woff2' %}",
];

function marcar(cache) {
  return cache.put(MARCA, new Response(CACHE_ESTATICOS));
}

self.addEventListener("install", (evento) => {
  evento.waitUntil(Promise.all([
    caches.open(CACHE).then((cache) => cache.add(PAGINA).then(() => marcar(cache)))
      .catch(() => undefined),
    caches.open(CACHE_ESTATICOS)
      .then((cache) => Promise.allSettled(PRECACHE.map((url) => cache.add(url)))),
  ]).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(limpar().then(() => self.clients.claim()));
});

async function limpar() {
  const nomes = await caches.keys();
  const fora = nomes.filter((n) => paginaVencida(n) || /^pcpr-km-\d+$/.test(n));  // antigo
  await Promise.all(fora.map((n) => caches.delete(n)));
  const usados = new Set([CACHE_ESTATICOS]);
  for (const nome of nomes) {
    if (!nome.startsWith("pcpr-km-pagina:") || fora.includes(nome)) continue;
    const marca = await (await caches.open(nome)).match(MARCA);
    if (!marca) return;  // página válida de antes da marca: guarda tudo até ela vencer
    usados.add(await marca.text());
  }
  await Promise.all(nomes
    .filter((n) => n.startsWith("pcpr-km-estaticos:") && !usados.has(n))
    .map((n) => caches.delete(n)));
}

function paginaVencida(nome) {
  if (!nome.startsWith("pcpr-km-pagina:")) return false;
  const vence = Number(nome.split(":").pop());
  return Number.isFinite(vence) && vence > 0 && Date.now() > vence;
}

function vencido() {
  return new Response(VENCIDO, { status: 410, headers: {
    "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store",
    "Content-Security-Policy": CSP_VENCIDO, "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex" } });
}

async function pagina(pedido) {
  let resposta;
  try {
    resposta = await fetch(pedido);
  } catch {
    if (EXPIRA && Date.now() > EXPIRA) {
      // Sem rede e o link já venceu: a cópia da página sai, e a página local deixa ver e
      // copiar os km que ficaram só neste aparelho (sem ela, ficariam inacessíveis).
      await caches.delete(CACHE);
      return vencido();
    }
    const copia = await (await caches.open(CACHE)).match(PAGINA);
    return copia || Response.error();
  }
  const cache = await caches.open(CACHE);
  if (resposta.ok) {
    await Promise.all([cache.put(PAGINA, resposta.clone()), marcar(cache)]);
  } else if (resposta.status === 404 || resposta.status === 410) {
    await caches.delete(CACHE);
    // Com rede, o servidor diz que o link não vale mais. Se já passou do vencimento, a mesma
    // página local do caso sem rede (os km que ficaram no aparelho, para copiar); revogado
    // antes de vencer continua com a página do servidor.
    if (EXPIRA && Date.now() > EXPIRA) return vencido();
  }
  return resposta;
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
