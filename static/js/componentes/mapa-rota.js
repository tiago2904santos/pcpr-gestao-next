// @ts-check
/**
 * Mapa da rota — o painel "Rota" do itinerário (Leaflet), usado por <pc-itinerario>
 * (ofício e roteiro) e por <pc-destinos> (termo, OS, plano, evento e viagem): o mesmo
 * mapa, os mesmos pinos ("S" na sede, 1, 2… nos destinos) e o mesmo traçado.
 *
 * O elemento dono carrega a configuração: `data-rota-url` (o serviço de rotas, que devolve
 * {pontos, pernas}), `data-leaflet`/`data-leaflet-css` (carregados só quando o mapa aparece
 * na tela), `data-tiles` e `data-atribuicao` (o mosaico). Dentro dele: `[data-mapa]` (a
 * caixa) e, opcional, `[data-ver-rota]` (o atalho "Ver a rota inteira").
 */

const MENOS_MOVIMENTO = matchMedia("(prefers-reduced-motion: reduce)");
const ENQUADRE = { padding: [28, 28], maxZoom: 11 };

/** @type {Promise<any> | null} */
let carregandoLeaflet = null;
/** @param {string} js @param {string} css */
export function carregarLeaflet(js, css) {
  if (/** @type {any} */ (window).L) return Promise.resolve(/** @type {any} */ (window).L);
  carregandoLeaflet ||= new Promise((resolve, reject) => {
    const folha = document.createElement("link");
    folha.rel = "stylesheet";
    folha.href = css;
    document.head.append(folha);
    const script = document.createElement("script");
    script.src = js;
    script.onload = () => resolve(/** @type {any} */ (window).L);
    script.onerror = reject;
    document.head.append(script);
  });
  return carregandoLeaflet;
}

export class MapaDaRota {
  /** @type {any} */
  mapa = null;
  /** @type {any} */
  camada = null;
  /** @type {any} */
  ultimaRota = null;
  /** @type {any} Limites do último desenho concluído (reenquadra quando o mapa muda de tamanho). */
  limites = null;
  /** Sede já centrada no mapa, para não refazer o pedido a cada tecla. */
  sedeNoMapa = "";
  visivel = false;

  /** @param {HTMLElement} dono */
  constructor(dono) {
    this.dono = dono;
    this.caixa = /** @type {HTMLElement} */ (dono.querySelector("[data-mapa]"));
  }

  /** O Leaflet só carrega quando o mapa aparece; e remede quando a caixa muda de tamanho.
   * Os limites são os do último desenho concluído: durante o desenho a camada ainda está
   * pela metade, e reenquadrar por ela jogaria o mapa em cima de um único ponto. */
  observar() {
    if (!this.caixa) return;
    new IntersectionObserver((entradas) => {
      if (entradas.some((e) => e.isIntersecting)) {
        this.visivel = true;
        if (this.ultimaRota) this.desenhar(this.ultimaRota);
        else if (this.sedeNoMapa) this.centrarNaSede(this.sedeNoMapa, true);
      }
    }, { rootMargin: "200px" }).observe(this.caixa);
    new ResizeObserver(() => {
      if (!this.mapa) return;
      this.mapa.invalidateSize();
      if (this.limites) this.mapa.fitBounds(this.limites, ENQUADRE);
    }).observe(this.caixa);
  }

  /** Pede a rota que passa pelos pontos ("Cidade/UF", na ordem). @param {string[]} pontos @param {AbortSignal} [sinal] */
  async buscar(pontos, sinal) {
    const url = `${this.dono.dataset.rotaUrl}?${pontos.map((p) => `p=${encodeURIComponent(p)}`).join("&")}`;
    const resposta = await fetch(url, { signal: sinal, headers: { Accept: "application/json" } });
    if (!resposta.ok) throw new Error(String(resposta.status));
    return resposta.json();
  }

  /** Guarda a rota e desenha (agora, se o mapa está na tela; senão quando aparecer). @param {any} rota */
  mostrar(rota) {
    this.ultimaRota = rota;
    this.sedeNoMapa = "";
    if (this.visivel) this.desenhar(rota);
  }

  /** Cria o mapa na primeira vez e devolve o Leaflet (null se ele não carregar). */
  async garantirMapa() {
    let L;
    try {
      L = await carregarLeaflet(this.dono.dataset.leaflet || "", this.dono.dataset.leafletCss || "");
    } catch {
      return null; // sem mapa: o resumo e os tempos continuam valendo
    }
    this.caixa.querySelector("[data-mapa-vazio]")?.remove();
    if (!this.mapa) {
      this.mapa = L.map(this.caixa, { scrollWheelZoom: false, keyboard: false, attributionControl: true, zoomSnap: 0.25 });
      this.mapa.on("moveend zoomend", () => this.atualizarVerRota());
      if (this.dono.dataset.tiles) {
        L.tileLayer(this.dono.dataset.tiles, { maxZoom: 17, attribution: this.dono.dataset.atribuicao || "" }).addTo(this.mapa);
      } else {
        this.caixa.classList.add("itin__mapa--sem-mosaico");
      }
    }
    return L;
  }

