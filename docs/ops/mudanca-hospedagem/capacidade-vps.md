# Capacidade e consumo reais da VPS — medição de 17/10/2026

Base para decidir onde e como o n8n entra. Fonte: `sysstat` da própria VPS (amostras a cada 10 min,
09–17/10/2026), `systemctl show MemoryCurrent` por serviço e `docker stats`, coletados por SSH somente
leitura. O nome do plano (KVM 2) foi conferido contra o hardware real. Este documento é público: versões
exatas, mapa de serviços e portas e o estado de firewall, swap e cópia externa ficam no inventário privado
do pacote de backup.

## Hardware

| Recurso | Medido |
|---|---|
| CPU | 2 vCPU (AMD EPYC 9354P) |
| Memória | 7,8 GiB |
| Disco | 96 GB NVMe (`rotational=0`), 52 GB livres após o backup |
| Sistema | Ubuntu LTS com Docker e Compose (versões no inventário privado) |

## Consumo

| | 09–13/10 (só os dois sistemas reais) | 14–17/10 (com o PREVIEW do sistema novo) |
|---|---|---|
| CPU média ocupada | 1,5–2,4 % | 12–14 % |
| CPU pico (média de 10 min) | 18 % | 45 % |
| Memória usada média / pico | 25–28 % / 30 % | 35–38 % / 46 % |
| Memória disponível mínima | 5,2 GB | 3,8 GB |
| Load (5 min) pico | 0,19 | 2,27 |
| Disco | ~21 IOPS, ~0,9 MB/s leitura e ~0,8 MB/s escrita médios | |
| Rede | ~8 kB/s | |

Memória em 17/10 (aprox., agrupada): sistemas reais com seus serviços de apoio (aplicações web, filas,
verificação e conversão de arquivos) ~2,4 GB · PREVIEW 0,60 GB · Docker/containerd 0,42 GB · agentes da
hospedagem 0,17 GB · banco e cache ~0,1 GB. O maior consumidor individual é um serviço de apoio dos
sistemas reais (~1,0 GB), não as aplicações.

## Leitura para o planejamento

- **CPU sobra** (picos de 45 % com o PREVIEW em servidor de desenvolvimento). O gargalo provável é
  **memória**: 3,8 GB livres no pior momento medido. Conversões de documentos (LibreOffice,
  WeasyPrint: 300–500 MB por PDF em pico) somadas a um n8n podem acionar o OOM killer se não houver
  swap e limites por contêiner.
- **n8n em modo normal** (um processo, PostgreSQL como banco) cabe. No protótipo local (SQLite, runner
  interno, Docker Desktop) ficou em 391 MiB em repouso, com pico de 884 MiB numa rajada de 20 eventos
  simultâneos ([desempenho-e-custos.md](../../automacao/desempenho-e-custos.md) §9.2). Orçamento
  proposto: ~1,5 GB (1 GB no principal + 0,5 GB no runner externo), a medir na VPS. Queue mode (Redis +
  workers) não reduz latência neste volume e custa memória.
- **IA local não cabe com folga**: um modelo de 7–8 B quantizado ocupa 4–6 GB e roda a poucos tokens por
  segundo em 2 vCPU sem GPU — competiria com os sistemas reais.
- Requisitos antes de instalar qualquer serviço novo: swap de 2–4 GB; firewall do host restrito ao
  mínimo necessário e acesso administrativo restrito; limites de memória por contêiner (`mem_limit`);
  portas internas só em localhost, nunca em 0.0.0.0.

A comparação das alternativas de hospedagem e a recomendação estão em
[`hospedagem-n8n.md`](hospedagem-n8n.md).
