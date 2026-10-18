"""Contêiner n8n descartável do protótipo (docker CLI; só 127.0.0.1; nada sai para a internet
por iniciativa do n8n — telemetria, notificações, templates, banners e licença desligados)."""

from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

IMAGEM = "docker.n8n.io/n8nio/n8n:2.43.7"
CONTEINER = "pcpr-prototipo-n8n"
VOLUME = "pcpr-prototipo-n8n-dados"
PORTA = 5678
URL = f"http://127.0.0.1:{PORTA}"


def variaveis(chave_cripto: str) -> dict[str, str]:
    """Ambiente do n8n. Conferido contra o @n8n/config da própria imagem 2.43.7."""
    return {
        "N8N_ENCRYPTION_KEY": chave_cripto,
        "GENERIC_TIMEZONE": "America/Sao_Paulo",
        "TZ": "America/Sao_Paulo",
        # sem chamadas externas por iniciativa do n8n
        "N8N_DIAGNOSTICS_ENABLED": "false",
        "N8N_DIAGNOSTICS_CONFIG_FRONTEND": "",
        "N8N_DIAGNOSTICS_CONFIG_BACKEND": "",
        "N8N_VERSION_NOTIFICATIONS_ENABLED": "false",
        "N8N_VERSION_NOTIFICATIONS_WHATS_NEW_ENABLED": "false",
        "N8N_TEMPLATES_ENABLED": "false",
        "N8N_PERSONALIZATION_ENABLED": "false",
        "N8N_HIRING_BANNER_ENABLED": "false",
        "N8N_DYNAMIC_BANNERS_ENABLED": "false",
        "N8N_LICENSE_AUTO_RENEW_ENABLED": "false",
        "N8N_AI_ENABLED": "false",
        "N8N_COMMUNITY_PACKAGES_ENABLED": "false",
        "N8N_PUBLIC_API_DISABLED": "true",
        "N8N_PUBLIC_API_SWAGGERUI_DISABLED": "true",
        # poda de execuções
        "EXECUTIONS_DATA_PRUNE": "true",
        "EXECUTIONS_DATA_MAX_AGE": "168",
        "EXECUTIONS_DATA_PRUNE_MAX_COUNT": "5000",
        # "não salvar" só marca a execução como apagada; a remoção física (com a entrada:
        # destino, link-credencial, telefone) roda a cada N minutos (padrão 15). Achado T13/WA-3.
        "EXECUTIONS_DATA_PRUNE_HARD_DELETE_INTERVAL": "1",
        # SSRF: só o host dos simuladores é liberado (na produção: o host da API do PCPR)
        "N8N_SSRF_PROTECTION_ENABLED": "true",
        "N8N_SSRF_ALLOWED_HOSTNAMES": "host.docker.internal",
        "N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS": "true",
        "N8N_BLOCK_ENV_ACCESS_IN_NODE": "true",
        # a imagem não traz Python; sem isto o n8n tenta subir o runner Python e loga erro
        "N8N_PYTHON_ENABLED": "false",
        "N8N_LOG_LEVEL": "info",
    }