  /** Mapa na cidade da sede enquanto não há rota para traçar.
   * @param {string} sede @param {boolean} [deNovo] */
  async centrarNaSede(sede, deNovo = false) {
    if (this.sedeNoMapa === sede && !deNovo) return;
    this.sedeNoMapa = sede;
    this.ultimaRota = null;
    this.limites = null;
    if (!this.visivel) return;
    const resposta = await fetch(`${this.dono.dataset.rotaUrl}?p=${encodeURIComponent(sede)}`,
      { headers: { Accept: "application/json" } });
    if (!resposta.ok || this.sedeNoMapa !== sede) return;
    const ponto = (await resposta.json()).pontos?.[0];
    if (!ponto || ponto.lat === null || ponto.lat === undefined) return;
    const L = await this.garantirMapa();
    if (!L) return;
    this.camada?.remove();
    this.camada = L.featureGroup().addTo(this.mapa);
    const icone = L.divIcon({ className: "itin-pino itin-pino--sede", html: "<span>S</span>", iconSize: [28, 28], iconAnchor: [14, 14] });
    L.marker([ponto.lat, ponto.lon], { icon: icone, keyboard: false, title: ponto.rotulo }).addTo(this.camada);
    this.mapa.setView([ponto.lat, ponto.lon], 11);
    this.atualizarVerRota();
  }

  /** @param {any} rota */
  async desenhar(rota) {
    const pontos = rota.pontos.filter((/** @type {any} */ p) => p.lat !== undefined && p.lat !== null);
    if (pontos.length < 2) return;
    const L = await this.garantirMapa();
    if (!L) return;
    this.camada?.remove();
    this.camada = L.featureGroup().addTo(this.mapa);
    rota.pernas.forEach((/** @type {any} */ perna, /** @type {number} */ i) => {
      if (!perna?.tracado?.length) return;
      const linha = L.polyline(perna.tracado, { className: `itin-rota${i === rota.pernas.length - 1 ? " itin-rota--volta" : ""}`, weight: 4 });
      linha.addTo(this.camada);
      this.desenharTracado(linha.getElement(), i);
    });
    // Paradas no mesmo lugar (bate-volta, volta pela sede) viram um marcador só: "S·2".
    const ultimo = rota.pontos.length - 1;
    /** @type {Map<string, {lat: number, lon: number, rotulos: string[], titulo: string, sede: boolean}>} */
    const grupos = new Map();
    rota.pontos.forEach((/** @type {any} */ p, /** @type {number} */ i) => {
      if (p.lat === null || p.lat === undefined || i === ultimo) return;
      const chave = `${p.lat},${p.lon}`;
      const grupo = grupos.get(chave) || { lat: p.lat, lon: p.lon, rotulos: /** @type {string[]} */ ([]), titulo: p.rotulo, sede: false };
      grupo.rotulos.push(i === 0 ? "S" : String(i));
      grupo.sede ||= i === 0;
      grupos.set(chave, grupo);
    });
    for (const g of grupos.values()) {
      const largura = 28 + (g.rotulos.length - 1) * 14;
      const icone = L.divIcon({ className: `itin-pino${g.sede ? " itin-pino--sede" : ""}`, html: `<span>${g.rotulos.join("·")}</span>`, iconSize: [largura, 28], iconAnchor: [largura / 2, 14] });
      L.marker([g.lat, g.lon], { icon: icone, keyboard: false, title: g.titulo }).addTo(this.camada);
    }
    this.mapa.invalidateSize();
    this.limites = this.camada.getBounds();
    this.mapa.fitBounds(this.limites, ENQUADRE);
  }

  /** Volta o mapa ao enquadramento que mostra a rota inteira. */
  enquadrar() {
    if (!this.mapa || !this.limites) return;
    this.mapa.fitBounds(this.limites, ENQUADRE);
  }

  /**
   * O traçado se desenha da origem ao destino. É o momento em que a rota deixa de ser
   * números e vira caminho — por isso vale a ênfase, e só aqui.
   * @param {SVGPathElement | null} caminho @param {number} ordem
   */
  desenharTracado(caminho, ordem) {
    if (!caminho || MENOS_MOVIMENTO.matches || typeof caminho.getTotalLength !== "function") return;
    const comprimento = caminho.getTotalLength();
    if (!comprimento) return;
    caminho.animate(
      [{ strokeDasharray: comprimento, strokeDashoffset: comprimento },
       { strokeDasharray: comprimento, strokeDashoffset: 0 }],
      { duration: 720, delay: ordem * 160, easing: "cubic-bezier(0.2, 0, 0, 1)", fill: "backwards" },
    );
  }

  /** O atalho só aparece quando a vista deixou de mostrar a rota toda. */
  atualizarVerRota() {
    const botao = /** @type {HTMLElement | null} */ (this.dono.querySelector("[data-ver-rota]"));
    if (!botao) return;
    botao.hidden = !this.limites || !this.mapa || this.mapa.getBounds().contains(this.limites);
  }
}
