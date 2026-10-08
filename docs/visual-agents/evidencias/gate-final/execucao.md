# Ambiente e reprodução do gate

- Data local: 07/10/2026, America/Sao_Paulo.
- Windows, PowerShell/Git Bash; Python 3.13.15, Django 6.1.1, pytest 9.1.1.
- Fonte congelada em worktree viagens-tempo-legado, HEAD inicial e5e48cc mais
  candidatos locais. manifesto-fontes.json registra exatamente as 43 fontes
  alteradas/novas e o CSS original como guard antes da execução final.
- Runtime Python/dependências: .venv do checkout original; node_modules reutiliza
  suas dependências locais por junction. Nenhum lockfile/dependência alterado.
- Banco TEST exclusivamente LAB: 127.0.0.1:55432, usuário pcpr_lab,
  base pcpr_lab_verificar, bancos test_pcpr_lab_verificar_gw0..gw3. Sem senha,
  dados fictícios. Não acessar bancos DEV remotos, STAGING ou PRODUCTION.
- Settings: config.settings.test / APP_ENV=test, MEDIA_ROOT var/test-media do
  worktree. GTK3 local para WeasyPrint; fontes/dependências já instaladas.
- PYTHONUTF8=1 e PYTHONIOENCODING=utf-8 alinham pai/filhos à saída UTF-8.
  O primeiro integral usou somente PYTHONIOENCODING e teve duas falhas de captura
  CP1252 dos subprocessos Windows, reproduzidas no baseline08.
- UV_PROJECT_ENVIRONMENT aponta para .venv original; UV_NO_SYNC=true e
  UV_FROZEN=true. PYTEST_XDIST_AUTO_NUM_WORKERS=4 limita -n auto à capacidade
  local. PYTEST_ADDOPTS=--create-db recria somente os bancos TEST próprios,
  incluindo carga inicial das migrações. Não semear/resetar DEMO ou DEV.
- Script real: `C:/Program Files/Git/bin/bash.exe scripts/verificar.sh`, sem
  editar checks. SHA256 do script idêntico nos dois checkouts:
  7303c6f5157e2bb8790ba4305daee9714a5de5b8dac6b25baa3c8a6bd2580d02.
- Verificador executa Ruff, lint-imports (16 contratos), mypy gestao/config,
  Bandit, makemigrations --check, tsc jsconfig.json e
  pytest -m "not e2e and not visual and not a11y and not perf" -n auto -q.
  Navegador/acessibilidade/performance foram executados separadamente, com
  resultados próprios no pacote. Não afirmar CI global verde por esse script.
- Plugin local só imprime longrepr de testes reprovados no processo mestre;
  não altera seleção, assertions, fixtures, política CSP ou códigos de saída.
- Primeira integral: 2184 verdes/3 falhas; log completo preservado. Três focused
  posteriores verdes. Segunda tentativa com --reuse-db interrompida: bancos
  esvaziados por testes transacionais não recarregavam catálogos de migração.
  Log parcial preservado, sem resultado de suíte completa.
- Integral final com --create-db:2187verdes/zero falhas/7avisos,2421,27s(40min21s),
  saída0 e tudo verde. Código incorporado em feb35e2 + bea84e3 na branch de entrega
  viagens/reconstrucao. Igualdade das43fontes congeladas e das897fontes Git
  comprovada em fontes-integradas.json; main/origin_main locais preservadas.
- Durante a integral não há outra suíte DB/navegador nem medição de performance
  concorrente. Aplicação permanece congelada; apenas documentação é finalizada.
