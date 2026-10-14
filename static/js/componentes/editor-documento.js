// @ts-check
/**
 * <pc-editor-documento> — o editor dentro do visualizador do documento (ADR 0018).
 *
 * A folha HTML do documento (a mesma que vira PDF) é mostrada num iframe da própria
 * origem. Este componente, de fora, torna as regiões marcadas editáveis, cuida da barra
 * de ferramentas, salva por JSON (com debounce e concorrência otimista), grava os campos
 * vinculados de volta no cadastro, lista versões (restaurar, voltar ao modelo), insere
 * textos prontos, quebras e tabelas, mostra páginas, pendências e quem mais está editando.
 *
 *   <pc-editor-documento class="editor" data-folha="…/folha/" data-base="…/documento/oficio/"
 *                        data-pdf="…/minuta.pdf?tipo=oficio" data-editavel>
 *     <div class="editor__barra" role="toolbar">…botões com data-comando / data-acao…</div>
 *     <div class="editor__avisos" data-avisos></div>
 *     <div class="previa-documento editor__folha"><iframe data-quadro="texto">…</iframe>…</div>
 *     <dialog data-historico>…</dialog>
 *   </pc-editor-documento>
 *
 * Sem `data-base` (UI Lab) funciona como vitrine: edita, formata e insere, mas não salva.
 */
import { confirmar } from "./dialogo.js";
import { icone } from "./menu.js";
import { MASCARAS } from "./mascara.js";

const ESPERA_SALVAR = 1200;
const ESPERA_CAMPO = 700;
/**
 * Blocos do modelo que mostram dados do formulário: um clique neles abre a parte da folha
 * que os altera (entidades-documento.js). Texto livre (saudação, declaração) não entra.
 * @type {Record<string, string>}
 */
const BLOCOS_DO_FORMULARIO = {
  identificacao: "identificacao", custos: "identificacao",
  resumo: "roteiro", roteiro: "roteiro",
  assinatura: "configuracao", destinatario: "configuracao",
};
/** Quantos algarismos fecham cada máscara de tamanho fixo (data e hora, protocolo). */
const DIGITOS_DA_MASCARA = /** @type {Record<string, number>} */ ({ datahora: 12, data: 8, hora: 4, protocolo: 9 });
/** Marca invisível que segura o cursor dentro de um campo vazio (nunca é gravada). */
const INVISIVEL = "\u200B";
const PRESENCA_MS = 30000;
const SELETOR_BLOCO = "p, div, table, h1, h2, h3, li, blockquote";

/** @typedef {{chave: string, rotulo: string}} Bloco */
/** @typedef {{numero: number, acao: string, acao_rotulo: string, do_modelo: boolean, blocos_alterados: Bloco[], restaurada_de: number | null, criado_por: string, criado_em: string, quando: string}} Versao */
/** @typedef {{chave: string, rotulo: string, valor: string, obrigatorio: boolean, vazio: boolean, secao: string, multilinha: boolean}} Campo */
/** @typedef {{tipo: string, pode_editar: boolean, pode_gerir_textos: boolean, versao_oficio: number, edicao: Versao | null, versoes: Versao[], desatualizadas: string[], campos: Campo[], pendencias: {chave: string, mensagem: string}[], presenca: {nome: string}[], regioes: Bloco[]}} Estado */
/** @typedef {{id: number, nome: string, texto: string, tipo: string, tipo_rotulo: string, padrao_sistema: boolean}} TextoPronto */

/** @param {string} texto */
function escapar(texto) {
  return texto.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] || c);
}

/** @param {string} nivel @param {string} mensagem */
function avisar(nivel, mensagem) {
  document.body.dispatchEvent(new CustomEvent("toast", { detail: { mensagem, nivel } }));
}

export class PcEditorDocumento extends HTMLElement {
  constructor() {
    super();
    /** @type {Estado | null} */
    this.estado = null;
    /** @type {HTMLIFrameElement | null} */
    this.quadro = null;
    /** @type {HTMLIFrameElement | null} */
    this.quadroPdf = null;
    /** @type {number | undefined} */
    this.timerSalvar = undefined;
    /** @type {number | undefined} */
    this.timerCampo = undefined;
    /** @type {number | undefined} */
    this.timerPresenca = undefined;
    /** @type {string | null} */
    this.campoPendente = null;
    this.sujo = false;
    this.salvando = false;
    /** @type {number | null} */
    this.vendoVersao = null;
    /** @type {HTMLElement | null} */
    this.blocoAtual = null;
    /** @type {HTMLElement | null} */
    this.campoRecente = null;
    /** @type {TextoPronto[] | null} */
    this.textos = null;
    this.vitrine = !this.dataset.base;
  }

  connectedCallback() {
    // data-base é a rota do estado; as demais ficam ao lado dela.
    this.base = (this.dataset.base || "").replace(/estado\/$/, "");
    this.editavel = this.hasAttribute("data-editavel");
    this.quadro = this.querySelector("iframe[data-quadro='texto']");
    this.quadroPdf = this.querySelector("iframe[data-quadro='pdf']");
    this.barra = /** @type {HTMLElement | null} */ (this.querySelector("[role='toolbar']"));
    this.avisos = /** @type {HTMLElement | null} */ (this.querySelector("[data-avisos]"));
    this.salvo = /** @type {HTMLElement | null} */ (this.querySelector("[data-salvo]"));
    this.historico = /** @type {HTMLDialogElement | null} */ (this.querySelector("dialog[data-historico]"));
    this.dialogoTexto = /** @type {HTMLDialogElement | null} */ (this.querySelector("dialog[data-guardar-texto]"));
    if (this.barra) this.barra.hidden = false;
    const ferramentas = this.querySelector("details[data-ferramentas-recolhiveis]");
    if (ferramentas instanceof HTMLDetailsElement) {
      ferramentas.open = !window.matchMedia("(max-width: 767.98px)").matches;
    }
    this.prepararBarra();
    // A folha chega sem `src` (só carrega quando o editor entra na tela — app.js).
    if (this.quadro && this.quadro.dataset.src && !this.quadro.getAttribute("src")) {
      this.quadro.src = this.quadro.dataset.src;
      this.quadro.hidden = false;
    }
    if (this.quadro) {
      const doc = this.quadro.contentDocument;
      if (doc && doc.readyState === "complete" && doc.body && doc.body.childElementCount) this.prepararFolha();
      this.quadro.addEventListener("load", () => this.prepararFolha());
    }
    if (!this.vitrine) {
      this.carregarEstado();
      this.timerPresenca = window.setInterval(() => this.presenca(), PRESENCA_MS);
    }
    this.aoSair = (/** @type {BeforeUnloadEvent} */ e) => {
      if (this.sujo || this.salvando) e.preventDefault();
    };
    window.addEventListener("beforeunload", this.aoSair);
    // Os dados do ofício mudaram noutro ponto da folha (autosave, equipe, roteiro): a
    // folha do documento se refaz sozinha — menos quando há texto em edição por salvar,
    // que recarregar apagaria.
    this.aoMudarDados = () => {
      if (this.sujo || this.salvando || this.vendoVersao !== null) return;
      // Folha ainda a caminho (o editor acabou de entrar na página): ela já chega com os
      // dados novos — recarregar o about:blank cancelaria a ida.
      const janela = this.quadro?.contentWindow;
      if (!janela || janela.location.href === "about:blank") return;
      janela.location.reload();
    };
    document.addEventListener("pcpr:dados-salvos", this.aoMudarDados);
    document.body.addEventListener("equipe-alterada", this.aoMudarDados);
    // O editor carrega quando chega à tela (app.js): se a folha já tinha sido desenhada e
    // os dados mudaram antes disso, ela se refaz agora.
    if (document.documentElement.dataset.dadosSalvos && this.quadro?.contentDocument?.body) {
      this.aoMudarDados();
    }
    this.addEventListener("keydown", (e) => this.atalhos(e));
    // Outro editor da página levou o texto dele para este (termo: "Aplicar em todos"):
    // a folha e a versão base se refazem, para a próxima gravação não dar conflito.
    this.aoAplicarNoutro = (/** @type {Event} */ e) => {
      if (/** @type {CustomEvent} */ (e).detail?.origem !== this) this.recarregar();
    };
    document.addEventListener("pc-editor:texto-aplicado", this.aoAplicarNoutro);
  }

  disconnectedCallback() {
    this.observadorBarra?.disconnect();
    if (this.aoAplicarNoutro) document.removeEventListener("pc-editor:texto-aplicado", this.aoAplicarNoutro);
    window.clearInterval(this.timerPresenca);
    window.clearTimeout(this.timerSalvar);
    window.clearTimeout(this.timerCampo);
    if (this.aoSair) window.removeEventListener("beforeunload", this.aoSair);
    if (this.aoMudarDados) {
      document.removeEventListener("pcpr:dados-salvos", this.aoMudarDados);
      document.body.removeEventListener("equipe-alterada", this.aoMudarDados);
    }
  }

  // ---------------------------------------------------------------- folha (iframe)
  /** @returns {Document | null} */
  get doc() {
    return this.quadro ? this.quadro.contentDocument : null;
  }

  /** Folha inteira (`data-folha-inteira`, vários editores empilhados — o termo): o quadro
   * tem a altura do documento todo e quem rola é a página, não a folha. */
  ajustarAltura() {
    const doc = this.doc;
    if (!this.quadro || !doc || !doc.documentElement || !this.hasAttribute("data-folha-inteira")) return;
    const raiz = doc.documentElement;
    // Linhas indivisíveis do documento oficial podem exceder a tela do celular.
    // Só a rolagem vertical é delegada à página; a horizontal precisa permanecer acessível.
    raiz.style.overflowX = "auto";
    raiz.style.overflowY = "hidden";
    const janela = doc.defaultView;
    if (!janela || !doc.body) return;
    const margem = parseFloat(janela.getComputedStyle(doc.body).marginBottom) || 0;
    const barra = Math.max(0, this.quadro.clientHeight - raiz.clientHeight);
    // scrollHeight da raiz inclui a altura anterior do iframe. Usá-lo aqui somaria
    // a barra a cada observação e impediria a folha de encolher após uma edição.
    const altura = Math.ceil(doc.body.getBoundingClientRect().bottom + janela.scrollY + margem + barra);
    if (this.quadro.style.height !== `${altura}px`) this.quadro.style.height = `${altura}px`;
  }