def docker(*args: str, timeout: int = 300, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if check and r.returncode != 0:
        raise RuntimeError(f"docker {' '.join(args[:3])}… falhou: {r.stderr.strip()[-1500:]}")
    return r


def _env_args(chave: str, extra: dict[str, str] | None = None) -> list[str]:
    saida: list[str] = []
    for k, v in {**variaveis(chave), **(extra or {})}.items():
        saida += ["-e", f"{k}={v}"]
    return saida


def existe() -> bool:
    r = docker("ps", "-a", "--filter", f"name=^{CONTEINER}$", "--format", "{{.Names}}", check=False)
    return CONTEINER in r.stdout


def remover() -> None:
    docker("rm", "-f", CONTEINER, check=False)
    docker("volume", "rm", "-f", VOLUME, check=False)


def preparar(dir_importacao: Path, chave: str, ids: list[str]) -> str:
    """Volume novo + import de credenciais e workflows + publicação (n8n parado)."""
    remover()
    docker("volume", "create", VOLUME)
    publicar = " && ".join(f"n8n publish:workflow --id={i}" for i in ids)
    script = (
        "set -e; n8n import:credentials --input=/importar/credenciais.json; "
        "n8n import:workflow --separate --input=/importar/workflows; "
        f"{publicar}; n8n list:workflow; n8n list:workflow --active=true --onlyId"
    )
    r = docker(
        "run",
        "--rm",
        "-v",
        f"{VOLUME}:/home/node/.n8n",
        "-v",
        f"{dir_importacao}:/importar:ro",
        *_env_args(chave),
        "--entrypoint",
        "sh",
        IMAGEM,
        "-c",
        script,
        timeout=600,
    )
    return r.stdout + r.stderr


def subir(
    chave: str, env_extra: dict[str, str] | None = None, hosts_extras: list[str] | None = None
) -> None:
    """`env_extra`: variáveis a mais (ex.: retenção no TW13). `hosts_extras`: entradas
    `nome:ip` no /etc/hosts do contêiner (o WA-3 aponta graph.facebook.com para 127.0.0.1:
    qualquer chamada acidental à Meta falha localmente)."""
    hosts: list[str] = []
    for h in hosts_extras or []:
        hosts += ["--add-host", h]
    docker(
        "run",
        "-d",
        "--name",
        CONTEINER,
        "-p",
        f"127.0.0.1:{PORTA}:{PORTA}",
        "--add-host",
        "host.docker.internal:host-gateway",
        *hosts,
        "-v",
        f"{VOLUME}:/home/node/.n8n",
        *_env_args(chave, env_extra),
        IMAGEM,
    )


def parar_abrupto() -> None:
    docker("kill", CONTEINER)


def parar() -> None:
    docker("stop", "-t", "30", CONTEINER, timeout=120)


def iniciar() -> None:
    docker("start", CONTEINER)


def _http(
    metodo: str, url: str, corpo: bytes = b"", cab: dict | None = None, timeout: float = 5
) -> int:
    req = urllib.request.Request(
        url,
        data=corpo or None,
        headers=cab or {},
        method=metodo,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, OSError):
        return 0


def esperar_pronto(timeout: float = 180) -> float:
    """Saudável + webhook do W1 registrado (POST sem assinatura → 401, não 404)."""
    inicio = time.time()
    while time.time() - inicio < timeout:
        if _http("GET", f"{URL}/healthz/readiness") == 200:
            st = _http(
                "POST", f"{URL}/webhook/pcpr-eventos", b"{}", {"Content-Type": "application/json"}
            )
            if st == 401:
                return time.time() - inicio
        time.sleep(1)
    raise TimeoutError(f"n8n não ficou pronto em {timeout}s:\n{logs(60)}")


def logs(n: int = 200) -> str:
    r = docker("logs", "--tail", str(n), CONTEINER, check=False)
    return r.stdout + r.stderr


_UNIDADES = {
    "B": 1,
    "KiB": 1024,
    "MiB": 1024**2,
    "GiB": 1024**3,
    "kB": 1000,
    "MB": 1000**2,
    "GB": 1000**3,
}


def memoria_bytes() -> int | None:
    r = docker("stats", "--no-stream", "--format", "{{.MemUsage}}", CONTEINER, check=False)
    m = re.match(r"\s*([\d.]+)\s*([A-Za-z]+)", r.stdout or "")
    if not m:
        return None
    return int(float(m.group(1)) * _UNIDADES.get(m.group(2), 1))


def tamanho_banco() -> dict[str, int]:
    r = docker(
        "exec",
        CONTEINER,
        "sh",
        "-c",
        "for f in /home/node/.n8n/database.sqlite*; do stat -c '%n %s' \"$f\"; done",
        check=False,
    )
    saida = {}
    for linha in r.stdout.splitlines():
        nome, _, tam = linha.rpartition(" ")
        if tam.isdigit():
            saida[nome.rsplit("/", 1)[-1]] = int(tam)
    return saida


def config_efetiva() -> dict:
    """Lê a configuração que o processo do contêiner enxerga (prova das flags)."""
    js = (
        "require('reflect-metadata');"
        "const {GlobalConfig}=require('@n8n/config');const {Container}=require('@n8n/di');"
        "const g=Container.get(GlobalConfig);"
        "console.log(JSON.stringify({diagnostics:g.diagnostics.enabled,"
        "versionNotifications:g.versionNotifications.enabled,"
        "whatsNew:g.versionNotifications.whatsNewEnabled,templates:g.templates.enabled,"
        "personalization:g.personalization.enabled,dynamicBanners:g.dynamicBanners.enabled,"
        "hiringBanner:g.hiringBanner.enabled,licenseAutoRenew:g.license.autoRenewalEnabled,"
        "ai:g.ai.enabled,publicApiDisabled:g.publicApi.disabled,"
        "ssrf:{enabled:g.ssrfProtection.enabled,allowedHostnames:g.ssrfProtection.allowedHostnames},"
        "prune:{on:g.executions.pruneData,maxAgeH:g.executions.pruneDataMaxAge,"
        "maxCount:g.executions.pruneDataMaxCount},timezone:g.generic.timezone,"
        "runnersMode:g.taskRunners.mode,db:g.database.type}))"
    )
    r = docker(
        "exec", "-w", "/usr/local/lib/node_modules/n8n", CONTEINER, "node", "-e", js, check=False
    )
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"erro": (r.stdout + r.stderr)[-800:]}


def exportar(dir_saida: Path, chave: str) -> str:
    """Com o n8n parado: despublica tudo e exporta workflows (+ credenciais CRIPTOGRAFADAS,
    só para conferir que o segredo não aparece em claro; esse arquivo não vai para docs/)."""
    script = (
        "set -e; n8n unpublish:workflow --all; "
        "n8n export:workflow --backup --output=/exportar/workflows/; "
        "n8n export:credentials --all --output=/exportar/credenciais-criptografadas.json; "
        "n8n list:workflow --active=true --onlyId; echo FIM"
    )
    r = docker(
        "run",
        "--rm",
        "-v",
        f"{VOLUME}:/home/node/.n8n",
        "-v",
        f"{dir_saida}:/exportar",
        *_env_args(chave),
        "--entrypoint",
        "sh",
        IMAGEM,
        "-c",
        script,
        timeout=600,
    )
    return r.stdout + r.stderr


def copiar_dados(destino: Path) -> Path:
    """Cópia da pasta inteira do n8n (banco + `storage/` com os binários das execuções)."""
    destino.mkdir(parents=True, exist_ok=True)
    docker("cp", f"{CONTEINER}:/home/node/.n8n/.", str(destino), timeout=300)
    return destino


def copiar_banco(destino: Path) -> list[Path]:
    """Cópia do SQLite (para depuração/inspeção das execuções)."""
    destino.mkdir(parents=True, exist_ok=True)
    copiados = []
    for nome in ("database.sqlite", "database.sqlite-wal", "database.sqlite-shm"):
        r = docker("cp", f"{CONTEINER}:/home/node/.n8n/{nome}", str(destino / nome), check=False)
        if r.returncode == 0:
            copiados.append(destino / nome)
    return copiados
