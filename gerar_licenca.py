import argparse
import base64
import json
import os
import sys
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


PLANOS = {
    "trimestral": 90,
    "semestral": 180,
    "anual": 365,
}


def gerar_par_de_chaves(private_key_path, public_key_path):
    private_key = Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    os.makedirs(os.path.dirname(os.path.abspath(private_key_path)), exist_ok=True)
    with open(private_key_path, "wb") as handle:
        handle.write(private_bytes)
    os.chmod(private_key_path, 0o600)

    os.makedirs(os.path.dirname(os.path.abspath(public_key_path)), exist_ok=True)
    with open(public_key_path, "wb") as handle:
        handle.write(public_bytes)
    print("Par de chaves criado.")
    print(f"Chave privada: {private_key_path}")
    print(f"Chave pública: {public_key_path}")
    print("Guarde a chave privada fora da pasta do aplicativo.")


def carregar_private_key(private_key_path):
    with open(private_key_path, "rb") as handle:
        return serialization.load_pem_private_key(handle.read(), password=None)


def gerar_licenca(args):
    private_key = carregar_private_key(args.private_key)
    inicio = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    if args.dias is not None:
        dias = int(args.dias)
        plano = args.plan or "personalizada"
    else:
        plano = args.plan.lower()
        if plano not in PLANOS:
            raise ValueError("Plano inválido.")
        dias = PLANOS[plano]

    if dias < 1:
        raise ValueError("A quantidade de dias deve ser maior que zero.")

    expira = inicio + timedelta(days=dias)
    payload = {
        "version": 1,
        "plan": plano,
        "issued_at": inicio.strftime("%Y-%m-%d"),
        "expires_at": expira.strftime("%Y-%m-%d"),
        "days": dias,
        "customer": args.customer or "",
        "machine_id": args.machine_id or "",
    }
    payload_bytes = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assinatura = private_key.sign(payload_bytes)
    objeto = {
        "payload": payload,
        "signature": base64.urlsafe_b64encode(assinatura).rstrip(b"=").decode("ascii"),
    }

    compacta = base64.urlsafe_b64encode(
        json.dumps(objeto, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).rstrip(b"=").decode("ascii")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(objeto, handle, ensure_ascii=False, indent=2)
        print(f"Licença JSON salva em: {args.output}")

    print("\nChave compacta:")
    print(compacta)


def main():
    parser = argparse.ArgumentParser(
        description="Gerador de licenças Ed25519 do EduHora"
    )
    parser.add_argument("--generate-keys", action="store_true")
    parser.add_argument("--private-key", default="license_private_key.pem")
    parser.add_argument("--public-key", default="license_public_key.pem")
    parser.add_argument("--plan", choices=["trimestral", "semestral", "anual"], default=None)
    parser.add_argument("--dias", type=int, default=None)
    parser.add_argument("--customer", default="")
    parser.add_argument("--machine-id", default="")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    if args.generate_keys:
        gerar_par_de_chaves(args.private_key, args.public_key)
        return

    try:
        gerar_licenca(args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
