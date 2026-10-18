// @ts-check
/**
 * Link de km (página pública `/p/<token>/`, fluxo 10-4): o que a pessoa salva num trecho
 * fica primeiro neste aparelho (localStorage, uma chave por link e por trecho) e vai para o
 * sistema quando há rede — na hora, quando a conexão volta, ao abrir a página e a cada 30 s
 * enquanto houver pendência. Cada trecho diz se está "salvo neste aparelho (ainda não
 * enviado)" ou "salvo no sistema às HH:MM".
 *
 * Cada lançamento leva um id gerado aqui e a `base` (os km que a pessoa via ao editar). O
 * servidor só grava se o valor dele ainda é a base; senão devolve conflito, e o trecho
 * mostra os dois valores para a pessoa escolher. O mesmo id de novo não grava duas vezes.
 * Um lote em voo por vez; editar um trecho com envio pendente gera outro lançamento (id
 * novo) com a mesma base. Sem JavaScript, cada trecho é um formulário comum.
 * O service worker (`sw/`, escopo só deste link) guarda a página para abrir sem rede.
 */

/** @typedef {"km_inicial" | "km_final"} Campo */
/** @typedef {{km_inicial?: number | null, km_final?: number | null}} Valores */
/**
 * @typedef {{id: string, linha: number, chave: string, campos: Valores, base: Valores,
 *   digitado_em: string, estado: "pendente" | "conflito" | "recusado", mensagem?: string,
 *   servidor?: Valores}} Lancamento
 */
/**
 * @typedef {{id: string, situacao: string, mensagem: string, linha: number | null,
 *   servidor: Valores, seu: Valores, salvo: string}} Resultado
 */

/** @type {Campo[]} */
const CAMPOS = ["km_inicial", "km_final"];
const KM_MAXIMO = 9_999_999;
const INTERVALO = 30_000;
const LOTE = 50;

const raiz = document.querySelector("[data-km-offline]");
if (raiz instanceof HTMLElement) iniciar(raiz);