  prepararFolha() {
    const doc = this.doc;
    if (!doc || !doc.body || !doc.documentElement) return;
    const raiz = doc.documentElement;
    // Vários editores num bloco só (o termo): quem recebe o cursor passa a ser o da barra.
    const ativar = () => this.dispatchEvent(new CustomEvent("pc-editor:ativo", { bubbles: true }));
    doc.addEventListener("focusin", ativar);
    doc.addEventListener("pointerdown", ativar);
    if (this.hasAttribute("data-folha-inteira")) {
      this.ajustarAltura();
      // Fontes, brasão e o que se digita mudam a altura: acompanha.
      new ResizeObserver(() => this.ajustarAltura()).observe(doc.body);
    }
    raiz.classList.toggle("folha--leitura", this.vendoVersao !== null);
    const podeEditar = this.editavel && this.vendoVersao === null;
    raiz.classList.toggle("folha--editavel", podeEditar);
    doc.querySelectorAll("[data-regiao]").forEach((r) => {
      if (podeEditar) r.setAttribute("contenteditable", "true");
      else r.removeAttribute("contenteditable");
      r.setAttribute("role", "textbox");
      r.setAttribute("aria-multiline", "true");
      r.setAttribute("aria-label", r.getAttribute("data-rotulo") || "Região do documento");
    });
    doc.querySelectorAll("[data-campo]").forEach((c) => {
      c.setAttribute("role", "textbox");
      c.setAttribute("aria-label", c.getAttribute("data-rotulo") || "Campo");
      // Dentro de uma região de texto o campo já é editável com ela (e não pode ter foco
      // próprio: o teclado só escreve com o foco no texto editável). Fora dela, ele mesmo
      // vira editável (só texto). Nos dois casos, o clique no amarelo libera a digitação.
      if (podeEditar && c.parentElement?.closest("[contenteditable='true']")) {
        c.removeAttribute("tabindex");
      } else if (podeEditar) {
        c.setAttribute("tabindex", "0");
        c.setAttribute("contenteditable", "plaintext-only");
        c.setAttribute("spellcheck", "false");
      }
      const mascara = this.mascaraDe(c.getAttribute("data-campo") || "");
      if (mascara) c.setAttribute("data-mascara-campo", mascara);
    });
    if (!podeEditar) return;
    doc.addEventListener("input", (e) => this.aoDigitar(/** @type {InputEvent} */ (e)));
    doc.addEventListener("beforeinput", (e) => {
      const ev = /** @type {InputEvent} */ (e);
      if (!this.digitarEmCampoVazio(ev) && !this.digitarNaBorda(ev) && !this.apagarComMascara(ev)) {
        this.sobrescreverComMascara(ev);
        this.protegerCampos(ev);
      }
    });
    doc.addEventListener("selectionchange", () => this.aoMudarSelecao());
    doc.addEventListener("paste", (e) => this.colar(/** @type {ClipboardEvent} */ (e)));
    doc.addEventListener("keydown", (e) => this.atalhos(/** @type {KeyboardEvent} */ (e)));
    // Clique no que vem do cadastro (servidor, motorista, transporte): avisa a página, que
    // abre a peça do formulário que o altera (entidades-documento.js).
    doc.addEventListener("click", (e) => {
      const alvo = /** @type {HTMLElement} */ (e.target);
      if (!this.quadro || alvo.closest("[data-campo]")) return;
      let entidade = /** @type {HTMLElement | null} */ (alvo.closest?.("[data-entidade]"));
      let tipo = entidade?.getAttribute("data-entidade") || "";
      let nome = "";
      if (entidade) {
        nome = tipo === "transporte" ? "Transporte"
          : entidade.matches("tr") ? (/** @type {HTMLTableRowElement} */ (entidade).cells[0]?.textContent || "") : (entidade.textContent || "");
      } else {
        // Blocos que mostram dados do formulário (e não texto livre): o clique leva a eles.
        const bloco = /** @type {HTMLElement | null} */ (alvo.closest("[data-bloco]"));
        const area = alvo.closest(".timbre, .rodape") ? "configuracao"
          : BLOCOS_DO_FORMULARIO[bloco?.getAttribute("data-bloco") || ""];
        if (!area) return;
        tipo = area;
        entidade = /** @type {HTMLElement} */ (alvo.closest("td, p, div, header") || bloco);
        nome = alvo.closest(".timbre") ? "Cabeçalho" : alvo.closest(".rodape") ? "Rodapé"
          : bloco?.getAttribute("data-rotulo") || "";
      }
      if (!entidade) return;
      const q = this.quadro.getBoundingClientRect();
      const r = entidade.getBoundingClientRect();
      this.dispatchEvent(new CustomEvent("pc-editor:entidade", { bubbles: true, detail: {
        tipo, id: entidade.getAttribute("data-id") || "",
        nome: nome.trim().replace(/\s+/g, " ").slice(0, 80),
        caixa: { left: q.left + r.left, top: q.top + r.top, bottom: q.top + r.bottom, width: r.width },
      } }));
    });
    // Clique no campo: o cursor entra nele (num campo vazio o navegador o deixaria fora).
    doc.addEventListener("click", (e) => {
      const campo = /** @type {HTMLElement} */ (e.target).closest?.("[data-campo]");
      if (!campo) return;
      const sel = doc.getSelection();
      if (sel && sel.anchorNode && this.campoDe(sel.anchorNode) === campo && (campo.textContent || "").length) return;
      this.entrarNoCampo(/** @type {HTMLElement} */ (campo));
    });
    // Saindo de um campo que ficou vazio, ele volta a mostrar o rótulo (o amarelo).
    doc.addEventListener("selectionchange", () => {
      this.limparVazio();
      // O campo em que o cursor estava por último: se o navegador o empurrar para a borda
      // de fora (apagou-se o primeiro caractere), a digitação ainda volta para ele.
      const no = doc.getSelection()?.anchorNode;
      const dentro = no ? this.campoDe(no) : null;
      if (dentro) this.campoRecente = dentro;
      else if (!this.bordaDoCampo(doc.getSelection())) this.campoRecente = null;
    });
    doc.addEventListener("click", (e) => {
      // Só o marcador de quebra (um bloco do modelo nunca é: `[data-bloco]`).
      const quebra = /** @type {HTMLElement} */ (e.target).closest(".quebra:not([data-bloco])");
      if (!quebra) return;
      e.preventDefault();
      if (quebra.classList.contains("quebra--livre")) quebra.remove();
      else quebra.classList.toggle("quebra--ativa");
      this.marcarSujo();
    });
    this.aplicarPaginas();
    this.marcarEntidades(doc);
  }

  /**
   * Troca partes da folha pelas do servidor (o roteiro, depois de mudar o destino no texto).
   * @param {string[]} seletores
   */
  async recarregarDaPagina(seletores) {
    const r = await fetch(window.location.pathname, { credentials: "same-origin", headers: { "X-Requested-With": "fetch" } }).catch(() => null);
    if (!r || !r.ok) return;
    const html = new DOMParser().parseFromString(await r.text(), "text/html");
    for (const seletor of seletores) {
      const novo = html.querySelector(seletor);
      const atual = document.querySelector(seletor);
      if (!novo || !atual) continue;
      const importado = /** @type {HTMLElement} */ (document.importNode(novo, true));
      atual.replaceWith(importado);
      /** @type {any} */ (window).htmx?.process(importado);
    }
  }

