// @ts-check
/**
 * <pc-destinos> — o componente de destinos de todas as telas que pedem destino (termo, OS,
 * plano, evento do plano, viagem). É o "Sede e destinos" + "Rota" do roteiro, sem trechos:
 *
 *  - a sede da unidade fica fixa no topo e na volta (`data-sede`, não vai ao formulário);
 *  - uma linha por destino (UF + cidade, com busca), remover em cada linha e "Adicionar
 *    destino" antes da volta à sede (no máximo `data-maximo`);
 *  - a ordem muda arrastando pela alça (ou setas para cima/baixo com o foco nela);
 *  - o painel Rota traça sede → destinos → sede no mesmo mapa do roteiro (mapa-rota.js),
 *    com km e tempo da ida e da ida e volta.
 *
 * Cada destino tem um <input type="hidden" name="{data-nome}" data-valor-id> com a cidade
 * ESCOLHIDA na lista ("Cidade/UF" — o <pc-combobox> a escreve nele); o texto digitado só
 * busca. O formulário recebe a lista na ordem da tela. A UF da linha só filtra a busca de cidades. Marcação: viagens/_destinos.html.
 */

import { MapaDaRota } from "./mapa-rota.js";

const dois = (/** @type {number} */ n) => String(n).padStart(2, "0");
/** @param {number} min */
const duracao = (min) => (min >= 60 ? `${Math.floor(min / 60)} h${min % 60 ? ` ${dois(min % 60)}` : ""}` : `${min} min`);
/** @param {number} km */
const kmBR = (km) => `${km.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} km`;

const MENOS_MOVIMENTO = matchMedia("(prefers-reduced-motion: reduce)");
const DESLIZE = { duration: 160, easing: "cubic-bezier(0.2, 0, 0, 1)" };

/** Anima um elemento do lugar onde estava (topo antigo) até onde está agora. @param {Element} el @param {number} topoAntigo */
function deslizar(el, topoAntigo) {
  if (MENOS_MOVIMENTO.matches) return;
  const delta = topoAntigo - el.getBoundingClientRect().top;
  if (Math.abs(delta) > 0.5) el.animate([{ transform: `translateY(${delta}px)` }, { transform: "none" }], DESLIZE);
}

export class PcDestinos extends HTMLElement {
  /** @type {number | undefined} */
  atraso = undefined;
  /** @type {AbortController | null} */
  pedido = null;

  connectedCallback() {
    if (this.dataset.pronto) return;
    this.dataset.pronto = "1";
    this.classList.add("itin--ativo");
    this.lista = /** @type {HTMLOListElement | null} */ (this.querySelector("[data-destinos-lista]"));
    this.modelo = /** @type {HTMLTemplateElement | null} */ (this.querySelector("template[data-destino-modelo]"));
    this.mapaRota = new MapaDaRota(this);
    this.mapaRota.observar();
    this.addEventListener("click", (e) => {
      const alvo = /** @type {HTMLElement} */ (e.target);
      if (alvo.closest("[data-adicionar-destino]")) {
        e.preventDefault();
        this.adicionar();
      } else if (alvo.closest("[data-remover-destino]")) {
        e.preventDefault();
        this.remover(/** @type {HTMLElement} */ (alvo.closest("[data-destino]")));
      } else if (alvo.closest("[data-ver-rota]")) {
        this.mapaRota?.enquadrar();
      }
    });
    this.addEventListener("change", (e) => {
      const alvo = /** @type {HTMLElement} */ (e.target);
      if (alvo.matches("[data-uf]")) this.filtrar(/** @type {HTMLSelectElement} */ (alvo));
      else this.agendarRota();
    });
    this.addEventListener("pc-selecionado", () => this.agendarRota(150));
    this.addEventListener("keydown", (e) => this.tecla(e));
    this.addEventListener("pointerdown", (e) => this.comecarArraste(e));
    this.querySelectorAll("[data-uf]").forEach((s) => this.filtrar(/** @type {HTMLSelectElement} */ (s)));
    this.querySelectorAll("[data-alca]").forEach((a) => a.removeAttribute("hidden"));
    this.renumerar();
    this.agendarRota(0);
  }

  /** @returns {HTMLElement[]} */
  linhas() {
    return /** @type {HTMLElement[]} */ (Array.from(this.lista?.querySelectorAll("[data-destino]") ?? []));
  }

  /** Os destinos preenchidos, na ordem da tela ("Cidade/UF"). */
  destinos() {
    return this.linhas().map((l) => /** @type {HTMLInputElement | null} */ (
      l.querySelector("input[data-valor-id]"))?.value.trim() || "");
  }

