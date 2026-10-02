// @ts-check
/**
 * <pc-itinerario> — itinerário 2.0 (ADR 0016), sobre um formulário que funciona sem JS.
 *
 *  - UF de cada parada filtra a busca de municípios (e acompanha a cidade escolhida);
 *  - destinos entram na hora ("Adicionar destino") e saem ("Remover") sem recarregar;
 *  - ordem por arrastar e soltar na alça (ou setas ↑/↓ com o foco nela);
 *  - rota automática: km, tempo de estrada e tempo adicional sugerido por trecho, totais e
 *    mapa (Leaflet, carregado só quando o itinerário aparece na tela);
 *  - a chegada de cada trecho é calculada ao vivo: saída + tempo de viagem + adicional;
 *  - "Preencher datas de saída": um calendário só para escolher a data de todos os trechos.
 * O servidor recalcula tudo ao salvar — o que aparece aqui é conforto, não regra.
 */

const dois = (/** @type {number} */ n) => String(n).padStart(2, "0");
const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
  "setembro", "outubro", "novembro", "dezembro"];

/** "08/10/2026" + "07:30" → Date (ou null). @param {string} data @param {string} hora */
function lerDataHora(data, hora) {
  const d = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec((data || "").trim());
  const h = /^(\d{1,2}):(\d{2})$/.exec((hora || "").trim());
  if (!d || !h) return null;
  const r = new Date(Number(d[3]), Number(d[2]) - 1, Number(d[1]), Number(h[1]), Number(h[2]));
  return Number.isNaN(r.getTime()) ? null : r;
}
/** "04:30" → 270 (ou null). @param {string} texto */
function lerMinutos(texto) {
  const m = /^(\d{1,2}):?(\d{2})$/.exec((texto || "").trim());
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}
/** @param {number} min */
const hhmm = (min) => `${dois(Math.floor(min / 60))}:${dois(min % 60)}`;
/** @param {number} min */
const duracao = (min) => (min >= 60 ? `${Math.floor(min / 60)} h${min % 60 ? ` ${dois(min % 60)}` : ""}` : `${min} min`);
/** @param {Date} d */
const dataBR = (d) => `${dois(d.getDate())}/${dois(d.getMonth() + 1)}/${d.getFullYear()}`;
/** @param {Date} d */
const dataHoraBR = (d) => `${dataBR(d)} ${dois(d.getHours())}:${dois(d.getMinutes())}`;
/** @param {number} km */
const kmBR = (km) => `${km.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} km`;

