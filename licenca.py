import base64
import hashlib
import json
import os
import platform
import uuid
import secrets
from urllib.request import Request, urlopen
from datetime import datetime, timezone

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
except ImportError:
    Ed25519PublicKey = None
    InvalidSignature = Exception
    serialization = None


PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAo+pBxoC26H7BZ9inrZLsH31NeYx5xwFhN+Itm/im9HQ=
-----END PUBLIC KEY-----
"""

PLANO_DIAS = {
    "trimestral": 90,
    "semestral": 180,
    "anual": 365,
}


def obter_diretorio_licenca():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    diretorio = os.path.join(base, "EduHora")
    os.makedirs(diretorio, exist_ok=True)
    return diretorio


def obter_arquivo_licenca():
    return os.path.join(obter_diretorio_licenca(), "license.json")


def obter_arquivo_ativacoes():
    return os.path.join(obter_diretorio_licenca(), "activated_licenses.json")


def obter_arquivo_revogacoes():
    return os.path.join(obter_diretorio_licenca(), "revocations.json")


def obter_license_id(payload, objeto=None):
    license_id = str(payload.get("license_id") or "").strip()
    if license_id:
        return license_id

    if objeto:
        assinatura = str(objeto.get("signature") or "")
        return hashlib.sha256(assinatura.encode("utf-8")).hexdigest()[:32].upper()
    return ""


def obter_machine_id():
    partes = [
        platform.system(),
        platform.node(),
        str(uuid.getnode()),
        os.environ.get("PROCESSOR_IDENTIFIER", ""),
        os.environ.get("COMPUTERNAME", ""),
    ]
    bruto = "|".join(partes).encode("utf-8")
    return hashlib.sha256(bruto).hexdigest()[:32].upper()


def _normalizar_chave(chave):
    texto = str(chave).strip()
    if texto.startswith("{"):
        try:
            return json.loads(texto)
        except json.JSONDecodeError:
            return None
    compactado = "".join(texto.split())
    compactado = compactado.replace("-", "")
    padding = "=" * (-len(compactado) % 4)
    try:
        bruto = base64.urlsafe_b64decode(compactado + padding)
        return json.loads(bruto.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _ler_revogacoes():
    revogados = set()

    url = os.environ.get("EDUHORA_REVOCATION_URL", "").strip()
    if url.startswith("https://"):
        try:
            requisicao = Request(
                url,
                headers={"User-Agent": "EduHora-License-Validator"},
            )
            with urlopen(requisicao, timeout=8) as resposta:
                remoto = json.loads(resposta.read().decode("utf-8"))
            payload = remoto.get("payload", {})
            assinatura = remoto.get("signature", "")
            payload_bytes = json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            assinatura_bytes = base64.urlsafe_b64decode(
                assinatura + "=" * (-len(assinatura) % 4)
            )
            chave_publica = serialization.load_pem_public_key(PUBLIC_KEY_PEM)
            chave_publica.verify(assinatura_bytes, payload_bytes)
            for license_id in payload.get("revoked", []):
                revogados.add(str(license_id).strip().upper())
        except Exception:
            pass

    arquivo_local = obter_arquivo_revogacoes()
    if os.path.exists(arquivo_local):
        try:
            with open(arquivo_local, "r", encoding="utf-8") as handle:
                local = json.load(handle)
            payload = local.get("payload", {})
            assinatura = local.get("signature", "")
            payload_bytes = json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            assinatura_bytes = base64.urlsafe_b64decode(
                assinatura + "=" * (-len(assinatura) % 4)
            )
            chave_publica = serialization.load_pem_public_key(PUBLIC_KEY_PEM)
            chave_publica.verify(assinatura_bytes, payload_bytes)
            for license_id in payload.get("revoked", []):
                revogados.add(str(license_id).strip().upper())
        except Exception:
            pass

    return revogados


def validar_licenca(chave=None, machine_id=None):
    if Ed25519PublicKey is None:
        return False, "Dependência de assinatura não instalada."

    if chave is None:
        arquivo = obter_arquivo_licenca()
        if not os.path.exists(arquivo):
            return False, "Nenhuma licença ativada."
        try:
            with open(arquivo, "r", encoding="utf-8") as handle:
                chave = handle.read()
        except OSError as exc:
            return False, f"Não foi possível ler a licença: {exc}"

    objeto = _normalizar_chave(chave)
    if not isinstance(objeto, dict):
        return False, "Formato da chave inválido."

    payload = objeto.get("payload")
    assinatura_b64 = objeto.get("signature")
    if not isinstance(payload, dict) or not isinstance(assinatura_b64, str):
        return False, "Chave incompleta."

    license_id = obter_license_id(payload, objeto)
    if not license_id:
        return False, "Identificador único da licença ausente."
    if license_id.upper() in _ler_revogacoes():
        return False, "Licença revogada pelo administrador."

    try:
        payload_bytes = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        assinatura = base64.urlsafe_b64decode(
            assinatura_b64 + "=" * (-len(assinatura_b64) % 4)
        )
        chave_publica = serialization.load_pem_public_key(PUBLIC_KEY_PEM)
        chave_publica.verify(
            assinatura,
            payload_bytes,
        )
    except InvalidSignature:
        return False, "A assinatura da licença não é válida."
    except (ValueError, TypeError):
        return False, "Não foi possível verificar a licença."

    maquina = payload.get("machine_id")
    maquina_atual = machine_id or obter_machine_id()
    if maquina and str(maquina).upper() != str(maquina_atual).upper():
        return False, "Esta licença pertence a outro computador."

    try:
        expira = datetime.strptime(payload["expires_at"], "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
    except (KeyError, ValueError, TypeError):
        return False, "Data de validade inválida."

    hoje = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    dias_restantes = (expira - hoje).days
    if dias_restantes < 0:
        return False, "A assinatura expirou."

    return True, {
        "plan": payload.get("plan", "personalizada"),
        "expires_at": payload["expires_at"],
        "machine_id": maquina or maquina_atual,
        "days_remaining": dias_restantes,
        "customer": payload.get("customer", ""),
        "license_id": license_id,
    }


def ativar_licenca(chave):
    objeto = _normalizar_chave(chave)
    if not isinstance(objeto, dict):
        return False, "Formato da chave inválido."

    valido, mensagem = validar_licenca(json.dumps(objeto, ensure_ascii=False))
    if not valido:
        return False, mensagem

    payload = objeto.get("payload", {})
    license_id = obter_license_id(payload, objeto).upper()
    maquina_atual = obter_machine_id()

    ativacoes = {}
    arquivo_ativacoes = obter_arquivo_ativacoes()
    if os.path.exists(arquivo_ativacoes):
        try:
            with open(arquivo_ativacoes, "r", encoding="utf-8") as handle:
                ativacoes = json.load(handle)
        except (OSError, json.JSONDecodeError):
            ativacoes = {}

    ativacao_existente = ativacoes.get(license_id)
    if ativacao_existente:
        if str(ativacao_existente).upper() != maquina_atual:
            return False, "Esta licença já foi ativada em outro computador."
    else:
        ativacoes[license_id] = maquina_atual

    try:
        with open(obter_arquivo_licenca(), "w", encoding="utf-8") as handle:
            json.dump(objeto, handle, ensure_ascii=False, indent=2)
        with open(arquivo_ativacoes, "w", encoding="utf-8") as handle:
            json.dump(ativacoes, handle, ensure_ascii=False, indent=2)
        return True, mensagem
    except OSError as exc:
        return False, f"Não foi possível salvar a licença: {exc}"
