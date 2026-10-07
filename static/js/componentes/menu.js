// @ts-check
/**
 * <pc-menu> — menu suspenso acessível (padrão "menu button" da WAI-ARIA).
 *
 *   <pc-menu class="menu">
 *     <button type="button" data-menu-botao aria-haspopup="menu">Ações</button>
 *     <div class="menu__painel" role="menu" hidden>
 *       <a role="menuitem" class="menu__item" href="…">Abrir</a>
 *     </div>
 *   </pc-menu>
 *
 * Teclado: Enter/Espaço/↓ abrem; ↑/↓/Home/End navegam; Esc fecha e devolve o foco.
 * Grupo recolhido (`[data-menu-grupo]` + `.menu__grupo[hidden]`): Enter/Espaço/→ abrem no
 * lugar e levam ao 1º item dele; ← (dentro) recolhe e volta ao título do grupo.
 * Item inativo (`aria-disabled="true"`) recebe o foco — o leitor de tela ouve o porquê na
 * descrição — mas não age (padrão da WAI-ARIA para menus).
 *
 * Menu de linha de lista (dentro de `.registro__acoes`, ou com `data-menu-flutuante`): o
 * painel sobe para a camada de topo (popover) sobre um véu que fecha ao toque fora — nada
 * por trás é acionado sem querer, e nenhum alvo fica meio coberto. ≥768px ele abre junto
 * do botão, para o lado em que cabe, nunca fora da janela (o que sobrar rola dentro dele);
 * no celular vira uma folha inferior com o nome do registro no alto.
 */
const CELULAR = "(max-width: 767.98px)";
const FOLGA = 8;
/** Mouse que só passa pelo ⋮ não pede nada; parado sobre ele, sim (intenção). */
const INTENCAO = 120;

/** Anúncio para leitor de tela (uma região viva para todos os menus). @param {string} texto */
function anunciar(texto) {
  let regiao = document.getElementById("menu-anuncio");
  if (!regiao) {
    regiao = document.createElement("div");
    regiao.id = "menu-anuncio";
    regiao.className = "sr-only";
    regiao.setAttribute("aria-live", "polite");
    document.body.append(regiao);
  }
  regiao.textContent = "";
  window.setTimeout(() => { if (regiao) regiao.textContent = texto; }, 50);
}
/** Topo da barra flutuante (ou o pé da janela): abaixo disso nada aparece inteiro. */
export function limiteInferior() {
  // A barra flutua acima da borda da janela: o limite é o topo dela, não a altura.
  const barra = document.querySelector(".barra-acoes")?.getBoundingClientRect();
  return (barra && barra.height ? barra.top : window.innerHeight) - 8;
}

/** Rola o mínimo para `el` aparecer inteiro acima da barra flutuante. @param {HTMLElement} el */
export function abrirEspaco(el) {
  const limite = limiteInferior();
  // offsetHeight ignora a animação de entrada (scale), que encolhe o retângulo medido.
  const sobra = el.getBoundingClientRect().top + el.offsetHeight + 4 - limite;
  if (sobra > 0) window.scrollBy({ top: sobra, behavior: "instant" });
}

/**
 * Ícone do sprite para os componentes que se montam no navegador. O caminho sai de um
 * ícone que a página já desenhou, então vale o mesmo arquivo (com o hash do static) —
 * sem repetir a URL em JavaScript.
 *
 * @param {string} nome nome do ícone no sprite, sem o prefixo "i-"
 * @param {string} [classe]
 */
export function icone(nome, classe = "icone") {
  const uso = document.querySelector("svg.icone use")?.getAttribute("href") || "";
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", classe);
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `${uso.split("#")[0]}#i-${nome}`);
  svg.append(use);
  return svg;
}