  adicionar() {
    if (!this.lista || !this.modelo) return;
    const max = Number(this.dataset.maximo || "10");
    if (this.linhas().length >= max) {
      this.anunciar(`No máximo ${max} destinos.`);
      return;
    }
    const nova = /** @type {HTMLElement} */ (this.modelo.content.firstElementChild?.cloneNode(true));
    if (!nova) return;
    // A UF da nova linha começa igual à do último destino: viagens costumam ficar no estado.
    const ultima = this.linhas().at(-1)?.querySelector("[data-uf]");
    const uf = /** @type {HTMLSelectElement | null} */ (nova.querySelector("[data-uf]"));
    if (uf && ultima) uf.value = /** @type {HTMLSelectElement} */ (ultima).value;
    // Entra antes de "Adicionar destino" (e da volta à sede), como no roteiro.
    const adicionar = this.lista.querySelector("[data-adicionar-li]");
    this.lista.insertBefore(nova, adicionar);
    if (uf) this.filtrar(uf);
    nova.querySelector("[data-alca]")?.removeAttribute("hidden");
    this.renumerar();
    this.anunciar("Destino adicionado.");
    /** @type {HTMLInputElement | null} */ (nova.querySelector("input[role='combobox']"))?.focus();
  }

  /** @param {HTMLElement | null} linha */
  remover(linha) {
    if (!linha) return;
    // Sempre sobra uma linha (em branco, se for o caso): a lista nunca some da tela.
    if (this.linhas().length <= 1) {
      const entrada = /** @type {HTMLInputElement | null} */ (linha.querySelector("input[role='combobox']"));
      const valor = /** @type {HTMLInputElement | null} */ (linha.querySelector("input[data-valor-id]"));
      if (entrada) entrada.value = "";
      if (valor) valor.value = "";
    } else {
      linha.remove();
      this.renumerar();
      this.anunciar("Destino removido.");
    }
    // O autosave e a proteção de saída só ouvem campos do formulário: o aviso sai de um
    // destino que ficou (o próprio <pc-destinos> não é campo).
    this.linhas()[0]?.querySelector("input[data-valor-id]")
      ?.dispatchEvent(new Event("change", { bubbles: true }));
    this.agendarRota();
  }

  /** A UF da linha restringe a busca de cidades. @param {HTMLSelectElement} select */
  filtrar(select) {
    const combobox = /** @type {HTMLElement | null} */ (select.closest("[data-destino]")?.querySelector("pc-combobox") ?? null);
    if (combobox) combobox.dataset.fonte = `${this.dataset.municipiosUrl}?uf=${encodeURIComponent(select.value)}&q=`;
  }

  renumerar() {
    this.linhas().forEach((linha, i) => {
      linha.querySelectorAll("[data-numero]").forEach((n) => { n.textContent = String(i + 1); });
      linha.querySelector(".itin__local")?.setAttribute("aria-label", `Destino ${i + 1}`);
      linha.querySelector("[data-alca]")?.setAttribute("aria-label", `Mover destino ${i + 1}: setas para cima e para baixo`);
    });
  }

  // ------------------------------------------------------------------ ordem (arrastar)
  /** @param {HTMLElement} linha @param {number} delta */
  mover(linha, delta) {
    const alvo = this.linhas()[this.linhas().indexOf(linha) + delta];
    if (!alvo) return;
    this.animarOrdem(() => { if (delta < 0) alvo.before(linha); else alvo.after(linha); });
    this.depoisDeMover(linha);
  }

  /** Muda a ordem e faz os itens deslizarem até o novo lugar (FLIP); a linha no ar fica de fora.
   * @param {() => void} mudar */
  animarOrdem(mudar) {
    const itens = Array.from(/** @type {HTMLElement} */ (this.lista).children)
      .filter((el) => !el.classList.contains("itin__parada--arrastando"));
    const antes = itens.map((el) => el.getBoundingClientRect().top);
    mudar();
    itens.forEach((el, i) => {
      el.getAnimations().forEach((a) => a.cancel());
      deslizar(el, antes[i]);
    });
  }

  /** @param {HTMLElement} linha */
  depoisDeMover(linha) {
    this.renumerar();
    this.agendarRota();
    // O autosave e a proteção de saída só ouvem campos do formulário.
    linha.querySelector("input[data-valor-id]")?.dispatchEvent(new Event("change", { bubbles: true }));
    this.anunciar(`Destino movido para a posição ${this.linhas().indexOf(linha) + 1}.`);
  }

  /** @param {KeyboardEvent} e */
  tecla(e) {
    const alca = /** @type {HTMLElement} */ (e.target).closest("[data-alca]");
    if (!alca || (e.key !== "ArrowUp" && e.key !== "ArrowDown")) return;
    e.preventDefault();
    const linha = /** @type {HTMLElement} */ (alca.closest("[data-destino]"));
    this.mover(linha, e.key === "ArrowUp" ? -1 : 1);
    /** @type {HTMLElement | null} */ (linha.querySelector("[data-alca]"))?.focus();
  }

