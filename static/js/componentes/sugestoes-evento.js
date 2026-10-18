// @ts-check
/**
 * Solicitação de evento: sugestões para preencher sem digitar tudo (nada grava sozinho).
 *
 * - `[data-sugestao-tipo]`: ao escolher o tipo, busca o que ele sugere (o modelo do tipo ou o
 *   que se repete nas últimas solicitações dele) e mostra num aviso com "Aplicar a sugestão".
 *   Aplicar marca os serviços e as equipes sugeridos (a quantidade só onde está em branco) e
 *   preenche quem pede, o cargo e o órgão só se estiverem vazios — nada é desmarcado.
 * - `pc-combobox[data-solicitante-anterior]`: escolher um solicitante de antes traz o cargo,
 *   o contato e o órgão do último pedido dele.
 *
 * Cada campo mudado recebe `input`/`change`, então o autosave e o aviso de alterações reagem
 * como à digitação.
 */

/** @param {HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement} campo @param {string} valor */
function escrever(campo, valor) {
  campo.value = valor;
  campo.dispatchEvent(new Event("input", { bubbles: true }));
  campo.dispatchEvent(new Event("change", { bubbles: true }));
}

/** @param {string} nome */
const campoPorNome = (nome) =>
  /** @type {HTMLInputElement | null} */ (document.querySelector(`[name="${nome}"]`));

/** @param {string[]} partes */
function juntar(partes) {
  if (partes.length < 2) return partes.join("");
  return `${partes.slice(0, -1).join(", ")} e ${partes[partes.length - 1]}`;
}

/**
 * @typedef {{id: number, nome: string, quantidade?: number | null}} Item
 * @typedef {{fonte: string, servicos: Item[], equipes: Item[], solicitante: string,
 *   cargo: string, orgao: {id: number, nome: string} | null, vazia: boolean}} Sugestao
 */

/** @param {HTMLElement} aviso */
function ligarTipo(aviso) {
  if (aviso.dataset.pronto) return;
  aviso.dataset.pronto = "1";
  const select = /** @type {HTMLSelectElement | null} */ (
    document.getElementById(aviso.dataset.alvoTipo || ""));
  const titulo = aviso.querySelector("[data-sugestao-titulo]");
  const texto = aviso.querySelector("[data-sugestao-texto]");
  const aplicar = /** @type {HTMLButtonElement | null} */ (aviso.querySelector("[data-sugestao-aplicar]"));
  const dispensar = aviso.querySelector("[data-sugestao-dispensar]");
  if (!select || !titulo || !texto || !aplicar) return;
  /** @type {Sugestao | null} */
  let atual = null;
  let pedido = 0;

  select.addEventListener("change", async () => {
    const tipo = select.value;
    const nome = select.selectedOptions[0]?.textContent?.trim() || "";
    atual = null;
    aviso.hidden = true;
    if (!tipo) return;
    const este = ++pedido;
    try {
      const resposta = await fetch(`${aviso.dataset.sugestaoTipo}?tipo=${encodeURIComponent(tipo)}`,
        { headers: { Accept: "application/json" }, credentials: "same-origin" });
      if (!resposta.ok || este !== pedido) return;
      /** @type {Sugestao} */
      const s = await resposta.json();
      if (s.vazia || este !== pedido) return;
      atual = s;
      const partes = [];
      if (s.servicos.length) partes.push(`serviços: ${juntar(s.servicos.map((x) => x.nome))}`);
      if (s.equipes.length) {
        partes.push(`equipes: ${juntar(s.equipes.map((x) => (x.quantidade ? `${x.nome} (${x.quantidade})` : x.nome)))}`);
      }
      const quem = [s.solicitante, s.cargo].filter(Boolean).join(", ");
      if (quem) partes.push(`quem pede: ${quem}`);
      if (s.orgao) partes.push(`órgão: ${s.orgao.nome}`);
      titulo.textContent = `Sugestão para ${nome}`;
      texto.textContent = `Vem de ${s.fonte} — ${partes.join("; ")}.`;
      aplicar.hidden = false;
      if (dispensar) dispensar.textContent = "Agora não";
      aviso.hidden = false;
    } catch {
      /* sem a sugestão, a pessoa preenche à mão */
    }
  });

  aplicar.addEventListener("click", () => {
    const s = atual;
    if (!s) return;
    for (const x of s.servicos) {
      const caixa = campoPorNome(`servico_${x.id}`);
      if (caixa && !caixa.checked) {
        caixa.checked = true;
        caixa.dispatchEvent(new Event("change", { bubbles: true }));
      }
    }
    for (const x of s.equipes) {
      const caixa = campoPorNome(`equipe_${x.id}`);
      if (caixa && !caixa.checked) {
        caixa.checked = true;
        caixa.dispatchEvent(new Event("change", { bubbles: true }));
      }
      const qtd = campoPorNome(`quantidade_equipe_${x.id}`);
      if (qtd && x.quantidade && !qtd.value.trim()) escrever(qtd, String(x.quantidade));
    }
    const vazio = (/** @type {string} */ nome, /** @type {string} */ valor) => {
      const campo = campoPorNome(nome);
      if (campo && valor && !campo.value.trim()) escrever(campo, valor);
    };
    vazio("solicitante_nome", s.solicitante);
    vazio("solicitante_cargo_unidade", s.cargo);
    if (s.orgao) vazio("orgao_responsavel", String(s.orgao.id));
    titulo.textContent = "Sugestão aplicada";
    texto.textContent = "Confira os serviços, as equipes e quem pede antes de enviar.";
    aplicar.hidden = true;
    if (dispensar) dispensar.textContent = "Fechar";
    atual = null;
  });

  dispensar?.addEventListener("click", () => {
    aviso.hidden = true;
    atual = null;
  });
}

/** @param {HTMLElement} caixa */
function ligarSolicitante(caixa) {
  if (caixa.dataset.solicitantePronto) return;
  caixa.dataset.solicitantePronto = "1";
  caixa.addEventListener("pc-selecionado", (evento) => {
    const opcao = /** @type {CustomEvent} */ (evento).detail || {};
    const preencher = (/** @type {string} */ nome, /** @type {unknown} */ valor) => {
      const campo = campoPorNome(nome);
      if (campo && valor !== null && valor !== undefined && valor !== "") escrever(campo, String(valor));
    };
    preencher("solicitante_cargo_unidade", opcao.cargo);
    preencher("contato", opcao.contato);
    preencher("orgao_responsavel", opcao.orgao);
  });
}

function ligarTudo() {
  document.querySelectorAll("[data-sugestao-tipo]").forEach((a) => ligarTipo(/** @type {HTMLElement} */ (a)));
  document.querySelectorAll("pc-combobox[data-solicitante-anterior]")
    .forEach((c) => ligarSolicitante(/** @type {HTMLElement} */ (c)));
}

ligarTudo();
document.body.addEventListener("htmx:afterSwap", ligarTudo);

export {};
