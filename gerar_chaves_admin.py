import argparse
import base64
import json
import os
import sys
import secrets
from datetime import datetime, timedelta, timezone

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
    import ttkbootstrap as ttk
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError as exc:
    print(f"Dependência ausente: {exc}", file=sys.stderr)
    raise SystemExit(1)


PLANOS = {
    "Trimestral": 90,
    "Semestral": 180,
    "Anual": 365,
}


def obter_diretorio_admin():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    diretorio = os.path.join(base, "EduHoraAdmin")
    os.makedirs(diretorio, exist_ok=True)
    return diretorio


def obter_chaves_padrao():
    diretorio = obter_diretorio_admin()
    private_path = os.path.join(diretorio, "license_private_key.pem")
    public_path = os.path.join(diretorio, "license_public_key.pem")
    if not os.path.isfile(private_path) or not os.path.isfile(public_path):
        gerar_par_de_chaves(private_path, public_path)
    return private_path, public_path


def gerar_par_de_chaves(private_key_path, public_key_path):
    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    for caminho, conteudo in (
        (private_key_path, private_pem),
        (public_key_path, public_pem),
    ):
        diretorio = os.path.dirname(os.path.abspath(caminho))
        os.makedirs(diretorio, exist_ok=True)
        with open(caminho, "wb") as handle:
            handle.write(conteudo)

    if os.name == "nt":
        os.chmod(private_key_path, 0o600)


def gerar_license(private_key_path, plano, dias, cliente, machine_id):
    with open(private_key_path, "rb") as handle:
        private_key = serialization.load_pem_private_key(handle.read(), password=None)

    inicio = datetime.now(timezone.utc).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    quantidade_dias = int(dias)
    if quantidade_dias < 1:
        raise ValueError("A quantidade de dias deve ser maior que zero.")

    payload = {
        "version": 1,
        "license_id": secrets.token_hex(16).upper(),
        "plan": plano.lower(),
        "issued_at": inicio.strftime("%Y-%m-%d"),
        "expires_at": (inicio + timedelta(days=quantidade_dias)).strftime("%Y-%m-%d"),
        "days": quantidade_dias,
        "customer": cliente.strip(),
        "machine_id": machine_id.strip().upper(),
    }
    payload_bytes = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    signature = private_key.sign(payload_bytes)
    objeto = {
        "payload": payload,
        "signature": base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii"),
    }

    compacta = base64.urlsafe_b64encode(
        json.dumps(objeto, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).rstrip(b"=").decode("ascii")
    return compacta, objeto


def gerar_lista_revogacao(private_key_path, license_ids, output_path=None):
    with open(private_key_path, "rb") as handle:
        private_key = serialization.load_pem_private_key(handle.read(), password=None)

    payload = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "revoked": sorted({str(value).strip().upper() for value in license_ids if str(value).strip()}),
    }
    payload_bytes = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    objeto = {
        "payload": payload,
        "signature": base64.urlsafe_b64encode(
            private_key.sign(payload_bytes)
        ).rstrip(b"=").decode("ascii"),
    }

    if output_path:
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(objeto, handle, ensure_ascii=False, indent=2)
    return objeto


