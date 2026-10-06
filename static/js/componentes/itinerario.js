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

import { MapaDaRota } from "./mapa-rota.js";

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

const MENOS_MOVIMENTO = matchMedia("(prefers-reduced-motion: reduce)");
const DESLIZE = { duration: 160, easing: "cubic-bezier(0.2, 0, 0, 1)" };

/** Anima um elemento do lugar onde estava (topo antigo) até onde está agora. @param {Element} el @param {number} topoAntigo */
function deslizar(el, topoAntigo) {
  if (MENOS_MOVIMENTO.matches) return;
  const delta = topoAntigo - el.getBoundingClientRect().top;
  if (Math.abs(delta) > 0.5) el.animate([{ transform: `translateY(${delta}px)` }, { transform: "none" }], DESLIZE);
}

export class PcItinerario extends HTMLElement {
  /** @type {number | undefined} */
  atraso = undefined;
  /** @type {AbortController | null} */
  pedido = null;
  /** @type {number | undefined} */
  atrasoDiarias = undefined;
  /** @type {AbortController | null} */
  pedidoDiarias = null;
  /** @type {AbortController | null} */
  pedidoTrechos = null;
  /** @type {MapaDaRota | null} */
  mapaRota = null;
  /** A pessoa já mexeu em algo (só então vale pedir a prévia das diárias). */
  tocado = false;
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
    this.querySelectorAll("[data-trecho]").forEach((t) => this.prepararTempos(t));
    this.querySelectorAll("[data-bloco-bv]").forEach((b) => this.prepararPeriodo(b));

    this.addEventListener("click", (e) => this.clique(e));
    this.addEventListener("input", (e) => this.digitou(e));
    this.addEventListener("change", (e) => this.mudou(e));
    this.addEventListener("pc-selecionado", (e) => this.escolheuCidade(e));
    this.addEventListener("keydown", (e) => this.tecla(e));
    this.addEventListener("pointerdown", (e) => this.comecarArraste(e));

    // O painel Rota (mapa, pinos, traçado) é o mesmo de <pc-destinos>: mapa-rota.js.
    this.mapaRota = new MapaDaRota(this);
    this.mapaRota.observar();

