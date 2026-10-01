// @ts-check
/**
 * Máscaras leves por atributo: `data-mascara="protocolo|cpf|placa"`.
 * O servidor valida e normaliza de novo — a máscara é só conforto de digitação.
 */
const MASCARAS = /** @type {Record<string, (d: string) => string>} */ ({
  // eProtocolo: 9 dígitos → 26.655.434-6
  protocolo: (d) => {
    const v = d.replace(/\D/g, "").slice(0, 9);
    return v
      .replace(/^(\d{2})(\d)/, "$1.$2")
      .replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
      .replace(/^(\d{2})\.(\d{3})\.(\d{3})(\d)/, "$1.$2.$3-$4");
  },
  cpf: (d) => {
    const v = d.replace(/\D/g, "").slice(0, 11);
    return v
      .replace(/^(\d{3})(\d)/, "$1.$2")
      .replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3")
      .replace(/^(\d{3})\.(\d{3})\.(\d{3})(\d)/, "$1.$2.$3-$4");
  },
});

document.addEventListener("input", (e) => {
  const campo = /** @type {HTMLInputElement} */ (e.target);
  const tipo = campo.dataset?.mascara;
  if (!tipo || !MASCARAS[tipo]) return;
  const fim = campo.selectionEnd === campo.value.length;
  campo.value = MASCARAS[tipo](campo.value);
  if (fim) campo.setSelectionRange(campo.value.length, campo.value.length);
});