  /**
   * Quem é quem no texto. O modelo já marca servidor, motorista e transporte
   * (`data-entidade`), mas um trecho editado e salvo antes guarda a cópia de então, sem as
   * marcas: aqui elas voltam, pelo que a folha da página mostra (a equipe e a viatura).
   * Só atributos — o texto não muda.
   * @param {Document} doc
   */
  marcarEntidades(doc) {
    /** @type {Map<string, string>} */
    const equipe = new Map();
    document.querySelectorAll("#equipe [data-servidor][data-nome]").forEach((c) => {
      const el = /** @type {HTMLElement} */ (c);
      equipe.set((el.dataset.nome || "").trim().toLowerCase(), el.dataset.servidor || "");
    });
    doc.querySelectorAll("[data-bloco='equipe'] tbody tr:not([data-entidade])").forEach((tr) => {
      const id = equipe.get((/** @type {HTMLTableRowElement} */ (tr).cells[0]?.textContent || "").trim().toLowerCase());
      if (!id) return;
      tr.setAttribute("data-entidade", "servidor");
      tr.setAttribute("data-id", id);
    });
    const viatura = /** @type {HTMLSelectElement | null} */ (document.querySelector("#transporte select[name='viatura'], #transporte [name='viatura']"));
    doc.querySelectorAll("[data-bloco='transporte'] tr:not([data-entidade])").forEach((tr) => {
      tr.setAttribute("data-entidade", "transporte");
      if (viatura?.value && /^\d+$/.test(viatura.value)) tr.setAttribute("data-id", viatura.value);
    });
    // Datas dos trechos num texto salvo antes de elas virarem campos: "Saída X: 13/12/2026
    // 08:30" ganha o campo do trecho (a ordem é a do documento — a mesma dos trechos). A
    // marcação é salva com o texto (só ela muda), e daí em diante a data acompanha o
    // cadastro e grava no trecho quando escrita aqui.
    let marcouTrechos = false;
    doc.querySelectorAll("[data-bloco='roteiro']").forEach((bloco) => {
      let ordem = 0;
      bloco.querySelectorAll("strong").forEach((forte) => {
        if (forte.querySelector("[data-campo]")) {
          if (/^Saída\b/.test(forte.textContent || "")) ordem += 1;
          return;
        }
        const texto = forte.lastChild;
        const m = /^(Saída|Chegada)\b.*?:\s*(\d{2}\/\d{2}\/\d{4} \d{2}:\d{2})\s*$/.exec(forte.textContent || "");
        if (!m || texto?.nodeType !== Node.TEXT_NODE) return;
        if (m[1] === "Saída") ordem += 1;
        if (!ordem) return;
        const no = /** @type {Text} */ (texto);
        const inicio = no.data.lastIndexOf(m[2]);
        if (inicio < 0) return;
        const data = no.splitText(inicio);
        data.splitText(m[2].length);
        const lado = m[1] === "Saída" ? "saida" : "chegada";
        const span = doc.createElement("span");
        span.setAttribute("data-campo", `trecho_${ordem}_${lado}`);
        span.setAttribute("data-rotulo", `${m[1]} do trecho ${ordem}`);
        span.setAttribute("data-obrigatorio", "");
        span.setAttribute("role", "textbox");
        span.setAttribute("aria-label", `${m[1]} do trecho ${ordem}`);
        span.setAttribute("data-mascara-campo", "datahora");
        data.replaceWith(span);
        span.append(data);
        marcouTrechos = true;
      });
    });
    // "Destino da viagem:" num texto salvo antes: o nome vira o campo dos destinos. Se o texto
    // diz outra cidade que o roteiro da folha (foi trocada aqui), ela vai para o roteiro.
    doc.querySelectorAll("[data-bloco='resumo'] td").forEach((celula) => {
      const rotulo = celula.querySelector("strong");
      if (!rotulo || !/^Destinos? da viagem:?$/.test((rotulo.textContent || "").trim()) || celula.querySelector("[data-campo]")) return;
      const texto = [...celula.childNodes].reverse().find((n) => n.nodeType === Node.TEXT_NODE && (n.textContent || "").trim());
      if (!texto) return;
      const no = /** @type {Text} */ (texto);
      const nome = no.data.trim();
      const resto = no.splitText(no.data.indexOf(nome));
      resto.splitText(nome.length);
      const span = doc.createElement("span");
      span.setAttribute("data-campo", "destinos");
      span.setAttribute("data-rotulo", "Destinos da viagem");
      span.setAttribute("data-obrigatorio", "");
      span.setAttribute("role", "textbox");
      span.setAttribute("aria-label", "Destinos da viagem");
      resto.replaceWith(span);
      span.append(resto);
      marcouTrechos = true;
      const sede = /** @type {HTMLInputElement | null} */ (document.querySelector(".itin__parada--sede input[name$='cidade']"))?.value.trim();
      const naFolha = [...new Set([...document.querySelectorAll(".itin__paradas [data-parada]:not(.itin__parada--sede) input[name$='-cidade']")]
        .map((c) => /** @type {HTMLInputElement} */ (c).value.trim()).filter((v) => v && v !== sede))];
      if (naFolha.length && naFolha.join(", ").toLowerCase() !== nome.toLowerCase()) this.agendarCampo(span);
    });
    if (marcouTrechos) this.marcarSujo();
    // "Motorista: Fulano" — o nome logo depois do rótulo vira o trecho clicável.
    doc.querySelectorAll("[data-bloco='transporte'] strong").forEach((rotulo) => {
      if (!/^Motorista:?$/.test((rotulo.textContent || "").trim())) return;
      const proximo = rotulo.nextSibling;
      if (proximo?.nodeType === Node.ELEMENT_NODE && /** @type {HTMLElement} */ (proximo).matches("[data-entidade]")) return;
      if (proximo?.nodeType !== Node.TEXT_NODE || !(proximo.textContent || "").trim()) return;
      const texto = /** @type {Text} */ (proximo);
      const nome = (texto.data.match(/^\s*([^\n]+?)\s*$/) || [])[1];
      if (!nome) return;
      const inicio = texto.data.indexOf(nome);
      const resto = texto.splitText(inicio);
      resto.splitText(nome.length);
      const span = doc.createElement("span");
      span.setAttribute("data-entidade", "motorista");
      resto.replaceWith(span);
      span.append(resto);
    });
  }

  /** @param {InputEvent} e */
  aoDigitar(e) {
    const alvo = /** @type {HTMLElement | null} */ (e.target);
    const doc = this.doc;
    if (!doc) return;
    const grupoTabela = /** @type {HTMLElement | null} */ (this.barra?.querySelector("[data-so-tabela]") ?? null);
    if (grupoTabela) grupoTabela.hidden = !this.celulaAtual();
    const selecao = doc.getSelection();
    const no = selecao && selecao.anchorNode;
    const campo = no ? this.campoDe(no) : null;
    if (campo) {
      this.limparVazio();
      this.mascarar(campo);
      this.agendarCampo(campo);
      return;
    }
    if (alvo && alvo.closest("[data-regiao]")) this.marcarSujo();
  }

  /**
   * Campo vazio: o navegador não deixa o cursor "dentro" de um elemento sem texto — o que
   * se digita cai no texto em volta ("Protocolo Nº: 123" fora do campo) e nunca chega ao
   * cadastro. Digitando (ou colando) com o cursor no campo vazio ou encostado nele, o texto
   * entra no campo e o cursor fica dentro dele, como em qualquer campo preenchido.
   * @param {InputEvent} e @returns {boolean} se cuidou da digitação
   */
  digitarEmCampoVazio(e) {
    if (e.inputType !== "insertText" && e.inputType !== "insertReplacementText") return false;
    const texto = e.data || "";
    return Boolean(texto) && this.inserirEmCampoVazio(texto, () => e.preventDefault());
  }

  /** @param {string} texto @param {() => void} antes @returns {boolean} */
  inserirEmCampoVazio(texto, antes) {
    const doc = this.doc;
    const sel = doc ? doc.getSelection() : null;
    if (!doc || !sel || !sel.rangeCount || !sel.isCollapsed) return false;
    const campo = this.campoVazioNoCursor(sel);
    if (!campo) return false;
    antes();
    campo.textContent = "";  // só tinha a marca invisível (ou nada)
    this.marcaVazio = null;
    const no = doc.createTextNode(texto.replace(/\s*\n\s*/g, " "));
    campo.append(no);
    const r = doc.createRange();
    r.setStart(no, no.length);
    r.collapse(true);
    sel.removeAllRanges();
    sel.addRange(r);
    this.mascarar(campo);
    this.agendarCampo(campo);
    return true;
  }

  /**
   * O campo encostado no cursor (logo antes ou logo depois dele), e de que lado.
   * @param {Selection | null | undefined} sel
   * @returns {{campo: HTMLElement, lado: "inicio" | "fim"} | null}
   */
  bordaDoCampo(sel) {
    if (!sel || !sel.isCollapsed || !sel.anchorNode) return null;
    const no = sel.anchorNode;
    const pos = sel.anchorOffset;
    const campo = (/** @type {Node | null | undefined} */ el) => (el && el.nodeType === Node.ELEMENT_NODE
      && /** @type {HTMLElement} */ (el).matches("[data-campo]") ? /** @type {HTMLElement} */ (el) : null);
    if (this.campoDe(no)) return null;
    if (no.nodeType === Node.TEXT_NODE) {
      const depois = pos === (no.textContent || "").length ? campo(no.nextSibling) : null;
      if (depois) return { campo: depois, lado: "inicio" };
      const antes = pos === 0 ? campo(no.previousSibling) : null;
      if (antes) return { campo: antes, lado: "fim" };
      return null;
    }
    const depois = campo(no.childNodes[pos]);
    if (depois) return { campo: depois, lado: "inicio" };
    const antes = campo(no.childNodes[pos - 1]);
    return antes ? { campo: antes, lado: "fim" } : null;
  }

  /**
   * Digitando encostado num campo (o navegador tirou o cursor dele — ex.: apagou-se o
   * primeiro algarismo da data): o texto entra no campo quando ele tem máscara (data, hora,
   * protocolo: ao redor não se escreve número solto) ou quando o cursor acabou de sair dele.
   * @param {InputEvent} e @returns {boolean}
   */
  digitarNaBorda(e) {
    if ((e.inputType !== "insertText" && e.inputType !== "insertReplacementText") || !e.data) return false;
    const doc = this.doc;
    const sel = doc?.getSelection();
    const borda = this.bordaDoCampo(sel);
    if (!doc || !sel || !borda) return false;
    const { campo, lado } = borda;
    const algarismo = campo.hasAttribute("data-mascara-campo") && /^\d+$/.test(e.data);
    if (!algarismo && campo !== this.campoRecente) return false;
    e.preventDefault();
    const texto = e.data.replace(/\s*\n\s*/g, " ");
    let no = /** @type {Text | null} */ (lado === "inicio" ? campo.firstChild : campo.lastChild);
    if (!no || no.nodeType !== Node.TEXT_NODE) {
      no = doc.createTextNode("");
      if (lado === "inicio") campo.prepend(no); else campo.append(no);
    }
    const alvo = /** @type {Text} */ (no);
    const pos = lado === "inicio" ? texto.length : alvo.length + texto.length;
    if (lado === "inicio") alvo.insertData(0, texto); else alvo.appendData(texto);
    const r = doc.createRange();
    r.setStart(alvo, pos);
    r.collapse(true);
    sel.removeAllRanges();
    sel.addRange(r);
    this.campoRecente = campo;
    this.mascarar(campo);
    this.agendarCampo(campo);
    return true;
  }

  /** O campo vazio em que o cursor está (ou em foco, ou logo encostado). @param {Selection} sel */
  campoVazioNoCursor(sel) {
    const vazio = (/** @type {Node | null | undefined} */ el) => (el && el.nodeType === Node.ELEMENT_NODE
      && /** @type {HTMLElement} */ (el).matches("[data-campo]") && !(el.textContent || "").split(INVISIVEL).join("").length
      ? /** @type {HTMLElement} */ (el) : null);
    const no = sel.anchorNode;
    const pos = sel.anchorOffset;
    if (!no) return null;
    const dentro = this.campoDe(no);
    if (dentro) return vazio(dentro);
    const ativo = vazio(this.doc?.activeElement);
    if (ativo) return ativo;
    if (no.nodeType === Node.ELEMENT_NODE) return vazio(no.childNodes[pos]) || vazio(no.childNodes[pos - 1]);
    if (no.nodeType === Node.TEXT_NODE) {
      if (pos === (no.textContent || "").length && vazio(no.nextSibling)) return vazio(no.nextSibling);
      if (pos === 0) return vazio(no.previousSibling);
    }
    return null;
  }

