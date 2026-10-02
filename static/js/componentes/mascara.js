// @ts-check
/**
 * Máscaras leves por atributo: `data-mascara="protocolo|cpf|data|hora"`.
 * O servidor valida e normaliza de novo — a máscara é só conforto de digitação.
 */
const MASCARAS = /** @type {Record<string, (d: string) => string>} */ ({
  // eProtocolo: 9 dígitos → 12.345.678-9
  protocolo: (d) => {
    const v = d.replace(/\D/g, "").slice(0, 9);
    return v
      .replace(/^(\d{2})(\d)/, "$1.$2")
      .replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
      .replace(/^(\d{2})\.(\d{3})\.(\d{3})(\d)/, "$1.$2.$3-$4");
  },
  // Data e hora: a barra/os dois-pontos entram quando chega o dígito seguinte (apagar
  // continua natural) e o que a pessoa digitou ("8/10/2026") é respeitado.
  data: (v) =>
    v.replace(/[^\d/]/g, "").slice(0, 10)
      .replace(/^(\d{2})(\d)/, "$1/$2")
      .replace(/^(\d{1,2}\/)(\d{2})(\d)/, "$1$2/$3"),
  hora: (v) => v.replace(/[^\d:]/g, "").slice(0, 5).replace(/^(\d{2})(\d)/, "$1:$2"),
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