  /**
   * Arrastar e soltar pela alça (mouse, caneta e toque), como no roteiro: a linha levanta e
   * segue o ponteiro, uma vaga tracejada marca onde ela vai cair e os outros destinos
   * deslizam para abrir espaço. Os ouvintes ficam no documento (a vaga muda de lugar).
   * @param {PointerEvent} e
   */
  comecarArraste(e) {
    const alca = /** @type {HTMLElement | null} */ (/** @type {HTMLElement} */ (e.target).closest("[data-alca]"));
    if (!alca || e.button !== 0 || this.linhas().length < 2) return;
    const linha = /** @type {HTMLElement} */ (alca.closest("[data-destino]"));
    const lista = /** @type {HTMLElement} */ (this.lista);
    e.preventDefault();
    const inicio = this.linhas().indexOf(linha);
    const caixa = linha.getBoundingClientRect();
    const pega = e.clientY - caixa.top;
    const vaga = document.createElement("li");
    vaga.className = "itin__vaga";
    vaga.setAttribute("aria-hidden", "true");
    vaga.style.height = `${caixa.height}px`;
    linha.before(vaga);
    linha.classList.add("itin__parada--arrastando");
    this.classList.add("itin--arrastando");
    /** Vizinho da vaga, pulando a linha que está no ar. @param {-1 | 1} lado */
    const vizinho = (lado) => {
      let el = lado < 0 ? vaga.previousElementSibling : vaga.nextElementSibling;
      if (el === linha) el = lado < 0 ? el.previousElementSibling : el.nextElementSibling;
      return el;
    };
    let y = e.clientY;
    const reposicionar = () => {
      linha.style.top = `${y - pega - lista.getBoundingClientRect().top}px`;
      const centro = y - pega + caixa.height / 2;
      const outras = this.linhas().filter((l) => l !== linha);
      const proxima = outras.find((l) => {
        const r = l.getBoundingClientRect();
        return centro < r.top + r.height / 2;
      });
      const ultima = outras.at(-1);
      if (proxima) {
        if (vizinho(1) !== proxima) this.animarOrdem(() => proxima.before(vaga));
      } else if (ultima && vizinho(-1) !== ultima) {
        this.animarOrdem(() => ultima.after(vaga));
      }
    };
    reposicionar();
    // Perto da borda da janela a página rola sozinha.
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
      const noAr = linha.getBoundingClientRect().top;
      vaga.replaceWith(linha);
      linha.classList.remove("itin__parada--arrastando");
      linha.style.removeProperty("top");
      this.classList.remove("itin--arrastando");
      deslizar(linha, noAr);
      if (this.linhas().indexOf(linha) !== inicio) this.depoisDeMover(linha);
      alca.focus(/** @type {FocusOptions} */ ({ preventScroll: true, focusVisible: false }));
    };
    document.addEventListener("pointermove", mover);
    document.addEventListener("pointerup", soltar);
    document.addEventListener("pointercancel", soltar);
  }

  // ------------------------------------------------------------------ rota e mapa
  agendarRota(espera = 450) {
    window.clearTimeout(this.atraso);
    this.atraso = window.setTimeout(() => this.buscarRota(), espera);
  }

  async buscarRota() {
    const sede = (this.dataset.sede || "").trim();
    const destinos = this.destinos().filter(Boolean);
    if (!sede || destinos.length === 0 || destinos.some((d) => !d.includes("/"))) {
      this.totais(null);
      // Ainda não há rota: em vez de uma caixa vazia, o mapa já mostra a cidade da sede.
      if (sede.includes("/")) this.mapaRota?.centrarNaSede(sede);
      return;
    }
    this.pedido?.abort();
    this.pedido = new AbortController();
    this.setAttribute("aria-busy", "true");
    try {
      const rota = await /** @type {MapaDaRota} */ (this.mapaRota).buscar([sede, ...destinos, sede], this.pedido.signal);
      this.totais(rota);
      this.mapaRota?.mostrar(rota);
    } catch (erro) {
      if (/** @type {Error} */ (erro).name !== "AbortError") {
        this.texto("[data-rota-fonte]", "Não foi possível calcular a rota agora.");
      }
    } finally {
      this.removeAttribute("aria-busy");
    }
  }

  /** Km e tempo da ida (sede → último destino) e da ida e volta. @param {any} rota */
  totais(rota) {
    const pernas = /** @type {any[]} */ (rota?.pernas || []).filter(Boolean);
    const somar = (/** @type {any[]} */ lista) => lista.reduce((t, p) => ({
      km: t.km + (p.km || 0), min: t.min + (p.minutos || 0) + (p.adicional_sugerido || 0) }), { km: 0, min: 0 });
    const ida = somar(pernas.slice(0, -1));
    const total = somar(pernas);
    this.texto("[data-ida-km]", ida.km ? kmBR(ida.km) : "—");
    this.texto("[data-ida-tempo]", ida.min ? duracao(ida.min) : "—");
    this.texto("[data-total-km]", total.km ? kmBR(total.km) : "—");
    this.texto("[data-total-tempo]", total.min ? duracao(total.min) : "—");
    this.texto("[data-rota-fonte]", pernas.some((p) => p.fonte === "estimativa")
      ? "Estimativa (linha reta × 1,3 a 70 km/h): o serviço de rotas não respondeu." : "");
  }

  /** @param {string} seletor @param {string} valor */
  texto(seletor, valor) {
    const el = this.querySelector(seletor);
    if (el && el.textContent !== valor) el.textContent = valor;
  }

  /** @param {string} texto */
  anunciar(texto) {
    const el = this.querySelector("[data-anuncio]");
    if (el) el.textContent = texto;
  }
}

customElements.define("pc-destinos", PcDestinos);