  /**
   * A máscara do campo: a do controle de mesmo nome no formulário da página (data-mascara),
   * ou a do formato do campo (data). Sem máscara, o texto fica como foi digitado.
   * @param {string} chave
   */
  mascaraDe(chave) {
    if (!chave) return "";
    const controle = /** @type {HTMLElement | null} */ (document.querySelector(`[name="${CSS.escape(chave)}"][data-mascara]`));
    const tipo = controle?.dataset.mascara || (chave.startsWith("data_") ? "data" : "")
      || (/^trecho_\d+_(saida|chegada)$/.test(chave) ? "datahora" : "");
    return tipo && MASCARAS[tipo] ? tipo : "";
  }

  /**
   * Aplica a máscara ao campo sem tirar o cursor do lugar: ele fica depois do mesmo número de
   * algarismos/letras que tinha antes (apagar um dígito do meio não joga o cursor para o fim).
   * @param {HTMLElement} campo
   */
  mascarar(campo) {
    const tipo = campo.getAttribute("data-mascara-campo");
    const doc = this.doc;
    if (!tipo || !MASCARAS[tipo] || !doc) return;
    const atual = campo.textContent || "";
    const novo = MASCARAS[tipo](atual.split(INVISIVEL).join(""));
    if (novo === atual) return;
    const sel = doc.getSelection();
    let antes = atual.length;
    if (sel && sel.rangeCount && sel.anchorNode && campo.contains(sel.anchorNode)) {
      const ate = doc.createRange();
      ate.selectNodeContents(campo);
      ate.setEnd(sel.anchorNode, sel.anchorOffset);
      antes = ate.toString().length;
    }
    const contam = atual.slice(0, antes).replace(/[^0-9A-Za-z]/g, "").length;
    campo.textContent = novo;
    let pos = 0;
    for (let vistos = 0; pos < novo.length && vistos < contam; pos += 1) {
      if (/[0-9A-Za-z]/.test(novo[pos])) vistos += 1;
    }
    const texto = campo.firstChild;
    if (!sel || !texto) return;
    const r = doc.createRange();
    r.setStart(texto, Math.min(pos, novo.length));
    r.collapse(true);
    sel.removeAllRanges();
    sel.addRange(r);
  }

  /**
   * Campo de tamanho fixo já completo (13/12/2026 08:30): digitar troca o algarismo seguinte
   * em vez de empurrar os outros — como num relógio, a data nunca fica embaralhada no meio.
   * @param {InputEvent} e
   */
  sobrescreverComMascara(e) {
    if (e.inputType !== "insertText" || !e.data || !/^\d$/.test(e.data)) return;
    const doc = this.doc;
    const sel = doc?.getSelection();
    if (!doc || !sel || !sel.isCollapsed || !sel.anchorNode || sel.anchorNode.nodeType !== Node.TEXT_NODE) return;
    const campo = this.campoDe(sel.anchorNode);
    const tipo = campo?.getAttribute("data-mascara-campo") || "";
    const limite = DIGITOS_DA_MASCARA[tipo];
    if (!campo || !limite || (campo.textContent || "").replace(/\D/g, "").length < limite) return;
    const no = /** @type {Text} */ (sel.anchorNode);
    let i = sel.anchorOffset;
    while (i < no.length && !/\d/.test(no.data[i])) i += 1;
    if (i >= no.length) return;
    const r = doc.createRange();
    r.setStart(no, sel.anchorOffset);
    r.setEnd(no, i + 1);
    sel.removeAllRanges();
    sel.addRange(r);
  }

  /**
   * Backspace logo depois de um separador da máscara ("/", ":", " "): apaga o dígito de
   * antes dele, em vez de apagar o separador que a máscara poria de volta (parecia travado).
   * @param {InputEvent} e @returns {boolean} se cuidou
   */
  apagarComMascara(e) {
    if (e.inputType !== "deleteContentBackward") return false;
    const doc = this.doc;
    const sel = doc?.getSelection();
    if (!doc || !sel || !sel.isCollapsed || !sel.anchorNode) return false;
    const campo = this.campoDe(sel.anchorNode);
    if (!campo?.getAttribute("data-mascara-campo") || sel.anchorNode.nodeType !== Node.TEXT_NODE) return false;
    const no = /** @type {Text} */ (sel.anchorNode);
    const pos = sel.anchorOffset;
    if (pos < 2 || /[0-9A-Za-z]/.test(no.data[pos - 1])) return false;
    e.preventDefault();
    no.deleteData(pos - 2, 1);
    const r = doc.createRange();
    r.setStart(no, pos - 2);
    r.collapse(true);
    sel.removeAllRanges();
    sel.addRange(r);
    this.mascarar(campo);
    this.agendarCampo(campo);
    return true;
  }

  /** @param {Node} no @returns {HTMLElement | null} */
  campoDe(no) {
    const el = no.nodeType === Node.ELEMENT_NODE ? /** @type {HTMLElement} */ (no) : no.parentElement;
    return el ? /** @type {HTMLElement | null} */ (el.closest("[data-campo]")) : null;
  }

  /**
   * Um campo vinculado não pode ser apagado inteiro de dentro do texto: ele vem do
   * cadastro. Edita-se o que está dentro dele; o contorno fica.
   * @param {InputEvent} e
   */
  protegerCampos(e) {
    if (e.inputType === "insertParagraph" || e.inputType === "insertLineBreak") {
      const sel = this.doc?.getSelection();
      const campo = sel && sel.anchorNode ? this.campoDe(sel.anchorNode) : null;
      if (campo && !campo.hasAttribute("data-multilinha")) {
        e.preventDefault();
        /** @type {HTMLElement} */ (campo).blur();
        return;
      }
    }
    if (!e.inputType.startsWith("delete") && e.inputType !== "insertFromPaste"
        && e.inputType !== "insertText" && e.inputType !== "insertParagraph") return;
    const faixas = typeof e.getTargetRanges === "function" ? e.getTargetRanges() : [];
    for (const faixa of faixas) {
      if (faixa.collapsed && e.inputType.startsWith("delete")) {
        // Backspace na borda de um campo: não deixa engolir o campo vizinho.
        const vizinho = this.campoNaBorda(faixa, e.inputType);
        if (vizinho) { e.preventDefault(); return; }
        continue;
      }
      const doc = this.doc;
      if (!doc) return;
      const r = doc.createRange();
      r.setStart(faixa.startContainer, faixa.startOffset);
      r.setEnd(faixa.endContainer, faixa.endOffset);
      const campos = Array.from(doc.querySelectorAll("[data-campo]"));
      const engolido = campos.some((c) => {
        const alvo = doc.createRange();
        alvo.selectNode(c);
        return r.compareBoundaryPoints(Range.START_TO_START, alvo) <= 0
          && r.compareBoundaryPoints(Range.END_TO_END, alvo) >= 0;
      });
      if (engolido) {
        e.preventDefault();
        avisar("aviso", "Este trecho vem do cadastro e não pode ser removido do texto; edite o que está dentro dele.");
        return;
      }
    }
  }

  /** @param {StaticRange} faixa @param {string} tipo */
  campoNaBorda(faixa, tipo) {
    const no = faixa.startContainer;
    if (this.campoDe(no)) return null; // dentro do campo: pode apagar o conteúdo
    const texto = no.nodeType === Node.TEXT_NODE ? /** @type {Text} */ (no) : null;
    if (!texto) return null;
    const noLimite = tipo === "deleteContentBackward" ? faixa.startOffset === 0
      : faixa.startOffset === texto.length;
    if (!noLimite) return null;
    const vizinho = tipo === "deleteContentBackward" ? texto.previousSibling : texto.nextSibling;
    return vizinho && vizinho.nodeType === Node.ELEMENT_NODE
      && /** @type {HTMLElement} */ (vizinho).matches("[data-campo]") ? vizinho : null;
  }