class AdminLicencasApp:
    def __init__(self, root):
        self.root = root
        root.title("EduHora - Gerador Administrativo de Licenças")
        root.geometry("760x620")
        root.minsize(680, 560)

        ttk.Label(
            root,
            text="Gerador Administrativo de Licenças",
            font=("Segoe UI", 18, "bold"),
            bootstyle="primary",
        ).pack(pady=(20, 12))

        formulario = ttk.Labelframe(
            root,
            text="Dados da Licença",
            padding=15,
            bootstyle="info",
        )
        formulario.pack(fill="x", padx=25)
        formulario.columnconfigure(1, weight=1)

        ttk.Label(formulario, text="Plano:").grid(row=0, column=0, sticky="w", pady=6)
        self.cb_plano = ttk.Combobox(
            formulario,
            values=["Trimestral", "Semestral", "Anual", "Personalizado"],
            state="readonly",
            width=20,
        )
        self.cb_plano.set("Trimestral")
        self.cb_plano.grid(row=0, column=1, sticky="w", pady=6)
        self.cb_plano.bind("<<ComboboxSelected>>", self.atualizar_dias)

        ttk.Label(formulario, text="Dias:").grid(row=1, column=0, sticky="w", pady=6)
        self.ent_dias = ttk.Entry(formulario, width=12)
        self.ent_dias.insert(0, "90")
        self.ent_dias.grid(row=1, column=1, sticky="w", pady=6)

        ttk.Label(formulario, text="Cliente:").grid(row=2, column=0, sticky="w", pady=6)
        self.ent_cliente = ttk.Entry(formulario)
        self.ent_cliente.grid(row=2, column=1, sticky="ew", pady=6)

        ttk.Label(formulario, text="ID da máquina:").grid(row=3, column=0, sticky="w", pady=6)
        self.ent_machine_id = ttk.Entry(formulario)
        self.ent_machine_id.grid(row=3, column=1, sticky="ew", pady=6)
        self.ent_machine_id.insert(0, "")

        ttk.Label(
            formulario,
            text="Universal: deixe vazio para servir em qualquer PC.",
            font=("Segoe UI", 8),
            bootstyle="secondary",
        ).grid(row=4, column=1, sticky="w")

        chaves = ttk.Labelframe(
            root,
            text="Arquivos de Criptografia",
            padding=15,
            bootstyle="warning",
        )
        chaves.pack(fill="x", padx=25, pady=12)
        chaves.columnconfigure(1, weight=1)

        ttk.Label(chaves, text="Chave privada:").grid(row=0, column=0, sticky="w", pady=5)
        self.ent_private_key = ttk.Entry(chaves)
        self.ent_private_key.grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(
            chaves,
            text="Selecionar",
            bootstyle="secondary",
            command=self.selecionar_private_key,
        ).grid(row=0, column=2)

        private_default, public_default = obter_chaves_padrao()
        self.ent_private_key.insert(0, private_default)

        ttk.Button(
            chaves,
            text="Gerar Novo Par",
            bootstyle="danger-outline",
            command=self.gerar_novo_par,
        ).grid(row=1, column=0, columnspan=3, pady=(10, 4))

        ttk.Label(chaves, text="License ID:").grid(row=2, column=0, sticky="w", pady=5)
        self.ent_license_id = ttk.Entry(chaves)
        self.ent_license_id.grid(row=2, column=1, sticky="ew", padx=8)
        ttk.Button(
            chaves,
            text="Revogar",
            bootstyle="danger",
            command=self.revogar_license,
        ).grid(row=2, column=2)

        botoes = ttk.Frame(root)
        botoes.pack(pady=8)
        ttk.Button(
            botoes,
            text="🔑 Gerar Licença",
            bootstyle="success",
            command=self.gerar_license,
        ).pack(side="left", padx=5)
        ttk.Button(
            botoes,
            text="📋 Copiar Chave",
            bootstyle="info",
            command=self.copiar_chave,
        ).pack(side="left", padx=5)
        ttk.Button(
            botoes,
            text="💾 Salvar Arquivo",
            bootstyle="warning",
            command=self.salvar_chave,
        ).pack(side="left", padx=5)

        self.txt_chave = tk.Text(root, height=10, wrap="char")
        self.txt_chave.pack(fill="both", expand=True, padx=25, pady=(8, 20))

    def atualizar_dias(self, event=None):
        plano = self.cb_plano.get()
        if plano in PLANOS:
            self.ent_dias.configure(state="readonly")
            self.ent_dias.configure(state="normal")
            self.ent_dias.delete(0, "end")
            self.ent_dias.insert(0, str(PLANOS[plano]))
            self.ent_dias.configure(state="readonly")
        else:
            self.ent_dias.configure(state="normal")

    def selecionar_private_key(self):
        caminho = filedialog.askopenfilename(
            title="Selecionar chave privada",
            filetypes=[("Chave PEM", "*.pem"), ("Todos os arquivos", "*.*")],
        )
        if caminho:
            self.ent_private_key.delete(0, "end")
            self.ent_private_key.insert(0, caminho)

    def gerar_novo_par(self):
        private_path = filedialog.asksaveasfilename(
            title="Salvar chave privada",
            defaultextension=".pem",
            filetypes=[("Chave privada PEM", "*.pem")],
            initialfile="license_private_key.pem",
        )
        if not private_path:
            return

        public_path = os.path.splitext(private_path)[0] + "_public.pem"
        try:
            gerar_par_de_chaves(private_path, public_path)
            self.ent_private_key.delete(0, "end")
            self.ent_private_key.insert(0, private_path)
            messagebox.showinfo(
                "Par criado",
                f"Chave privada: {private_path}\nChave pública: {public_path}",
            )
        except Exception as exc:
            messagebox.showerror("Erro", f"Não foi possível gerar o par:\n{exc}")

    def revogar_license(self):
        private_path = self.ent_private_key.get().strip()
        license_id = self.ent_license_id.get().strip().upper()
        if not private_path or not os.path.isfile(private_path):
            messagebox.showwarning("Chave privada", "Selecione uma chave privada válida.")
            return
        if not license_id:
            messagebox.showwarning("License ID", "Informe o identificador da licença.")
            return
        if not messagebox.askyesno(
            "Revogar licença",
            f"Revogar permanentemente a licença {license_id}?",
        ):
            return

        caminho = filedialog.asksaveasfilename(
            title="Salvar lista de revogações",
            defaultextension=".json",
            filetypes=[("Revogação JSON", "*.json")],
            initialfile="revocations.json",
        )
        if not caminho:
            return
        try:
            objeto = gerar_lista_revogacao(
                private_path,
                [license_id],
                caminho,
            )
            messagebox.showinfo(
                "Licença revogada",
                f"{license_id} foi incluída na lista assinada.\n\n"
                "Publique revocations.json no endereço configurado.",
            )
        except Exception as exc:
            messagebox.showerror("Erro", f"Não foi possível revogar:\n{exc}")

    def gerar_license(self):
        private_path = self.ent_private_key.get().strip()
        if not private_path or not os.path.isfile(private_path):
            messagebox.showwarning("Chave privada", "Selecione uma chave privada válida.")
            return

        plano = self.cb_plano.get()
        try:
            dias = int(self.ent_dias.get().strip())
            chave, objeto = gerar_license(
                private_path,
                plano,
                dias,
                self.ent_cliente.get(),
                self.ent_machine_id.get(),
            )
        except Exception as exc:
            messagebox.showerror("Erro", f"Não foi possível gerar a licença:\n{exc}")
            return

        self.txt_chave.delete("1.0", "end")
        self.txt_chave.insert("1.0", chave)
        self._ultimo_objeto = objeto
        messagebox.showinfo(
            "Licença criada",
            f"Plano: {objeto['payload']['plan']}\n"
            f"Validade: {objeto['payload']['expires_at']}",
        )

    def copiar_chave(self):
        chave = self.txt_chave.get("1.0", "end").strip()
        if not chave:
            messagebox.showwarning("Aviso", "Gere uma licença primeiro.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(chave)
        messagebox.showinfo("Copiada", "Chave copiada para a área de transferência.")

    def salvar_chave(self):
        chave = self.txt_chave.get("1.0", "end").strip()
        if not chave:
            messagebox.showwarning("Aviso", "Gere uma licença primeiro.")
            return
        caminho = filedialog.asksaveasfilename(
            title="Salvar licença",
            defaultextension=".json",
            filetypes=[("Licença JSON", "*.json"), ("Texto", "*.txt")],
            initialfile="licenca_eduhora.json",
        )
        if caminho:
            objeto = getattr(self, "_ultimo_objeto", None)
            with open(caminho, "w", encoding="utf-8") as handle:
                if caminho.lower().endswith(".json") and objeto:
                    json.dump(objeto, handle, ensure_ascii=False, indent=2)
                else:
                    handle.write(chave)
            messagebox.showinfo("Licença salva", f"Licença salva em:\n{caminho}")


def executar_admin_cli(args):
    if args.revoke:
        private_path = args.private_key or obter_chaves_padrao()[0]
        objeto = gerar_lista_revogacao(
            private_path,
            args.revoke,
            args.revocation_output or "",
        )
        print(json.dumps(objeto, ensure_ascii=False, indent=2))
        return

    if args.generate_keys:
        private_path = args.private_key or os.path.join(
            obter_diretorio_admin(),
            "license_private_key.pem",
        )
        public_path = args.public_key or os.path.join(
            obter_diretorio_admin(),
            "license_public_key.pem",
        )
        gerar_par_de_chaves(private_path, public_path)
        print("Par de chaves gerado.")
        print(f"Privada: {private_path}")
        print(f"Pública: {public_path}")
        return

    private_path = args.private_key or obter_chaves_padrao()[0]

    plano = args.plan.lower() if args.plan else "personalizado"
    dias = args.dias
    if dias < 1:
        dias = PLANOS.get(plano.capitalize(), 0)
    chave, objeto = gerar_license(
        private_path,
        plano,
        dias,
        args.customer,
        args.machine_id,
    )
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(objeto, handle, ensure_ascii=False, indent=2)
    print(chave)


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--generate-keys", action="store_true")
    parser.add_argument("--private-key", default="")
    parser.add_argument("--public-key", default="")
    parser.add_argument("--plan", choices=["trimestral", "semestral", "anual"], default=None)
    parser.add_argument("--dias", type=int, default=0)
    parser.add_argument("--customer", default="")
    parser.add_argument("--machine-id", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--revoke", nargs="+", default=[], metavar="LICENSE_ID")
    parser.add_argument("--revocation-output", default="")
    parser.add_argument("--cli", action="store_true")
    args = parser.parse_args()

    if args.generate_keys or args.cli:
        executar_admin_cli(args)
        return

    root = ttk.Window(themename="flatly")
    AdminLicencasApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
