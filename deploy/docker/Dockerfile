# syntax=docker/dockerfile:1
# Camada de implantação sobre a imagem do PRODUTO (construída do commit aprovado com o
# Dockerfile da raiz, sem alterações). Acrescenta só entrada, health check e rótulos de
# versão — o código do produto não muda. Construída por deploy/vps/implantar.sh.
ARG BASE
FROM ${BASE}
ARG PRODUTO_COMMIT=desconhecido
ARG INFRA_COMMIT=desconhecido
COPY --chmod=0755 entrypoint.sh /usr/local/bin/pcpr-entrypoint
COPY --chmod=0755 saude.py pos_migracao.py verificar.py /opt/pcpr/
ENV PCPR_PRODUTO_COMMIT=${PRODUTO_COMMIT} \
    PCPR_INFRA_COMMIT=${INFRA_COMMIT}
LABEL org.opencontainers.image.title="pcpr-gestao" \
      org.opencontainers.image.source="https://github.com/tiago2904santos/pcpr-gestao-next" \
      org.opencontainers.image.revision="${PRODUTO_COMMIT}" \
      br.gov.pr.pc.gestao.infra-revision="${INFRA_COMMIT}"
USER pcpr
ENTRYPOINT ["pcpr-entrypoint"]
CMD ["web"]