    this.renumerar();
    // Tempos já gravados valem para a rota atual: só uma rota nova (cidade trocada ou
    // ordem mudada) recalcula. Ver aplicarRota().
    for (const t of this.trechos()) t.raiz.dataset.rota = `${t.de}→${t.para}`;
    // A prévia só vale depois de a pessoa mexer: ao abrir, o servidor já mandou o cálculo
    // gravado, e pedir de novo seria uma ida à rede por nada.
    for (const evento of ["input", "change", "click"]) {
      this.addEventListener(evento, (e) => { this.tocado ||= e.isTrusted; }, true);
    }
    this.recalcular();
    this.agendarRota(0);
  }

  // ------------------------------------------------------------------ prévia das diárias
  /** O servidor calcula com as mesmas regras do salvamento; aqui nada é decidido. */
  agendarDiarias(espera = 700) {
    const alvo = document.querySelector("[data-previa-diarias]");
    if (!alvo || !this.tocado) return;
    window.clearTimeout(this.atrasoDiarias);
    this.atrasoDiarias = window.setTimeout(() => {
      this.buscarTrechosGerados();
      this.buscarDiarias(alvo);
    }, espera);
  }

  /** Trechos gerados pelos blocos, pedidos ao servidor (mesma expansão do salvamento). */
  async buscarTrechosGerados() {
    const alvo = this.querySelector("[data-previa-trechos]");
    const form = /** @type {HTMLFormElement | null} */ (document.getElementById(this.dataset.form || ""));
    if (!alvo || !form || !this.classList.contains("itin--bate-volta")) return;
    const completo = Array.from(this.querySelectorAll("[data-bloco-bv]")).some((b) =>
      ["-cidade", "-dia_inicial", "-dia_final", "-hora_saida", "-hora_volta"].every((c) =>
        /** @type {HTMLInputElement | null} */ (b.querySelector(`input[name$='${c}']`))?.value));
    if (!completo) return;
    this.pedidoTrechos?.abort();
    this.pedidoTrechos = new AbortController();
    try {
      const resposta = await fetch(String(/** @type {HTMLElement} */ (alvo).dataset.previaTrechos), {
        method: "POST", body: new FormData(form), signal: this.pedidoTrechos.signal,
      });
      if (resposta.ok) alvo.innerHTML = await resposta.text();
    } catch (erro) {
      if (/** @type {Error} */ (erro).name !== "AbortError") throw erro;
    }
  }

  /** @param {Element} alvo */
  async buscarDiarias(alvo) {
    const form = /** @type {HTMLFormElement | null} */ (document.getElementById(this.dataset.form || ""));
    if (!form) return;
    // Só pede o cálculo quando há ida, volta e datas: antes disso o servidor só repetiria
    // "faltam trechos", e cada tecla viraria uma requisição.
    if (!this.cidadeSede()) return;
    let completo;
    if (this.classList.contains("itin--bate-volta")) {
      // No bate-volta o que conta é o bloco: destino, período e horários.
      const blocos = Array.from(this.querySelectorAll("[data-bloco-bv]"));
      completo = blocos.length > 0 && blocos.every((b) =>
        ["-cidade", "-dia_inicial", "-dia_final", "-hora_saida", "-hora_volta"].every((c) =>
          /** @type {HTMLInputElement | null} */ (b.querySelector(`input[name$='${c}']`))?.value));
    } else {
      const comData = (/** @type {Element | null} */ raiz) => Boolean(this.campo(raiz, "saida_0")?.value && this.campo(raiz, "saida_1")?.value);
      const destinos = this.paradas();
      if (destinos.length === 0) return;
      completo = destinos.every((p) => this.campo(p, "cidade")?.value.includes("/") && comData(this.trechoDa(p)))
        && comData(this.querySelector("[data-retorno]"));
    }
    if (!completo) return;
    this.pedidoDiarias?.abort();
    this.pedidoDiarias = new AbortController();
    try {
      const resposta = await fetch(String(/** @type {HTMLElement} */ (alvo).dataset.previaDiarias), {
        method: "POST", body: new FormData(form), signal: this.pedidoDiarias.signal,
      });
      if (!resposta.ok) return;
      alvo.innerHTML = await resposta.text();
    } catch (erro) {
      if (/** @type {Error} */ (erro).name !== "AbortError") throw erro;
    }
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
    const voltaSede = this.querySelector("[data-volta-sede]");
    if (voltaSede) voltaSede.textContent = this.cidadeSede() || "—";
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
    const retorno = this.querySelector("[data-retorno]");
    retorno?.insertAdjacentHTML("beforebegin", trocar(modeloTrecho?.innerHTML || ""));
    if (retorno?.previousElementSibling) this.prepararTempos(retorno.previousElementSibling);
    contador.value = String(indice + 1);
    const nova = /** @type {HTMLElement} */ (antes.previousElementSibling);
    nova.querySelector("[data-alca]")?.removeAttribute("hidden");
    // A nova parada começa na UF da sede (o caso mais comum: viagem dentro do estado).
    const ufSede = this.campo(this.querySelector(".itin__parada--sede"), "uf")?.value;
    const uf = /** @type {HTMLSelectElement | null} */ (nova.querySelector("[data-uf]"));
    if (uf && ufSede) {
      uf.value = ufSede;
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
    this.animarOrdem(() => {
      if (delta < 0) alvo.before(parada);
      else alvo.after(parada);
    });
    this.depoisDeMover(parada, saidas);
  }

  /**
   * Muda a ordem da lista e faz os itens deslizarem até o novo lugar (FLIP). A linha que está
   * sendo arrastada segue o ponteiro e fica de fora.
   * @param {() => void} mudar
   */
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
    } else if (alvo.closest("[data-ver-rota]")) {
      this.mapaRota?.enquadrar();
    } else if (alvo.closest("[data-passo]")) {
      this.passoDeTempo(/** @type {HTMLElement} */ (alvo.closest("[data-passo]")));
    } else if (alvo.closest("[data-limpar-bv]")) {
      this.limparBloco(/** @type {HTMLElement} */ (alvo.closest("[data-bloco-bv]")));
    } else if (alvo.closest("[data-adicionar-bv]")) {
      // Bate-volta ainda não tem clonagem no navegador: o servidor devolve a linha nova.
      return;
    }
  }

  /** Zera as datas e as horas da ida e da volta de um bate-volta. @param {HTMLElement | null} bloco */
  limparBloco(bloco) {
    if (!bloco) return;
    const campos = ["dia_inicial", "hora_saida", "dia_final", "hora_volta"]
      .map((c) => /** @type {HTMLInputElement | null} */ (bloco.querySelector(`input[name$='-${c}']`)))
      .filter((c) => c && c.value);
    if (campos.length === 0) return;
    for (const campo of campos) {
      /** @type {HTMLInputElement} */ (campo).value = "";
      campo?.dispatchEvent(new Event("input", { bubbles: true }));
      campo?.dispatchEvent(new Event("change", { bubbles: true }));
    }
    this.anunciar("Datas e horas do bate-volta apagadas.");
    /** @type {HTMLInputElement | null} */ (bloco.querySelector("input[name$='-dia_inicial']"))?.focus();
  }

  /** O primeiro dia abre o calendário do período; o último é preenchido por ele. @param {Element} bloco */
  prepararPeriodo(bloco) {
    const datas = bloco.querySelectorAll("pc-data");
    const fim = datas[1]?.querySelector("input");
    if (datas.length === 2 && fim?.id) {
      /** @type {HTMLElement} */ (datas[0]).dataset.ate = fim.id;
    }
  }

  /** Mostra os botões de 15 minutos do trecho (só existem com JavaScript). @param {Element} trecho */
  prepararTempos(trecho) {
    trecho.querySelectorAll("[data-passo]").forEach((b) => b.removeAttribute("hidden"));
  }

  /** Soma (ou tira) 15 minutos do campo ao lado, nunca abaixo de zero. @param {HTMLElement} botao */
  passoDeTempo(botao) {
    const campo = /** @type {HTMLInputElement | null} */ (
      botao.closest(".itin__passo")?.querySelector("input"));
    if (!campo) return;
    const minutos = Math.max(0, (lerMinutos(campo.value) ?? 0) + Number(botao.dataset.passo));
    campo.value = hhmm(minutos);
    campo.dataset.manual = "1";
    campo.dispatchEvent(new Event("input", { bubbles: true }));
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
    // As duas listas já estão na página: alternar só troca qual aparece, sem recarregar e
    // sem perder o que foi digitado na outra.
    if (alvo.matches("[data-bate-volta]")) {
      this.classList.toggle("itin--bate-volta", alvo.checked);
      this.moverSede(alvo.checked);
      this.herdarDestino(alvo.checked);
      this.renumerar();
      this.recalcular();
      this.agendarRota();
      return;
    }
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

  /** A sede é um campo só, que muda de lista conforme o modo. @param {boolean} paraBv */
  moverSede(paraBv) {
    const sede = this.querySelector("[data-sede]");
    const lista = this.querySelector(paraBv ? "[data-blocos]" : "[data-paradas]");
    if (sede && lista && sede.parentElement !== lista) lista.prepend(sede);
  }

  /**
   * Alternar o modo não pode fazer o destino escolhido sumir da tela: ele passa para o
   * campo do outro modo, desde que lá ainda esteja vazio (o que foi digitado manda).
   * @param {boolean} paraBv
   */
  herdarDestino(paraBv) {
    const bloco = /** @type {HTMLElement | null} */ (this.querySelector("[data-bloco-bv]"));
    const parada = this.paradas()[0] || null;
    const de = paraBv ? parada : bloco;
    const para = paraBv ? bloco : parada;
    const cidadeDe = this.campo(de, "cidade");
    const cidadePara = this.campo(para, "cidade");
    if (!cidadeDe?.value.trim() || !cidadePara || cidadePara.value.trim()) return;
    const ufDe = /** @type {HTMLSelectElement | null} */ (de?.querySelector("[data-uf]") || null);
    const ufPara = /** @type {HTMLSelectElement | null} */ (para?.querySelector("[data-uf]") || null);
    if (ufDe && ufPara) ufPara.value = ufDe.value;
    cidadePara.value = cidadeDe.value;
    cidadePara.dispatchEvent(new Event("change", { bubbles: true }));
    // A busca de municípios do campo que recebeu passa a ser a da UF que veio junto.
    if (ufPara) this.filtrarPorUF(ufPara);
  }

  /** UF filtra a busca de municípios da mesma parada. @param {HTMLSelectElement} select */
  filtrarPorUF(select) {
    // A UF mora em ".itin__local" (sede e destinos) ou em ".itin__bv-onde" (bate-volta).
    const local = select.closest(".itin__local, .itin__bv-onde");
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
   * Arrastar e soltar pela alça (mouse, caneta e toque). A linha levanta e segue o ponteiro
   * (posição absoluta na lista); uma vaga tracejada marca onde ela vai cair e os outros
   * destinos deslizam para abrir espaço. Ao soltar, a linha se encaixa na vaga.
   * Os ouvintes ficam no documento: a vaga muda de lugar no DOM durante o arraste.
   * @param {PointerEvent} e
   */
  comecarArraste(e) {
    const alca = /** @type {HTMLElement | null} */ (/** @type {HTMLElement} */ (e.target).closest("[data-alca]"));
    if (!alca || e.button !== 0 || this.paradas().length < 2) return;
    const parada = /** @type {HTMLElement} */ (alca.closest("[data-parada]"));
    const lista = /** @type {HTMLElement} */ (this.lista);
    e.preventDefault();
    const saidas = this.saidas();
    const inicio = this.paradas().indexOf(parada);
    const caixa = parada.getBoundingClientRect();
    const pega = e.clientY - caixa.top;

    const vaga = document.createElement("li");
    vaga.className = "itin__vaga";
    vaga.setAttribute("aria-hidden", "true");
    vaga.style.height = `${caixa.height}px`;
    parada.before(vaga);
    parada.classList.add("itin__parada--arrastando");
    this.classList.add("itin--arrastando");

    /** Vizinho da vaga na lista, pulando a linha que está no ar. @param {-1 | 1} lado */
    const vizinho = (lado) => {
      let el = lado < 0 ? vaga.previousElementSibling : vaga.nextElementSibling;
      if (el === parada) el = lado < 0 ? el.previousElementSibling : el.nextElementSibling;
      return el;
    };
    let y = e.clientY;
    const reposicionar = () => {
      parada.style.top = `${y - pega - lista.getBoundingClientRect().top}px`;
      const centro = y - pega + caixa.height / 2;
      const outras = this.paradas().filter((p) => p !== parada);
      const proxima = outras.find((p) => {
        const r = p.getBoundingClientRect();
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
    // Perto da borda da janela a página rola sozinha (destino lá embaixo ou lá em cima).
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
      const noAr = parada.getBoundingClientRect().top;
      vaga.replaceWith(parada);
      parada.classList.remove("itin__parada--arrastando");
      parada.style.removeProperty("top");
      this.classList.remove("itin--arrastando");
      deslizar(parada, noAr);
      if (this.paradas().indexOf(parada) !== inicio) this.depoisDeMover(parada, saidas);
      // Foco volta à alça (o teclado continua dali) sem acender o anel depois de um arraste com mouse.
      alca.focus(/** @type {FocusOptions} */ ({ preventScroll: true, focusVisible: false }));
    };
    document.addEventListener("pointermove", mover);
    document.addEventListener("pointerup", soltar);
    document.addEventListener("pointercancel", soltar);
  }

  // ------------------------------------------------------------------ tempos e chegadas
  recalcular() {
    let anterior = /** @type {Date | null} */ (null);
    // Ida = todos os trechos até o último destino; volta = o trecho de retorno à sede.
    const ida = { km: 0, minutos: 0 };
    const regresso = { km: 0, minutos: 0 };
    const lista = this.trechos();
    for (const [i, t] of lista.entries()) {
      if (!t.raiz) continue;
      const parte = i === lista.length - 1 ? regresso : ida;
      const data = this.campo(t.raiz, "saida_0")?.value || "";
      const hora = this.campo(t.raiz, "saida_1")?.value || "";
      const saida = lerDataHora(data, hora);
      const viagem = lerMinutos(this.campo(t.raiz, "tempo_viagem")?.value || "");
      const adicional = lerMinutos(this.campo(t.raiz, "tempo_adicional")?.value || "") ?? 0;
      parte.minutos += (viagem || 0) + adicional;
      parte.km += Number(t.raiz.dataset.km || 0);
      const saidaChegada = /** @type {HTMLElement | null} */ (t.raiz.querySelector("[data-chegada]"));
      const chegada = saida && viagem !== null ? new Date(saida.getTime() + (viagem + adicional) * 60000) : null;
      if (saidaChegada) saidaChegada.textContent = chegada ? dataHoraBR(chegada) : "—";
      // Sai antes de chegar ao ponto anterior: avisa já (o servidor recusa ao salvar).
      const conflito = Boolean(saida && anterior && saida < anterior);
      t.raiz.classList.toggle("itin__trecho--conflito", conflito);
      const aviso = /** @type {HTMLElement | null} */ (t.raiz.querySelector("[data-aviso]"));
      if (aviso) aviso.hidden = !conflito;
      if (chegada) anterior = chegada;
    }
    // No bate-volta os totais são o par do dia, preenchido direto da rota (aplicarRota):
    // somar trechos aqui só os apagaria, porque nesse modo não há trechos editáveis.
    if (this.classList.contains("itin--bate-volta")) {
      this.agendarDiarias();
      return;
    }
    // Ida e volta percorrem a mesma estrada: em vez de dois tempos quase iguais, vale o maior
    // (o pior caso) — e a viagem inteira é esse tempo duas vezes.
    const tempo = Math.max(ida.minutos, regresso.minutos);
    this.texto("[data-ida-km]", ida.km ? kmBR(ida.km) : "—");
    this.texto("[data-ida-tempo]", tempo ? duracao(tempo) : "—");
    this.texto("[data-total-km]", ida.km || regresso.km ? kmBR(ida.km + regresso.km) : "—");
    this.texto("[data-total-tempo]", tempo ? duracao(tempo * 2) : "—");
    this.agendarDiarias();
  }

  /** @param {string} seletor @param {string} valor */
  texto(seletor, valor) {
    const el = this.querySelector(seletor);
    if (!el || el.textContent === valor) return;
    const tinha = el.textContent && el.textContent !== "—";
    el.textContent = valor;
    // Só o número que mudou se move; trocar tudo a cada tecla seria ruído.
    if (tinha && !MENOS_MOVIMENTO.matches && valor !== "—") {
      el.animate([{ transform: "translateY(-0.35em)", opacity: 0 }, { transform: "none", opacity: 1 }],
        { duration: 260, easing: "cubic-bezier(0.34, 1.35, 0.64, 1)" });
    }
  }

  /** @param {Element} raiz @param {string} seletor @param {string} valor */
  textoEm(raiz, seletor, valor) {
    const el = raiz.querySelector(seletor);
    if (el) el.textContent = valor;
  }

  // ------------------------------------------------------------------ rota e mapa
  agendarRota(espera = 450) {
    window.clearTimeout(this.atraso);
    this.atraso = window.setTimeout(() => this.buscarRota(), espera);
  }

  /** Destinos dos bate-voltas, na ordem dos blocos. */
  destinosDosBlocos() {
    return Array.from(this.querySelectorAll("[data-bloco-bv]"))
      .filter((b) => !(/** @type {HTMLInputElement | null} */ (b.querySelector("[data-remover]"))?.checked))
      .map((b) => /** @type {HTMLInputElement | null} */ (b.querySelector("input[name$='-cidade']"))?.value.trim() || "");
  }

  async buscarRota() {
    const sede = this.cidadeSede();
    const destinos = this.classList.contains("itin--bate-volta")
      ? this.destinosDosBlocos()
      : this.paradas().map((p) => this.campo(p, "cidade")?.value.trim() || "");
    if (!sede || destinos.length === 0 || destinos.some((d) => !d.includes("/"))) {
      this.texto("[data-rota-fonte]", "");
      // Ainda não há rota: em vez de uma caixa vazia, o mapa já mostra a cidade da sede.
      if (sede.includes("/")) this.mapaRota?.centrarNaSede(sede);
      return;
    }
    const pontos = this.classList.contains("itin--bate-volta")
      ? [sede, ...destinos.flatMap((d) => [d, sede])]
      : [sede, ...destinos, sede];
    this.pedido?.abort();
    this.pedido = new AbortController();
    this.setAttribute("aria-busy", "true");
    try {
      this.aplicarRota(await /** @type {MapaDaRota} */ (this.mapaRota).buscar(pontos, this.pedido.signal));
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
    const trechos = this.classList.contains("itin--bate-volta") ? [] : this.trechos();
    let estimativa = false;
    rota.pernas.forEach((/** @type {any} */ perna, /** @type {number} */ i) => {
      const t = trechos[i];
      if (!t || !perna) return;
      estimativa ||= perna.fonte === "estimativa";
      t.raiz.dataset.km = String(perna.km || 0);
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
    // A fonte só fala quando há o que avisar: a rota por estrada é o esperado, e dizer isso
    // a cada cálculo era ruído na tela.
    // No bate-volta não há trechos editáveis para somar: os totais são o próprio par do dia,
    // uma ida e uma volta, direto da rota.
    if (this.classList.contains("itin--bate-volta")) {
      const [ida, volta] = rota.pernas;
      const mostrar = (/** @type {string} */ seletorKm, /** @type {string} */ seletorTempo, /** @type {any} */ perna) => {
        this.texto(seletorKm, perna?.km ? kmBR(perna.km) : "—");
        const minutos = perna ? perna.minutos + (perna.adicional_sugerido || 0) : 0;
        this.texto(seletorTempo, minutos ? duracao(minutos) : "—");
      };
      mostrar("[data-ida-km]", "[data-ida-tempo]", ida);
      mostrar("[data-total-km]", "[data-total-tempo]", volta);
    }
    this.texto("[data-rota-fonte]", estimativa
      ? "Estimativa (linha reta × 1,3 a 70 km/h): o serviço de rotas não respondeu. Ajuste os tempos se precisar."
      : "");
    this.recalcular();
    this.mapaRota?.mostrar(rota);
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
    this.caberCalendario(painel);
    /** @type {HTMLElement | null} */ (painel.querySelector("td[tabindex='0']"))?.focus();
    this.foraDoCalendario = (/** @type {PointerEvent} */ ev) => {
      if (!painel?.contains(/** @type {Node} */ (ev.target)) && ev.target !== botao && !botao.contains(/** @type {Node} */ (ev.target))) this.fecharCalendario(false);
    };
    document.addEventListener("pointerdown", this.foraDoCalendario);
  }

  /**
   * Abre para baixo quando há espaço; senão sobe e abre acima do botão, para o mês não
   * ficar cortado na borda da janela.
   * @param {HTMLElement} painel
   */
  caberCalendario(painel) {
    painel.classList.remove("itin__calendario--acima");
    const caixa = painel.getBoundingClientRect();
    const cabeAbaixo = caixa.bottom <= window.innerHeight;
    const gatilho = /** @type {HTMLElement} */ (this.querySelector("[data-preencher-datas]"));
    const cabeAcima = gatilho.getBoundingClientRect().top - caixa.height > 0;
    painel.classList.toggle("itin__calendario--acima", !cabeAbaixo && cabeAcima);
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
    // Entre a primeira e a última saída a viagem está em curso: o intervalo fica marcado.
    const marcadas = datas.filter(Boolean).map((d) => /** @type {Date} */ (d).getTime());
    const [inicioViagem, fimViagem] = [Math.min(...marcadas), Math.max(...marcadas)];
    const emFoco = trechos[atual];
    const titulo = emFoco
      ? `<b>${atual === trechos.length - 1 ? "Volta" : `Trecho ${atual + 1}`}</b> ${escapar(emFoco.de)} → ${escapar(emFoco.para)}`
      : "";
    const inicio = new Date(mes.getFullYear(), mes.getMonth(), 1);
    inicio.setDate(1 - inicio.getDay());
    let linhas = "";
    for (let s = 0; s < 6; s += 1) {
      linhas += "<tr>";
      for (let d = 0; d < 7; d += 1) {
        const dia = new Date(inicio.getFullYear(), inicio.getMonth(), inicio.getDate() + s * 7 + d);
        const marcados = datas.map((x, i) => (x && x.toDateString() === dia.toDateString() ? (i === trechos.length - 1 ? "V" : String(i + 1)) : null)).filter(Boolean);
        const foco = dia.toDateString() === (datas[atual] || new Date(mes.getFullYear(), mes.getMonth(), Math.min(new Date().getDate(), 28))).toDateString() && dia.getMonth() === mes.getMonth();
        linhas += `<td tabindex="${foco ? 0 : -1}" data-dia="${dataBR(dia)}" aria-label="${dia.getDate()} de ${MESES[dia.getMonth()]}${marcados.length ? `, trecho ${marcados.join(" e ")}` : ""}" aria-selected="${marcados.length > 0}"${dia.toDateString() === hoje ? ' aria-current="date"' : ""} class="${[dia.getMonth() !== mes.getMonth() ? "calendario__fora" : "", marcadas.length > 1 && dia.getTime() > inicioViagem && dia.getTime() < fimViagem ? "calendario__intervalo" : ""].filter(Boolean).join(" ")}">${dia.getDate()}${marcados.length ? `<span class="itin__marca-dia">${marcados.join("·")}</span>` : ""}</td>`;
      }
      linhas += "</tr>";
    }
    const nomeMes = MESES[mes.getMonth()];
    painel.innerHTML = `
      <p class="itin__calendario-titulo" aria-live="polite">${titulo}</p>
      <div class="calendario__topo">
        <button type="button" class="calendario__nav" data-mes="-1" aria-label="Mês anterior">‹</button>
        <p class="calendario__mes" aria-live="polite" id="itin-cal-mes">${nomeMes[0].toUpperCase()}${nomeMes.slice(1)} de ${mes.getFullYear()}</p>
        <button type="button" class="calendario__nav" data-mes="1" aria-label="Próximo mês">›</button>
      </div>
      <table class="calendario__grade" role="grid" aria-labelledby="itin-cal-mes">
        <thead><tr>${["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"].map((n) => `<th scope="col" abbr="${n}">${n[0].toUpperCase()}</th>`).join("")}</tr></thead>
        <tbody>${linhas}</tbody>
      </table>
      <div class="calendario__rodape">
        <button type="button" class="botao botao--sm" data-limpar${datas.some(Boolean) ? "" : " disabled"}>Limpar datas</button>
        <button type="button" class="botao botao--sm botao--primario" data-concluir>Concluir</button>
      </div>`;
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
    } else if (alvo.closest("[data-limpar]")) {
      this.limparDatas();
    } else if (alvo.closest("[data-concluir]")) {
      this.fecharCalendario();
    }
  }

  /** Apaga a saída (data e hora) de todos os trechos e volta o foco ao primeiro. */
  limparDatas() {
    for (const t of this.trechos()) {
      for (const nome of ["saida_0", "saida_1"]) {
        const campo = this.campo(t.raiz, nome);
        if (campo) campo.value = "";
      }
    }
    this.atual = 0;
    this.anunciar("Datas de saída apagadas.");
    this.recalcular();
    this.agendarRota();
    this.desenharCalendario();
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