/** @param {HTMLElement} raiz */
function iniciar(raiz) {
  const prefixo = `pcpr-km:v1:${raiz.dataset.link || ""}:`;
  const urlSalvar = raiz.dataset.salvar || "";
  const somenteLeitura = raiz.hasAttribute("data-somente-leitura");
  /** @type {Map<string, Lancamento>} chave de armazenamento -> lançamento (cópia em memória) */
  const memoria = new Map();
  /** @type {Set<string> | null} ids em voo */
  let emVoo = null;
  /** @type {Map<number, HTMLFormElement>} */
  const formularios = new Map();
  /** @type {Map<number, Valores>} o último valor confirmado pelo servidor */
  const confirmados = new Map();
  /** @type {Map<number, string>} "às 14:05" */
  const salvoEm = new Map();
  /** @type {number | null} o trecho que a pessoa acabou de salvar (o único anunciado) */
  let anunciar = null;
  const anuncio = raiz.querySelector("[data-km-anuncio]");

  for (const form of raiz.querySelectorAll("form[data-km-form]")) {
    if (!(form instanceof HTMLFormElement)) continue;
    const linha = Number(form.dataset.linha);
    formularios.set(linha, form);
    confirmados.set(linha, { km_inicial: numero(form.dataset.kmInicial || ""),
                             km_final: numero(form.dataset.kmFinal || "") });
    salvoEm.set(linha, form.dataset.salvo || "");
    form.addEventListener("submit", (evento) => {
      evento.preventDefault();
      const quem = /** @type {SubmitEvent} */ (evento).submitter;
      if (quem instanceof HTMLElement && quem.hasAttribute("data-km-usar-meu")) usarMeu(linha);
      else salvarLocal(form, linha);
    });
    const manter = form.querySelector("[data-km-manter]");
    manter?.setAttribute("role", "button");  // com JavaScript é uma ação, não navegação
    manter?.addEventListener("click", (evento) => { evento.preventDefault(); manterSistema(linha); });
    manter?.addEventListener("keydown", (evento) => {
      if (/** @type {KeyboardEvent} */ (evento).key === " ") {
        evento.preventDefault();
        manterSistema(linha);
      }
    });
  }

  // ---------------------------------------------------------------- armazenamento
  /** @param {number} linha */
  function chave(linha) { return `${prefixo}${linha}`; }

  /** @param {number} linha @returns {Lancamento | null} */
  function ler(linha) {
    const k = chave(linha);
    if (memoria.has(k)) return memoria.get(k) || null;
    try {
      const texto = window.localStorage.getItem(k);
      const item = texto ? /** @type {Lancamento} */ (JSON.parse(texto)) : null;
      if (item) memoria.set(k, item);
      return item;
    } catch {
      return null;
    }
  }

  /** @param {number} linha @param {Lancamento | null} item */
  function gravar(linha, item) {
    const k = chave(linha);
    if (item) memoria.set(k, item); else memoria.delete(k);
    try {
      if (item) window.localStorage.setItem(k, JSON.stringify(item));
      else window.localStorage.removeItem(k);
    } catch {
      // Sem armazenamento (navegação privada): fica só na memória desta aba.
    }
  }

  /** @returns {Lancamento[]} */
  function todos() {
    /** @type {Lancamento[]} */
    const lista = [];
    try {
      for (let i = 0; i < window.localStorage.length; i += 1) {
        const k = window.localStorage.key(i);
        if (k && k.startsWith(prefixo)) {
          const item = ler(Number(k.slice(prefixo.length)));
          if (item) lista.push(item);
        }
      }
    } catch { /* só a memória */ }
    for (const item of memoria.values()) if (!lista.includes(item)) lista.push(item);
    return lista;
  }

  // ---------------------------------------------------------------- valores
  /** @param {string} texto @returns {number | null} */
  function numero(texto) {
    const limpo = String(texto).replace(/[.\s]/g, "");
    return limpo === "" ? null : Number(limpo);
  }

  /** @param {HTMLFormElement} form @param {Campo} campo */
  function entrada(form, campo) {
    const el = form.elements.namedItem(campo);
    return el instanceof HTMLInputElement ? el : null;
  }

  /** @returns {string} */
  function novoId() {
    if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  }

  /** @param {number | null | undefined} valor */
  function km(valor) {
    return valor === null || valor === undefined ? "—" : valor.toLocaleString("pt-BR");
  }

  // ---------------------------------------------------------------- tela
  /** @param {number} linha */
  function pintar(linha) {
    const form = formularios.get(linha);
    if (!form) return;
    const item = ler(linha);
    const estado = form.querySelector("[data-km-estado]");
    const painel = form.querySelector("[data-km-conflito]");
    const textoConflito = form.querySelector("[data-km-conflito-texto]");
    // Cada situação tem o seu selo: no sistema (sucesso), só no aparelho/enviando/conflito
    // (aviso), recusado (perigo), vazio (neutro) — o texto diz o mesmo para leitor de tela.
    let mensagem;
    let tom;
    if (!item) {
      const salvo = salvoEm.get(linha);
      mensagem = salvo ? `Salvo no sistema ${salvo}.` : "Ainda sem km no sistema.";
      tom = salvo ? "sucesso" : "neutro";
    } else if (item.estado === "conflito") {
      mensagem = "Este trecho foi alterado no sistema depois que você digitou.";
      tom = "aviso";
    } else if (item.estado === "recusado") {
      mensagem = `Não foi salvo: ${item.mensagem || "confira os números."}`;
      tom = "perigo";
    } else if (emVoo?.has(item.id)) {
      mensagem = "Enviando…";
      tom = "aviso";
    } else {
      mensagem = "Salvo neste aparelho (ainda não enviado).";
      tom = "aviso";
    }
    // Só reescreve o que mudou, e só o trecho que a pessoa acabou de salvar vai para a região
    // viva da página (antes cada repintura relia todos os trechos no leitor de tela).
    const classe = `selo km-estado selo--${tom}`;
    if (estado && (estado.textContent !== mensagem || estado.className !== classe)) {
      estado.textContent = mensagem;
      estado.className = classe;
      if (linha === anunciar && mensagem !== "Enviando…" && anuncio) {
        const titulo = form.closest("section")?.querySelector("h2")?.textContent?.trim() || "";
        anuncio.textContent = `${titulo.replace(/^\d+\s*/, "")}: ${mensagem}`;
      }
    }
    if (painel instanceof HTMLElement) {
      painel.hidden = item?.estado !== "conflito";
      if (item?.estado === "conflito" && textoConflito) {
        const s = item.servidor || {};
        const meu = { ...confirmados.get(linha), ...item.campos };
        textoConflito.textContent = `No sistema: saída ${km(s.km_inicial)}, chegada `
          + `${km(s.km_final)}. O seu: saída ${km(meu.km_inicial)}, chegada ${km(meu.km_final)}.`;
      }
    }
    for (const campo of CAMPOS) {
      const el = entrada(form, campo);
      if (!el) continue;
      el.closest(".campo")?.classList.toggle("campo--erro", item?.estado === "recusado"
        && campo in (item.campos || {}));
    }
  }

  function pintarRede() {
    const aviso = raiz.querySelector("[data-km-rede]");
    const texto = raiz.querySelector("[data-km-rede-texto]");
    if (!(aviso instanceof HTMLElement) || !texto) return;
    const pendentes = todos().filter((i) => i.estado === "pendente").length;
    let novo = "";
    if (!navigator.onLine) {
      novo = "Sem internet. O que você salvar fica neste aparelho e é enviado quando a conexão "
        + "voltar.";
    } else if (pendentes) {
      novo = `${pendentes} trecho${pendentes > 1 ? "s" : ""} salvo${pendentes > 1 ? "s" : ""} `
        + "neste aparelho, aguardando envio.";
    }
    if (texto.textContent !== novo) texto.textContent = novo;  // sem reanunciar o mesmo aviso
    aviso.hidden = !novo;
  }

  function pintarTudo() {
    for (const linha of formularios.keys()) pintar(linha);
    pintarRede();
  }

  /** @param {number} linha @param {Valores} valores */
  function mostrarValores(linha, valores) {
    const form = formularios.get(linha);
    if (!form) return;
    for (const campo of CAMPOS) {
      const el = entrada(form, campo);
      if (el && campo in valores) {
        const v = valores[campo];
        el.value = v === null || v === undefined ? "" : String(v);
      }
    }
  }

  // ---------------------------------------------------------------- ações
  /** @param {HTMLFormElement} form @param {number} linha */
  function salvarLocal(form, linha) {
    if (somenteLeitura) return;
    anunciar = linha;
    /** @type {Valores} */
    const digitados = {};
    for (const campo of CAMPOS) {
      const el = entrada(form, campo);
      const texto = (el?.value || "").replace(/[.\s]/g, "");
      if (!/^\d{0,7}$/.test(texto) || (texto !== "" && Number(texto) > KM_MAXIMO)) {
        avisar(form, "Use só números no km (até 9.999.999), sem vírgula nem letras.");
        el?.focus();
        return;
      }
      digitados[campo] = texto === "" ? null : Number(texto);
    }
    const atual = ler(linha);
    const voando = atual && emVoo?.has(atual.id);
    /** @type {Valores} o que a pessoa via antes desta edição */
    const base = voando && atual ? { ...confirmados.get(linha), ...atual.campos }
      : atual && atual.estado === "pendente" ? atual.base : { ...confirmados.get(linha) };
    /** @type {Valores} */
    const campos = {};
    for (const campo of CAMPOS) {
      if ((digitados[campo] ?? null) !== (base[campo] ?? null)) campos[campo] = digitados[campo];
    }
    const inicial = digitados.km_inicial ?? null;
    const final = digitados.km_final ?? null;
    if (inicial !== null && final !== null && final < inicial) {
      avisar(form, "O km de chegada não pode ser menor que o de saída.");
      return;
    }
    if (!Object.keys(campos).length) {
      if (atual && !voando) gravar(linha, null);
      pintar(linha);
      return;
    }
    gravar(linha, { id: novoId(), linha, chave: form.dataset.chave || "", campos, base,
                    digitado_em: new Date().toISOString(), estado: "pendente" });
    pintar(linha);
    pintarRede();
    void sincronizar();
  }

  /** @param {HTMLFormElement} form @param {string} texto */
  function avisar(form, texto) {
    const estado = form.querySelector("[data-km-estado]");
    if (estado) {
      estado.textContent = texto;
      estado.className = "selo km-estado selo--perigo";
    }
    if (anuncio) anuncio.textContent = texto;
  }

  /** @param {number} linha */
  function usarMeu(linha) {
    const item = ler(linha);
    if (!item || item.estado !== "conflito") return;
    const base = { ...(item.servidor || {}) };
    gravar(linha, { ...item, id: novoId(), base, estado: "pendente", mensagem: "",
                    digitado_em: new Date().toISOString() });
    anunciar = linha;
    pintar(linha);
    focarTrecho(linha);  // o painel do conflito some: o foco não pode cair no <body>
    void sincronizar();
  }

  /** @param {number} linha */
  function manterSistema(linha) {
    const item = ler(linha);
    const servidor = item?.servidor || confirmados.get(linha) || {};
    confirmados.set(linha, { ...servidor });
    gravar(linha, null);
    mostrarValores(linha, { km_inicial: servidor.km_inicial ?? null,
                            km_final: servidor.km_final ?? null });
    anunciar = linha;
    pintar(linha);
    pintarRede();
    focarTrecho(linha);
  }

  /** @param {number} linha */
  function focarTrecho(linha) {
    const form = formularios.get(linha);
    const alvo = form?.querySelector("[data-km-salvar]") || (form && entrada(form, "km_inicial"));
    if (alvo instanceof HTMLElement) alvo.focus();
  }

  /** @param {Resultado[]} resultados */
  function aplicar(resultados) {
    for (const r of resultados) {
      if (r.linha === null) continue;
      const item = ler(r.linha);
      if (r.situacao === "gravado" || r.situacao === "conflito") {
        confirmados.set(r.linha, { ...r.servidor });
        if (r.salvo) salvoEm.set(r.linha, r.salvo);
      }
      if (!item || item.id !== r.id) continue; // editado de novo enquanto voava
      if (r.situacao === "gravado") {
        gravar(r.linha, null);
        mostrarValores(r.linha, r.servidor);
      } else if (r.situacao === "conflito") {
        gravar(r.linha, { ...item, estado: "conflito", servidor: { ...r.servidor } });
      } else {
        gravar(r.linha, { ...item, estado: "recusado", mensagem: r.mensagem });
      }
    }
  }

  /** @returns {string} */
  function tokenCsrf() {
    const meta = document.querySelector("meta[name='csrf-token']");
    return meta?.getAttribute("content") || "";
  }

  async function sincronizar() {
    if (emVoo || somenteLeitura || !urlSalvar) return;
    const lote = todos().filter((i) => i.estado === "pendente").slice(0, LOTE);
    if (!lote.length || !navigator.onLine) { pintarRede(); return; }
    emVoo = new Set(lote.map((i) => i.id));
    pintarTudo();
    try {
      const resposta = await fetch(urlSalvar, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", Accept: "application/json",
                   "X-CSRFToken": tokenCsrf(), "X-Requested-With": "fetch" },
        body: JSON.stringify({ lancamentos: lote.map(({ id, linha, chave: c, campos, base }) => (
          { id, linha, chave: c, campos, base })) }),
      });
      const corpo = await resposta.json().catch(() => null);
      if (resposta.ok && corpo && Array.isArray(corpo.resultados)) {
        aplicar(/** @type {Resultado[]} */ (corpo.resultados));
      } else if (corpo && typeof corpo.mensagem === "string") {
        // Travado, suspenso ou link indisponível: fica tudo guardado aqui.
        const texto = raiz.querySelector("[data-km-rede-texto]");
        const aviso = raiz.querySelector("[data-km-rede]");
        if (texto && aviso instanceof HTMLElement) { texto.textContent = corpo.mensagem; aviso.hidden = false; }
        emVoo = null;
        for (const linha of formularios.keys()) pintar(linha);
        return;
      }
    } catch {
      // Sem rede ou resposta perdida: os lançamentos ficam para a próxima tentativa (o mesmo
      // id de novo não grava duas vezes).
    }
    emVoo = null;
    pintarTudo();
  }

  // ---------------------------------------------------------------- começo
  for (const linha of formularios.keys()) {
    const item = ler(linha);
    if (item) mostrarValores(linha, { ...confirmados.get(linha), ...item.campos });
  }
  pintarTudo();
  window.addEventListener("online", () => { pintarRede(); void sincronizar(); });
  window.addEventListener("offline", pintarRede);
  window.setInterval(() => { void sincronizar(); }, INTERVALO);
  void sincronizar();

  const sw = raiz.dataset.sw;
  if (sw && "serviceWorker" in navigator) {
    navigator.serviceWorker.register(sw, { scope: raiz.dataset.escopo || undefined })
      .catch(() => { /* sem service worker: funciona enquanto a aba estiver aberta */ });
  }
}

export {};