  /** @param {ClipboardEvent} e */
  colar(e) {
    const doc = this.doc;
    if (!doc || !e.clipboardData) return;
    e.preventDefault();
    const texto = e.clipboardData.getData("text/plain");
    if (!texto) return;
    if (this.inserirEmCampoVazio(texto.trim(), () => {})) return;
    // Texto puro: parágrafos viram <p>, o resto é escapado — nada de formatação de fora.
    const paragrafos = texto.replace(/\r/g, "").split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);
    const html = paragrafos.length > 1
      ? paragrafos.map((p) => `<p>${escapar(p).replace(/\n/g, "<br>")}</p>`).join("")
      : escapar(texto).replace(/\n/g, "<br>");
    doc.execCommand("insertHTML", false, html);
    this.marcarSujo();
  }

  aoMudarSelecao() {
    const doc = this.doc;
    if (!doc || !this.barra) return;
    this.barra.querySelectorAll("[data-comando]").forEach((b) => {
      const comando = /** @type {HTMLElement} */ (b).dataset.comando || "";
      let ativo = false;
      try { ativo = doc.queryCommandState(comando); } catch { ativo = false; }
      b.setAttribute("aria-pressed", String(ativo));
    });
    const selecao = doc.getSelection();
    const no = selecao && selecao.anchorNode;
    const el = no ? (no.nodeType === Node.ELEMENT_NODE ? /** @type {HTMLElement} */ (no) : no.parentElement) : null;
    this.blocoAtual = el ? /** @type {HTMLElement | null} */ (el.closest("[data-bloco]")) : null;
    const botao = /** @type {HTMLButtonElement | null} */ (this.querySelector("[data-acao='original']"));
    if (botao) {
      const rotulo = this.blocoAtual ? this.blocoAtual.getAttribute("data-rotulo") || "" : "";
      botao.disabled = !this.blocoAtual || this.vitrine;
      botao.title = rotulo ? `Voltar «${rotulo}» ao original` : "Voltar o bloco ao original";
      botao.setAttribute("aria-label", botao.title);
    }
  }

  /** @param {KeyboardEvent} e */
  atalhos(e) {
    if (!(e.ctrlKey || e.metaKey)) return;
    if (e.key.toLowerCase() === "s") {
      e.preventDefault();
      if (this.sujo) this.salvar();
      else if (this.campoPendente) this.salvarCampo();
    }
  }

  // ---------------------------------------------------------------- barra
  prepararBarra() {
    const barra = this.barra;
    if (!barra) return;
    barra.addEventListener("click", (e) => {
      const botao = /** @type {HTMLElement | null} */ (/** @type {HTMLElement} */ (e.target).closest("button"));
      if (!botao) return;
      if (botao.dataset.comando) this.comando(botao.dataset.comando);
      else if (botao.dataset.estiloValor) {
        const [prop, valor] = botao.dataset.estiloValor.split(":");
        this.estilizarSelecao(prop, valor);
      } else if (botao.dataset.modo) this.modo(botao.dataset.modo);
      else if (botao.dataset.acao) this.acao(botao.dataset.acao, botao);
    });
    barra.addEventListener("change", (e) => {
      const campo = /** @type {HTMLSelectElement} */ (e.target);
      if (!(campo instanceof HTMLSelectElement) || !campo.value) return;
      if (campo.dataset.estilo) {
        this.estilizarSelecao(campo.dataset.estilo, campo.value);
      } else if (campo.dataset.tabelaEstilo || campo.dataset.linhaEstilo) {
        const celula = this.celulaAtual();
        const alvo = campo.dataset.tabelaEstilo ? celula?.closest("table") : celula?.closest("tr");
        if (alvo) {
          /** @type {HTMLElement} */ (alvo).style.setProperty(
            campo.dataset.tabelaEstilo || campo.dataset.linhaEstilo || "", campo.value);
          this.marcarSujo();
        }
      }
      campo.value = "";  // a escolha é uma ação, não um estado
      // O <pc-select> em volta volta a mostrar o rótulo ("Largura"); sem borbulhar, este
      // ouvinte não roda de novo.
      campo.dispatchEvent(new Event("change"));
      this.focarFolha();
    });
    // Padrão "toolbar" da WAI-ARIA: um só tabstop; setas andam entre os botões.
    const controles = () => /** @type {HTMLElement[]} */ (Array.from(
      barra.querySelectorAll("button, a[href], select, input, summary")))
      .filter((b) => !b.closest("[role='menu'], [role='listbox']"));
    const elegiveis = () => controles().filter((b) => !b.matches(":disabled, [aria-hidden='true']")
        && !b.closest("[hidden], [role='menu'], [role='listbox']")
        && (!b.closest("details:not([open])") || b.matches("summary")));
    let tabulavel = elegiveis()[0];
    const atualizarTabulacao = () => {
      const lista = elegiveis();
      const foco = /** @type {HTMLElement} */ (document.activeElement);
      if (lista.includes(foco)) tabulavel = foco;
      else if (!lista.includes(tabulavel)) tabulavel = lista[0];
      controles().forEach((b) => b.setAttribute("tabindex", b === tabulavel ? "0" : "-1"));
    };
    atualizarTabulacao();
    // pc-select e as pendências inserem controles depois da inicialização.
    this.observadorBarra?.disconnect();
    this.observadorBarra = new MutationObserver(atualizarTabulacao);
    this.observadorBarra.observe(barra, { childList: true, subtree: true,
      attributes: true, attributeFilter: ["hidden", "disabled", "aria-hidden", "open"] });
    barra.addEventListener("keydown", (e) => {
      if (e.defaultPrevented || /** @type {HTMLElement} */ (e.target).closest("[role='menu'], [role='listbox']")) return;
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) return;
      const lista = elegiveis().filter((b) => b.getClientRects().length);
      const i = lista.indexOf(/** @type {HTMLElement} */ (document.activeElement));
      if (i < 0) return;
      e.preventDefault();
      const alvo = e.key === "Home" ? 0 : e.key === "End" ? lista.length - 1
        : e.key === "ArrowRight" ? (i + 1) % lista.length : (i - 1 + lista.length) % lista.length;
      tabulavel = lista[alvo];
      tabulavel.focus();
      atualizarTabulacao();
    });
    const tabela = /** @type {HTMLFormElement | null} */ (this.querySelector("form[data-tabela]"));
    if (tabela) tabela.addEventListener("submit", (e) => { e.preventDefault(); this.inserirTabela(tabela); });
    const guardar = /** @type {HTMLFormElement | null} */ (this.querySelector("form[data-guardar]"));
    if (guardar) guardar.addEventListener("submit", (e) => { e.preventDefault(); this.guardarTextoPronto(guardar); });
    const menuTextos = this.querySelector("[data-textos-painel]");
    if (menuTextos) {
      const botaoMenu = /** @type {HTMLElement | null} */ (menuTextos.closest("pc-menu")?.querySelector("[data-menu-botao]"));
      if (botaoMenu) botaoMenu.addEventListener("click", () => this.carregarTextos(), { once: true });
      menuTextos.addEventListener("click", (e) => this.cliqueTextos(/** @type {MouseEvent} */ (e)));
    }
    if (this.historico) {
      this.historico.addEventListener("click", (e) => {
        const b = /** @type {HTMLElement | null} */ (/** @type {HTMLElement} */ (e.target).closest("[data-versao]"));
        if (!b) return;
        const numero = Number(b.dataset.versao);
        if (b.dataset.ver !== undefined) this.verVersao(numero);
        else this.restaurar(numero);
      });
    }
  }

  /** Aplica um estilo inline ao trecho selecionado (tamanho/cor da fonte), embrulhando-o
   * num <span>. Sem trecho selecionado (só o cursor num parágrafo), vale para o parágrafo
   * inteiro — escolher um tamanho e nada acontecer parecia defeito. O saneador do servidor
   * guarda só valores da lista que a barra oferece.
   * @param {string} propriedade @param {string} valor */
  estilizarSelecao(propriedade, valor) {
    const doc = this.doc;
    const sel = doc?.getSelection();
    if (!doc || !sel || !sel.rangeCount || !valor) return;
    const faixa = sel.getRangeAt(0);
    const no = faixa.commonAncestorContainer;
    const elemento = no.nodeType === 1 ? /** @type {Element} */ (no) : no.parentElement;
    if (!elemento?.closest("[data-regiao]")) return;
    if (sel.isCollapsed) {
      const bloco = /** @type {HTMLElement | null} */ (
        elemento.closest("p, li, td, th, h1, h2, h3, blockquote, [data-bloco]"));
      if (!bloco || !bloco.closest("[data-regiao]") || bloco.matches("[data-regiao]")) return;
      bloco.style.setProperty(propriedade, valor);
      this.marcarSujo();
      return;
    }
    const span = doc.createElement("span");
    span.style.setProperty(propriedade, valor);
    try {
      span.append(faixa.extractContents());
      faixa.insertNode(span);
    } catch {
      return;
    }
    sel.removeAllRanges();
    const nova = doc.createRange();
    nova.selectNodeContents(span);
    sel.addRange(nova);
    this.marcarSujo();
  }

  /** Célula onde o cursor está (ou nada). @returns {HTMLTableCellElement | null} */
  celulaAtual() {
    const no = this.doc?.getSelection()?.anchorNode;
    const el = no?.nodeType === 1 ? /** @type {Element} */ (no) : no?.parentElement;
    return /** @type {HTMLTableCellElement | null} */ (el?.closest("td, th") ?? null);
  }

  /** @param {string} comando */
  comando(comando) {
    const doc = this.doc;
    if (!doc) return;
    this.focarFolha();
    doc.execCommand(comando, false);
    this.marcarSujo();
    this.aoMudarSelecao();
  }

  focarFolha() {
    const doc = this.doc;
    if (!doc) return;
    const ativo = doc.activeElement;
    if (ativo && ativo.closest("[data-regiao]")) return;
    const sel = doc.getSelection();
    const regiao = /** @type {HTMLElement | null} */ (doc.querySelector("[data-regiao='corpo'], [data-regiao]"));
    if (!regiao) return;
    regiao.focus();
    if (sel && sel.rangeCount === 0) {
      const r = doc.createRange();
      r.selectNodeContents(regiao);
      r.collapse(true);
      sel.addRange(r);
    }
  }

  /** @param {string} modo */
  modo(modo) {
    // No PDF o índice de páginas do bloco (termo) some — editor.css.
    this.classList.toggle("editor--pdf", modo === "pdf");
    this.querySelectorAll("[data-modo]").forEach((b) => b.setAttribute("aria-pressed", String(/** @type {HTMLElement} */ (b).dataset.modo === modo)));
    if (this.quadro) this.quadro.hidden = modo !== "texto";
    if (this.quadroPdf) {
      this.quadroPdf.hidden = modo !== "pdf";
      if (modo === "pdf" && this.dataset.pdf) {
        const url = new URL(this.dataset.pdf, window.location.href);
        url.searchParams.set("_", String(Date.now()));
        this.quadroPdf.src = url.toString();
      }
    }
    this.querySelectorAll("[data-so-texto]").forEach((g) => { /** @type {HTMLElement} */ (g).hidden = modo !== "texto"; });
  }

  /** @param {string} acao @param {HTMLElement} botao */
  async acao(acao, botao) {
    switch (acao) {
      case "quebra": return this.inserirQuebra();
      case "original": return this.voltarBlocoAoOriginal();
      case "modelo": return this.voltarAoModelo();
      case "historico": if (this.historico) { this.montarHistorico(); this.historico.showModal(); } return;
      case "salvar": return this.sujo ? this.salvar() : undefined;
      case "recarregar": return this.recarregar();
      case "atualizar": return this.atualizarDocumento(botao);
      case "guardar-texto": return this.abrirGuardarTexto();
      case "atual": return this.verVersao(null);
      case "ir-campo": return this.irParaCampo(botao.dataset.campo || "");
      default: return undefined;
    }
  }

  // ---------------------------------------------------------------- inserções
  /** Insere a quebra como bloco, antes do bloco onde está o cursor. */
  inserirQuebra() {
    const doc = this.doc;
    if (!doc) return;
    this.focarFolha();
    const sel = doc.getSelection();
    const no = sel && sel.anchorNode;
    const el = no ? (no.nodeType === Node.ELEMENT_NODE ? /** @type {HTMLElement} */ (no) : no.parentElement) : null;
    const regiao = el ? el.closest("[data-regiao]") : null;
    if (!el || !regiao) return;
    let bloco = /** @type {HTMLElement | null} */ (el.closest(SELETOR_BLOCO));
    while (bloco && bloco.parentElement && bloco.parentElement !== regiao) bloco = bloco.parentElement;
    const quebra = doc.createElement("div");
    quebra.className = "quebra quebra--ativa quebra--livre";
    quebra.setAttribute("data-rotulo", "Quebra de página");
    quebra.setAttribute("contenteditable", "false");
    if (bloco && bloco.parentElement === regiao) regiao.insertBefore(quebra, bloco);
    else regiao.appendChild(quebra);
    this.marcarSujo();
  }

  /** @param {HTMLFormElement} form */
  inserirTabela(form) {
    const doc = this.doc;
    if (!doc) return;
    const linhas = Math.min(20, Math.max(1, Number(new FormData(form).get("linhas")) || 2));
    const colunas = Math.min(8, Math.max(1, Number(new FormData(form).get("colunas")) || 2));
    const celulas = "<td>&nbsp;</td>".repeat(colunas);
    const html = `<table><tbody>${`<tr>${celulas}</tr>`.repeat(linhas)}</tbody></table><p><br></p>`;
    this.focarFolha();
    doc.execCommand("insertHTML", false, html);
    this.marcarSujo();
    const menu = form.closest("pc-menu");
    const botao = menu ? /** @type {HTMLElement | null} */ (menu.querySelector("[data-menu-botao]")) : null;
    if (botao) botao.click();
  }

  async carregarTextos() {
    const painel = this.querySelector("[data-textos-painel]");
    if (!painel) return;
    if (this.vitrine) {
      this.textos = [{ id: 0, nome: "Exemplo", texto: "Texto pronto de exemplo.", tipo: "oficio", tipo_rotulo: "Trecho", padrao_sistema: true }];
    } else {
      try {
        const r = await fetch(`${this.base}textos/`, { headers: { Accept: "application/json" } });
        const dados = await r.json();
        this.textos = dados.textos || [];
      } catch {
        this.textos = [];
      }
    }
    this.montarTextos();
  }

  montarTextos() {
    const painel = this.querySelector("[data-textos-painel]");
    if (!painel) return;
    const lista = /** @type {HTMLElement | null} */ (painel.querySelector("[data-textos-lista]"));
    if (!lista) return;
    const podeGerir = Boolean(this.estado && this.estado.pode_gerir_textos);
    lista.replaceChildren();
    for (const t of this.textos || []) {
      const linha = document.createElement("div");
      linha.className = "editor__texto-pronto";
      const b = document.createElement("button");
      b.type = "button";
      b.className = "menu__item";
      b.setAttribute("role", "menuitem");
      b.dataset.inserir = String(t.id);
      b.innerHTML = `${escapar(t.nome)}<small>${escapar(t.tipo_rotulo)} · ${escapar(t.texto.slice(0, 80))}${t.texto.length > 80 ? "…" : ""}</small>`;
      linha.append(b);
      if (podeGerir && !t.padrao_sistema) {
        const x = document.createElement("button");
        x.type = "button";
        x.className = "botao botao--sm botao--icone";
        x.dataset.remover = String(t.id);
        x.setAttribute("aria-label", `Remover o texto pronto ${t.nome}`);
        x.textContent = "×";
        linha.append(x);
      }
      lista.append(linha);
    }
    if (!(this.textos || []).length) {
      // Vazio: o que é e como criar o primeiro, sem um parágrafo espremido no menu.
      const vazio = document.createElement("div");
      vazio.className = "editor__textos-vazio";
      const simbolo = document.createElement("span");
      simbolo.className = "editor__textos-vazio-icone";
      simbolo.setAttribute("aria-hidden", "true");
      simbolo.append(icone("book-open-text", "icone"));
      const titulo = document.createElement("strong");
      titulo.textContent = "Nenhum texto pronto ainda";
      const dica = document.createElement("span");
      dica.textContent = "Selecione um trecho da folha e guarde-o abaixo para reaproveitar.";
      vazio.append(simbolo, titulo, dica);
      lista.append(vazio);
    }
  }

  /** @param {MouseEvent} e */
  async cliqueTextos(e) {
    const alvo = /** @type {HTMLElement} */ (e.target);
    const inserir = /** @type {HTMLElement | null} */ (alvo.closest("[data-inserir]"));
    if (inserir) {
      const t = (this.textos || []).find((x) => String(x.id) === inserir.dataset.inserir);
      if (t) this.inserirTexto(t.texto);
      return;
    }
    const remover = /** @type {HTMLElement | null} */ (alvo.closest("[data-remover]"));
    if (remover && !this.vitrine) {
      e.stopPropagation();
      const t = (this.textos || []).find((x) => String(x.id) === remover.dataset.remover);
      if (!t || !(await confirmar({ titulo: "Remover texto pronto?", mensagem: `«${t.nome}» deixa de aparecer para todos.`, confirmar: "Remover", perigo: true }))) return;
      const r = await this.pedir(`textos/${t.id}/remover/`, {});
      if (r && r.textos) { this.textos = r.textos; this.montarTextos(); }
    }
  }

  /** @param {string} texto */
  inserirTexto(texto) {
    const doc = this.doc;
    if (!doc) return;
    this.focarFolha();
    const paragrafos = texto.replace(/\r/g, "").split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);
    const html = paragrafos.length > 1
      ? paragrafos.map((p) => `<p>${escapar(p).replace(/\n/g, "<br>")}</p>`).join("")
      : escapar(texto).replace(/\n/g, "<br>");
    doc.execCommand("insertHTML", false, html);
    this.marcarSujo();
  }

  abrirGuardarTexto() {
    const doc = this.doc;
    const d = this.dialogoTexto;
    if (!doc || !d) return;
    const sel = doc.getSelection();
    const texto = sel ? sel.toString().trim() : "";
    const area = /** @type {HTMLTextAreaElement | null} */ (d.querySelector("textarea[name='texto']"));
    if (area) area.value = texto;
    d.showModal();
  }

  /** @param {HTMLFormElement} form */
  async guardarTextoPronto(form) {
    const dados = new FormData(form);
    if (this.vitrine) { avisar("info", "Na vitrine nada é guardado."); return; }
    const r = await this.pedir("textos/", { nome: String(dados.get("nome") || ""), texto: String(dados.get("texto") || "") });
    if (!r) return;
    this.textos = r.textos || this.textos;
    this.montarTextos();
    form.reset();
    const d = form.closest("dialog");
    if (d) /** @type {HTMLDialogElement} */ (d).close();
    avisar("sucesso", "Texto pronto guardado.");
  }

  // ---------------------------------------------------------------- salvar
  marcarSujo() {
    if (this.vitrine) {
      this.mostrarSalvo("Vitrine: nada é salvo", "");
      return;
    }
    this.sujo = true;
    this.mostrarSalvo("Alterado — salvando em instantes…", "editor__salvo--pendente");
    window.clearTimeout(this.timerSalvar);
    this.timerSalvar = window.setTimeout(() => this.salvar(), ESPERA_SALVAR);
  }

  /** @returns {Record<string, string>} */
  regioes() {
    const doc = this.doc;
    /** @type {Record<string, string>} */
    const r = {};
    if (!doc) return r;
    doc.querySelectorAll("[data-regiao]").forEach((el) => {
      r[el.getAttribute("data-regiao") || ""] = el.innerHTML;
    });
    return r;
  }

  async salvar() {
    if (this.vitrine || !this.sujo || this.vendoVersao !== null) return;
    window.clearTimeout(this.timerSalvar);
    this.sujo = false;
    this.salvando = true;
    this.mostrarSalvo("Salvando…", "editor__salvo--salvando");
    const base = this.estado && this.estado.edicao ? this.estado.edicao.numero : 0;
    const r = await this.pedir("salvar/", { regioes: this.regioes(), versao_base: base });
    this.salvando = false;
    if (!r) {
      this.sujo = true;
      this.mostrarSalvo("Não salvo", "editor__salvo--erro");
      return;
    }
    this.aplicarEstado(r);
    this.marcarBlocosAlterados();
    this.paginas();
    this.avisarGravado();
    this.oferecerAplicarEmTodos();
  }

  /** O texto gravado mudou (quem mostra a folha em miniatura refaz: editores.js). */
  avisarGravado() {
    this.dispatchEvent(new CustomEvent("pc-editor:gravado", { bubbles: true }));
  }

  /** @param {HTMLElement} campo */
  agendarCampo(campo) {
    const chave = campo.getAttribute("data-campo");
    // Trocou de campo antes da pausa: o anterior grava agora (senão o novo tomava o lugar
    // dele na fila e o que foi digitado nele se perdia).
    if (this.campoPendente && this.campoPendente !== chave) {
      window.clearTimeout(this.timerCampo);
      this.salvarCampo();
    }
    this.campoPendente = chave;
    window.clearTimeout(this.timerCampo);
    this.timerCampo = window.setTimeout(() => this.salvarCampo(), ESPERA_CAMPO);
  }

  async salvarCampo() {
    const doc = this.doc;
    const chave = this.campoPendente;
    if (!doc || !chave || this.vitrine) return;
    const span = /** @type {HTMLElement | null} */ (doc.querySelector(`[data-campo="${CSS.escape(chave)}"]`));
    if (!span) return;
    const limite = DIGITOS_DA_MASCARA[span.getAttribute("data-mascara-campo") || ""];
    const digitos = (span.textContent || "").replace(/\D/g, "").length;
    if (limite && digitos && digitos < limite) return;  // grava quando a pessoa completar
    this.campoPendente = null;
    const valor = span.hasAttribute("data-multilinha") ? span.innerText.replace(/ /g, " ") : span.textContent || "";
    const versao = this.estado ? this.estado.versao_oficio : undefined;
    const r = await this.pedir(`campos/${encodeURIComponent(chave)}/`, { valor: valor.split(INVISIVEL).join(""), versao });
    if (!r) return;
    this.aplicarEstado(r);
    this.avisarGravado();
    const resultado = r.resultado || {};
    // O formulário da folha mostra o mesmo campo: acompanha, e a versão do ofício também.
    const nome = CSS.escape(chave);
    const entrada = /** @type {HTMLInputElement | HTMLTextAreaElement | null} */ (document.querySelector(`#form-oficio [name="${nome}"], [form="form-oficio"][name="${nome}"]`)
      || document.querySelector(`form [name="${nome}"]:not([type='hidden']), [form][name="${nome}"]:not([type='hidden'])`));
    if (entrada && typeof resultado.valor === "string") {
      entrada.value = resultado.valor;
      entrada.dispatchEvent(new Event("pc-campo-externo", { bubbles: true }));
    }
    // Destino trocado no texto: o roteiro da folha vem de novo do servidor (paradas, mapa).
    if (Array.isArray(resultado.recarregar) && resultado.recarregar.length) {
      this.recarregarDaPagina(resultado.recarregar);
      document.body.dispatchEvent(new CustomEvent("equipe-alterada"));
    }
    // Saída/chegada de um trecho: os campos do trecho no roteiro da folha acompanham (e o
    // autosave não devolve o valor antigo); as diárias se refazem.
    const trecho = resultado.trecho;
    if (trecho) {
      const linha = document.querySelectorAll(".itin__trechos [data-trecho]")[trecho.ordem - 1];
      for (const [sufixo, novo] of [["saida_0", trecho.saida_data], ["saida_1", trecho.saida_hora], ["tempo_viagem", trecho.tempo_viagem]]) {
        const controle = /** @type {HTMLInputElement | null} */ (linha?.querySelector(`[name$="-${sufixo}"]`) ?? null);
        if (controle && novo && controle.value !== novo) {
          controle.value = novo;
          controle.dispatchEvent(new Event("input", { bubbles: true }));
        }
      }
      document.body.dispatchEvent(new CustomEvent("equipe-alterada"));
    }
    const vivo = doc.querySelector(`[data-campo="${nome}"]`);
    const cursor = doc.getSelection()?.anchorNode;
    const digitando = vivo === doc.activeElement || (cursor && this.campoDe(cursor) === vivo);
    if (vivo && typeof resultado.valor === "string" && !digitando
        && !vivo.hasAttribute("data-multilinha") && vivo.textContent !== resultado.valor) {
      vivo.textContent = resultado.valor;
    }
    const versaoForm = /** @type {HTMLInputElement | null} */ (document.querySelector("#form-oficio [name='versao']"));
    if (versaoForm && r.versao_oficio) versaoForm.value = String(r.versao_oficio);
    this.dispatchEvent(new CustomEvent("pc-editor:campo", { bubbles: true, detail: { chave, valor: resultado.valor } }));
  }

  /**
   * @param {string} caminho @param {object | null} corpo
   * @returns {Promise<any | null>}
   */
  async pedir(caminho, corpo) {
    const token = document.querySelector("meta[name='csrf-token']")?.getAttribute("content") || "";
    try {
      const r = await fetch(`${this.base}${caminho}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json", "X-CSRFToken": token, "X-Requested-With": "fetch" },
        body: JSON.stringify(corpo || {}),
      });
      const dados = await r.json().catch(() => ({}));
      if (r.status === 409) {
        this.aplicarEstado(dados);
        this.mostrarAviso("conflito", "perigo", dados.erro || "Outra pessoa salvou antes de você.", [["recarregar", "Recarregar a folha"]]);
        return null;
      }
      if (!r.ok) {
        avisar("erro", dados.erro || `Não foi possível concluir (${r.status}).`);
        return null;
      }
      return dados;
    } catch {
      avisar("erro", "Sem conexão: tente de novo em instantes.");
      return null;
    }
  }

  async carregarEstado() {
    try {
      const r = await fetch(`${this.base}estado/`, { headers: { Accept: "application/json" } });
      if (r.ok) this.aplicarEstado(await r.json());
    } catch {
      this.mostrarSalvo("Sem conexão", "editor__salvo--erro");
    }
    this.paginas();
  }

  /** @param {Estado} estado */
  aplicarEstado(estado) {
    if (!estado || !estado.versoes) return;
    this.estado = estado;
    const e = estado.edicao;
    if (!e || e.do_modelo) this.mostrarSalvo("Como o modelo", "");
    else this.mostrarSalvo(`Salvo ${e.quando} · v${e.numero}`, "editor__salvo--ok");
    this.removerAviso("conflito");
    // Dados que mudaram depois da edição: sem alerta sobre a folha (aparecia a cada página,
    // a cada gravação); fica dito, discreto, no botão "Voltar ao modelo" da barra.
    this.removerAviso("desatualizado");
    this.montarPendencias(estado.pendencias);
    this.montarPresenca(estado.presenca);
    const modelo = /** @type {HTMLButtonElement | null} */ (this.querySelector("[data-acao='modelo']"));
    if (modelo) {
      modelo.disabled = !e || e.do_modelo;
      const rotulo = estado.desatualizadas.length
        ? "Voltar ao modelo (os dados mudaram depois da edição: o texto editado não acompanha)"
        : "Voltar ao modelo";
      modelo.title = rotulo;
      modelo.setAttribute("aria-label", rotulo);
    }
    const hist = /** @type {HTMLButtonElement | null} */ (this.querySelector("[data-acao='historico']"));
    if (hist) {
      hist.disabled = !estado.versoes.length;
      const n = estado.versoes.length;
      hist.title = n ? `Histórico do texto (${n} ${n === 1 ? "versão" : "versões"})` : "Histórico do texto (nenhuma versão ainda)";
      hist.setAttribute("aria-label", hist.title);
    }
    if (this.historico && this.historico.open) this.montarHistorico();
  }

  /** Pendências na própria barra: um botão por dado que falta, que leva ao trecho.
   * @param {{chave: string, mensagem: string}[]} pendencias */
  montarPendencias(pendencias) {
    this.removerAviso("pendencias");  // versão antiga, em alerta sobre a folha
    const el = /** @type {HTMLElement | null} */ (this.querySelector("[data-pendencias]"));
    if (!el) return;
    el.hidden = !pendencias.length;
    el.innerHTML = pendencias.map((p) =>
      `<button type="button" class="botao botao--sm botao--sutil editor__pendencia"
         data-acao="ir-campo" data-campo="${escapar(p.chave)}"
         title="Ir ao trecho no documento">${escapar(p.mensagem)}</button>`).join("");
  }

  /** @param {{nome: string}[]} presenca */
  montarPresenca(presenca) {
    const el = /** @type {HTMLElement | null} */ (this.querySelector("[data-presenca]"));
    if (!el) return;
    el.hidden = !presenca.length;
    el.textContent = presenca.length ? `Também editando: ${presenca.map((p) => p.nome).join(", ")}` : "";
  }

  async presenca() {
    if (this.vitrine) return;
    try {
      const r = await this.pedir("presenca/", {});
      if (r && r.presenca) this.montarPresenca(r.presenca);
    } catch { /* silêncio: presença é cortesia */ }
  }

  /** @param {string} chave */
  irParaCampo(chave) {
    const doc = this.doc;
    if (!doc) return;
    this.modo("texto");
    const span = /** @type {HTMLElement | null} */ (doc.querySelector(`[data-campo="${CSS.escape(chave)}"]`));
    if (!span) {
      // O campo não está no documento (ex.: justificativa fora desta folha): leva ao cartão.
      const campo = this.estado ? this.estado.campos.find((c) => c.chave === chave) : null;
      if (campo) window.location.hash = `#${campo.secao}`;
      return;
    }
    span.scrollIntoView({ block: "center", behavior: "smooth" });
    this.entrarNoCampo(span);
  }

  /**
   * Põe o cursor no fim do campo, pronto para digitar. O foco vai para quem edita (a região
   * de texto, ou o próprio campo fora dela). Num campo vazio, o navegador não deixa o cursor
   * dentro de um elemento sem texto: entra um caractere invisível (U+200B), que sai assim
   * que se digita e nunca é gravado.
   * @param {HTMLElement} campo
   */
  entrarNoCampo(campo) {
    const doc = this.doc;
    if (!doc) return;
    const hospedeiro = /** @type {HTMLElement | null} */ (campo.closest("[contenteditable]"));
    hospedeiro?.focus({ preventScroll: true });
    if (!(campo.textContent || "").length) {
      this.marcaVazio = doc.createTextNode(INVISIVEL);
      campo.append(this.marcaVazio);
    }
    const sel = doc.getSelection();
    if (!sel) return;
    const r = doc.createRange();
    r.selectNodeContents(campo);
    r.collapse(false);
    sel.removeAllRanges();
    sel.addRange(r);
  }

  /** O caractere invisível do campo vazio sai quando o campo recebe texto ou o cursor sai. */
  limparVazio() {
    const marca = this.marcaVazio;
    const doc = this.doc;
    if (!marca || !doc) return;
    if (!marca.isConnected) { this.marcaVazio = null; return; }
    const campo = marca.parentElement;
    const cursor = doc.getSelection()?.anchorNode;
    const dentro = Boolean(cursor && campo && this.campoDe(cursor) === campo);
    if (dentro && marca.data === INVISIVEL) return;
    if (marca.data === INVISIVEL) {
      marca.remove();
    } else if (marca.data.includes(INVISIVEL)) {
      marca.data = marca.data.split(INVISIVEL).join("");
      if (dentro) {
        const r = doc.createRange();
        r.setStart(marca, marca.length);
        r.collapse(true);
        doc.getSelection()?.removeAllRanges();
        doc.getSelection()?.addRange(r);
      }
    }
    this.marcaVazio = null;
  }

  // ---------------------------------------------------------------- versões
  montarHistorico() {
    const d = this.historico;
    if (!d || !this.estado) return;
    const lista = /** @type {HTMLElement | null} */ (d.querySelector("[data-versoes]"));
    if (!lista) return;
    const vigente = this.estado.edicao ? this.estado.edicao.numero : 0;
    lista.replaceChildren();
    if (!this.estado.versoes.length) {
      const p = document.createElement("p");
      p.className = "texto-secundario";
      p.textContent = "O texto nunca foi editado: o documento sai como o modelo gera.";
      lista.append(p);
      return;
    }
    for (const v of this.estado.versoes) {
      const li = document.createElement("li");
      li.className = `editor__versao${v.numero === vigente ? " editor__versao--vigente" : ""}`;
      const blocos = v.do_modelo ? "Como o modelo" : v.blocos_alterados.map((b) => b.rotulo).join(", ") || "Texto";
      const origem = v.restaurada_de ? ` · restaurada da v${v.restaurada_de}` : "";
      li.innerHTML = `<span class="editor__versao-numero">v${v.numero}</span>`
        + `<div class="editor__versao-texto"><strong>${escapar(v.acao_rotulo)}</strong>${v.numero === vigente ? " <span class=\"selo selo--info selo--sem-ponto\">em vigor</span>" : ""}`
        + `<small>${escapar(v.quando)} · ${escapar(v.criado_por || "sistema")}${escapar(origem)}</small><small>${escapar(blocos)}</small></div>`
        + `<div class="grupo-botoes"><button type="button" class="botao botao--sm" data-versao="${v.numero}" data-ver>Ver</button>`
        + (v.numero !== vigente ? `<button type="button" class="botao botao--sm botao--primario" data-versao="${v.numero}">Restaurar</button>` : "")
        + "</div>";
      lista.append(li);
    }
  }

  /** @param {number | null} numero */
  verVersao(numero) {
    if (!this.quadro) return;
    this.vendoVersao = numero;
    if (this.historico && this.historico.open) this.historico.close();
    const url = new URL(this.dataset.folha || this.quadro.src, window.location.href);
    if (numero === null) url.searchParams.delete("versao");
    else url.searchParams.set("versao", String(numero));
    this.quadro.src = url.toString();
    this.modo("texto");
    if (numero === null) {
      this.removerAviso("versao");
    } else {
      this.mostrarAviso("versao", "info", `Vendo a versão ${numero} do texto, só para leitura.`, [["atual", "Voltar à versão em vigor"]]);
    }
  }

  /** @param {number} numero */
  async restaurar(numero) {
    if (!(await confirmar({ titulo: `Restaurar a versão ${numero}?`, mensagem: "O texto atual continua no histórico; a versão restaurada passa a valer.", confirmar: "Restaurar" }))) return;
    const r = await this.pedir(`restaurar/${numero}/`, {});
    if (!r) return;
    this.aplicarEstado(r);
    this.verVersao(null);
    this.avisarGravado();
    avisar("sucesso", `Versão ${numero} restaurada.`);
  }

  async voltarAoModelo() {
    if (!(await confirmar({ titulo: "Voltar ao modelo?", mensagem: "O texto editado deixa de valer e o documento volta a sair como o modelo gera. As versões continuam no histórico.", confirmar: "Voltar ao modelo", perigo: true }))) return;
    const r = await this.pedir("modelo/", {});
    if (!r) return;
    this.sujo = false;
    this.aplicarEstado(r);
    this.verVersao(null);
    this.avisarGravado();
    avisar("sucesso", "O documento voltou ao modelo.");
  }

  async voltarBlocoAoOriginal() {
    const bloco = this.blocoAtual;
    const doc = this.doc;
    if (!bloco || !doc || this.vitrine) return;
    const chave = bloco.getAttribute("data-bloco") || "";
    try {
      const r = await fetch(`${this.base}original/?bloco=${encodeURIComponent(chave)}`, { headers: { Accept: "application/json" } });
      if (!r.ok) throw new Error(String(r.status));
      const dados = await r.json();
      const modelo = doc.createElement("div");
      modelo.innerHTML = dados.html;
      const novo = modelo.firstElementChild;
      if (novo) {
        bloco.replaceWith(novo);
        this.blocoAtual = null;
        this.marcarSujo();
      }
    } catch {
      avisar("erro", "Não foi possível recuperar o original deste bloco.");
    }
  }

  marcarBlocosAlterados() {
    const doc = this.doc;
    if (!doc || !this.estado) return;
    const chaves = new Set((this.estado.edicao ? this.estado.edicao.blocos_alterados : []).map((b) => b.chave));
    doc.querySelectorAll("[data-bloco]").forEach((b) => b.classList.toggle("bloco--alterado", chaves.has(b.getAttribute("data-bloco") || "")));
  }

  /**
   * Termo (vários documentos, um por servidor): depois de salvar o texto de um, pergunta se
   * a alteração vai para os outros. "Sim" vale para o resto da edição (as próximas
   * gravações já levam); "Não" não pergunta de novo. Vai só o texto comum — o servidor
   * deixa de fora o que tem dado de cada um (termos.aplicar_texto_em_todos).
   */
  async oferecerAplicarEmTodos() {
    const url = this.dataset.aplicarEmTodos;
    if (!url || this.aplicarEmTodos === "nao") return;
    if (this.aplicarEmTodos !== "sim") {
      const sim = await confirmar({
        titulo: "Aplicar em todos os termos?",
        mensagem: "Levar esta alteração do texto para os termos dos outros servidores, o genérico e o da viatura? Vai só o texto comum: o que é de cada servidor (nome, CPF, lotação) fica como está.",
        confirmar: "Sim, aplicar em todos", cancelar: "Não",
      });
      this.aplicarEmTodos = sim ? "sim" : "nao";
      if (!sim) return;
    }
    const token = document.querySelector("meta[name='csrf-token']")?.getAttribute("content") || "";
    try {
      const r = await fetch(url, { method: "POST", headers: { Accept: "application/json", "X-CSRFToken": token, "X-Requested-With": "fetch" } });
      const dados = await r.json().catch(() => ({}));
      if (!r.ok) {
        avisar("erro", dados.erro || "Não foi possível aplicar nos outros termos.");
        return;
      }
      const n = Number(dados.atualizados || 0);
      const ficaram = /** @type {string[]} */ (dados.ficaram || []);
      avisar(n ? "sucesso" : "info", (n ? `Aplicado em ${n} ${n === 1 ? "termo" : "termos"}.` : "Nada a levar para os outros termos.")
        + (ficaram.length ? ` Ficou só neste (é de cada servidor): ${ficaram.join(", ")}.` : ""));
      if (n) document.dispatchEvent(new CustomEvent("pc-editor:texto-aplicado", { detail: { origem: this } }));
    } catch {
      avisar("erro", "Sem conexão: tente de novo em instantes.");
    }
  }

  recarregar() {
    this.sujo = false;
    this.verVersao(null);
    this.carregarEstado();
  }

  /**
   * "Atualizar": grava o texto em edição e os campos da folha (mesmo sem mudança — a
   * gravação é que refaz os textos automáticos e as diárias no servidor) e redesenha o
   * documento, as miniaturas e o PDF com os dados de agora.
   * @param {HTMLElement} botao
   */
  async atualizarDocumento(botao) {
    if (botao instanceof HTMLButtonElement) botao.disabled = true;
    try {
      if (this.sujo && typeof this.salvar === "function") await this.salvar();
      const { Autosave } = await import("./autosave.js");
      for (const a of Autosave.todos) a.ultima = "";
      await Promise.all(Autosave.todos.map((a) => a.descarregar()));
      // A gravação avisa (pcpr:dados-salvos) e a folha, as miniaturas e o PDF se refazem;
      // sem formulário que grave (só leitura), o aviso sai daqui.
      if (!Autosave.todos.length) document.dispatchEvent(new CustomEvent("pcpr:dados-salvos"));
      this.carregarEstado();
    } finally {
      if (botao instanceof HTMLButtonElement) botao.disabled = false;
    }
  }

  // ---------------------------------------------------------------- páginas
  async paginas() {
    if (this.vitrine) return;
    try {
      const r = await fetch(`${this.base}paginas/`, { headers: { Accept: "application/json" } });
      if (!r.ok) return;
      this.paginacao = /** @type {{total: number, blocos: Record<string, number>}} */ (await r.json());
      this.aplicarPaginas();
    } catch { /* a contagem é informativa */ }
  }

  aplicarPaginas() {
    const el = /** @type {HTMLElement | null} */ (this.querySelector("[data-paginas]"));
    const p = this.paginacao;
    if (!p) return;
    if (el) {
      el.hidden = false;
      el.textContent = p.total === 1 ? "1 página" : `${p.total} páginas`;
    }
    const doc = this.doc;
    if (!doc) return;
    doc.querySelectorAll("[data-pagina]").forEach((b) => b.removeAttribute("data-pagina"));
    /** @type {Set<number>} */
    const vistas = new Set([1]);
    for (const [chave, pagina] of Object.entries(p.blocos)) {
      if (vistas.has(pagina)) continue;
      const bloco = doc.querySelector(`[data-bloco="${CSS.escape(chave)}"]`);
      if (bloco) { bloco.setAttribute("data-pagina", String(pagina)); vistas.add(pagina); }
    }
  }

  // ---------------------------------------------------------------- avisos e estado visível
  /** @param {string} texto @param {string} classe */
  mostrarSalvo(texto, classe) {
    const el = this.salvo;
    if (!el) return;
    el.className = `editor__salvo selo selo--sem-ponto ${classe}`.trim();
    el.textContent = texto;
  }

  /**
   * @param {string} id @param {string} nivel @param {string} mensagem
   * @param {[string, string][]} acoes @param {string} [extra]
   */
  mostrarAviso(id, nivel, mensagem, acoes, extra = "") {
    const caixa = this.avisos;
    if (!caixa) return;
    this.removerAviso(id);
    const alerta = document.createElement("div");
    alerta.className = `alerta alerta--${nivel}`;
    alerta.setAttribute("role", nivel === "perigo" ? "alert" : "status");
    alerta.dataset.aviso = id;
    const botoes = acoes.map(([acao, rotulo]) => `<button type="button" class="botao botao--sm" data-acao="${acao}">${escapar(rotulo)}</button>`).join("");
    alerta.innerHTML = `<div class="alerta__corpo"><p>${escapar(mensagem)}</p>${extra}${botoes ? `<div class="grupo-botoes mt-2">${botoes}</div>` : ""}</div>`;
    alerta.addEventListener("click", (e) => {
      const b = /** @type {HTMLElement | null} */ (/** @type {HTMLElement} */ (e.target).closest("[data-acao]"));
      if (b) this.acao(b.dataset.acao || "", b);
    });
    caixa.append(alerta);
  }

  /** @param {string} id */
  removerAviso(id) {
    if (!this.avisos) return;
    this.avisos.querySelectorAll(`[data-aviso="${id}"]`).forEach((a) => a.remove());
  }
}

customElements.define("pc-editor-documento", PcEditorDocumento);
