# Infraestrutura atual (Hostinger) — estudo

Estudo de 03/10/2026, feito **sem acesso à VPS** (nenhum comando foi executado nela). Fontes:
`docs/DEPLOY_AUTOMATICO.md` da referência (VPS Hostinger `srv1775737.hstgr.cloud`, deploy
por GitHub Actions + SSH), `DEPLOY_VPS.md` do Gerenciador de Viagens (recomendava KVM 2), a
página pública da Hostinger para n8n e os documentos de deploy deste repositório.

## O que está confirmado

- A referência roda numa VPS Hostinger com deploy automático (backup do banco → `git pull` →
  dependências → migrações → estáticos → check → reinício).
- Planos KVM da Hostinger (preços de vitrine, out/2026): KVM 1 (1 vCPU, 4 GB, 50 GB NVMe),
  **KVM 2 (2 vCPU, 8 GB, 100 GB)**, KVM 4 (4 vCPU, 16 GB, 200 GB), KVM 8 (8 vCPU, 32 GB,
  400 GB). Há modelo de n8n auto-hospedado com Docker em um clique e gerenciador Docker no
  painel.
- O sistema novo já tem imagem de produção (`Dockerfile`: gunicorn + WhiteNoise) e o PREVIEW
  em `compose.preview.yml` com a mesma imagem.

## A medir (precisa do dono da conta — hPanel ou SSH autorizado)

Plano contratado, uso real de CPU/RAM/disco, se o IP é fixo (necessário para o eProtocolo),
política de snapshots/backups, domínio e certificado, outros serviços na mesma VPS.

## Necessidade estimada do sistema novo

| Serviço | RAM típica | Observação |
|---|---|---|
| web (gunicorn, 3–4 workers) | 0,6–1 GB | |
| worker da outbox | 0,3–0,5 GB, picos de WeasyPrint de 300–500 MB por PDF | |
| PostgreSQL 16 | 1–2 GB | `shared_buffers` ~25% |
| n8n (se adotado) | 0,5–1 GB; +Redis e worker no modo fila | isolar em contêiner/rede próprios |
| Redis (só se n8n em modo fila) | 0,1 GB | |

**Recomendação inicial:** KVM 2 (8 GB) acomoda PCPR Gestão + PostgreSQL + n8n com folga
para ~10–30 usuários simultâneos; subir para KVM 4 se o n8n rodar fluxos com IA pesados ou
muitos PDFs em lote. Decidir **depois** de medir a VPS atual.

## Desenho proposto

```
VPS (Docker Compose)
├── proxy (Caddy/Nginx, TLS)                 ← único exposto
├── pcpr-web + pcpr-outbox (mesma imagem)
├── postgres (volume + backup diário externo + teste de restauração)
├── n8n (rede interna; acesso só por VPN/IP ou SSO; credenciais próprias)
└── redis (apenas se n8n em modo fila)
```

Regras: banco nunca exposto; n8n fala com o PCPR **só pela API de ferramentas** (nunca no
banco); backups fora da VPS; produção separada do PREVIEW.

## Hostinger: agente de administração ≠ agente do produto

A Hostinger oferece um assistente de IA para **administrar a VPS** (painel, comandos, DNS) e
recursos de MCP ligados à hospedagem. Isso é ferramenta de **operação de infraestrutura** e
age sobre o servidor; o **agente operacional do PCPR** age sobre dados do negócio (ofícios,
protocolos) pela camada de ferramentas com política e auditoria (ver `docs/ai/`). Os dois não
se misturam: o agente do produto nunca recebe credencial da VPS, e o da hospedagem nunca
recebe acesso aos dados do sistema.
