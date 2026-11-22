import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen


VERSAO_APP = "1.1.3"
REPOSITORIO_GITHUB = "SamukaMath/EduHora"
API_RELEASES = f"https://api.github.com/repos/{REPOSITORIO_GITHUB}/releases/latest"


def normalizar_versao(valor):
    return tuple(
        int(parte)
        for parte in str(valor).strip().lower().lstrip("v").split(".")
        if parte.isdigit()
    )


def baixar_json(url, timeout=12):
    requisicao = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "EduHora-Updater",
        },
    )
    with urlopen(requisicao, timeout=timeout) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


def verificar_atualizacao():
    release = baixar_json(API_RELEASES)
    versao_nova = str(release.get("tag_name") or "").strip()
    if normalizar_versao(versao_nova) <= normalizar_versao(VERSAO_APP):
        return None

    assets = release.get("assets", [])
    candidato = None
    for asset in assets:
        nome = str(asset.get("name", "")).lower()
        if nome.endswith(".zip") or nome.endswith(".exe"):
            candidato = asset
            if nome.endswith(".zip"):
                break

    if candidato is None:
        return None

    return {
        "versao": versao_nova,
        "nome": candidato["name"],
        "url": candidato["browser_download_url"],
        "notas": str(release.get("body") or "").strip(),
    }


def baixar_arquivo(url, destino, timeout=60):
    requisicao = Request(
        url,
        headers={
            "Accept": "application/octet-stream",
            "User-Agent": "EduHora-Updater",
        },
    )
    with urlopen(requisicao, timeout=timeout) as resposta:
        with open(destino, "wb") as arquivo:
            shutil.copyfileobj(resposta, arquivo)


def sha256_arquivo(caminho):
    digest = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def iniciar_atualizacao(url_asset, nome_asset):
    if not getattr(sys, "frozen", False):
        return False, "Atualizações automáticas estão disponíveis apenas no executável instalado."

    if not str(url_asset).startswith("https://"):
        return False, "A atualização não foi fornecida por HTTPS."

    diretorio_app = Path(sys.executable).resolve().parent
    arquivo_temp = Path(tempfile.gettempdir()) / nome_asset
    try:
        baixar_arquivo(url_asset, arquivo_temp)
    except Exception as exc:
        return False, f"Falha no download: {exc}"

    if nome_asset.lower().endswith(".exe"):
        argumentos = [str(arquivo_temp), "/S"]
        subprocess.Popen(argumentos, close_fds=True)
        return True, "Atualização instalada ao iniciar o instalador."

    if not nome_asset.lower().endswith(".zip"):
        return False, "Formato de atualização não suportado."

    script = Path(tempfile.gettempdir()) / "eduhora_updater.ps1"
    destino = tempfile.mkdtemp(prefix="eduhora-update-")
    pid_atual = os.getpid()
    executavel_atual = str(Path(sys.executable).resolve())

    script_ps1 = r"""
param(
    [int]$ParentPid,
    [string]$ZipFile,
    [string]$ExtractDir,
    [string]$InstallDir,
    [string]$CurrentExe
)

Start-Sleep -Milliseconds 1200

$deadline = (Get-Date).AddSeconds(20)
while ((Get-Process -Id $ParentPid -ErrorAction SilentlyContinue) -and (Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 250
}

$backup = Join-Path $env:TEMP ("eduhora-backup-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $backup -Force | Out-Null

Get-ChildItem -LiteralPath $InstallDir -Force |
    Move-Item -Destination $backup -Force

Expand-Archive -LiteralPath $ZipFile -DestinationPath $ExtractDir -Force

$exeCandidate = Get-ChildItem -LiteralPath $ExtractDir -Filter "EduHora_v3.exe" -Recurse -File |
    Select-Object -First 1

if ($exeCandidate) {
    $sourceDir = $exeCandidate.DirectoryName
    Get-ChildItem -LiteralPath $sourceDir -Force |
        Copy-Item -Destination $InstallDir -Recurse -Force

    Start-Sleep -Milliseconds 500
    Start-Process -FilePath (Join-Path $InstallDir "EduHora_v3.exe")
} else {
    Get-ChildItem -LiteralPath $backup -Force |
        Move-Item -Destination $InstallDir -Force
}

Remove-Item -LiteralPath $ZipFile -Force -ErrorAction SilentlyContinue
"""

    script.write_text(script_ps1, encoding="utf-8")
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-ParentPid",
            str(pid_atual),
            "-ZipFile",
            str(arquivo_temp),
            "-ExtractDir",
            destino,
            "-InstallDir",
            str(diretorio_app),
            "-CurrentExe",
            executavel_atual,
        ],
        close_fds=True,
        creationflags=(
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        ),
    )
    return True, "Atualização pronta. O EduHora será reiniciado."
