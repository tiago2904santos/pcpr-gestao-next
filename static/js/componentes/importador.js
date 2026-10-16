// @ts-check
/** Envio concorrente por arquivo; a leitura continua na fila persistente do servidor. */
/** @type {Record<string, string>} */
const estados = { fila: "Na fila", lendo: "Lendo e identificando", revisao: "Precisa de revisão",
  concluido: "Concluído", erro: "Não foi possível ler", anexado: "Anexado", repetido: "Já anexado", ignorado: "Ignorado" };
/** @type {number[]} */
let ids = [];
let enviando = false;
let timer = 0;
let leituraEmCurso = false;
/** @param {string} tag @param {string} texto @param {string} [classe] */
function el(tag, texto, classe = "") {
  const item = document.createElement(tag); item.textContent = texto; item.className = classe; return item;
}
/** @param {any[]} arquivos */
function mostrar(arquivos) {
  if (!arquivos.length) return;
  document.querySelectorAll("[data-importar-resultados]").forEach((caixa) => {
    // Preserva foco/seleção quando o estado não mudou.
    const assinatura = JSON.stringify(arquivos);
    if (caixa.getAttribute("data-estado") === assinatura) return;
    caixa.setAttribute("data-estado", assinatura);
    caixa.replaceChildren(...arquivos.map((a) => {
      const card = el("article", "", "cartao mb-4");
      const corpo = el("div", "", "cartao__corpo pilha");
      corpo.append(el("h3", a.nome, "resumo__titulo"),
        el("p", estados[a.estado] || a.estado, "texto-secundario"));
      if (a.erro) corpo.append(el("p", a.erro, "alerta alerta--aviso"));
      for (const p of a.partes || []) {
        const linha = el("div", "", "pilha");
        linha.append(el("strong", `${p.tipo} · ${estados[p.estado] || p.estado}`),
          el("p", p.destino || p.motivo, "texto-secundario texto-sm"));
        if (p.estado === "revisao") {
          const link = /** @type {HTMLAnchorElement} */ (el("a", "Revisar documento", "botao botao--sm"));
          link.href = p.url; linha.append(link);
        }
        corpo.append(linha);
      }
      const original = /** @type {HTMLAnchorElement} */ (el("a", "Baixar original", "botao botao--sm botao--sutil"));
      original.href = `/viagens/importacoes/${a.id}/original/`; corpo.append(original);
      card.append(corpo); return card;
    }));
  });
}
async function acompanhar() {
  clearTimeout(timer);
  if (leituraEmCurso) { timer = window.setTimeout(acompanhar, 1000); return; }
  const url = document.querySelector("[data-estado-url]")?.getAttribute("data-estado-url");
  if (!url) return;
  leituraEmCurso = true;
  try {
    const resposta = await fetch(url + (ids.length ? `?ids=${ids.join(",")}` : ""),
      {headers: {"X-Requested-With": "fetch"}});
    if (!resposta.ok) throw new Error();
    /** @type {{arquivos: any[]}} */
    const dados = await resposta.json();
    mostrar(dados.arquivos);
    if (enviando || dados.arquivos.some((a) => ["fila", "lendo"].includes(a.estado))) {
      timer = window.setTimeout(acompanhar, 1800);
    }
  } catch {
    document.querySelectorAll("[data-importar-aviso]").forEach((p) => {
      p.textContent = "Não foi possível atualizar o andamento. A leitura continua; reabra o histórico.";
    });
  } finally {
    leituraEmCurso = false;
  }
}
export function abrir() {
  const janela = /** @type {HTMLDialogElement | null} */ (document.getElementById("dialogo-importar"));
  if (janela && !janela.open) janela.showModal();
  acompanhar();
}
/** @param {HTMLFormElement} form @param {File[]} arquivos */
async function enviar(form, arquivos) {
  const aviso = form.querySelector("[data-importar-aviso]");
  if (enviando || !aviso) return;
  if (!arquivos.length || arquivos.length > 50) { aviso.textContent = "Escolha de 1 a 50 arquivos."; return; }
  enviando = true;
  const botao = /** @type {HTMLButtonElement | null} */ (form.querySelector("button[type=submit]"));
  if (botao) { botao.disabled = true; botao.setAttribute("aria-busy", "true"); }
  let indice = 0, terminados = 0;
  /** @type {string[]} */
  const falhas = [];
  form.setAttribute("aria-busy", "true");
  const processar = async () => {
    while (indice < arquivos.length) {
      const arquivo = arquivos[indice++];
      try {
        if (arquivo.size > 25 * 1024 * 1024) throw new Error("Arquivo maior que 25 MB.");
        const dados = new FormData(form); dados.delete("arquivos"); dados.append("arquivos", arquivo);
        const resposta = await fetch(form.action, { method: "POST", body: dados,
          headers: { "X-Requested-With": "fetch" } });
        if (!resposta.ok) throw new Error("Envio interrompido. Selecione novamente para tentar; repetições serão reconhecidas.");
        const resultado = (await resposta.json()).arquivos[0];
        if (resultado.erro) throw new Error(resultado.erro);
        if (!ids.includes(resultado.id)) ids.push(resultado.id);
        ids = ids.slice(-50);
        acompanhar();
      } catch (erro) {
        falhas.push(`${arquivo.name}: ${erro instanceof Error ? erro.message : "Falha no envio."}`);
      }
      terminados += 1;
      aviso.textContent = `${terminados} de ${arquivos.length} arquivos enviados ou conferidos. ${falhas.join(" ")}`;
    }
  };
  await Promise.all(Array.from({ length: Math.min(3, arquivos.length) }, processar));
  enviando = false; form.removeAttribute("aria-busy");
  if (botao) { botao.disabled = false; botao.removeAttribute("aria-busy"); }
  acompanhar();
}
document.addEventListener("submit", (e) => {
  const form = e.target;
  if (!(form instanceof HTMLFormElement) || !form.matches("[data-importar-form]")) return;
  e.preventDefault();
  const entrada = /** @type {HTMLInputElement} */ (form.querySelector("input[type=file]"));
  enviar(form, Array.from(entrada.files || []));
});
document.querySelectorAll("[data-importar-soltar]").forEach((zona) => {
  zona.querySelector("input")?.addEventListener("change", (evento) => {
    const entrada = /** @type {HTMLInputElement} */ (evento.target);
    const aviso = zona.closest("form")?.querySelector("[data-importar-aviso]");
    if (aviso) aviso.textContent = `${entrada.files?.length || 0} arquivo(s) selecionado(s).`;
  });
  zona.addEventListener("dragover", (e) => { e.preventDefault(); zona.classList.add("importador-soltar--ativo"); });
  zona.addEventListener("dragleave", () => zona.classList.remove("importador-soltar--ativo"));
  zona.addEventListener("drop", (e) => {
    e.preventDefault(); zona.classList.remove("importador-soltar--ativo");
    const form = zona.closest("form");
    const arquivos = /** @type {DragEvent} */ (e).dataTransfer?.files;
    if (form && arquivos) enviar(form, Array.from(arquivos));
  });
});
const revisao = document.querySelector("[data-importar-revisao]");
if (revisao) {
  const tipo = /** @type {HTMLSelectElement} */ (revisao.querySelector("[data-importar-tipo]"));
  const busca = /** @type {HTMLInputElement} */ (revisao.querySelector("[data-importar-busca]"));
  const destino = /** @type {HTMLSelectElement} */ (revisao.querySelector("[data-importar-destino]"));
  const opcoes = Array.from(destino.options);
  const filtrar = () => {
    const valor = destino.value;
    const texto = busca.value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    destino.replaceChildren(...opcoes.filter((o) => !o.value || ((!tipo.value || o.dataset.tipo === tipo.value)
      && o.text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().includes(texto))));
    destino.value = Array.from(destino.options).some((o) => o.value === valor) ? valor : "";
  };
  tipo.addEventListener("change", filtrar); busca.addEventListener("input", filtrar); filtrar();
}
const pagina = document.querySelector("[data-importar-acompanhar]");
if (pagina) {
  ids = (pagina.getAttribute("data-importar-ids") || "").split(",").filter(Boolean).map(Number);
  acompanhar();
}