/** @type {Promise<any> | null} */
let carregandoLeaflet = null;
/** @param {string} js @param {string} css */
function carregarLeaflet(js, css) {
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

export class PcItinerario extends HTMLElement {
  /** @type {number | undefined} */
  atraso = undefined;
  /** @type {AbortController | null} */
  pedido = null;
  /** @type {any} */
  mapa = null;
  /** @type {any} */
  camada = null;
  /** @type {any} */
  ultimaRota = null;
  visivel = false;
  arrastando = /** @type {HTMLElement | null} */ (null);

  connectedCallback() {
    if (this.dataset.pronto) return;
    this.dataset.pronto = "1";
    this.classList.add("itin--ativo");
    this.lista = /** @type {HTMLOListElement} */ (this.querySelector("[data-paradas]"));
    this.anuncio = document.createElement("p");
    this.anuncio.className = "sr-only";
    this.anuncio.setAttribute("aria-live", "polite");
    this.append(this.anuncio);
    this.querySelectorAll("[data-alca], [data-preencher-datas], [data-dica-arraste]").forEach((a) => a.removeAttribute("hidden"));

    this.addEventListener("click", (e) => this.clique(e));
    this.addEventListener("input", (e) => this.digitou(e));
    this.addEventListener("change", (e) => this.mudou(e));
    this.addEventListener("pc-selecionado", (e) => this.escolheuCidade(e));
    this.addEventListener("keydown", (e) => this.tecla(e));
    this.addEventListener("pointerdown", (e) => this.comecarArraste(e));

    new IntersectionObserver((entradas) => {
      if (entradas.some((e) => e.isIntersecting)) {
        this.visivel = true;
        if (this.ultimaRota) this.desenhar(this.ultimaRota);
      }
    }, { rootMargin: "200px" }).observe(/** @type {Element} */ (this.querySelector("[data-mapa]")));

    this.renumerar();
    // Tempos já gravados valem para a rota atual: só uma rota nova (cidade trocada ou
    // ordem mudada) recalcula. Ver aplicarRota().
    for (const t of this.trechos()) t.raiz.dataset.rota = `${t.de}→${t.para}`;
    this.recalcular();
    this.agendarRota(0);
  }

  // ------------------------------------------------------------------ paradas
  /** Destinos visíveis, na ordem da tela. */
  paradas() {
    return Array.from(this.querySelectorAll("[data-parada]"))
      .filter((p) => p instanceof HTMLElement && !p.hidden && !p.closest("template"))
      .map((p) => /** @type {HTMLElement} */ (p));
  }

  /** @param {Element | null} raiz @param {string} campo */
  campo(raiz, campo) {
    return /** @type {HTMLInputElement | null} */ (raiz?.querySelector(`[name$='-${campo}']`) || null);
  }

  /** Card do trecho que chega a esta parada (mesmo prefixo de formulário). @param {HTMLElement} parada */
  trechoDa(parada) {
    return /** @type {HTMLElement} */ (this.querySelector(`[data-trecho-de="${parada.dataset.prefixo}"]`));
  }

  cidadeSede() {
    return this.campo(this.querySelector(".itin__parada--sede"), "cidade")?.value.trim() || "";
  }

  /** Trechos: um por destino + a volta. Cada um sabe de onde sai e aonde chega. */
  trechos() {
    const sede = this.cidadeSede();
    const lista = [];
    let de = sede || "sede";
    for (const p of this.paradas()) {
      const para = this.campo(p, "cidade")?.value.trim() || "destino";
      lista.push({ raiz: this.trechoDa(p), de, para });
      de = para;
    }
    lista.push({ raiz: /** @type {HTMLElement} */ (this.querySelector("[data-retorno]")), de, para: sede || "sede" });
    return lista;
  }

  renumerar() {
    this.paradas().forEach((p, i) => {
      p.querySelectorAll("[data-numero]").forEach((n) => { n.textContent = String(i + 1); });
      const ordem = /** @type {HTMLInputElement | null} */ (p.querySelector("[data-ordem]"));
      if (ordem) ordem.value = String(i + 1);
      p.querySelector("[data-alca]")?.setAttribute("aria-label", `Mover destino ${i + 1}: setas para cima e para baixo`);
    });
    // Os cards dos trechos seguem a ordem das paradas (a volta fica sempre por último).
    const volta = this.querySelector("[data-retorno]");
    this.paradas().forEach((p, i) => {
      const card = this.trechoDa(p);
      if (!card) return;
      volta?.before(card);
      card.querySelectorAll("[data-numero]").forEach((n) => { n.textContent = String(i + 1); });
    });
    for (const t of this.trechos()) {
      const de = t.raiz.querySelector("[data-de]");
      const para = t.raiz.querySelector("[data-para]");
      if (de) de.textContent = t.de;
      if (para) para.textContent = t.para;
    }
    const total = this.paradas().length;
    const adicionar = /** @type {HTMLElement | null} */ (this.querySelector("[data-adicionar-li]"));
    if (adicionar) adicionar.hidden = total >= 10;
  }

  adicionar() {
    const modelo = /** @type {HTMLTemplateElement | null} */ (this.querySelector("template[data-modelo]"));
    const contador = /** @type {HTMLInputElement | null} */ (
      document.getElementById("id_destino-TOTAL_FORMS"));
    const antes = this.querySelector("[data-adicionar-li]");
    if (!modelo || !contador || !antes) return;
    const indice = Number(contador.value);
    const numero = this.paradas().length + 1;
    const trocar = (/** @type {string} */ html) => html.replaceAll("__prefix__", String(indice)).replaceAll("__n__", String(numero));
    antes.insertAdjacentHTML("beforebegin", trocar(modelo.innerHTML));
    const modeloTrecho = /** @type {HTMLTemplateElement | null} */ (this.querySelector("template[data-modelo-trecho]"));
    this.querySelector("[data-retorno]")?.insertAdjacentHTML("beforebegin", trocar(modeloTrecho?.innerHTML || ""));
    contador.value = String(indice + 1);
    const nova = /** @type {HTMLElement} */ (antes.previousElementSibling);
    nova.querySelector("[data-alca]")?.removeAttribute("hidden");
    // A nova parada começa na mesma UF da anterior (o caso mais comum: interior do estado).
    const ufAnterior = this.campo(this.paradas().at(-2) || this.querySelector(".itin__parada--sede"), "uf")?.value;
    const uf = /** @type {HTMLSelectElement | null} */ (nova.querySelector("[data-uf]"));
    if (uf && ufAnterior) {
      uf.value = ufAnterior;
      uf.dispatchEvent(new Event("change", { bubbles: true }));
    }
    this.renumerar();
    this.recalcular();
    this.sujar(nova);
    this.anunciar(`Destino ${numero} incluído antes da volta à sede.`);
    /** @type {HTMLElement | null} */ (nova.querySelector("input[role='combobox'], input[name$='-cidade']"))?.focus();
  }

  /** @param {HTMLElement} parada */
  remover(parada) {
    const numero = this.paradas().indexOf(parada) + 1;
    parada.hidden = true;
    const card = this.trechoDa(parada);
    if (card) card.hidden = true;
    this.renumerar();
    this.recalcular();
    this.agendarRota();
    this.anunciar(`Destino ${numero} removido. Ele sai do roteiro ao salvar.`);
    /** @type {HTMLElement | null} */ (this.querySelector("[data-adicionar]"))?.focus();
  }

  /** @param {HTMLElement} parada @param {number} delta */
  mover(parada, delta) {
    const lista = this.paradas();
    const i = lista.indexOf(parada);
    const alvo = lista[i + delta];
    if (!alvo) return;
    const saidas = this.saidas();
    if (delta < 0) alvo.before(parada);
    else alvo.after(parada);
    this.depoisDeMover(parada, saidas);
  }

  /** Saídas (data e hora) dos destinos, na ordem atual da tela. */
  saidas() {
    return this.paradas().map((p) => {
      const card = this.trechoDa(p);
      return [this.campo(card, "saida_0")?.value || "", this.campo(card, "saida_1")?.value || ""];
    });
  }

  /**
   * A ordem muda as cidades, não o calendário: o 1º trecho continua saindo na 1ª data.
   * @param {HTMLElement} parada @param {string[][]} saidas
   */
  depoisDeMover(parada, saidas) {
    this.renumerar();
    this.paradas().forEach((p, i) => {
      const [data, hora] = saidas[i] || ["", ""];
      const card = this.trechoDa(p);
      const d = this.campo(card, "saida_0");
      const h = this.campo(card, "saida_1");
      if (d) d.value = data;
      if (h) h.value = hora;
    });
    this.recalcular();
    this.agendarRota();
    this.sujar(parada);
    this.anunciar(`Destino movido para a posição ${this.paradas().indexOf(parada) + 1}.`);
  }

  // ------------------------------------------------------------------ eventos
  /** @param {Event} e */
  clique(e) {
    const alvo = /** @type {HTMLElement} */ (e.target);
    if (alvo.closest("[data-adicionar]")) {
      e.preventDefault();
      this.adicionar();
    } else if (alvo.closest("[data-preencher-datas]")) {
      this.abrirCalendario();
    }
  }

  /** @param {Event} e */
  digitou(e) {
    const alvo = /** @type {HTMLInputElement} */ (e.target);
    // Tempo digitado pela pessoa não é mais sobrescrito pela rota.
    if (/-tempo_(viagem|adicional)$/.test(alvo.name || "") && e.isTrusted) alvo.dataset.manual = "1";
    this.recalcular();
  }

  /** @param {Event} e */
  mudou(e) {
    const alvo = /** @type {HTMLInputElement} */ (e.target);
    if (alvo.matches("[data-remover]") && alvo.checked) {
      const parada = /** @type {HTMLElement | null} */ (alvo.closest("[data-parada]"));
      if (parada) this.remover(parada);
      return;
    }
    if (alvo.matches("[data-uf]")) {
      this.filtrarPorUF(/** @type {HTMLSelectElement} */ (/** @type {unknown} */ (alvo)));
      return;
    }
    if (/-cidade$/.test(alvo.name || "")) {
      this.renumerar();
      this.agendarRota();
    }
    this.recalcular();
  }

  /** UF filtra a busca de municípios da mesma parada. @param {HTMLSelectElement} select */
  filtrarPorUF(select) {
    const local = select.closest(".itin__local");
    const combobox = /** @type {HTMLElement | null} */ (local?.querySelector("pc-combobox") || null);
    if (combobox) combobox.dataset.fonte = `${this.dataset.municipiosUrl}?uf=${encodeURIComponent(select.value)}&q=`;
    const cidade = this.campo(local || null, "cidade");
    const ufAtual = (cidade?.value.split("/")[1] || "").trim().toUpperCase();
    if (cidade && select.value && ufAtual && ufAtual !== select.value) {
      cidade.value = "";
      this.anunciar(`UF trocada para ${select.value}: escolha o município de novo.`);
      this.renumerar();
      this.agendarRota();
    }
  }

  /** Cidade escolhida na lista: a UF acompanha. @param {Event} e */
  escolheuCidade(e) {
    const opcao = /** @type {CustomEvent} */ (e).detail || {};
    const local = /** @type {HTMLElement} */ (e.target).closest(".itin__local");
    const uf = /** @type {HTMLSelectElement | null} */ (local?.querySelector("[data-uf]") || null);
    const sigla = String(opcao.titulo || "").split("/")[1];
    if (uf && sigla && uf.value !== sigla) {
      uf.value = sigla;
      uf.dispatchEvent(new Event("change", { bubbles: true }));
    }
    this.renumerar();
    this.agendarRota(150);
  }

  /** @param {KeyboardEvent} e */
  tecla(e) {
    const alca = /** @type {HTMLElement} */ (e.target).closest("[data-alca]");
    if (!alca || (e.key !== "ArrowUp" && e.key !== "ArrowDown")) return;
    e.preventDefault();
    const parada = /** @type {HTMLElement} */ (alca.closest("[data-parada]"));
    this.mover(parada, e.key === "ArrowUp" ? -1 : 1);
    /** @type {HTMLElement | null} */ (parada.querySelector("[data-alca]"))?.focus();
  }

  /**
   * Arrastar e soltar pela alça (mouse, caneta e toque). Os ouvintes ficam no documento:
   * o cartão muda de lugar no DOM durante o arraste (o que desfaria uma captura de ponteiro).
   * @param {PointerEvent} e
   */
  comecarArraste(e) {
    const alca = /** @type {HTMLElement | null} */ (/** @type {HTMLElement} */ (e.target).closest("[data-alca]"));
    if (!alca || e.button !== 0) return;
    const parada = /** @type {HTMLElement} */ (alca.closest("[data-parada]"));
    e.preventDefault();
    const saidas = this.saidas();
    const inicio = this.paradas().indexOf(parada);
    parada.classList.add("itin__parada--arrastando");
    this.classList.add("itin--arrastando");
    // Perto da borda da janela a página rola sozinha (destino lá embaixo ou lá em cima).
    let y = e.clientY;
    let quadro = 0;
    const rolar = () => {
      const margem = 72;
      const passo = y < margem ? -(margem - y) / 4 : y > innerHeight - margem ? (y - innerHeight + margem) / 4 : 0;
      if (passo) {
        window.scrollBy(0, passo);
        reposicionar();
      }
      quadro = requestAnimationFrame(rolar);
    };
    const reposicionar = () => {
      for (const outra of this.paradas()) {
        if (outra === parada) continue;
        const r = outra.getBoundingClientRect();
        if (y > r.top && y < r.bottom) {
          if (y < r.top + r.height / 2) outra.before(parada);
          else outra.after(parada);
          this.renumerar();
          break;
        }
      }
    };
    const mover = (/** @type {PointerEvent} */ ev) => {
      y = ev.clientY;
      reposicionar();
    };
    quadro = requestAnimationFrame(rolar);
    const soltar = () => {
      cancelAnimationFrame(quadro);
      document.removeEventListener("pointermove", mover);
      document.removeEventListener("pointerup", soltar);
      document.removeEventListener("pointercancel", soltar);
      parada.classList.remove("itin__parada--arrastando");
      this.classList.remove("itin--arrastando");
      if (this.paradas().indexOf(parada) !== inicio) this.depoisDeMover(parada, saidas);
      /** @type {HTMLElement | null} */ (parada.querySelector("[data-alca]"))?.focus();
    };
    document.addEventListener("pointermove", mover);
    document.addEventListener("pointerup", soltar);
    document.addEventListener("pointercancel", soltar);
  }

  // ------------------------------------------------------------------ tempos e chegadas
  recalcular() {
    let anterior = /** @type {Date | null} */ (null);
    let viagemTotal = 0;
    let adicionalTotal = 0;
    let volta = /** @type {Date | null} */ (null);
    for (const t of this.trechos()) {
      if (!t.raiz) continue;
      const data = this.campo(t.raiz, "saida_0")?.value || "";
      const hora = this.campo(t.raiz, "saida_1")?.value || "";
      const saida = lerDataHora(data, hora);
      const viagem = lerMinutos(this.campo(t.raiz, "tempo_viagem")?.value || "");
      const adicional = lerMinutos(this.campo(t.raiz, "tempo_adicional")?.value || "") ?? 0;
      viagemTotal += viagem || 0;
      adicionalTotal += adicional;
      const saidaChegada = /** @type {HTMLElement | null} */ (t.raiz.querySelector("[data-chegada]"));
      const chegada = saida && viagem !== null ? new Date(saida.getTime() + (viagem + adicional) * 60000) : null;
      if (saidaChegada) saidaChegada.textContent = chegada ? dataHoraBR(chegada) : "—";
      // Sai antes de chegar ao ponto anterior: avisa já (o servidor recusa ao salvar).
      const conflito = Boolean(saida && anterior && saida < anterior);
      t.raiz.classList.toggle("itin__trecho--conflito", conflito);
      const aviso = /** @type {HTMLElement | null} */ (t.raiz.querySelector("[data-aviso]"));
      if (aviso) aviso.hidden = !conflito;
      if (chegada) anterior = chegada;
      volta = chegada;
    }
    this.texto("[data-total-viagem]", viagemTotal ? duracao(viagemTotal) : "—");
    this.texto("[data-total-adicional]", adicionalTotal ? duracao(adicionalTotal) : "—");
    this.texto("[data-volta]", volta ? dataHoraBR(volta) : "—");
  }

  /** @param {string} seletor @param {string} valor */
  texto(seletor, valor) {
    const el = this.querySelector(seletor);
    if (el) el.textContent = valor;
  }

  // ------------------------------------------------------------------ rota e mapa
  agendarRota(espera = 450) {
    window.clearTimeout(this.atraso);
    this.atraso = window.setTimeout(() => this.buscarRota(), espera);
  }

  async buscarRota() {
    const sede = this.cidadeSede();
    const destinos = this.paradas().map((p) => this.campo(p, "cidade")?.value.trim() || "");
    if (!sede || destinos.length === 0 || destinos.some((d) => !d.includes("/"))) {
      this.texto("[data-rota-fonte]", "Complete a sede e as cidades para traçar a rota.");
      return;
    }
    const pontos = [sede, ...destinos, sede];
    const url = `${this.dataset.rotaUrl}?${pontos.map((p) => `p=${encodeURIComponent(p)}`).join("&")}`;
    this.pedido?.abort();
    this.pedido = new AbortController();
    this.setAttribute("aria-busy", "true");
    try {
      const resposta = await fetch(url, { signal: this.pedido.signal, headers: { Accept: "application/json" } });
      if (!resposta.ok) throw new Error(String(resposta.status));
      this.aplicarRota(await resposta.json());
    } catch (erro) {
      if (/** @type {Error} */ (erro).name !== "AbortError") {
        this.texto("[data-rota-fonte]", "Não foi possível calcular a rota agora; informe os tempos manualmente.");
      }
    } finally {
      this.removeAttribute("aria-busy");
    }
  }

  /** @param {any} rota */
  aplicarRota(rota) {
    const trechos = this.trechos();
    let km = 0;
    let estimativa = false;
    rota.pernas.forEach((/** @type {any} */ perna, /** @type {number} */ i) => {
      const t = trechos[i];
      if (!t || !perna) return;
      km += perna.km;
      estimativa ||= perna.fonte === "estimativa";
      const rotulo = t.raiz.querySelector("[data-km]");
      if (rotulo) rotulo.textContent = perna.km ? kmBR(perna.km) : "";
      // Rota nova (cidade trocada, ordem mudada): os tempos são refeitos. Mesma rota: só
      // completa o que está em branco — tempo gravado ou digitado é da pessoa.
      const chave = `${t.de}→${t.para}`;
      const nova = t.raiz.dataset.rota !== chave;
      t.raiz.dataset.rota = chave;
      const viagem = this.campo(t.raiz, "tempo_viagem");
      const adicional = this.campo(t.raiz, "tempo_adicional");
      for (const [campo, minutos] of /** @type {[HTMLInputElement | null, number][]} */ ([[viagem, perna.minutos], [adicional, perna.adicional_sugerido]])) {
        if (!campo) continue;
        if (nova) delete campo.dataset.manual;
        if (nova || (!campo.value && !campo.dataset.manual)) campo.value = hhmm(minutos);
      }
    });
    this.texto("[data-total-km]", km ? kmBR(km) : "—");
    this.texto("[data-rota-fonte]", estimativa
      ? "Estimativa (linha reta × 1,3 a 70 km/h): o serviço de rotas não respondeu. Ajuste os tempos se precisar."
      : "Rota por estrada (OpenStreetMap). Tempo adicional sugerido: 15 min a cada 2 h de estrada.");
    this.recalcular();
    this.ultimaRota = rota;
    if (this.visivel) this.desenhar(rota);
  }

  /** @param {any} rota */
  async desenhar(rota) {
    const caixa = /** @type {HTMLElement} */ (this.querySelector("[data-mapa]"));
    const pontos = rota.pontos.filter((/** @type {any} */ p) => p.lat !== undefined && p.lat !== null);
    if (pontos.length < 2) return;
    let L;
    try {
      L = await carregarLeaflet(this.dataset.leaflet || "", this.dataset.leafletCss || "");
    } catch {
      return; // sem mapa: o resumo e os tempos continuam valendo
    }
    caixa.querySelector("[data-mapa-vazio]")?.remove();
    if (!this.mapa) {
      this.mapa = L.map(caixa, { scrollWheelZoom: false, keyboard: false, attributionControl: true, zoomSnap: 0.25 });
      if (this.dataset.tiles) {
        L.tileLayer(this.dataset.tiles, { maxZoom: 17, attribution: this.dataset.atribuicao || "" }).addTo(this.mapa);
      } else {
        caixa.classList.add("itin__mapa--sem-mosaico");
      }
    }
    this.camada?.remove();
    this.camada = L.featureGroup().addTo(this.mapa);
    rota.pernas.forEach((/** @type {any} */ perna, /** @type {number} */ i) => {
      if (!perna?.tracado?.length) return;
      L.polyline(perna.tracado, { className: `itin-rota${i === rota.pernas.length - 1 ? " itin-rota--volta" : ""}`, weight: 4 }).addTo(this.camada);
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
    this.mapa.fitBounds(this.camada.getBounds(), { padding: [28, 28], maxZoom: 11 });
  }

  // ------------------------------------------------------------------ calendário das saídas
  abrirCalendario() {
    const botao = /** @type {HTMLButtonElement} */ (this.querySelector("[data-preencher-datas]"));
    let painel = /** @type {HTMLElement | null} */ (this.querySelector(".itin__calendario"));
    if (painel && !painel.hidden) {
      this.fecharCalendario();
      return;
    }
    if (!painel) {
      painel = document.createElement("div");
      painel.className = "seletor__painel itin__calendario";
      painel.setAttribute("role", "dialog");
      painel.setAttribute("aria-label", "Datas de saída dos trechos");
      painel.addEventListener("keydown", (e) => this.teclaCalendario(e));
      painel.addEventListener("click", (e) => this.cliqueCalendario(e));
      botao.after(painel);
    }
    this.atual = 0;
    const primeira = this.datasDosTrechos().find(Boolean);
    this.mes = primeira ? new Date(primeira.getFullYear(), primeira.getMonth(), 1) : new Date();
    this.mes.setDate(1);
    painel.hidden = false;
    botao.setAttribute("aria-expanded", "true");
    this.desenharCalendario();
    /** @type {HTMLElement | null} */ (painel.querySelector("td[tabindex='0']"))?.focus();
    this.foraDoCalendario = (/** @type {PointerEvent} */ ev) => {
      if (!painel?.contains(/** @type {Node} */ (ev.target)) && ev.target !== botao && !botao.contains(/** @type {Node} */ (ev.target))) this.fecharCalendario(false);
    };
    document.addEventListener("pointerdown", this.foraDoCalendario);
  }

  fecharCalendario(devolver = true) {
    const painel = /** @type {HTMLElement | null} */ (this.querySelector(".itin__calendario"));
    const botao = /** @type {HTMLButtonElement} */ (this.querySelector("[data-preencher-datas]"));
    if (!painel || painel.hidden) return;
    painel.hidden = true;
    botao.setAttribute("aria-expanded", "false");
    if (this.foraDoCalendario) document.removeEventListener("pointerdown", this.foraDoCalendario);
    if (devolver) botao.focus();
  }

  datasDosTrechos() {
    return this.trechos().map((t) => {
      const v = this.campo(t.raiz, "saida_0")?.value || "";
      const m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(v);
      return m ? new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1])) : null;
    });
  }

  desenharCalendario() {
    const painel = /** @type {HTMLElement} */ (this.querySelector(".itin__calendario"));
    const trechos = this.trechos();
    const datas = this.datasDosTrechos();
    const mes = /** @type {Date} */ (this.mes);
    const atual = this.atual || 0;
    const hoje = new Date().toDateString();
    const chips = trechos.map((t, i) => `<li><button type="button" class="itin__chip${i === atual ? " itin__chip--atual" : ""}" data-trecho-indice="${i}"${i === atual ? ' aria-current="step"' : ""}><b>${i === trechos.length - 1 ? "Volta" : i + 1}</b> ${escapar(t.de)} → ${escapar(t.para)}<span>${datas[i] ? dataBR(datas[i]) : "sem data"}</span></button></li>`).join("");
    const inicio = new Date(mes.getFullYear(), mes.getMonth(), 1);
    inicio.setDate(1 - inicio.getDay());
    let linhas = "";
    for (let s = 0; s < 6; s += 1) {
      linhas += "<tr>";
      for (let d = 0; d < 7; d += 1) {
        const dia = new Date(inicio.getFullYear(), inicio.getMonth(), inicio.getDate() + s * 7 + d);
        const marcados = datas.map((x, i) => (x && x.toDateString() === dia.toDateString() ? (i === trechos.length - 1 ? "V" : String(i + 1)) : null)).filter(Boolean);
        const foco = dia.toDateString() === (datas[atual] || new Date(mes.getFullYear(), mes.getMonth(), Math.min(new Date().getDate(), 28))).toDateString() && dia.getMonth() === mes.getMonth();
        linhas += `<td tabindex="${foco ? 0 : -1}" data-dia="${dataBR(dia)}" aria-label="${dia.getDate()} de ${MESES[dia.getMonth()]}${marcados.length ? `, trecho ${marcados.join(" e ")}` : ""}" aria-selected="${marcados.length > 0}"${dia.toDateString() === hoje ? ' aria-current="date"' : ""} class="${dia.getMonth() !== mes.getMonth() ? "calendario__fora" : ""}">${dia.getDate()}${marcados.length ? `<span class="itin__marca-dia">${marcados.join("·")}</span>` : ""}</td>`;
      }
      linhas += "</tr>";
    }
    const nomeMes = MESES[mes.getMonth()];
    painel.innerHTML = `
      <p class="itin__calendario-ajuda">Escolha o trecho e clique no dia da saída — o próximo trecho fica selecionado.</p>
      <ol class="itin__chips">${chips}</ol>
      <div class="calendario__topo">
        <button type="button" class="calendario__nav" data-mes="-1" aria-label="Mês anterior">‹</button>
        <p class="calendario__mes" aria-live="polite" id="itin-cal-mes">${nomeMes[0].toUpperCase()}${nomeMes.slice(1)} de ${mes.getFullYear()}</p>
        <button type="button" class="calendario__nav" data-mes="1" aria-label="Próximo mês">›</button>
      </div>
      <table class="calendario__grade" role="grid" aria-labelledby="itin-cal-mes">
        <thead><tr>${["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"].map((n) => `<th scope="col" abbr="${n}">${n[0].toUpperCase()}</th>`).join("")}</tr></thead>
        <tbody>${linhas}</tbody>
      </table>
      <div class="calendario__rodape"><button type="button" class="botao botao--sm botao--primario" data-concluir>Concluir</button></div>`;
  }

  /** @param {Event} e */
  cliqueCalendario(e) {
    const alvo = /** @type {HTMLElement} */ (e.target);
    const chip = /** @type {HTMLElement | null} */ (alvo.closest("[data-trecho-indice]"));
    const dia = /** @type {HTMLElement | null} */ (alvo.closest("td[data-dia]"));
    const nav = /** @type {HTMLElement | null} */ (alvo.closest("[data-mes]"));
    if (chip) {
      this.atual = Number(chip.dataset.trechoIndice);
      this.desenharCalendario();
    } else if (dia) {
      this.marcarDia(String(dia.dataset.dia));
    } else if (nav) {
      const mes = /** @type {Date} */ (this.mes);
      this.mes = new Date(mes.getFullYear(), mes.getMonth() + Number(nav.dataset.mes), 1);
      this.desenharCalendario();
    } else if (alvo.closest("[data-concluir]")) {
      this.fecharCalendario();
    }
  }

  /** @param {string} dataTexto */
  marcarDia(dataTexto) {
    const trechos = this.trechos();
    const t = trechos[this.atual || 0];
    const data = this.campo(t.raiz, "saida_0");
    const hora = this.campo(t.raiz, "saida_1");
    if (data) data.value = dataTexto;
    if (hora && !hora.value) hora.value = "08:00";
    data?.dispatchEvent(new Event("change", { bubbles: true }));
    this.anunciar(`Saída do trecho ${(this.atual || 0) + 1} em ${dataTexto}.`);
    this.atual = Math.min((this.atual || 0) + 1, trechos.length - 1);
    this.recalcular();
    this.desenharCalendario();
    /** @type {HTMLElement | null} */ (this.querySelector(`.itin__calendario td[data-dia='${dataTexto}']`))?.focus();
  }

  /** @param {KeyboardEvent} e */
  teclaCalendario(e) {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      this.fecharCalendario();
      return;
    }
    const td = /** @type {HTMLElement} */ (e.target).closest("td[data-dia]");
    if (!td) return;
    const passo = /** @type {Record<string, number>} */ ({ ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 })[e.key];
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      this.marcarDia(String(/** @type {HTMLElement} */ (td).dataset.dia));
    } else if (passo) {
      e.preventDefault();
      const celulas = /** @type {HTMLElement[]} */ (Array.from(this.querySelectorAll(".itin__calendario td[data-dia]")));
      const i = celulas.indexOf(/** @type {HTMLElement} */ (td)) + passo;
      if (celulas[i]) {
        celulas.forEach((c) => { c.tabIndex = -1; });
        celulas[i].tabIndex = 0;
        celulas[i].focus();
      }
    }
  }

  // ------------------------------------------------------------------ utilidades
  /** @param {string} texto */
  anunciar(texto) {
    if (this.anuncio) this.anuncio.textContent = texto;
  }

  /** Proteção de saída (protecao.js escuta change). @param {Element} el */
  sujar(el) {
    el.querySelector("input")?.dispatchEvent(new Event("change", { bubbles: true }));
  }
}

/** @param {string} texto */
function escapar(texto) {
  return texto.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

customElements.define("pc-itinerario", PcItinerario);