export class PcMenu extends HTMLElement {
  connectedCallback() {
    this.botao = /** @type {HTMLButtonElement} */ (this.querySelector("[data-menu-botao]"));
    this.painel = /** @type {HTMLElement} */ (this.querySelector("[role='menu']"));
    if (!this.botao || !this.painel) return;
    if (!this.painel.id) this.painel.id = `menu-${Math.random().toString(36).slice(2, 9)}`;
    this.botao.setAttribute("aria-controls", this.painel.id);
    this.botao.setAttribute("aria-expanded", "false");

    this.botao.addEventListener("click", () => (this.aberto() ? this.fechar() : this.abrir()));
    this.botao.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        this.abrir();
      }
    });
    this.painel.addEventListener("keydown", (e) => this.teclado(e));
    // Inativo não age (é um <span>, mas o clique não pode fechar nem navegar por engano).
    // Menu flutuante: escolher um item fecha o menu e devolve o foco ao botão — antes de a janela que o
    // item abre (resumo, motivo, baixar, confirmação) guardar quem tinha o foco: ao fechar
    // a janela, o foco volta ao ⋮, não a um item escondido.
    this.painel.addEventListener("click", (e) => {
      const item = /** @type {HTMLElement} */ (e.target).closest?.("[role='menuitem']");
      if (!item) return;
      if (item.getAttribute("aria-disabled") === "true") {
        e.preventDefault();
        return;
      }
      if (item.hasAttribute("data-menu-grupo")) {
        e.preventDefault();
        this.alternarGrupo(/** @type {HTMLElement} */ (item));
        return;
      }
      if (this.flutuante()) this.fechar();
    });
    // O menu tem nome: o do botão que o abre ("Ações do Ofício 12/2026").
    if (!this.painel.hasAttribute("aria-label") && !this.painel.hasAttribute("aria-labelledby")) {
      if (!this.botao.id) this.botao.id = `${this.painel.id}-botao`;
      this.painel.setAttribute("aria-labelledby", this.botao.id);
    }
    this.fora = (/** @type {Event} */ e) => {
      if (!this.contains(/** @type {Node} */ (e.target))) this.fechar(false);
    };
    // Itens que vêm do servidor (`data-menu-carregar`): pedidos quando a pessoa chega ao
    // botão — mouse por cima ou foco —, para já estarem lá no clique.
    // Foco e toque pedem na hora; o mouse, só se parar sobre o botão (passar por cima de
    // uma coluna de ⋮ não dispara 20 pedidos).
    if (this.dataset.menuCarregar) {
      /** @type {number | undefined} */
      let espera;
      this.botao.addEventListener("pointerenter", (e) => {
        if (e.pointerType !== "mouse") { this.carregar(); return; }
        espera = window.setTimeout(() => this.carregar(), INTENCAO);
      });
      this.botao.addEventListener("pointerleave", () => window.clearTimeout(espera));
      this.botao.addEventListener("focus", () => { this.carregar(); });
    }
  }

  /** Abre ou recolhe um grupo no lugar (ex.: "Criar a partir deste ofício").
   * @param {HTMLElement} titulo @param {boolean} [abrir] */
  alternarGrupo(titulo, abrir) {
    const grupo = /** @type {HTMLElement | null} */ (
      document.getElementById(titulo.getAttribute("aria-controls") || ""));
    if (!grupo) return;
    const mostrar = abrir ?? grupo.hidden;
    grupo.hidden = !mostrar;
    titulo.setAttribute("aria-expanded", String(mostrar));
    if (this.flutuante()) this.posicionar();
    if (mostrar) /** @type {HTMLElement | null} */ (grupo.querySelector("[role='menuitem']"))?.focus();
    else titulo.focus();
  }

  /** @returns {Promise<void>} */
  carregar() {
    const url = this.dataset.menuCarregar;
    if (!url || !this.painel) return Promise.resolve();
    if (this.promessa) return this.promessa;
    const painel = this.painel;
    const aviso = /** @type {HTMLElement | null} */ (painel.querySelector("[data-menu-carregando]"));
    this.promessa = fetch(url, { credentials: "same-origin", headers: { "HX-Request": "true" } })
      .then(async (r) => {
        // Sessão expirada: o servidor responde 401 com o caminho de volta (identidade/
        // middleware.py); nunca a tela de login dentro do menu.
        if (r.status === 401 || r.redirected) {
          const corpo = r.status === 401 ? await r.json().catch(() => ({})) : {};
          this.sessaoTerminou(corpo.entrar || `/conta/entrar/?next=${encodeURIComponent(
            window.location.pathname + window.location.search)}`);
          throw new Error("sessão");
        }
        if (!r.ok) throw new Error(String(r.status));
        return r.text();
      })
      .then((html) => {
        aviso?.remove();
        painel.insertAdjacentHTML("beforeend", html);
        /** @type {any} */ (window).htmx?.process(painel); // "Ver resumo" usa hx-get
        delete this.dataset.menuCarregar;
      })
      .catch((erro) => {
        this.promessa = undefined; // a próxima abertura tenta de novo
        if (erro?.message === "sessão") return;
        const texto = "Não deu para carregar as ações. Feche e abra de novo.";
        if (aviso) aviso.textContent = texto;
        if (this.aberto()) anunciar(texto);
      });
    return this.promessa;
  }

  /** O menu diz que a sessão terminou e oferece entrar de novo, voltando para esta página.
   * @param {string} entrar */
  sessaoTerminou(entrar) {
    const painel = this.painel;
    if (!painel) return;
    painel.querySelectorAll("[data-menu-carregando], [data-menu-sessao]").forEach((e) => e.remove());
    const link = document.createElement("a");
    link.className = "menu__item menu__item--descrito";
    link.setAttribute("role", "menuitem");
    link.dataset.menuSessao = "";
    link.href = entrar;
    const texto = document.createElement("span");
    texto.className = "menu__item-texto";
    const titulo = document.createElement("span");
    titulo.textContent = "Entrar de novo";
    const descricao = document.createElement("span");
    descricao.className = "menu__item-descricao";
    descricao.textContent = "Sua sessão terminou — entre de novo e volte para esta página.";
    texto.append(titulo, descricao);
    link.append(icone("log-out"), texto);
    painel.append(link);
    if (this.aberto()) {
      link.focus({ preventScroll: true });
      anunciar("Sua sessão terminou — entre de novo.");
      if (this.flutuante()) this.posicionar();
    }
  }

  disconnectedCallback() {
    if (this.fora) document.removeEventListener("pointerdown", this.fora);
    this.recolher(); // a busca ao vivo trocou a lista com o menu aberto: o véu sai junto
  }

  /** Painel na camada de topo (menus das linhas das listas). */
  flutuante() {
    return Boolean(this.painel && typeof (/** @type {any} */ (this.painel).showPopover) === "function"
      && (this.hasAttribute("data-menu-flutuante") || this.closest(".registro__acoes")));
  }

  aberto() {
    return this.botao?.getAttribute("aria-expanded") === "true";
  }

  itens() {
    return /** @type {HTMLElement[]} */ (
      Array.from(this.painel?.querySelectorAll("[role='menuitem']") ?? [])
    ).filter((i) => !i.closest(".menu__grupo[hidden]"));
  }

  abrir() {
    if (!this.botao || !this.painel) return;
    this.painel.hidden = false;
    this.botao.setAttribute("aria-expanded", "true");
    if (this.flutuante()) {
      this.soltar();
    } else {
      if (this.fora) document.addEventListener("pointerdown", this.fora);
      this.encaixar();
    }
    this.focarPrimeiro();
    if (this.dataset.menuCarregar) {
      // Ainda chegando: o aviso "Carregando…" fica com o foco; os itens assumem ao chegar.
      this.carregar().then(() => {
        if (!this.aberto()) return;
        if (this.flutuante()) this.posicionar();
        else this.encaixar();
        this.focarPrimeiro();
      });
    }
  }

  focarPrimeiro() {
    const itens = this.itens();
    const primeiro = itens.find((i) => i.getAttribute("aria-disabled") !== "true") || itens[0];
    primeiro?.focus({ preventScroll: true });
  }

  /** Véu (camada de topo, sob o painel) + painel solto junto do botão. */
  soltar() {
    const painel = /** @type {any} */ (this.painel);
    // Na folha do celular o menu se solta da linha: o alto dela diz de que registro se trata.
    // Quem não escreveu o título ganha o nome do botão ("Ações do Termo #7").
    if (!painel.querySelector(".menu__folha-titulo") && this.botao) {
      const titulo = document.createElement("p");
      titulo.className = "menu__folha-titulo";
      titulo.setAttribute("aria-hidden", "true");
      titulo.textContent = this.botao.getAttribute("aria-label") || this.botao.textContent?.trim() || "";
      painel.prepend(titulo);
    }
    const veu = document.createElement("div");
    veu.className = "menu__veu";
    veu.setAttribute("popover", "manual");
    veu.setAttribute("aria-hidden", "true");
    // Numa janela modal o véu mora dentro dela; fora dela, seria inerte (não fecharia).
    (this.closest("dialog[open]") || document.body).append(veu);
    veu.addEventListener("pointerdown", (e) => {
      e.preventDefault(); // o toque fora só fecha: nada por trás é acionado
      // No toque, o "click" de compatibilidade chega depois: o véu fica (transparente)
      // para recebê-lo — senão ele cairia na página e levaria o foco para o <body>.
      if (e.pointerType !== "mouse") this.veuAteOClique = true;
      this.fechar();
    });
    veu.addEventListener("wheel", (e) => { if (this.folha) e.preventDefault(); }, { passive: false });
    this.veu = veu;
    /** @type {any} */ (veu).showPopover();
    painel.setAttribute("popover", "manual");
    painel.showPopover();
    this.posicionar();
    this.acompanhar = () => this.posicionar();
    window.addEventListener("scroll", this.acompanhar, true);
    window.addEventListener("resize", this.acompanhar);
  }

  /** ≥768px: abaixo do botão, alinhado à direita dele; sem espaço, acima; o que não couber
   * rola dentro do painel. Celular: folha inferior (CSS). */
  posicionar() {
    const painel = this.painel;
    if (!painel || !this.botao || !painel.matches(":popover-open")) return;
    this.folha = window.matchMedia(CELULAR).matches;
    painel.classList.toggle("menu__painel--folha", this.folha);
    painel.style.position = "fixed";
    for (const lado of ["left", "right", "top", "bottom", "maxHeight"]) painel.style.setProperty(
      lado === "maxHeight" ? "max-height" : lado, "");
    if (this.folha) return;
    const b = this.botao.getBoundingClientRect();
    if (b.bottom < 0 || b.top > window.innerHeight) {
      this.fechar(false); // o botão saiu da tela rolando: o menu não fica solto
      return;
    }
    const largura = painel.offsetWidth;
    const alto = window.innerHeight;
    const abaixo = alto - FOLGA - (b.bottom + 4);
    const acima = b.top - 4 - FOLGA;
    const altura = painel.scrollHeight;
    painel.classList.remove("menu__painel--acima", "menu__painel--lado");
    const alinhar = (/** @type {number} */ x) => {
      painel.style.left = `${Math.max(FOLGA, Math.min(x, window.innerWidth - FOLGA - largura))}px`;
    };
    if (altura <= abaixo) { // 1º: logo abaixo do botão, alinhado à direita dele
      alinhar(b.right - largura);
      painel.style.top = `${b.bottom + 4}px`;
    } else if (altura <= acima) { // 2º: logo acima
      alinhar(b.right - largura);
      painel.style.bottom = `${alto - b.top + 4}px`;
      painel.classList.add("menu__painel--acima");
    } else { // 3º: ao lado do botão, deslizado até caber na janela (o que sobrar rola)
      const lado = b.left - 4 - largura >= FOLGA ? b.left - 4 - largura : b.right + 4;
      alinhar(lado);
      const topo = Math.max(FOLGA, Math.min(b.top, alto - FOLGA - altura));
      painel.style.top = `${topo}px`;
      painel.style.maxHeight = `${alto - FOLGA - topo}px`;
      painel.classList.add("menu__painel--lado");
    }
  }

  recolher() {
    const painel = /** @type {any} */ (this.painel);
    if (this.acompanhar) {
      window.removeEventListener("scroll", this.acompanhar, true);
      window.removeEventListener("resize", this.acompanhar);
      this.acompanhar = undefined;
    }
    if (this.veu) {
      const veu = this.veu;
      this.veu = undefined;
      const tirar = () => {
        try { /** @type {any} */ (veu).hidePopover(); } catch { /* já fechado */ }
        veu.remove();
      };
      if (this.veuAteOClique) {
        this.veuAteOClique = false;
        veu.classList.add("menu__veu--saindo");
        veu.addEventListener("click", (e) => { e.preventDefault(); tirar(); }, { once: true });
        window.setTimeout(tirar, 700);
      } else {
        tirar();
      }
    }
    if (!painel?.hasAttribute("popover")) return;
    if (painel.matches(":popover-open")) {
      try { painel.hidePopover(); } catch { /* já fechado */ }
    }
    painel.removeAttribute("popover");
    painel.classList.remove("menu__painel--folha", "menu__painel--acima");
    for (const prop of ["position", "left", "right", "top", "bottom", "max-height"]) {
      painel.style.removeProperty(prop);
    }
  }

  /** O painel nunca sai da tela nem fica sob a barra flutuante: abre para o lado em que
   * cabe e, perto do pé da página, rola o necessário ou abre para cima. */
  encaixar() {
    if (!this.painel) return;
    this.painel.classList.remove("menu__painel--forcar-esquerda", "menu__painel--forcar-direita",
      "menu__painel--acima");
    const r = this.painel.getBoundingClientRect();
    if (r.left < 0) this.painel.classList.add("menu__painel--forcar-esquerda");
    else if (r.right > window.innerWidth) this.painel.classList.add("menu__painel--forcar-direita");
    abrirEspaco(this.painel);
    if (this.painel.getBoundingClientRect().bottom > limiteInferior()) {
      this.painel.classList.add("menu__painel--acima");
    }
  }

  fechar(devolverFoco = true) {
    if (!this.botao || !this.painel || !this.aberto()) return;
    this.recolher();
    this.painel.hidden = true;
    this.botao.setAttribute("aria-expanded", "false");
    if (this.fora) document.removeEventListener("pointerdown", this.fora);
    if (devolverFoco) this.botao.focus({ preventScroll: true });
  }

  /** @param {KeyboardEvent} e */
  teclado(e) {
    const itens = this.itens();
    const i = itens.indexOf(/** @type {HTMLElement} */ (document.activeElement));
    const ir = (/** @type {number} */ n) => itens[(n + itens.length) % itens.length]?.focus();
    switch (e.key) {
      case "ArrowDown": e.preventDefault(); ir(i + 1); break;
      case "ArrowUp": e.preventDefault(); ir(i - 1); break;
      case "Home": e.preventDefault(); ir(0); break;
      case "End": e.preventDefault(); ir(itens.length - 1); break;
      case "Escape": e.preventDefault(); this.fechar(); break;
      case "ArrowRight":
        if (itens[i]?.hasAttribute("data-menu-grupo")) {
          e.preventDefault();
          this.alternarGrupo(itens[i], true);
        }
        break;
      case "ArrowLeft": {
        const grupo = itens[i]?.closest(".menu__grupo");
        const titulo = grupo && this.painel?.querySelector(`[aria-controls="${grupo.id}"]`);
        if (titulo) {
          e.preventDefault();
          this.alternarGrupo(/** @type {HTMLElement} */ (titulo), false);
        }
        break;
      }
      case "Enter":
      case " ":
        if (itens[i]?.getAttribute("aria-disabled") === "true") e.preventDefault();
        break;
      case "Tab": this.fechar(false); break;
      default: break;
    }
  }
}

customElements.define("pc-menu", PcMenu);
