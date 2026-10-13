"""Compara a renderização documental entre ambientes (VPS × local) com os MESMOS dados.

    # 1. na VPS: amostra de documentos sintéticos prontos (tipo, dados, SHA-256 gravado)
    deploy/homologacao/comparar-renderizacao.sh <instância>   (exporta, renderiza e compara)
    # 2. em qualquer máquina com o código do mesmo commit:
    DJANGO_SETTINGS_MODULE=config.settings.test uv run python \
        deploy/homologacao/comparar_renderizacao.py renderizar amostra.json > local.json
    python3 deploy/homologacao/comparar_renderizacao.py comparar vps.json local.json

A geração é determinística (identificador fixo do PDF/A): bytes iguais ⇒ renderização
idêntica. Se os bytes diferirem, compara páginas, fontes embutidas e texto por página.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import sys
from pathlib import Path


def renderizar(caminho: str) -> None:
    sys.path.insert(0, os.environ.get("PCPR_APP_DIR", str(Path.cwd())))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
    import django

    django.setup()
    from pypdf import PdfReader

    from gestao.viagens.documentos.pdf import gerar_pdf

    saida = []
    with Path(caminho).open(encoding="utf-8") as arq:
        amostra = json.load(arq)
    for item in amostra:
        conteudo, sha = gerar_pdf(item["tipo"], item["dados"])
        leitor = PdfReader(io.BytesIO(conteudo))
        fontes = set()
        for pagina in leitor.pages:
            recursos = pagina.get("/Resources") or {}
            for fonte in (recursos.get("/Font") or {}).values():
                fontes.add(str(fonte.get_object().get("/BaseFont", "")).split("+")[-1])
        saida.append({
            "id": item["id"], "tipo": item["tipo"], "sha256_gravado": item["sha256"],
            "sha256": sha, "bytes": len(conteudo), "paginas": len(leitor.pages),
            "fontes": sorted(fontes),
            "texto": [hashlib.sha256((p.extract_text() or "").encode()).hexdigest()[:16]
                      for p in leitor.pages],
        })
    json.dump(saida, sys.stdout, ensure_ascii=False, indent=1)


def comparar(a: str, b: str) -> int:
    with Path(a).open(encoding="utf-8") as fa, Path(b).open(encoding="utf-8") as fb:
        lado_a = {d["id"]: d for d in json.load(fa)}
        lado_b = {d["id"]: d for d in json.load(fb)}
    divergencias = 0
    # Amostras diferentes (arquivo velho, truncado, outra amostra) não provam nada.
    for ident in sorted(lado_a.keys() ^ lado_b.keys()):
        lado = "A" if ident in lado_a else "B"
        sys.stdout.write(f"  doc {ident:>5} só no lado {lado} | DIVERGENTE (amostras diferentes)\n")
        divergencias += 1
    for ident, da in sorted(lado_a.items()):
        db = lado_b.get(ident)
        if db is None:
            continue
        if da["sha256"] == db["sha256"]:
            veredito = "idêntico (bytes)"
        elif all(da[c] == db[c] for c in ("paginas", "fontes", "texto")):
            veredito = "equivalente (páginas, fontes e texto iguais; bytes diferem)"
        else:
            veredito = "DIVERGENTE"
            divergencias += 1
        # O lado A (a VPS) tem de reproduzir o PDF gravado no banco; senão, é divergência
        # mesmo que A e B concordem entre si (ex.: comparar vps.json com ele mesmo).
        gravado = "sim" if da["sha256"] == da["sha256_gravado"] else "NÃO"
        if gravado == "NÃO" and veredito != "DIVERGENTE":
            divergencias += 1
        sys.stdout.write(f"  doc {ident:>5} {da['tipo']:<14} {da['paginas']} pág. "
                         f"| igual ao gravado no banco: {gravado} | {veredito}\n")
    return 1 if divergencias else 0


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "renderizar":
        renderizar(sys.argv[2])
    elif len(sys.argv) >= 4 and sys.argv[1] == "comparar":
        sys.exit(comparar(sys.argv[2], sys.argv[3]))
    else:
        sys.exit(__doc__)
