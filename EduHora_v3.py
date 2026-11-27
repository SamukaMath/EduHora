import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import threading
import json
import re
import sys
import webbrowser
from atualizador import verificar_atualizacao
from version import VERSAO_APP

class AppHorariosPro:
    def __init__(self, root):
        self.root = root
        self.root.title("EduHora - Gerador de Horários Escolar")
        self.root.geometry("1180x820")
        self.root.minsize(1000, 700)
        self.root.iconbitmap("eduhora.ico")
        self.configurar_estilo()
        
        self.professores = {} 
        self.disciplinas = []
        self.turmas = {}
        self.requerimentos = [] 
        self.dias_semana = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta"]
        self._timer_legenda = None
        self._largura_legenda = 0
        self._redistribuindo_legenda = False
        self.historico_aprendizado = {
            "periodos": 0,
            "preferencias": {},
            "ultima_qualidade": None,
        }
        self._dados_dashboard = []
        if hasattr(self, "canvas_prof_ind_manha"):
            self.canvas_prof_ind_manha.delete("all")
        if hasattr(self, "canvas_prof_ind_tarde"):
            self.canvas_prof_ind_tarde.delete("all")
        if hasattr(self, "lbl_carga_individual"):
            self.lbl_carga_individual.configure(text="")
        self.paleta_professores = [
            "#D32F2F", "#1565C0", "#2E7D32", "#6A1B9A", "#EF6C00",
            "#00838F", "#AD1457", "#283593", "#558B2F", "#C62828",
            "#0277BD", "#7B1FA2", "#00695C", "#9E9D24", "#4527A0",
            "#BF360C", "#37474F", "#5D4037", "#1B5E20", "#0D47A1",
            "#880E4F", "#4A148C", "#33691E", "#E65100", "#006064",
            "#512DA8", "#827717", "#B71C1C", "#01579B", "#1A237E",
        ]

        self.configurar_menu()

        self.cabecalho = ttk.Frame(root, style="Header.TFrame", padding=(24, 16))
        self.cabecalho.pack(fill='x', padx=15, pady=(15, 0))
        ttk.Label(
            self.cabecalho,
            text="EduHora",
            style="HeaderTitle.TLabel"
        ).pack(side='left')
        ttk.Label(
            self.cabecalho,
            text="  •  Gerador profissional de horários escolares",
            style="HeaderSubtitle.TLabel"
        ).pack(side='left', pady=(5, 0))
        
        self.notebook = ttk.Notebook(root, bootstyle="info")
        self.notebook.pack(fill='both', expand=True, padx=15, pady=(10, 15))

        self.aba_prof = ttk.Frame(self.notebook)
        self.aba_disc = ttk.Frame(self.notebook)
        self.aba_turmas = ttk.Frame(self.notebook)
        self.aba_distrib = ttk.Frame(self.notebook)
        self.aba_gerar = ttk.Frame(self.notebook)
        self.aba_grade = ttk.Frame(self.notebook)
        self.aba_dash = ttk.Frame(self.notebook)
        self.aba_prof_individual = ttk.Frame(self.notebook)

        self.notebook.add(self.aba_prof, text="👩‍🏫 Professores")
        self.notebook.add(self.aba_disc, text="📚 Disciplinas")
        self.notebook.add(self.aba_turmas, text="🎓 Turmas")
        self.notebook.add(self.aba_distrib, text="⚙️ Grade (Vínculos)")
        self.notebook.add(self.aba_gerar, text="🚀 Gerar")
        self.notebook.add(self.aba_grade, text="📅 Visualizar Grade")
        self.notebook.add(self.aba_dash, text="📊 Dashboard")
        self.notebook.add(self.aba_prof_individual, text="🧑‍🏫 Horário Individual")

        self.construir_abas()

    def configurar_estilo(self):
        estilo = ttk.Style()
        estilo.configure("Header.TFrame", background="#17324d")
        estilo.configure(
            "HeaderTitle.TLabel",
            background="#17324d",
            foreground="#ffffff",
            font=("Segoe UI", 22, "bold")
        )
        estilo.configure(
            "HeaderSubtitle.TLabel",
            background="#17324d",
            foreground="#b8c9d9",
            font=("Segoe UI", 10)
        )
        estilo.configure("TNotebook.Tab", padding=(18, 10), font=("Segoe UI", 10, "bold"))
        estilo.configure("Treeview", rowheight=30, font=("Segoe UI", 10))
        estilo.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), padding=(8, 8))
        estilo.configure("TButton", font=("Segoe UI", 10), padding=(12, 7))
        estilo.configure("TLabel", font=("Segoe UI", 10))
        estilo.configure("TEntry", padding=(8, 6))
        estilo.configure("TCombobox", padding=(8, 5))

    # ================= CONSTRUÇÃO DA INTERFACE =================
    def construir_abas(self):
        # --- Aba Professores ---
        f_prof_top = ttk.Frame(self.aba_prof)
        f_prof_top.pack(pady=20)
        
        ttk.Label(f_prof_top, text="Nome do Professor:", font=("Arial", 10, "bold")).grid(row=0, column=0, padx=5)
        self.ent_prof = ttk.Entry(f_prof_top, width=35)
        self.ent_prof.grid(row=0, column=1, padx=5)
        
        ttk.Button(f_prof_top, text="➕ Adicionar Professor", bootstyle="success", command=self.add_prof).grid(row=0, column=2, padx=15)
        
        f_botoes_prof = ttk.Frame(self.aba_prof)
        f_botoes_prof.pack(pady=5)
        
        ttk.Button(f_botoes_prof, text="⚙️ Configurar Restrições (Selecionado)", bootstyle="warning", command=self.abrir_janela_restricoes).pack(side='left', padx=10)
        ttk.Button(f_botoes_prof, text="✏️ Renomear Professor", bootstyle="info-outline", command=self.renomear_professor).pack(side='left', padx=10)
        ttk.Button(f_botoes_prof, text="🗑️ Excluir Professor", bootstyle="danger-outline", command=lambda: self.excluir_item(self.tv_prof, "prof")).pack(side='left', padx=10)
        
        ttk.Label(self.aba_prof, text="Dica: Dê um duplo-clique num professor para configurar as suas restrições.", font=("Arial", 9, "italic")).pack(pady=5)

        self.tv_prof = ttk.Treeview(self.aba_prof, columns=("Nome", "Carga", "Dias OFF", "Bloqueios"), show='headings', bootstyle="info")
        self.tv_prof.heading("Nome", text="Professor")
        self.tv_prof.heading("Carga", text="Aulas Vinculadas")
        self.tv_prof.heading("Dias OFF", text="Dias Evitados")
        self.tv_prof.heading("Bloqueios", text="Bloqueios Exatos")
        
        self.tv_prof.column("Carga", width=120, anchor="center")
        self.tv_prof.pack(fill='both', expand=True, padx=20, pady=10)
        self.tv_prof.bind("<Double-1>", self.abrir_janela_restricoes)

        # --- Aba Disciplinas ---
        f_disc = ttk.Frame(self.aba_disc)
        f_disc.pack(pady=20)
        
        ttk.Label(f_disc, text="Disciplina:", font=("Arial", 10, "bold")).pack(side='left', padx=5)
        self.ent_disc = ttk.Entry(f_disc, width=35)
        self.ent_disc.pack(side='left', padx=10)
        ttk.Button(f_disc, text="➕ Adicionar", bootstyle="success", command=self.add_disc).pack(side='left')
        
        self.list_disc = tk.Listbox(self.aba_disc, font=("Arial", 10), relief="flat", highlightthickness=1)
        self.list_disc.pack(fill='both', expand=True, padx=20, pady=10)
        ttk.Button(self.aba_disc, text="🗑️ Excluir Selecionada", bootstyle="danger-outline", command=lambda: self.excluir_listbox(self.list_disc, "disc")).pack(pady=10)

        # --- Aba Turmas ---
        f_turma = ttk.Frame(self.aba_turmas)
        f_turma.pack(pady=20)
        
        ttk.Label(f_turma, text="Nome da Turma:", font=("Arial", 10, "bold")).grid(row=0, column=0, padx=5)
        self.ent_turma = ttk.Entry(f_turma, width=20)
        self.ent_turma.grid(row=0, column=1, padx=5)
        
        ttk.Label(f_turma, text="Turno:", font=("Arial", 10, "bold")).grid(row=0, column=2, padx=10)
        self.combo_turno_turma = ttk.Combobox(f_turma, values=["Manhã", "Tarde"], state="readonly", width=15)
        self.combo_turno_turma.grid(row=0, column=3, padx=5)
        self.combo_turno_turma.set("Manhã")
        
        ttk.Button(f_turma, text="➕ Adicionar/Atualizar", bootstyle="success", command=self.add_turma).grid(row=0, column=4, padx=15)
        
        self.tv_turma = ttk.Treeview(self.aba_turmas, columns=("Turma", "Turno"), show='headings', bootstyle="info")
        self.tv_turma.heading("Turma", text="Nome da Turma")
        self.tv_turma.heading("Turno", text="Turno da Aula")
        self.tv_turma.pack(fill='both', expand=True, padx=20, pady=10)
        self.tv_turma.bind("<Double-1>", self.carregar_turma_para_editar)
        
        ttk.Button(self.aba_turmas, text="🗑️ Excluir Selecionada", bootstyle="danger-outline", command=lambda: self.excluir_item(self.tv_turma, "turma")).pack(pady=10)

        # --- Aba Distribuição (Grade) ---
        f_dist = ttk.Frame(self.aba_distrib)
        f_dist.pack(pady=20, fill='x')
        
        ttk.Label(f_dist, text="Turma:", font=("Arial", 9, "bold")).grid(row=0, column=0, padx=5)
        self.cb_t = ttk.Combobox(f_dist, state="readonly", width=12)
        self.cb_t.grid(row=0, column=1, padx=5)
        
        ttk.Label(f_dist, text="Disciplina:", font=("Arial", 9, "bold")).grid(row=0, column=2, padx=5)
        self.cb_d = ttk.Combobox(f_dist, state="readonly", width=18)
        self.cb_d.grid(row=0, column=3, padx=5)
        
        ttk.Label(f_dist, text="Professor:", font=("Arial", 9, "bold")).grid(row=0, column=4, padx=5)
        self.cb_p = ttk.Combobox(f_dist, state="readonly", width=18)
        self.cb_p.grid(row=0, column=5, padx=5)
        
        ttk.Label(f_dist, text="Aulas:", font=("Arial", 9, "bold")).grid(row=0, column=6, padx=5)
        self.ent_a = ttk.Entry(f_dist, width=8)
        self.ent_a.grid(row=0, column=7, padx=5)
        
        ttk.Button(f_dist, text="🔗 Vincular", bootstyle="primary", command=self.add_req).grid(row=0, column=8, padx=15)
        
        # === FILTRO DE TURMAS ===
        # === INÍCIO DA ÁREA DE FILTROS (TURMA E PROFESSOR) ===
        f_filtro = ttk.Frame(self.aba_distrib) # ATENÇÃO: Mude 'self.aba_distrib' para o nome da sua aba se for diferente!
        f_filtro.pack(fill='x', padx=20, pady=(10, 5))
        
        # 1. Label e Filtro de Turma
        ttk.Label(f_filtro, text="🔍 Turma:", font=("Arial", 9, "bold")).pack(side='left', padx=(5, 2))
        self.cb_filtro_turma = ttk.Combobox(f_filtro, state="readonly", width=15)
        self.cb_filtro_turma.pack(side='left', padx=5)
        self.cb_filtro_turma.bind("<<ComboboxSelected>>", self.atualizar_tabela_req)
        
        # 2. Label e Filtro de Professor
        ttk.Label(f_filtro, text="🎓 Professor:", font=("Arial", 9, "bold")).pack(side='left', padx=(20, 2))
        self.cb_filtro_prof = ttk.Combobox(f_filtro, state="readonly", width=25)
        self.cb_filtro_prof.pack(side='left', padx=5)
        self.cb_filtro_prof.bind("<<ComboboxSelected>>", self.atualizar_tabela_req)
        
        # 3. Botão para Limpar os Filtros
        ttk.Button(f_filtro, text="❌ Limpar", bootstyle="secondary-outline", command=self.limpar_filtro_req).pack(side='left', padx=20)
        # === FIM DA ÁREA DE FILTROS ===
        # ========================
        
        self.tv_req = ttk.Treeview(self.aba_distrib, columns=("T","D","P","A"), show='headings', bootstyle="primary")
        self.tv_req.heading("T", text="Turma"); self.tv_req.heading("D", text="Disciplina")
        self.tv_req.heading("P", text="Professor"); self.tv_req.heading("A", text="Qtd Aulas")
        self.tv_req.pack(fill='both', expand=True, padx=20, pady=10)
        
        ttk.Button(self.aba_distrib, text="🗑️ Remover Vínculo", bootstyle="danger-outline", command=lambda: self.excluir_item(self.tv_req, "req")).pack(pady=10)
        # ========================
        
        # --- Aba Gerar ---
        f_config_turnos = ttk.Frame(self.aba_gerar)
        f_config_turnos.pack(pady=15)

        ttk.Label(f_config_turnos, text="Aulas/dia (Manhã):", font=("Arial", 10)).pack(side='left', padx=5)
        self.spin_manha = ttk.Spinbox(f_config_turnos, from_=1, to=10, width=5)
        self.spin_manha.set(5)
        self.spin_manha.pack(side='left', padx=(0, 20))

        ttk.Label(f_config_turnos, text="Aulas/dia (Tarde):", font=("Arial", 10)).pack(side='left', padx=5)
        self.spin_tarde = ttk.Spinbox(f_config_turnos, from_=1, to=10, width=5)
        self.spin_tarde.set(5)
        self.spin_tarde.pack(side='left', padx=(0, 20))
        
        ttk.Button(f_config_turnos, text="⏰ Definir Horários", bootstyle="info", command=self.abrir_janela_horarios).pack(side='left', padx=10)

        f_btn = ttk.Frame(self.aba_gerar)
        f_btn.pack(pady=10)
        
        self.btn_gerar = ttk.Button(f_btn, text="⚙️ CALCULAR", bootstyle="success", command=self.iniciar_geracao)
        self.btn_gerar.pack(side='left', padx=10)
        
        self.var_agrupar_triplas = ttk.BooleanVar(value=True)
        self.chk_triplas = ttk.Checkbutton(
            f_btn,
            text="Agrupar 3 aulas seguidas (3+ aulas/sem)",
            variable=self.var_agrupar_triplas,
            bootstyle="round-toggle"
        )
        self.chk_triplas.pack(side='left', padx=10)
        
        self.lbl_status = ttk.Label(self.aba_gerar, text="Status: Aguardando...", font=("Arial", 10, "italic"))
        self.lbl_status.pack(pady=5)
        
        self.progresso_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(self.aba_gerar, variable=self.progresso_var, maximum=100, mode="determinate", bootstyle="success-striped")
        self.progress_bar.pack(fill="x", padx=40, pady=10)

        ttk.Label(
            self.aba_gerar,
            text="💡 A grade gerada será exibida na aba “Visualizar Grade”.",
            bootstyle="inverse-warning",
            font=("Segoe UI", 9),
        ).pack(pady=12)

        # --- Aba Visualizar Grade ---
        ttk.Label(
            self.aba_grade,
            text="Visualização da Grade Escolar",
            font=("Segoe UI", 16, "bold"),
            bootstyle="primary",
        ).pack(pady=(12, 6))

        ttk.Label(
            self.aba_grade,
            text="💡 Clique duplo em uma aula para editar manualmente.",
            bootstyle="inverse-warning",
            font=("Segoe UI", 9),
        ).pack(pady=(0, 6))

        self.lbl_status_grade = ttk.Label(
            self.aba_grade,
            text="Status: Aguardando geração...",
            font=("Segoe UI", 9, "italic"),
            bootstyle="secondary",
        )
        self.lbl_status_grade.pack(pady=(0, 4))

        barra_zoom = ttk.Frame(self.aba_grade)
        barra_zoom.pack(fill="x", padx=20, pady=(0, 5))

        ttk.Label(
            barra_zoom,
            text="Zoom da grade:",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(0, 8))

        self.zoom_grade = 0.60
        self.lbl_zoom_grade = ttk.Label(
            barra_zoom,
            text="60%",
            width=8,
            anchor="center",
            font=("Segoe UI", 9, "bold"),
        )
        self.lbl_zoom_grade.pack(side="left", padx=5)

        ttk.Button(
            barra_zoom,
            text="−",
            width=3,
            bootstyle="secondary",
            command=lambda: self.alterar_zoom_grade(-0.10),
        ).pack(side="left", padx=2)
        ttk.Button(
            barra_zoom,
            text="100%",
            width=6,
            bootstyle="secondary",
            command=lambda: self.definir_zoom_grade(1.0),
        ).pack(side="left", padx=2)
        ttk.Button(
            barra_zoom,
            text="+",
            width=3,
            bootstyle="secondary",
            command=lambda: self.alterar_zoom_grade(0.10),
        ).pack(side="left", padx=2)

        acoes_exportacao = ttk.Frame(barra_zoom)
        acoes_exportacao.pack(side="right")
        self.btn_exportar = ttk.Button(
            acoes_exportacao,
            text="📥 Excel",
            bootstyle="warning",
            state="disabled",
            command=self.salvar_excel
        )
        self.btn_exportar.pack(side="left", padx=4)
        self.btn_exportar_pdf = ttk.Button(
            acoes_exportacao,
            text="📄 PDF",
            bootstyle="danger",
            state="disabled",
            command=self.salvar_pdf
        )
        self.btn_exportar_pdf.pack(side="left", padx=4)

        self.legenda_professores = ttk.Frame(self.aba_grade)
        self.legenda_professores.pack(fill="x", padx=20, pady=(0, 5))

        self.painel_grades = ttk.Panedwindow(self.aba_grade, orient="vertical")
        self.painel_grades.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        painel_manha = ttk.Labelframe(self.painel_grades, text="☀️  Grade - Turno da Manhã", bootstyle="primary", padding=5)
        self.tv_previa_manha = ttk.Treeview(painel_manha, show='headings', bootstyle="primary")
        self.canvas_previa_manha, barra_manha_v, barra_manha_h = self.criar_canvas_grade(painel_manha)
        self.canvas_previa_manha.bind(
            "<Double-1>",
            lambda event: self.editar_aula_visual(event, self.tv_previa_manha, self.canvas_previa_manha)
        )
        self.canvas_previa_manha.bind("<Control-MouseWheel>", self.zoom_mouse_grade)

        painel_tarde = ttk.Labelframe(self.painel_grades, text="🌆  Grade - Turno da Tarde", bootstyle="warning", padding=5)
        self.tv_previa_tarde = ttk.Treeview(painel_tarde, show='headings', bootstyle="warning")
        self.canvas_previa_tarde, barra_tarde_v, barra_tarde_h = self.criar_canvas_grade(painel_tarde)
        self.canvas_previa_tarde.bind(
            "<Double-1>",
            lambda event: self.editar_aula_visual(event, self.tv_previa_tarde, self.canvas_previa_tarde)
        )
        self.canvas_previa_tarde.bind("<Control-MouseWheel>", self.zoom_mouse_grade)

        self.painel_grades.add(painel_manha, weight=1)
        self.painel_grades.add(painel_tarde, weight=1)

        # --- Aba Dashboard ---
        dashboard_area = ttk.Frame(self.aba_dash)
        dashboard_area.pack(fill="both", expand=True)

        self.canvas_dashboard = tk.Canvas(
            dashboard_area,
            background="#f3f6fa",
            highlightthickness=0
        )
        barra_dashboard = ttk.Scrollbar(
            dashboard_area,
            orient="vertical",
            command=self.canvas_dashboard.yview
        )
        self.canvas_dashboard.configure(yscrollcommand=barra_dashboard.set)
        self.canvas_dashboard.pack(side="left", fill="both", expand=True)
        barra_dashboard.pack(side="right", fill="y")

        conteudo_dashboard = ttk.Frame(self.canvas_dashboard, padding=(14, 8, 14, 16))
        self._janela_dashboard = self.canvas_dashboard.create_window(
            (0, 0),
            window=conteudo_dashboard,
            anchor="nw"
        )
        conteudo_dashboard.bind(
            "<Configure>",
            lambda event: self.canvas_dashboard.configure(
                scrollregion=self.canvas_dashboard.bbox("all")
            )
        )
        self.canvas_dashboard.bind(
            "<Configure>",
            lambda event: self.canvas_dashboard.itemconfigure(
                self._janela_dashboard,
                width=event.width
            )
        )
        self.root.bind_all("<MouseWheel>", self.rolar_dashboard_com_mouse, add="+")

        ttk.Label(
            conteudo_dashboard,
            text="Dashboard da Distribuição",
            font=("Segoe UI", 18, "bold"),
            bootstyle="primary"
        ).pack(anchor="w", padx=6, pady=(8, 2))
        ttk.Label(
            conteudo_dashboard,
            text="Resumo da carga horária e da qualidade da grade por professor.",
            font=("Segoe UI", 9),
            bootstyle="secondary"
        ).pack(anchor="w", padx=7, pady=(0, 12))

        cards = ttk.Frame(conteudo_dashboard)
        cards.pack(fill="x", padx=4, pady=(0, 12))
        cards.columnconfigure((0, 1, 2, 3), weight=1)

        self.dash_card_professores = self.criar_card_dashboard(
            cards, "PROFESSORES", "0", 0, "primary"
        )
        self.dash_card_aulas = self.criar_card_dashboard(
            cards, "AULAS NA GRADE", "0", 1, "info"
        )
        self.dash_card_perfeitos = self.criar_card_dashboard(
            cards, "SEM PENALIDADES", "0", 2, "success"
        )
        self.dash_card_penalidades = self.criar_card_dashboard(
            cards, "AULAS CEDIDAS", "0", 3, "warning"
        )

        area_graficos = ttk.Panedwindow(conteudo_dashboard, orient="horizontal")
        area_graficos.pack(fill="x", padx=4, pady=(0, 12))

        painel_barras = ttk.Labelframe(
            area_graficos,
            text="Carga semanal por professor",
            bootstyle="primary",
            padding=8
        )
        self.canvas_carga_professores = tk.Canvas(
            painel_barras,
            height=220,
            background="#ffffff",
            highlightthickness=0
        )
        barra_carga = ttk.Scrollbar(
            painel_barras,
            orient="vertical",
            command=self.canvas_carga_professores.yview
        )
        self.canvas_carga_professores.configure(yscrollcommand=barra_carga.set)
        self.canvas_carga_professores.pack(side="left", fill="both", expand=True)
        barra_carga.pack(side="right", fill="y")

        painel_qualidade = ttk.Labelframe(
            area_graficos,
            text="Qualidade da distribuição",
            bootstyle="success",
            padding=8
        )
        self.canvas_qualidade = tk.Canvas(
            painel_qualidade,
            height=220,
            background="#ffffff",
            highlightthickness=0
        )
        self.canvas_qualidade.pack(fill="both", expand=True)
        self.canvas_carga_professores.bind(
            "<Configure>",
            lambda event: self.root.after_idle(
                lambda: self.desenhar_grafico_carga(getattr(self, "_dados_dashboard", []))
            )
        )
        self.canvas_qualidade.bind(
            "<Configure>",
            lambda event: self.root.after_idle(
                lambda: self.desenhar_grafico_qualidade(getattr(self, "_dados_dashboard", []))
            )
        )

        area_graficos.add(painel_barras, weight=3)
        area_graficos.add(painel_qualidade, weight=2)

        ttk.Label(
            conteudo_dashboard,
            text="Detalhamento por professor",
            font=("Segoe UI", 12, "bold"),
            bootstyle="primary"
        ).pack(anchor="w", padx=6, pady=(3, 6))

        tabela_frame = ttk.Frame(conteudo_dashboard)
        tabela_frame.pack(fill="x", padx=4, pady=(0, 4))

        self.tv_dash = ttk.Treeview(
            tabela_frame,
            columns=("Prof", "Total", "Penalidades", "Qualidade", "Status"),
            show="headings",
            bootstyle="primary",
            height=1
        )
        self.tv_dash.heading("Prof", text="Professor")
        self.tv_dash.heading("Total", text="Aulas Semanais")
        self.tv_dash.heading("Penalidades", text="Aulas em Dias Evitados")
        self.tv_dash.heading("Qualidade", text="Aproveitamento")
        self.tv_dash.heading("Status", text="Status")
        self.tv_dash.column("Prof", width=220, anchor="w")
        self.tv_dash.column("Total", width=120, anchor="center")
        self.tv_dash.column("Penalidades", width=170, anchor="center")
        self.tv_dash.column("Qualidade", width=120, anchor="center")
        self.tv_dash.column("Status", width=150, anchor="center")

        barra_tabela = ttk.Scrollbar(
            tabela_frame,
            orient="vertical",
            command=self.tv_dash.yview
        )
        self.tv_dash.configure(yscrollcommand=barra_tabela.set)
        self.tv_dash.pack(side="left", fill="both", expand=True)
        barra_tabela.pack(side="right", fill="y")
        self.tv_dash.tag_configure("perfeito", foreground="#1B5E20")
        self.tv_dash.tag_configure("aviso", foreground="#C62828")
        self.atualizar_legenda_professores()

        # --- Aba Horário Individual ---
        cabecalho_individual = ttk.Frame(self.aba_prof_individual)
        cabecalho_individual.pack(fill="x", padx=20, pady=15)

        ttk.Label(
            cabecalho_individual,
            text="Professor:",
            font=("Segoe UI", 10, "bold")
        ).pack(side="left", padx=(0, 8))

        self.cb_prof_individual = ttk.Combobox(
            cabecalho_individual,
            state="readonly",
            width=32
        )
        self.cb_prof_individual.pack(side="left")
        self.cb_prof_individual.bind(
            "<<ComboboxSelected>>",
            lambda event: self.atualizar_horario_individual()
        )

        self.lbl_carga_individual = ttk.Label(
            cabecalho_individual,
            text="",
            font=("Segoe UI", 10, "bold")
        )
        self.lbl_carga_individual.pack(side="left", padx=20)

        self.zoom_grade_individual = 0.60
        controles_zoom_individual = ttk.Frame(cabecalho_individual)
        controles_zoom_individual.pack(side="right")
        ttk.Label(
            controles_zoom_individual,
            text="Zoom:",
            font=("Segoe UI", 9, "bold")
        ).pack(side="left", padx=(0, 5))
        self.lbl_zoom_grade_individual = ttk.Label(
            controles_zoom_individual,
            text="60%",
            width=6,
            anchor="center",
            font=("Segoe UI", 9, "bold")
        )
        self.lbl_zoom_grade_individual.pack(side="left", padx=3)
        ttk.Button(
            controles_zoom_individual,
            text="−",
            width=3,
            bootstyle="secondary",
            command=lambda: self.alterar_zoom_grade_individual(-0.10)
        ).pack(side="left", padx=2)
        ttk.Button(
            controles_zoom_individual,
            text="100%",
            width=6,
            bootstyle="secondary",
            command=lambda: self.definir_zoom_grade_individual(1.0)
        ).pack(side="left", padx=2)
        ttk.Button(
            controles_zoom_individual,
            text="+",
            width=3,
            bootstyle="secondary",
            command=lambda: self.alterar_zoom_grade_individual(0.10)
        ).pack(side="left", padx=2)

        frame_individual = ttk.Frame(self.aba_prof_individual)
        frame_individual.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        painel_individual = ttk.Panedwindow(frame_individual, orient="vertical")
        painel_individual.pack(fill="both", expand=True)

        painel_ind_manha = ttk.Labelframe(
            painel_individual,
            text="☀️  Horário da Manhã",
            bootstyle="primary",
            padding=5
        )
        painel_ind_tarde = ttk.Labelframe(
            painel_individual,
            text="🌆  Horário da Tarde",
            bootstyle="warning",
            padding=5
        )
        painel_individual.add(painel_ind_manha, weight=1)
        painel_individual.add(painel_ind_tarde, weight=1)

        def configurar_canvas_individual(parent):
            canvas = tk.Canvas(parent, background="#ffffff", highlightthickness=0)
            barra_v = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
            barra_h = ttk.Scrollbar(parent, orient="horizontal", command=canvas.xview)
            canvas.configure(yscrollcommand=barra_v.set, xscrollcommand=barra_h.set)
            canvas.bind("<Control-MouseWheel>", self.zoom_mouse_grade_individual)
            parent.columnconfigure(0, weight=1)
            parent.rowconfigure(0, weight=1)
            canvas.grid(row=0, column=0, sticky="nsew")
            barra_v.grid(row=0, column=1, sticky="ns")
            barra_h.grid(row=1, column=0, sticky="ew")
            return canvas

        self.canvas_prof_ind_manha = configurar_canvas_individual(painel_ind_manha)
        self.canvas_prof_ind_tarde = configurar_canvas_individual(painel_ind_tarde)

    # ================= MÉTODOS BASE E ATUALIZAÇÕES =================
    # ================= MÉTODOS BASE E ATUALIZAÇÕES =================
    def configurar_menu(self):
        menu_bar = tk.Menu(self.root)
        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Novo Projeto", command=self.novo_projeto)
        file_menu.add_command(label="Abrir Projeto...", command=self.abrir_projeto)
        file_menu.add_command(label="Salvar Projeto", command=self.salvar_projeto)
        file_menu.add_separator()
        file_menu.add_command(label="Sair", command=self.root.quit)
        menu_bar.add_cascade(label="Arquivo", menu=file_menu)
        
        sobre_menu = tk.Menu(menu_bar, tearoff=0)
        sobre_menu.add_command(label="Sobre o Sistema", command=self.abrir_janela_sobre)
        sobre_menu.add_command(label="Verificar Atualizações", command=self.verificar_atualizacoes_manual)
        menu_bar.add_cascade(label="Sobre", menu=sobre_menu)
        
        self.root.config(menu=menu_bar)

    def verificar_atualizacoes_manual(self):
        threading.Thread(
            target=self._processar_verificacao_atualizacao,
            daemon=True,
        ).start()

    def _processar_verificacao_atualizacao(self):
        try:
            atualizacao = verificar_atualizacao()
            if atualizacao is None:
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Atualizações",
                        f"Você já está usando a versão mais recente ({VERSAO_APP}).",
                    ),
                )
                return

            if atualizacao.get("requer_manual"):
                versao_encontrada = atualizacao.get("versao")
                mensagem_pasta = (
                    f"Nova versão encontrada: {versao_encontrada}\n\n"
                    if versao_encontrada
                    else ""
                )
                pasta_drive = atualizacao["pasta"]
                self.root.after(
                    0,
                    lambda: (
                        webbrowser.open(pasta_drive),
                        messagebox.showinfo(
                            "Atualizações no Google Drive",
                            f"{mensagem_pasta}"
                            "Abra a pasta e baixe o arquivo RAR da versão indicada.\n"
                            "Use WinRAR ou 7-Zip para substituir a instalação.",
                        ),
                    ),
                )
                return
        except Exception as exc:
            self.root.after(
                0,
                lambda: messagebox.showwarning(
                    "Atualização",
                    f"Não foi possível verificar:\n{exc}",
                ),
            )

    def salvar_projeto(self):
        dados = {
            "professores": self.professores,
            "disciplinas": self.disciplinas,
            "turmas": self.turmas,
            "requerimentos": self.requerimentos,
            "historico_aprendizado": self.historico_aprendizado,
        }
        caminho = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Arquivo JSON", "*.json")])
        if caminho:
            with open(caminho, 'w', encoding='utf-8') as f: json.dump(dados, f, indent=4)
            messagebox.showinfo("Sucesso", "Projeto salvo!")

    def abrir_projeto(self):
        caminho = filedialog.askopenfilename(filetypes=[("Arquivo JSON", "*.json")])
        if caminho:
            try:
                with open(caminho, 'r', encoding='utf-8') as f: dados = json.load(f)
                self.professores = dados.get("professores", {})
                self.disciplinas = dados.get("disciplinas", [])
                self.turmas = dados.get("turmas", [])
                self.requerimentos = dados.get("requerimentos", [])
                self.historico_aprendizado = dados.get("historico_aprendizado", {
                    "periodos": 0,
                    "preferencias": {},
                    "ultima_qualidade": None,
                })
                self.repopular_interface()
            except Exception as e: messagebox.showerror("Erro", f"Erro: {e}")

    def novo_projeto(self):
        if messagebox.askyesno("Limpar", "Começar um novo projeto?"):
            self.professores = {}; self.disciplinas = []; self.turmas = {}; self.requerimentos = []
            self.historico_aprendizado = {
                "periodos": 0,
                "preferencias": {},
                "ultima_qualidade": None,
            }
            self.tv_previa_manha.delete(*self.tv_previa_manha.get_children()); self.tv_previa_manha["columns"] = ()
            self.tv_previa_tarde.delete(*self.tv_previa_tarde.get_children()); self.tv_previa_tarde["columns"] = ()
            self.canvas_previa_manha.delete("all")
            self.canvas_previa_tarde.delete("all")
            self.tv_dash.delete(*self.tv_dash.get_children())
            self.tv_dash.configure(height=1)
            self._dados_dashboard = []
            self.atualizar_card_dashboard(self.dash_card_professores, 0)
            self.atualizar_card_dashboard(self.dash_card_aulas, 0)
            self.atualizar_card_dashboard(self.dash_card_perfeitos, 0)
            self.atualizar_card_dashboard(self.dash_card_penalidades, 0)
            self.desenhar_grafico_carga([])
            self.desenhar_grafico_qualidade([])
            self.atualizar_tabela_professores()
            self.list_disc.delete(0, 'end')
            self.tv_turma.delete(*self.tv_turma.get_children())
            self.tv_req.delete(*self.tv_req.get_children())
            self.btn_exportar.config(state="disabled")
            self.btn_exportar_pdf.config(state="disabled")
            
    def abrir_janela_sobre(self):
        # Cria a janela pop-up
        janela_sobre = tk.Toplevel(self.root)
        janela_sobre.title("Sobre")
        janela_sobre.geometry("350x250")
        janela_sobre.resizable(False, False)
        
        # Centraliza a janela na tela
        janela_sobre.transient(self.root)
        janela_sobre.grab_set()

        # --- Conteúdo da Janela ---
        ttk.Label(janela_sobre, text="EduHora", font=("Arial", 16, "bold"), bootstyle="primary").pack(pady=(20, 5))
        ttk.Label(janela_sobre, text="Gerador de Horários Escolar", font=("Arial", 10, "italic")).pack(pady=(0, 15))
        
        # Detalhes (Substitua os textos abaixo pelos seus dados reais)
        ttk.Label(janela_sobre, text=f"Versão: {VERSAO_APP}", font=("Arial", 10)).pack(pady=2)
        ttk.Label(janela_sobre, text="Criador: Samuel de Sousa Apolinário", font=("Arial", 10)).pack(pady=2)
        ttk.Label(janela_sobre, text="contato: prof.samuelapolinario@gmail.com", font=("Arial", 10)).pack(pady=2)
        
        # Botão Fechar
        ttk.Button(janela_sobre, text="Fechar", bootstyle="secondary", command=janela_sobre.destroy).pack(pady=25)

    def repopular_interface(self):
        self.atualizar_tabela_professores()
        self.list_disc.delete(0, 'end')
        for d in self.disciplinas: self.list_disc.insert("end", d)
        if isinstance(self.turmas, list): self.turmas = {t: "Manhã" for t in self.turmas}
        self.tv_turma.delete(*self.tv_turma.get_children())
        for t, turno in self.turmas.items(): self.tv_turma.insert("", "end", values=(t, turno))
        self.tv_req.delete(*self.tv_req.get_children())
        for r in self.requerimentos: self.tv_req.insert("", "end", values=(r['turma'], r['disciplina'], r['professor'], r['aulas']))
        self.atualizar_combos()

    def registrar_preferencia_grade(self, requerimento, dia, aula, quantidade=1):
        chave = f"{requerimento['turma']}|{requerimento['disciplina']}|{requerimento['professor']}"
        preferencias = self.historico_aprendizado.setdefault("preferencias", {})
        slots = preferencias.setdefault(chave, {})
        slot = f"{dia},{aula}"
        slots[slot] = max(0, int(slots.get(slot, 0)) + int(quantidade))

    def registrar_grade_aprendida(self, grade, motor=None):
        preferencias = self.historico_aprendizado.setdefault("preferencias", {})
        periodos = int(self.historico_aprendizado.get("periodos", 0))

        # Suavização temporal: preserva o histórico, mas valoriza preferências dos períodos recentes.
        if periodos > 0:
            for slots in preferencias.values():
                for slot in list(slots):
                    slots[slot] = max(0, int(slots[slot] * 0.98))

        for (turma, dia, aula), r_idx in grade.items():
            if r_idx is None:
                continue
            req = self.requerimentos[r_idx]
            if req["turma"] == turma:
                self.registrar_preferencia_grade(req, dia, aula)

        self.historico_aprendizado["periodos"] = periodos + 1
        self.historico_aprendizado["ultima_qualidade"] = {
            "motor": motor,
            "periodo": periodos + 1,
        }

    def registrar_edicao_aprendida(self, tv_alvo, item_id, col_idx, valor_antigo, valor_novo):
        valores = list(tv_alvo.item(item_id)["values"])
        dia_nome = str(valores[0])
        try:
            dia = self.dias_semana.index(dia_nome)
        except ValueError:
            return

        horarios = (
            getattr(self, "horarios_m_custom", [])
            if tv_alvo is self.tv_previa_manha
            else getattr(self, "horarios_t_custom", [])
        )
        horario = str(valores[1])
        if horario in horarios:
            aula_local = horarios.index(horario)
        else:
            match = re.search(r"(\d+)", horario)
            aula_local = max(0, int(match.group(1)) - 1) if match else 0

        aula = aula_local if tv_alvo is self.tv_previa_manha else aula_local + int(self.spin_manha.get())

        if valor_antigo and valor_antigo != "---" and "(" in str(valor_antigo):
            texto = str(valor_antigo)
            disciplina = texto.rsplit("(", 1)[0].strip()
            professor = texto.rsplit("(", 1)[1].rstrip(")").strip()
            turma = str(tv_alvo.heading(f"#{col_idx + 1}")["text"])
            req = {"turma": turma, "disciplina": disciplina, "professor": professor}
            chave = f"{turma}|{disciplina}|{professor}"
            slots = self.historico_aprendizado.setdefault("preferencias", {}).setdefault(chave, {})
            slot = f"{dia},{aula}"
            slots[slot] = max(0, int(slots.get(slot, 0)) - 1)

        if valor_novo and valor_novo != "- LIVRE -" and "(" in str(valor_novo):
            texto = str(valor_novo)
            disciplina = texto.rsplit("(", 1)[0].strip()
            professor = texto.rsplit("(", 1)[1].rstrip(")").strip()
            turma = str(tv_alvo.heading(f"#{col_idx + 1}")["text"])
            req = {"turma": turma, "disciplina": disciplina, "professor": professor}
            self.registrar_preferencia_grade(req, dia, aula, 3)

    def add_prof(self):
        nome = self.ent_prof.get().strip().upper()
        if not nome: return
        
        if nome not in self.professores:
            self.professores[nome] = {"manha": [], "tarde": [], "bloqueios": []}
            
        self.ent_prof.delete(0, 'end')
        self.ent_prof.focus_set()
        
        self.atualizar_tabela_professores()
        self.atualizar_combos()

    def atualizar_tabela_professores(self):
        self.tv_prof.delete(*self.tv_prof.get_children())
        
        aulas_alocadas = {p: 0 for p in self.professores}
        for req in self.requerimentos:
            p = req['professor']
            if p in aulas_alocadas:
                aulas_alocadas[p] += int(req['aulas'])
                
        for p, dados in self.professores.items():
            atual = aulas_alocadas.get(p, 0)
            str_carga = f"{atual} aulas"
            
            dias_off_m = len(dados.get("manha", []))
            dias_off_t = len(dados.get("tarde", []))
            str_dias = f"M:{dias_off_m} / T:{dias_off_t}" if (dias_off_m > 0 or dias_off_t > 0) else "Nenhum"
            
            qtd_bloq = len(dados.get("bloqueios", []))
            str_bloq = f"{qtd_bloq} restrições" if qtd_bloq > 0 else "Nenhum"
            
            self.tv_prof.insert("", "end", values=(p, str_carga, str_dias, str_bloq))
        self.atualizar_legenda_professores()

    def atualizar_legenda_professores(self):
        if not hasattr(self, "legenda_professores"):
            return

        for widget in self.legenda_professores.winfo_children():
            widget.destroy()

        if not self.professores:
            ttk.Label(
                self.legenda_professores,
                text="As cores dos professores aparecerão aqui após a geração da grade.",
                bootstyle="secondary"
            ).pack(side="left")
            return

        ttk.Label(
            self.legenda_professores,
            text="Professores:",
            font=("Segoe UI", 8, "bold")
        ).grid(row=0, column=0, padx=(0, 6), pady=2, sticky="w")

        faixa = ttk.Frame(self.legenda_professores)
        faixa.grid(row=0, column=1, sticky="ew")
        self.legenda_professores.columnconfigure(1, weight=1)

        self._itens_legenda_professores = []
        for indice, nome in enumerate(self.professores):
            cor = self.paleta_professores[indice % len(self.paleta_professores)]
            vermelho = int(cor[1:3], 16)
            verde = int(cor[3:5], 16)
            azul = int(cor[5:7], 16)
            cor_texto = "#000000" if (0.299 * vermelho + 0.587 * verde + 0.114 * azul) > 145 else "#FFFFFF"
            item = tk.Label(
                faixa,
                text=f"  {nome}  ",
                bg=cor,
                fg=cor_texto,
                font=("Segoe UI", 7, "bold"),
                padx=3,
                pady=2
            )
            self._itens_legenda_professores.append(item)

        self._faixa_legenda_professores = faixa
        faixa.bind("<Configure>", self.solicitar_distribuicao_legenda, add="+")
        self.legenda_professores.after_idle(self.solicitar_distribuicao_legenda)

    def distribuir_legenda_professores(self):
        faixa = getattr(self, "_faixa_legenda_professores", None)
        itens = getattr(self, "_itens_legenda_professores", [])
        if faixa is None or not itens or getattr(self, "_redistribuindo_legenda", False):
            return

        largura_disponivel = max(1, faixa.winfo_width())
        if largura_disponivel == getattr(self, "_largura_legenda", 0):
            return

        self._redistribuindo_legenda = True
        self._largura_legenda = largura_disponivel
        for item in itens:
            item.grid_forget()

        largura_usada = 0
        linha = 0
        coluna = 0

        for item in itens:
            largura_item = item.winfo_reqwidth() + 4
            if coluna > 0 and largura_usada + largura_item > largura_disponivel:
                linha += 1
                coluna = 0
                largura_usada = 0

            item.grid(row=linha, column=coluna, padx=2, pady=1, sticky="w")
            largura_usada += largura_item
            coluna += 1
        self._redistribuindo_legenda = False

    def solicitar_distribuicao_legenda(self, event=None):
        if getattr(self, "_timer_legenda", None) is not None:
            try:
                self.root.after_cancel(self._timer_legenda)
            except tk.TclError:
                pass
        self._timer_legenda = None
        self._timer_legenda = self.root.after(
            180,
            self.executar_distribuicao_legenda,
        )

    def executar_distribuicao_legenda(self):
        self._timer_legenda = None
        self.distribuir_legenda_professores()

    def criar_canvas_grade(self, parent):
        canvas = tk.Canvas(parent, background="#ffffff", highlightthickness=0)
        barra_vertical = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        barra_horizontal = ttk.Scrollbar(parent, orient="horizontal", command=canvas.xview)
        canvas.configure(
            yscrollcommand=barra_vertical.set,
            xscrollcommand=barra_horizontal.set
        )

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        canvas.grid(row=0, column=0, sticky="nsew")
        barra_vertical.grid(row=0, column=1, sticky="ns")
        barra_horizontal.grid(row=1, column=0, sticky="ew")
        return canvas, barra_vertical, barra_horizontal

    def renomear_professor(self):
        selecionado = self.tv_prof.selection()
        if not selecionado:
            messagebox.showwarning("Aviso", "Selecione um professor na tabela primeiro!")
            return

        nome_atual = self.tv_prof.item(selecionado[0])['values'][0]
        novo_nome = simpledialog.askstring(
            "Renomear Professor",
            "Digite o novo nome do professor:",
            initialvalue=nome_atual,
            parent=self.root
        )
        if novo_nome is None:
            return

        novo_nome = novo_nome.strip().upper()
        if not novo_nome:
            messagebox.showwarning("Aviso", "O nome do professor não pode ficar vazio.")
            return
        if novo_nome == nome_atual:
            return
        if novo_nome in self.professores:
            messagebox.showwarning("Aviso", "Já existe um professor com esse nome.")
            return

        self.professores = {
            (novo_nome if nome == nome_atual else nome): dados
            for nome, dados in self.professores.items()
        }
        for requerimento in self.requerimentos:
            if requerimento['professor'] == nome_atual:
                requerimento['professor'] = novo_nome

        self.atualizar_tabela_professores()
        self.atualizar_combos()
        if self.cb_p.get() == nome_atual:
            self.cb_p.set(novo_nome)
        if self.cb_filtro_prof.get() == nome_atual:
            self.cb_filtro_prof.set(novo_nome)
        self.atualizar_tabela_req()
        messagebox.showinfo("Sucesso", f"Professor renomeado para {novo_nome}.")

    # ================= JANELA POP-UP DE RESTRIÇÕES =================
    def abrir_janela_restricoes(self, event=None):
        selecionado = self.tv_prof.selection()
        if not selecionado:
            messagebox.showwarning("Aviso", "Selecione um professor na tabela primeiro!")
            return
            
        nome_prof = self.tv_prof.item(selecionado[0])['values'][0]
        dados_prof = self.professores[nome_prof]
        
        janela = ttk.Toplevel(self.root)
        janela.title(f"⚙️ Restrições: {nome_prof}")
        janela.geometry("500x550")
        janela.grab_set() 
        
        ttk.Label(janela, text=f"Configurações Avançadas - {nome_prof}", font=("Arial", 12, "bold")).pack(pady=15)
        
        # --- Dias Evitados ---
        f_dias = ttk.Labelframe(janela, text="Turnos que prefere EVITAR", bootstyle="warning")
        f_dias.pack(fill="x", padx=20, pady=10)
        
        ttk.Label(f_dias, text="Manhã:").grid(row=0, column=0, padx=10, pady=5)
        ttk.Label(f_dias, text="Tarde:").grid(row=1, column=0, padx=10, pady=5)
        
        vars_m = []
        vars_t = []
        
        for i, d in enumerate(self.dias_semana):
            vm = tk.IntVar(value=1 if i in dados_prof.get("manha", []) else 0)
            ttk.Checkbutton(f_dias, text=d, variable=vm, bootstyle="round-toggle").grid(row=0, column=i+1, padx=5, pady=5)
            vars_m.append((i, vm))
            
            vt = tk.IntVar(value=1 if i in dados_prof.get("tarde", []) else 0)
            ttk.Checkbutton(f_dias, text=d, variable=vt, bootstyle="round-toggle").grid(row=1, column=i+1, padx=5, pady=5)
            vars_t.append((i, vt))

        # --- Bloqueios Exatos ---
        f_bloq = ttk.Labelframe(janela, text="Aulas INDISPONÍVEIS (Bloqueio Absoluto)", bootstyle="danger")
        f_bloq.pack(fill="x", padx=20, pady=10)
        
        f_inputs = ttk.Frame(f_bloq)
        f_inputs.pack(pady=5)
        
        cb_dia = ttk.Combobox(f_inputs, values=self.dias_semana, state="readonly", width=10)
        cb_dia.grid(row=0, column=0, padx=5)
        cb_dia.set("Segunda")
        
        cb_turno = ttk.Combobox(f_inputs, values=["Manhã", "Tarde"], state="readonly", width=8)
        cb_turno.grid(row=0, column=1, padx=5)
        cb_turno.set("Manhã")
        
        cb_aula = ttk.Combobox(f_inputs, values=["1ª", "2ª", "3ª", "4ª", "5ª"], state="readonly", width=5)
        cb_aula.grid(row=0, column=2, padx=5)
        cb_aula.set("1ª")
        
        list_bloqueios = tk.Listbox(f_bloq, height=4, font=("Arial", 9))
        list_bloqueios.pack(fill="x", padx=10, pady=5)
        
        bloqueios_temporarios = list(dados_prof.get("bloqueios", []))
        for b in bloqueios_temporarios: list_bloqueios.insert("end", b["texto"])
        
        def add_bloq():
            d = cb_dia.get(); t = cb_turno.get(); a = cb_aula.get()
            d_idx = self.dias_semana.index(d)
            a_idx = int(a.replace("ª", "")) - 1
            t_str = "M" if t == "Manhã" else "T"
            texto = f"{d} | {t} | {a} Aula"
            bloq = {"dia": d_idx, "turno": t_str, "aula": a_idx, "texto": texto}
            
            if bloq not in bloqueios_temporarios:
                bloqueios_temporarios.append(bloq)
                list_bloqueios.insert("end", texto)

        def rem_bloq():
            sel = list_bloqueios.curselection()
            if sel:
                idx = sel[0]
                list_bloqueios.delete(idx)
                bloqueios_temporarios.pop(idx)

        ttk.Button(f_inputs, text="➕", bootstyle="danger", command=add_bloq).grid(row=0, column=3, padx=5)
        ttk.Button(f_bloq, text="🗑️ Remover Selecionado", bootstyle="outline-danger", command=rem_bloq).pack(pady=5)

        # --- Salvar Pop-up ---
        def salvar():
            self.professores[nome_prof]["manha"] = [i for i, var in vars_m if var.get() == 1]
            self.professores[nome_prof]["tarde"] = [i for i, var in vars_t if var.get() == 1]
            self.professores[nome_prof]["bloqueios"] = bloqueios_temporarios
            self.atualizar_tabela_professores()
            janela.destroy()
            messagebox.showinfo("Sucesso", f"Restrições de {nome_prof} guardadas!")

        ttk.Button(janela, text="💾 Guardar Alteraçoes", bootstyle="success", command=salvar).pack(pady=20)

    # ================= OUTROS CADASTROS E CRUD =================
    def add_disc(self):
        disc = self.ent_disc.get().strip()
        if disc and disc not in self.disciplinas:
            self.disciplinas.append(disc); self.list_disc.insert("end", disc)
            self.ent_disc.delete(0, 'end'); self.atualizar_combos()

    def add_turma(self):
        nome = self.ent_turma.get().strip().upper()
        turno = self.combo_turno_turma.get()
        if not nome or not turno: return
        self.turmas[nome] = turno
        encontrado = False
        for item in self.tv_turma.get_children():
            if self.tv_turma.item(item)['values'][0] == nome:
                self.tv_turma.item(item, values=(nome, turno)); encontrado = True; break
        if not encontrado: self.tv_turma.insert("", "end", values=(nome, turno))
        self.ent_turma.delete(0, 'end'); self.atualizar_combos()

    def carregar_turma_para_editar(self, event):
        item_id = self.tv_turma.identify_row(event.y)
        if not item_id: return
        valores = self.tv_turma.item(item_id)['values']
        self.ent_turma.delete(0, 'end')
        self.ent_turma.insert(0, valores[0])
        self.combo_turno_turma.set(valores[1])

    def add_req(self):
        t, d, p, a = self.cb_t.get(), self.cb_d.get(), self.cb_p.get(), self.ent_a.get()
        if not t or not d or not p or not a.isdigit(): return messagebox.showwarning("Aviso", "Preencha corretamente.")
        self.requerimentos.append({'turma': t, 'disciplina': d, 'professor': p, 'aulas': int(a)})
        self.atualizar_tabela_req(); self.ent_a.delete(0, 'end')
        self.atualizar_tabela_professores() 
        
    def atualizar_tabela_req(self, event=None):
        filtro_turma = self.cb_filtro_turma.get()
        filtro_prof = self.cb_filtro_prof.get()
        
        # Limpa a tabela atual
        self.tv_req.delete(*self.tv_req.get_children())
        
        # Preenche apenas com a turma e professor selecionados
        for r in self.requerimentos:
            # Verifica se passa nos filtros (se estiver vazio ou em "Todos...", ele aprova)
            passa_turma = (not filtro_turma or filtro_turma == "Todas as Turmas" or r['turma'] == filtro_turma)
            passa_prof = (not filtro_prof or filtro_prof == "Todos os Professores" or r['professor'] == filtro_prof)
            
            # Se a linha respeitar os dois filtros, ela aparece na tabela
            if passa_turma and passa_prof:
                self.tv_req.insert("", "end", values=(r['turma'], r['disciplina'], r['professor'], r['aulas']))

    def limpar_filtro_req(self):
        self.cb_filtro_turma.set("Todas as Turmas")
        self.cb_filtro_prof.set("Todos os Professores")
        self.atualizar_tabela_req()
        
    def atualizar_combos(self):
        self.cb_t['values'] = sorted(self.turmas); self.cb_d['values'] = sorted(self.disciplinas); 
        self.cb_p['values'] = sorted(list(self.professores.keys())); 
        # Alimenta o combobox do filtro de turmas
        self.cb_filtro_turma['values'] = ["Todas as Turmas"] + list(self.turmas.keys())
        
        # Alimenta o combobox do filtro de professores (ADICIONE ESTA LINHA)
        self.cb_filtro_prof['values'] = ["Todos os Professores"] + list(self.professores.keys())
        if hasattr(self, "cb_prof_individual"):
            nomes_professores = sorted(self.professores)
            selecionado = self.cb_prof_individual.get()
            self.cb_prof_individual["values"] = nomes_professores
            if selecionado in nomes_professores:
                self.cb_prof_individual.set(selecionado)
            elif nomes_professores:
                self.cb_prof_individual.set(nomes_professores[0])
            self.atualizar_horario_individual()

    def excluir_item(self, widget, tipo):
        selecionado = widget.selection()
        if not selecionado: return
        item = selecionado[0]
        valores = widget.item(item)['values']
        if tipo == "prof": del self.professores[valores[0]]
        elif tipo == "turma": del self.turmas[valores[0]]
        elif tipo == "req":
            for r in self.requerimentos:
                if r['turma'] == valores[0] and r['disciplina'] == valores[1] and r['professor'] == valores[2] and str(r['aulas']) == str(valores[3]):
                    self.requerimentos.remove(r); break
        widget.delete(item)
        self.atualizar_combos()
        if tipo in ("prof", "req"): self.atualizar_tabela_professores()

    def excluir_listbox(self, lb, tipo):
        sel = lb.curselection()
        if not sel: return
        valor = lb.get(sel[0])
        if tipo == "disc" and valor in self.disciplinas: self.disciplinas.remove(valor)
        elif tipo == "turma" and valor in self.turmas: self.turmas.remove(valor)
        lb.delete(sel[0]); self.atualizar_combos()

    # ================= PRÉVIA EDITÁVEL =================
    def editar_aula_manual(self, event):
        tv_alvo = event.widget
        item_id = tv_alvo.identify_row(event.y)
        col_id = tv_alvo.identify_column(event.x)
        if not item_id or col_id in ("#1", "#2"): return
        self.abrir_editor_aula(tv_alvo, item_id, col_id)

    def editar_aula_visual(self, event, tv_alvo, canvas):
        x = canvas.canvasx(event.x)
        y = canvas.canvasy(event.y)
        zoom = getattr(self, "zoom_grade", 1.0)
        cabecalho_altura = int(30 * zoom)
        altura_linha = int(38 * zoom)
        larguras = self.larguras_grade(tv_alvo)

        if y < cabecalho_altura:
            return

        linha_idx = int((y - cabecalho_altura) // altura_linha)
        itens = tv_alvo.get_children()
        if linha_idx >= len(itens):
            return

        limite_x = 0
        coluna_idx = None
        for indice, largura in enumerate(larguras):
            if limite_x <= x < limite_x + largura:
                coluna_idx = indice
                break
            limite_x += largura

        if coluna_idx is None or coluna_idx < 2:
            return

        item_id = itens[linha_idx]
        if "---" in str(tv_alvo.item(item_id)['values'][0]):
            return
        self.abrir_editor_aula(tv_alvo, item_id, f"#{coluna_idx + 1}")

    def abrir_editor_aula(self, tv_alvo, item_id, col_id):
        valores_atuais = list(tv_alvo.item(item_id)['values'])
        if "---" in str(valores_atuais[0]): return
        
        col_idx = int(col_id.replace("#", "")) - 1
        turma_nome = tv_alvo.heading(col_id)['text']
        
        janela_ed = ttk.Toplevel(self.root)
        janela_ed.title(f"Editar: {turma_nome}")
        janela_ed.geometry("350x180")
        
        ttk.Label(janela_ed, text=f"Selecione a nova aula:", font=("Arial", 10, "bold")).pack(pady=15)
        opcoes = ["- LIVRE -"]
        for r in self.requerimentos:
            if r['turma'] == turma_nome: opcoes.append(f"{r['disciplina']} ({r['professor']})")
                
        combo_ed = ttk.Combobox(janela_ed, values=opcoes, state="readonly", width=30)
        combo_ed.set(valores_atuais[col_idx] if valores_atuais[col_idx] else "- LIVRE -")
        combo_ed.pack(pady=5)
        
        def confirmar():
            novo_valor = combo_ed.get()
            if novo_valor != "- LIVRE -":
                prof_selecionado = novo_valor.split("(")[1].replace(")", "")
                for cid, val in enumerate(valores_atuais):
                    if cid != col_idx and val and "(" in str(val):
                        if prof_selecionado == str(val).split("(")[1].replace(")", ""):
                            messagebox.showerror("Erro!", f"Professor já alocado nesta turma noutra aba!")
                            janela_ed.lift(); return
            valor_antigo = valores_atuais[col_idx]
            self.registrar_edicao_aprendida(
                tv_alvo,
                item_id,
                col_idx,
                valor_antigo,
                novo_valor,
            )
            valores_atuais[col_idx] = "" if novo_valor == "- LIVRE -" else novo_valor
            tv_alvo.item(item_id, values=valores_atuais)
            canvas = self.canvas_previa_manha if tv_alvo is self.tv_previa_manha else self.canvas_previa_tarde
            self.renderizar_grade_colorida(tv_alvo, canvas)
            self.atualizar_horario_individual()
            janela_ed.destroy()
            
        ttk.Button(janela_ed, text="✅ Confirmar", bootstyle="success", command=confirmar).pack(pady=15)

    # ================= ALGORITMO E GERAÇÃO =================
    def validar_dados_antes_de_gerar(self):
        aulas_manha = int(self.spin_manha.get())
        aulas_tarde = int(self.spin_tarde.get())
        total_dias = len(self.dias_semana)
        aulas_por_turma = {}

        for req in self.requerimentos:
            turma = req.get('turma')
            qtd_aulas = int(req.get('aulas', 0))
            aulas_por_turma[turma] = aulas_por_turma.get(turma, 0) + qtd_aulas

        for turma, total in aulas_por_turma.items():
            turno_turma = self.turmas.get(turma, "Manhã")
            max_aulas_semana = total_dias * aulas_manha if turno_turma == "Manhã" else total_dias * aulas_tarde
            if total > max_aulas_semana:
                messagebox.showerror("Erro de Validação", f"A turma {turma} ({turno_turma}) exige {total} aulas, mas a semana configurada só comporta {max_aulas_semana}!")
                return False

        return True
    
    def iniciar_geracao(self):
        if not self.requerimentos: return messagebox.showwarning("Aviso", "A grade está vazia!")
        if not self.validar_dados_antes_de_gerar(): return 
        self.btn_gerar.config(state="disabled"); self.btn_exportar.config(state="disabled"); self.btn_exportar_pdf.config(state="disabled")
        self.lbl_status.config(text="Status: Calculando a melhor rota matemática...", bootstyle="warning")
        
        self.tv_previa_manha.delete(*self.tv_previa_manha.get_children()); self.tv_previa_manha["columns"] = ()
        self.tv_previa_tarde.delete(*self.tv_previa_tarde.get_children()); self.tv_previa_tarde["columns"] = ()
        self.canvas_previa_manha.delete("all")
        self.canvas_previa_tarde.delete("all")
        self._usar_triplas = bool(self.var_agrupar_triplas.get()) if hasattr(self, "var_agrupar_triplas") else False
        self.notebook.select(self.aba_grade)
        
        self.progresso_var.set(0)
        threading.Thread(target=self.processar_algoritmo).start()
      
    # Motor híbrido Ortools + Algorítmo Genético  
    def processar_algoritmo(self):
        import time
        from tkinter import messagebox
        from motor.gerenciador import gerar_grade_inteligente

        def atualizar_ui(pct, texto):
            def aplicar_status():
                self.progresso_var.set(pct)
                self.lbl_status.config(text=texto, bootstyle="info")
                if hasattr(self, "lbl_status_grade"):
                    self.lbl_status_grade.config(text=texto, bootstyle="info")

            self.root.after(0, aplicar_status)

        def atualizar_grade_vivo(grade_preview):
            def aplicar_preview():
                self.animar_grade_vivo(
                    grade_preview,
                    int(self.spin_manha.get()),
                    int(self.spin_tarde.get()),
                )
                self.root.update_idletasks()

            self.root.after(0, aplicar_preview)

        try:
            t0 = time.time()
            if hasattr(self, "btn_gerar"):
                self.btn_gerar.config(state="disabled")

            atualizar_ui(10, "Status: A analisar hardware e viabilidade do horário...")

            dias = len(self.dias_semana)
            aulas_manha = int(self.spin_manha.get())
            aulas_tarde = int(self.spin_tarde.get())
            total_aulas_dia = aulas_manha + aulas_tarde

            horarios_m = getattr(self, "horarios_m_custom", [f"{i+1}ª Aula (Manhã)" for i in range(aulas_manha)])
            horarios_t = getattr(self, "horarios_t_custom", [f"{i+1}ª Aula (Tarde)" for i in range(aulas_tarde)])

            self._analisador_grade_vivo = {
                "manha": self.ordenar_turmas_naturalmente([
                    turma for turma, turno in self.turmas.items()
                    if str(turno).strip().lower().startswith("m")
                ]),
                "tarde": self.ordenar_turmas_naturalmente([
                    turma for turma, turno in self.turmas.items()
                    if not str(turno).strip().lower().startswith("m")
                ]),
            }
            self.root.after(0, lambda: self.lbl_status.config(
                text="Status: Montando aulas ao vivo...",
                bootstyle="warning",
            ))

            resultado = gerar_grade_inteligente(
                self.dias_semana, aulas_manha, aulas_tarde,
                self.turmas, self.professores, self.requerimentos,
                callback_progresso=atualizar_ui,
                agrupar_triplas=getattr(self, "_usar_triplas", False),
                historico_aprendizado=self.historico_aprendizado,
                callback_grade=atualizar_grade_vivo,
            )

            if not resultado:
                self.progresso_var.set(0)
                self.lbl_status.config(text="Status: Sem solução possível.", bootstyle="danger")
                messagebox.showerror("Aviso", "Nenhum motor encontrou combinação válida.")
                return

            atualizar_ui(90, f"Status: A desenhar tabelas ({resultado['motor']})...")

            self.preparar_tabelas_previa()
            self.tv_previa_manha.delete(*self.tv_previa_manha.get_children())
            self.tv_previa_tarde.delete(*self.tv_previa_tarde.get_children())

            analisador = resultado["analisador"]
            grade = resultado["grade"]
            self.registrar_grade_aprendida(grade, resultado["motor"])

            turmas_m = self.ordenar_turmas_naturalmente([t for t in self.turmas if analisador.eh_manha(t)])
            turmas_t = self.ordenar_turmas_naturalmente([t for t in self.turmas if not analisador.eh_manha(t)])

            for tv, turmas_lista, offset, h_custom, qtd_aulas in (
                (self.tv_previa_manha, turmas_m, 0, horarios_m, aulas_manha),
                (self.tv_previa_tarde, turmas_t, aulas_manha, horarios_t, aulas_tarde),
            ):
                sep = ["-" * 10] * (2 + len(turmas_lista))
                for d in range(dias):
                    dia_nome = self.dias_semana[d] if d < len(self.dias_semana) else f"Dia {d + 1}"
                    for a in range(qtd_aulas):
                        g_a = offset + a
                        h_str = h_custom[a] if a < len(h_custom) else f"{a + 1}º Horário"
                        linha = [dia_nome, h_str] + [
                            f"{self.requerimentos[grade[(t, d, g_a)]]['disciplina']} ({self.requerimentos[grade[(t, d, g_a)]]['professor']})"
                            if (t, d, g_a) in grade else "---"
                            for t in turmas_lista
                        ]
                        tv.insert("", "end", values=linha)
                    if qtd_aulas > 0:
                        tv.insert("", "end", values=sep)

            self.renderizar_grade_colorida(self.tv_previa_manha, self.canvas_previa_manha)
            self.renderizar_grade_colorida(self.tv_previa_tarde, self.canvas_previa_tarde)
            self.atualizar_horario_individual()

            tempo = time.time() - t0
            self.progresso_var.set(100)
            self.lbl_status.config(
                text=f"Status: Concluído via {resultado['motor']} em {tempo:.1f}s! (100% alocado)",
                bootstyle="success"
            )

            if resultado["concessoes"]:
                messagebox.showinfo(
                    f"Grade 100% Fechada ({resultado['motor']})",
                    f"Motor escolhido para este PC/Horário: {resultado['motor']}\n"
                    "Todas as aulas foram alocadas sem deixar NENHUM horário vago!\n\n"
                    "Ajuste pontual de aula avulsa por falta física de professores no horário:\n"
                    + "\n".join(resultado["concessoes"])
                )

            self.atualizar_dashboard(resultado["adapter"], resultado["alocacoes"], aulas_manha, total_aulas_dia)
            self.btn_exportar.config(state="normal")
            self.btn_exportar_pdf.config(state="normal")

        except Exception as e:
            self.progresso_var.set(0)
            self.lbl_status.config(text="Status: Erro na geração.", bootstyle="danger")
            messagebox.showerror("Erro de Execução", f"Ocorreu um erro:\n{str(e)}")

        finally:
            if hasattr(self, "btn_gerar"):
                self.btn_gerar.config(state="normal")               
                    
               
    def preparar_tabelas_previa(self):
        turmas_manha = self.ordenar_turmas_naturalmente([t for t, turno in self.turmas.items() if turno == "Manhã"])
        turmas_tarde = self.ordenar_turmas_naturalmente([t for t, turno in self.turmas.items() if turno == "Tarde"])
        
        colunas_m = ["Dia", "Horário"] + turmas_manha
        self.tv_previa_manha["columns"] = colunas_m
        for col in colunas_m:
            self.tv_previa_manha.heading(col, text=col, anchor="center")
            if col == "Dia": self.tv_previa_manha.column(col, width=80, minwidth=80, anchor="center", stretch=False)
            elif col == "Horário": self.tv_previa_manha.column(col, width=120, minwidth=120, anchor="w", stretch=False)
            else: self.tv_previa_manha.column(col, width=140, minwidth=100, anchor="center")
            
        colunas_t = ["Dia", "Horário"] + turmas_tarde
        self.tv_previa_tarde["columns"] = colunas_t
        for col in colunas_t:
            self.tv_previa_tarde.heading(col, text=col, anchor="center")
            if col == "Dia": self.tv_previa_tarde.column(col, width=80, minwidth=80, anchor="center", stretch=False)
            elif col == "Horário": self.tv_previa_tarde.column(col, width=120, minwidth=120, anchor="w", stretch=False)
            else: self.tv_previa_tarde.column(col, width=140, minwidth=100, anchor="center")

    def animar_grade_vivo(self, grade_preview, aulas_manha, aulas_tarde, horarios_m=None, horarios_t=None):
        if not hasattr(self, "tv_previa_manha"):
            return

        analisador_turnos = getattr(self, "_analisador_grade_vivo", None)
        if not analisador_turnos:
            turmas_m = self.ordenar_turmas_naturalmente([
                turma for turma, turno in self.turmas.items()
                if str(turno).strip().lower().startswith("m")
            ])
            turmas_t = self.ordenar_turmas_naturalmente([
                turma for turma, turno in self.turmas.items()
                if not str(turno).strip().lower().startswith("m")
            ])
        else:
            turmas_m = analisador_turnos["manha"]
            turmas_t = analisador_turnos["tarde"]

        if not horarios_m:
            horarios_m = getattr(
                self,
                "horarios_m_custom",
                [f"{indice + 1}ª Aula (Manhã)" for indice in range(aulas_manha)],
            )
        if not horarios_t:
            horarios_t = getattr(
                self,
                "horarios_t_custom",
                [f"{indice + 1}ª Aula (Tarde)" for indice in range(aulas_tarde)],
            )

        colunas_m = ["Dia", "Horário"] + turmas_m
        colunas_t = ["Dia", "Horário"] + turmas_t
        if list(self.tv_previa_manha["columns"]) != colunas_m:
            self.tv_previa_manha["columns"] = colunas_m
            for coluna in colunas_m:
                self.tv_previa_manha.heading(coluna, text=coluna, anchor="center")
        if list(self.tv_previa_tarde["columns"]) != colunas_t:
            self.tv_previa_tarde["columns"] = colunas_t
            for coluna in colunas_t:
                self.tv_previa_tarde.heading(coluna, text=coluna, anchor="center")

        for tv, turmas_lista, offset, horarios, quantidade in (
            (self.tv_previa_manha, turmas_m, 0, horarios_m, aulas_manha),
            (self.tv_previa_tarde, turmas_t, aulas_manha, horarios_t, aulas_tarde),
        ):
            tv.delete(*tv.get_children())
            for dia in range(len(self.dias_semana)):
                for aula in range(quantidade):
                    horario_global = offset + aula
                    linha = [
                        self.dias_semana[dia],
                        horarios[aula] if aula < len(horarios) else f"{aula + 1}ª Aula",
                    ]
                    for turma in turmas_lista:
                        r_idx = grade_preview.get((turma, dia, horario_global))
                        if r_idx is not None:
                            req = self.requerimentos[r_idx]
                            linha.append(f"{req['disciplina']} ({req['professor']})")
                        else:
                            linha.append("---")
                    tv.insert("", "end", values=linha)

        self.renderizar_grade_colorida(
            self.tv_previa_manha,
            self.canvas_previa_manha,
        )
        self.renderizar_grade_colorida(
            self.tv_previa_tarde,
            self.canvas_previa_tarde,
        )

    def larguras_grade(self, treeview):
        return [
            90 if indice == 0 else 150 if indice == 1 else 190
            for indice, _ in enumerate(treeview["columns"])
        ]

    def alterar_zoom_grade(self, incremento):
        novo_zoom = round(max(0.60, min(1.40, self.zoom_grade + incremento)), 2)
        self.definir_zoom_grade(novo_zoom)

    def definir_zoom_grade(self, novo_zoom):
        self.zoom_grade = round(max(0.60, min(1.40, novo_zoom)), 2)
        if hasattr(self, "lbl_zoom_grade"):
            self.lbl_zoom_grade.configure(text=f"{int(self.zoom_grade * 100)}%")
        if hasattr(self, "tv_previa_manha"):
            self.renderizar_grade_colorida(
                self.tv_previa_manha,
                self.canvas_previa_manha,
            )
        if hasattr(self, "tv_previa_tarde"):
            self.renderizar_grade_colorida(
                self.tv_previa_tarde,
                self.canvas_previa_tarde,
            )

    def zoom_mouse_grade(self, event):
        incremento = 0.10 if event.delta > 0 else -0.10
        self.alterar_zoom_grade(incremento)
        return "break"

    def cor_professor(self, nome_professor):
        nome_professor = str(nome_professor).strip().upper()
        professores = [nome.upper() for nome in self.professores]
        if nome_professor not in professores:
            return "#FFFFFF"
        indice = professores.index(nome_professor)
        return self.paleta_professores[indice % len(self.paleta_professores)]

    def extrair_professor_da_aula(self, valor):
        texto = str(valor).strip()
        if "(" not in texto or not texto.endswith(")"):
            return ""
        return texto.rsplit("(", 1)[1][:-1].strip()

    def cor_do_texto(self, cor):
        vermelho = int(cor[1:3], 16)
        verde = int(cor[3:5], 16)
        azul = int(cor[5:7], 16)
        luminancia = 0.299 * vermelho + 0.587 * verde + 0.114 * azul
        return "#000000" if luminancia > 145 else "#FFFFFF"

    def renderizar_grade_colorida(self, treeview, canvas):
        canvas.delete("all")
        colunas = list(treeview["columns"])
        if not colunas:
            canvas.configure(scrollregion=(0, 0, 0, 0))
            return

        larguras = self.larguras_grade(treeview)
        zoom = getattr(self, "zoom_grade", 1.0)
        larguras = [int(largura * zoom) for largura in larguras]
        cabecalho_altura = int(30 * zoom)
        altura_linha = int(38 * zoom)
        largura_total = sum(larguras)
        itens = treeview.get_children()

        x_atual = 0
        for indice, coluna in enumerate(colunas):
            canvas.create_rectangle(
                x_atual, 0, x_atual + larguras[indice], cabecalho_altura,
                fill="#17324d", outline="#d5dde5"
            )
            tamanho_fonte = max(7, int(8 * zoom))
            canvas.create_text(
                x_atual + larguras[indice] / 2,
                cabecalho_altura / 2,
                text=treeview.heading(coluna)["text"],
                fill="#FFFFFF",
                font=("Segoe UI", tamanho_fonte, "bold")
            )
            x_atual += larguras[indice]

        for linha_idx, item_id in enumerate(itens):
            valores = list(treeview.item(item_id)["values"])
            eh_separador = valores and "---" in str(valores[0])
            y_atual = cabecalho_altura + linha_idx * altura_linha
            x_atual = 0

            for coluna_idx, largura in enumerate(larguras):
                valor = str(valores[coluna_idx]) if coluna_idx < len(valores) else ""
                cor_fundo = "#eef2f6" if coluna_idx < 2 else "#FFFFFF"
                cor_texto = "#263238"
                texto_linhas = valor

                if eh_separador:
                    cor_fundo = "#dce5ed"
                    valor = ""
                    texto_linhas = ""
                elif coluna_idx >= 2 and valor and valor != "---":
                    nome_professor = self.extrair_professor_da_aula(valor)
                    cor_fundo = self.cor_professor(nome_professor)
                    cor_texto = self.cor_do_texto(cor_fundo)
                    if nome_professor:
                        nome_disciplina = valor.rsplit("(", 1)[0].strip()
                        texto_linhas = f"{nome_disciplina}\n{nome_professor}"
                elif valor == "---":
                    valor = "—"
                    texto_linhas = "—"
                    cor_texto = "#9aa7b2"

                canvas.create_rectangle(
                    x_atual, y_atual,
                    x_atual + largura, y_atual + altura_linha,
                    fill=cor_fundo, outline="#d5dde5"
                )
                canvas.create_text(
                    x_atual + largura / 2,
                    y_atual + altura_linha / 2,
                    text=texto_linhas,
                    fill=cor_texto,
                    font=("Segoe UI", max(7, int(8 * zoom)), "bold" if coluna_idx >= 2 and valor not in ("", "—") else "normal"),
                    width=max(40, largura - int(10 * zoom)),
                    justify="center"
                )
                x_atual += largura

        altura_total = cabecalho_altura + len(itens) * altura_linha
        canvas.configure(scrollregion=(0, 0, largura_total, altura_total))

    def ordenar_turmas_naturalmente(self, lista_turmas):
        def chave_alfa_numerica(texto): return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', texto)]
        return sorted(lista_turmas, key=chave_alfa_numerica)

    def abrir_janela_horarios(self):
        janela = ttk.Toplevel(self.root)
        janela.title("Configurar Horários das Aulas")
        janela.geometry("500x600")
        janela.grab_set() 

        if not hasattr(self, 'horarios_m_custom'): self.horarios_m_custom = []
        if not hasattr(self, 'horarios_t_custom'): self.horarios_t_custom = []

        aulas_m = int(self.spin_manha.get())
        aulas_t = int(self.spin_tarde.get())

        f_m = ttk.Labelframe(janela, text="☀️ Turno da Manhã", bootstyle="primary")
        f_m.pack(fill="x", padx=20, pady=10)
        
        self.entradas_m = []
        for i in range(aulas_m):
            ttk.Label(f_m, text=f"{i+1}ª Aula:").grid(row=i, column=0, padx=10, pady=5, sticky="e")
            ent = ttk.Entry(f_m, width=30)
            if i < len(self.horarios_m_custom): ent.insert(0, self.horarios_m_custom[i])
            else: ent.insert(0, f"{i+1}° aula: {7+i}:30 às {8+i}:20")
            ent.grid(row=i, column=1, padx=10, pady=5)
            self.entradas_m.append(ent)

        f_t = ttk.Labelframe(janela, text="🌆 Turno da Tarde", bootstyle="warning")
        f_t.pack(fill="x", padx=20, pady=10)
        
        self.entradas_t = []
        for i in range(aulas_t):
            ttk.Label(f_t, text=f"{i+1}ª Aula:").grid(row=i, column=0, padx=10, pady=5, sticky="e")
            ent = ttk.Entry(f_t, width=30)
            if i < len(self.horarios_t_custom): ent.insert(0, self.horarios_t_custom[i])
            else: ent.insert(0, f"{i+1}° aula: {13+i}:00 às {13+i}:50")
            ent.grid(row=i, column=1, padx=10, pady=5)
            self.entradas_t.append(ent)
            
        ttk.Button(janela, text="💾 Salvar e Fechar", bootstyle="success", command=lambda: self.salvar_horarios_custom(janela)).pack(pady=20)

    def salvar_horarios_custom(self, janela):
        self.horarios_m_custom = [ent.get() for ent in self.entradas_m]
        self.horarios_t_custom = [ent.get() for ent in self.entradas_t]
        janela.destroy()

    def criar_card_dashboard(self, parent, titulo, valor, coluna, bootstyle):
        card = ttk.Labelframe(
            parent,
            text=titulo,
            bootstyle=bootstyle,
            padding=(10, 10)
        )
        card.grid(row=0, column=coluna, sticky="nsew", padx=5)
        label = ttk.Label(
            card,
            text=valor,
            font=("Segoe UI", 20, "bold"),
            anchor="center"
        )
        label.pack(fill="both", expand=True)
        return label

    def rolar_dashboard_com_mouse(self, event):
        canvas = getattr(self, "canvas_dashboard", None)
        if canvas is None:
            return

        widget_path = str(event.widget)
        canvas_path = str(canvas)
        if widget_path != canvas_path and not widget_path.startswith(canvas_path + "."):
            return

        unidades = int(-event.delta / 120)
        if unidades == 0:
            unidades = -1 if event.delta > 0 else 1
        canvas.yview_scroll(unidades, "units")
        return "break"

    def atualizar_card_dashboard(self, label, valor):
        if hasattr(label, "configure"):
            label.configure(text=str(valor))

    def atualizar_horario_individual(self):
        if not hasattr(self, "canvas_prof_ind_manha"):
            return

        professor = getattr(self, "cb_prof_individual", None)
        nome_professor = professor.get().strip().upper() if professor is not None else ""
        carga_total = 0

        def extrair_professor(valor):
            texto = str(valor).strip()
            if "\n" in texto:
                return texto.split("\n")[-1].strip().upper()
            if "(" in texto and texto.endswith(")"):
                return texto.rsplit("(", 1)[1].rstrip(")").strip().upper()
            return ""

        def extrair_disciplina(valor):
            texto = str(valor).strip()
            if "\n" in texto:
                return texto.split("\n")[0].strip()
            if "(" in texto:
                return texto.rsplit("(", 1)[0].strip()
            return texto

        def renderizar_grade_individual(treeview, canvas):
            nonlocal carga_total
            canvas.delete("all")
            colunas = list(treeview["columns"])
            itens = treeview.get_children()
            if not colunas:
                canvas.configure(scrollregion=(0, 0, 0, 0))
                return

            zoom = self.zoom_grade_individual
            largura_dia = max(1, int(90 * zoom))
            largura_horario = max(1, int(150 * zoom))
            largura_turma = max(1, int(190 * zoom))
            altura_cabecalho = max(1, int(32 * zoom))
            altura_linha = max(1, int(38 * zoom))
            larguras = [largura_dia, largura_horario] + [
                largura_turma for _ in colunas[2:]
            ]
            largura_total = sum(larguras)
            altura_total = altura_cabecalho + len(itens) * altura_linha

            x_atual = 0
            for indice, coluna in enumerate(colunas):
                largura = larguras[indice] if indice < len(larguras) else largura_turma
                canvas.create_rectangle(
                    x_atual, 0, x_atual + largura, altura_cabecalho,
                    fill="#17324d", outline="#d5dde5"
                )
                canvas.create_text(
                    x_atual + largura / 2,
                    altura_cabecalho / 2,
                    text=treeview.heading(coluna)["text"],
                    fill="#ffffff",
                    font=("Segoe UI", max(6, round(8 * zoom)), "bold")
                )
                x_atual += largura

            for linha_idx, item_id in enumerate(itens):
                valores = list(treeview.item(item_id)["values"])
                y = altura_cabecalho + linha_idx * altura_linha
                eh_separador = valores and "---" in str(valores[0])
                x_atual = 0

                for coluna_idx, largura in enumerate(larguras):
                    valor = str(valores[coluna_idx]) if coluna_idx < len(valores) else ""
                    fundo = "#edf2f7" if coluna_idx < 2 else "#f7f9fb"
                    cor_texto = "#263238"
                    texto = valor

                    if eh_separador:
                        fundo = "#dce5ed"
                        texto = ""
                    elif coluna_idx >= 2 and valor and valor != "---":
                        professor_celula = extrair_professor(valor)
                        if professor_celula == nome_professor:
                            fundo = self.cor_professor(nome_professor)
                            cor_texto = self.cor_do_texto(fundo)
                            texto = (
                                f"{str(treeview.heading(colunas[coluna_idx])['text'])}\n"
                                f"{extrair_disciplina(valor)}"
                            )
                            carga_total += 1
                        else:
                            texto = ""
                    elif valor == "---":
                        texto = ""

                    canvas.create_rectangle(
                        x_atual, y, x_atual + largura, y + altura_linha,
                        fill=fundo, outline="#d5dde5"
                    )
                    if texto:
                        canvas.create_text(
                            x_atual + largura / 2,
                            y + altura_linha / 2,
                            text=texto,
                            fill=cor_texto,
                            font=("Segoe UI", max(6, round(8 * zoom)), "bold"),
                            width=largura - 12,
                            justify="center"
                        )
                    x_atual += largura

            canvas.configure(scrollregion=(0, 0, largura_total, altura_total))

        renderizar_grade_individual(
            self.tv_previa_manha,
            self.canvas_prof_ind_manha,
        )
        renderizar_grade_individual(
            self.tv_previa_tarde,
            self.canvas_prof_ind_tarde,
        )

        if hasattr(self, "lbl_carga_individual"):
            self.lbl_carga_individual.configure(
                text=f"{carga_total} aula(s) na semana"
            )

    def alterar_zoom_grade_individual(self, incremento):
        novo_zoom = round(
            max(0.60, min(1.40, self.zoom_grade_individual + incremento)),
            2
        )
        self.definir_zoom_grade_individual(novo_zoom)

    def definir_zoom_grade_individual(self, novo_zoom):
        self.zoom_grade_individual = round(max(0.60, min(1.40, novo_zoom)), 2)
        if hasattr(self, "lbl_zoom_grade_individual"):
            self.lbl_zoom_grade_individual.configure(
                text=f"{int(self.zoom_grade_individual * 100)}%"
            )
        self.atualizar_horario_individual()

    def zoom_mouse_grade_individual(self, event):
        incremento = 0.10 if event.delta > 0 else -0.10
        self.alterar_zoom_grade_individual(incremento)
        return "break"

    def desenhar_grafico_carga(self, dados):
        canvas = getattr(self, "canvas_carga_professores", None)
        if canvas is None:
            return

        canvas.delete("all")
        largura = max(canvas.winfo_width(), 300)
        altura = max(canvas.winfo_height(), 220)
        margem_esquerda = 110
        margem_direita = 35
        margem_superior = 18
        margem_inferior = 18

        if not dados:
            canvas.create_text(
                largura / 2,
                altura / 2,
                text="Gere uma grade para visualizar a carga",
                fill="#78909c",
                font=("Segoe UI", 10)
            )
            return

        maior_carga = max([item["total"] for item in dados] or [1])
        altura_calculada = max(220, margem_superior + len(dados) * 34 + margem_inferior)
        area = largura - margem_esquerda - margem_direita
        altura_linha = 34

        canvas.configure(scrollregion=(0, 0, largura, altura_calculada))

        escala_maxima = max(5, maior_carga)
        for divisao in range(0, escala_maxima + 1, max(1, escala_maxima // 5)):
            x = margem_esquerda + area * divisao / escala_maxima
            canvas.create_line(
                x,
                margem_superior,
                x,
                altura_calculada - margem_inferior,
                fill="#dfe6ec",
                dash=(2, 3)
            )
            canvas.create_text(
                x,
                altura_calculada - 6,
                text=str(divisao),
                anchor="n",
                fill="#78909c",
                font=("Segoe UI", 7)
            )

        for indice, item in enumerate(dados):
            y = margem_superior + indice * altura_linha + altura_linha / 2
            nome = item["prof"]
            nome_visual = nome if len(nome) <= 16 else nome[:14] + "..."
            canvas.create_text(
                margem_esquerda - 8,
                y,
                text=nome_visual,
                anchor="e",
                fill="#263238",
                font=("Segoe UI", 8, "bold")
            )

            largura_barra = 0
            if maior_carga > 0:
                largura_barra = area * item["total"] / maior_carga
            canvas.create_rectangle(
                margem_esquerda,
                y - 8,
                margem_esquerda + area,
                y + 8,
                fill="#edf2f7",
                outline=""
            )
            cor = self.paleta_professores[indice % len(self.paleta_professores)]
            canvas.create_rectangle(
                margem_esquerda,
                y - 8,
                margem_esquerda + largura_barra,
                y + 8,
                fill=cor,
                outline=""
            )
            canvas.create_text(
                margem_esquerda + largura_barra + 8,
                y,
                text=str(item["total"]),
                anchor="w",
                fill="#263238",
                font=("Segoe UI", 8, "bold")
            )

    def desenhar_grafico_qualidade(self, dados):
        canvas = getattr(self, "canvas_qualidade", None)
        if canvas is None:
            return

        canvas.delete("all")
        largura = max(canvas.winfo_width(), 220)
        altura = max(canvas.winfo_height(), 220)

        perfeitos = sum(1 for item in dados if item["penalidades"] == 0)
        com_penalidade = len(dados) - perfeitos
        total = len(dados)

        canvas.create_text(
            largura / 2,
            20,
            text="Professores sem penalidades",
            fill="#263238",
            font=("Segoe UI", 9, "bold")
        )

        if total == 0:
            canvas.create_text(
                largura / 2,
                altura / 2,
                text="Sem dados",
                fill="#78909c",
                font=("Segoe UI", 10)
            )
            return

        cx = largura / 2
        cy = altura / 2 + 8
        raio_exterior = min(largura, altura) * 0.27
        raio_interno = raio_exterior * 0.62

        def ponto(x, y, raio, angulo):
            import math
            rad = math.radians(angulo)
            return x + raio * math.cos(rad), y + raio * math.sin(rad)

        canvas.create_oval(
            cx - raio_exterior,
            cy - raio_exterior,
            cx + raio_exterior,
            cy + raio_exterior,
            fill="#ede7f6",
            outline=""
        )

        if perfeitos > 0:
            angulo_perfeitos = 360 * perfeitos / total
            canvas.create_arc(
                cx - raio_exterior,
                cy - raio_exterior,
                cx + raio_exterior,
                cy + raio_exterior,
                start=90,
                extent=-angulo_perfeitos,
                fill="#2E7D32",
                outline="#2E7D32"
            )

        canvas.create_oval(
            cx - raio_interno,
            cy - raio_interno,
            cx + raio_interno,
            cy + raio_interno,
            fill="#ffffff",
            outline=""
        )
        percentual = round(perfeitos * 100 / total)
        canvas.create_text(
            cx,
            cy - 5,
            text=f"{percentual}%",
            fill="#263238",
            font=("Segoe UI", 17, "bold")
        )
        canvas.create_text(
            cx,
            cy + 18,
            text="ideal",
            fill="#78909c",
            font=("Segoe UI", 8)
        )

        canvas.create_rectangle(
            cx - 65,
            cy + raio_exterior + 12,
            cx - 55,
            cy + raio_exterior + 22,
            fill="#2E7D32",
            outline=""
        )
        canvas.create_text(
            cx - 48,
            cy + raio_exterior + 17,
            text=f"{perfeitos} perfeitos",
            anchor="w",
            fill="#263238",
            font=("Segoe UI", 8)
        )
        canvas.create_rectangle(
            cx - 65,
            cy + raio_exterior + 28,
            cx - 55,
            cy + raio_exterior + 38,
            fill="#C62828",
            outline=""
        )
        canvas.create_text(
            cx - 48,
            cy + raio_exterior + 33,
            text=f"{com_penalidade} com ajuste",
            anchor="w",
            fill="#263238",
            font=("Segoe UI", 8)
        )

    def atualizar_dashboard(self, solver, alocacoes, aulas_manha, total_aulas_dia):
        self.tv_dash.delete(*self.tv_dash.get_children())
        dados_dashboard = []
        total_aulas_grade = 0
        total_penalidades = 0

        for prof, dados in self.professores.items():
            total_aulas = 0; aulas_penalizadas = 0
            off_manha = dados.get("manha", []); off_tarde = dados.get("tarde", [])
            for r_idx, req in enumerate(self.requerimentos):
                if req['professor'] == prof:
                    for d in range(len(self.dias_semana)):
                        for a in range(total_aulas_dia):
                            if (r_idx, d, a) in alocacoes and solver.Value(alocacoes[(r_idx, d, a)]) == 1:
                                total_aulas += 1
                                if a < aulas_manha and d in off_manha: aulas_penalizadas += 1
                                elif a >= aulas_manha and d in off_tarde: aulas_penalizadas += 1

            aproveitamento = 100 if total_aulas == 0 else round((total_aulas - aulas_penalizadas) * 100 / total_aulas)
            status = "✅ Perfeito" if aulas_penalizadas == 0 else f"⚠️ Ajustar"
            tag = "perfeito" if aulas_penalizadas == 0 else "aviso"
            item = self.tv_dash.insert(
                "",
                "end",
                values=(prof, total_aulas, aulas_penalizadas, f"{aproveitamento}%", status),
                tags=(tag,)
            )

            dados_dashboard.append({
                "prof": prof,
                "total": total_aulas,
                "penalidades": aulas_penalizadas,
                "aproveitamento": aproveitamento,
            })
            total_aulas_grade += total_aulas
            total_penalidades += aulas_penalizadas

        self.tv_dash.configure(height=max(1, len(dados_dashboard)))
        perfeitos = sum(1 for item in dados_dashboard if item["penalidades"] == 0)

        self.atualizar_card_dashboard(
            self.dash_card_professores,
            len(dados_dashboard),
        )
        self.atualizar_card_dashboard(
            self.dash_card_aulas,
            total_aulas_grade,
        )
        self.atualizar_card_dashboard(
            self.dash_card_perfeitos,
            perfeitos,
        )
        self.atualizar_card_dashboard(
            self.dash_card_penalidades,
            total_penalidades,
        )

        dados_dashboard.sort(key=lambda item: item["total"], reverse=True)
        self._dados_dashboard = dados_dashboard
        self.root.after_idle(lambda: self.desenhar_grafico_carga(dados_dashboard))
        self.root.after_idle(lambda: self.desenhar_grafico_qualidade(dados_dashboard))

    # ================= EXPORTAÇÕES (EXCEL E PDF PREMIUM) =================
    def salvar_excel(self):
        from openpyxl import Workbook 
        from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
        from tkinter import filedialog, messagebox
        
        caminho = filedialog.asksaveasfilename(
            defaultextension=".xlsx", 
            initialfile="Horario.xlsx", 
            filetypes=[("Arquivo Excel", "*.xlsx")]
        )
        if not caminho: 
            return
            
        try:
            wb = Workbook()
            wb.remove(wb.active) 
            estilo_borda = Border(
                left=Side(style='thin'), right=Side(style='thin'), 
                top=Side(style='thin'), bottom=Side(style='thin')
            )
            
            paleta_50 = self.paleta_professores
            mapa_cores_prof = {}
            
            # Pré-carrega os professores cadastrados para garantir cores fixas na ordem
            for prof_cad in self.professores.keys():
                chave_p = str(prof_cad).strip().upper()
                if chave_p not in mapa_cores_prof:
                    mapa_cores_prof[chave_p] = paleta_50[len(mapa_cores_prof) % len(paleta_50)]
            
            def formatar_celula(texto):
                t = str(texto).strip()
                if not t or t == "---": return t
                if " (" in t and t.endswith(")"): return t.replace(" (", "\n").replace(")", "")
                elif "(" in t and t.endswith(")"): return t.replace("(", "\n").replace(")", "")
                elif " - " in t: return t.replace(" - ", "\n")
                return t
            
            def obter_cor_professor(texto_ou_prof):
                """Extrai o nome do professor da célula (ou recebe direto) e retorna o HEX sem '#'."""
                t = str(texto_ou_prof).strip()
                
                # Caso 1: Texto já foi formatado com quebra de linha ("Disciplina\nProfessor")
                if "\n" in t:
                    nome_prof = t.split("\n")[-1].strip().upper()
                # Caso 2: Texto bruto no formato "Disciplina (Professor)"
                elif "(" in t and ")" in t:
                    nome_prof = t.split("(")[-1].replace(")", "").strip().upper()
                # Caso 3: Foi passado o nome do professor diretamente (ex: na aba do professor)
                else:
                    nome_prof = t.upper()
                    
                if nome_prof not in mapa_cores_prof:
                    mapa_cores_prof[nome_prof] = paleta_50[len(mapa_cores_prof) % len(paleta_50)]
                    
                return mapa_cores_prof[nome_prof].replace("#", "")

            def cor_fonte_contraste(cor_hex_sem_hash):
                """Calcula a luminância da cor de fundo para escolher letra preta ou branca."""
                try:
                    r = int(cor_hex_sem_hash[0:2], 16)
                    g = int(cor_hex_sem_hash[2:4], 16)
                    b = int(cor_hex_sem_hash[4:6], 16)
                    luminancia = (0.299 * r + 0.587 * g + 0.114 * b)
                    return "000000" if luminancia > 145 else "FFFFFF"
                except Exception:
                    return "000000"

            def processar_tabela(nome_aba, treeview_obj):
                ws = wb.create_sheet(title=nome_aba)
                colunas_nome = [treeview_obj.heading(c)['text'] for c in treeview_obj['columns']]
                ws.append(colunas_nome)
                
                for cell in ws[1]:
                    cell.font = Font(bold=True, color="000000")
                    cell.fill = PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                    cell.border = estilo_borda

                dados_extraidos = []
                linha_excel, inicio_bloco_dia = 2, 2

                for item in treeview_obj.get_children():
                    valores_brutos = treeview_obj.item(item)['values']
                    if valores_brutos and "---" not in str(valores_brutos[0]):
                        valores = [valores_brutos[0], valores_brutos[1]] + [formatar_celula(v) for v in valores_brutos[2:]]
                    else:
                        valores = valores_brutos
                        
                    dados_extraidos.append(valores) 
                    
                    if valores and "---" in str(valores[0]): 
                        if linha_excel > inicio_bloco_dia: 
                            ws.merge_cells(start_row=inicio_bloco_dia, start_column=1, end_row=linha_excel-1, end_column=1)
                        ws.append(valores)
                        linha_excel += 1
                        inicio_bloco_dia = linha_excel
                        continue 
                        
                    ws.append(valores)
                    for col_idx, cell in enumerate(ws[linha_excel], start=1):
                        cell.border = estilo_borda
                        if col_idx > 2 and cell.value:
                            texto_celula = str(cell.value).strip()
                            if texto_celula != "" and texto_celula != "---":
                                # Pinta pela cor do PROFESSOR
                                cor_hex = obter_cor_professor(texto_celula)
                                cor_letra = cor_fonte_contraste(cor_hex)
                                cell.fill = PatternFill(start_color=cor_hex, end_color=cor_hex, fill_type="solid")
                                cell.font = Font(bold=True, color=cor_letra, size=9) 
                            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                        elif col_idx == 1: 
                            cell.font = Font(bold=True, size=12, color="000000")
                            cell.alignment = Alignment(horizontal="center", vertical="center", text_rotation=90)
                        else:
                            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                    linha_excel += 1
                    
                if linha_excel > inicio_bloco_dia: 
                    ws.merge_cells(start_row=inicio_bloco_dia, start_column=1, end_row=linha_excel-1, end_column=1)
                
                ws.column_dimensions['A'].width = 6 
                ws.column_dimensions['B'].width = 12
                for i in range(len(colunas_nome) - 2): 
                    ws.column_dimensions[ws.cell(row=1, column=i+3).column_letter].width = 15
                
                ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
                ws.sheet_properties.pageSetUpPr.fitToPage = True
                ws.page_setup.fitToWidth = 1
                ws.page_setup.fitToHeight = False 
                
                return colunas_nome, dados_extraidos

            col_m, d_m = processar_tabela("Grade Manhã", self.tv_previa_manha)
            col_t, d_t = processar_tabela("Grade Tarde", self.tv_previa_tarde)

            for prof in self.professores.keys():
                ws_prof = wb.create_sheet(title=f"Prof {prof}"[:30])
                ws_prof.append(["Dia", "Horário", "Turma", "Disciplina"])
                for cell in ws_prof[1]:
                    cell.font = Font(bold=True, color="FFFFFF")
                    cell.fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                    cell.border = estilo_borda

                linha_prof = 2
                cor_deste_prof = obter_cor_professor(prof)
                cor_letra_prof = cor_fonte_contraste(cor_deste_prof)

                def preencher_prof(dados, colunas):
                    nonlocal linha_prof
                    dia_atual = ""
                    for valores in dados:
                        if valores and "---" in str(valores[0]):
                            ws_prof.append(["---", "---", "---", "---"])
                            linha_prof += 1
                            continue
                        if valores[0] != "": 
                            dia_atual = valores[0]
                            
                        horario = valores[1]
                        turma_enc, disc_enc = "-", "-"
                        
                        for c_idx in range(2, len(valores)):
                            celula_str = str(valores[c_idx])
                            # Verifica se o nome do professor está na segunda linha da célula
                            prof_na_celula = celula_str.split("\n")[-1].strip().upper() if "\n" in celula_str else celula_str.upper()
                            if prof.strip().upper() == prof_na_celula or prof.strip().upper() in celula_str.upper():
                                turma_enc = colunas[c_idx]
                                if "\n" in celula_str:
                                    disc_enc = celula_str.split("\n")[0].strip()
                                elif "(" in celula_str: 
                                    disc_enc = celula_str.split("(")[0].strip()
                                else: 
                                    disc_enc = celula_str.strip()
                                break
                                
                        ws_prof.append([dia_atual if valores[0] != "" else "", horario, turma_enc, disc_enc])
                        
                        for c_idx, cell in enumerate(ws_prof[linha_prof], start=1):
                            cell.alignment = Alignment(horizontal="center", vertical="center")
                            cell.border = estilo_borda
                            if turma_enc != "-" and c_idx > 2 and disc_enc != "---":
                                # Usa a mesma cor única do professor na aba individual dele
                                cell.fill = PatternFill(start_color=cor_deste_prof, end_color=cor_deste_prof, fill_type="solid")
                                cell.font = Font(bold=True, color=cor_letra_prof, size=9)
                        linha_prof += 1
                        
                preencher_prof(d_m, col_m)
                preencher_prof(d_t, col_t)
                
                ws_prof.column_dimensions['A'].width = 12
                ws_prof.column_dimensions['B'].width = 12
                ws_prof.column_dimensions['C'].width = 18
                ws_prof.column_dimensions['D'].width = 25
                ws_prof.page_setup.orientation = ws_prof.ORIENTATION_LANDSCAPE
                ws_prof.sheet_properties.pageSetUpPr.fitToPage = True
                ws_prof.page_setup.fitToWidth = 1
                ws_prof.page_setup.fitToHeight = False

            wb.save(caminho)
            messagebox.showinfo("Sucesso", "Excel gerado com sucesso!")
            
        except Exception as e: 
            messagebox.showerror("Erro", f"Erro no Excel:\n{str(e)}")
                    
    def salvar_pdf(self):
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        
        caminho = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile="Grade_Horaria.pdf", filetypes=[("Arquivo PDF", "*.pdf")])
        if not caminho: return
        try:
            doc = SimpleDocTemplate(caminho, pagesize=landscape(A4), leftMargin=20, rightMargin=20, topMargin=20, bottomMargin=20)
            elementos = []
            estilos = getSampleStyleSheet()
            
            def formatar_celula(texto):
                t = str(texto).strip()
                if not t or t == "---": return t
                if " (" in t and t.endswith(")"): return t.replace(" (", "\n").replace(")", "")
                elif "(" in t and t.endswith(")"): return t.replace("(", "\n").replace(")", "")
                elif " - " in t: return t.replace(" - ", "\n")
                return t
            
            def desenhar_tabela_pdf(treeview_obj, titulo_texto):
                elementos.append(Paragraph(titulo_texto, estilos['Title'])) 
                elementos.append(Spacer(1, 10))
                colunas = [treeview_obj.heading(c)['text'] for c in treeview_obj['columns']]
                dados_pdf = [colunas]
                
                for item in treeview_obj.get_children():
                    valores = treeview_obj.item(item)['values']
                    if valores and "---" in str(valores[0]): dados_pdf.append([""] * len(valores)) 
                    else: 
                        linha = [str(valores[0]) if valores[0] != "" else " ", str(valores[1]) if valores[1] != "" else " "]
                        for v in valores[2:]: linha.append(formatar_celula(v) if v != "" else " ")
                        dados_pdf.append(linha)
                
                tabela = Table(dados_pdf)
                tabela.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#262626")), 
                    ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'), 
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), 
                    ('FONTSIZE', (0,0), (-1,-1), 8),
                    ('BOTTOMPADDING', (0,0), (-1,0), 10), 
                    ('BACKGROUND', (0,1), (-1,-1), colors.beige),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                ]))
                elementos.append(tabela)

            desenhar_tabela_pdf(self.tv_previa_manha, "☀️ Grade Escolar - Turno da Manhã")
            elementos.append(PageBreak()) 
            desenhar_tabela_pdf(self.tv_previa_tarde, "🌆 Grade Escolar - Turno da Tarde")
            
            doc.build(elementos)
            messagebox.showinfo("Sucesso", "PDF exportado com sucesso!")
        except Exception as e: messagebox.showerror("Erro", f"Erro: {str(e)}")



# =========================================================
# INICIALIZAÇÃO DO SISTEMA
# =========================================================

def iniciar_com_splash():
    root = ttk.Window(themename="flatly")
    root.withdraw()
    iniciar_splash_na_root(root)
    root.mainloop()


def iniciar_splash_na_root(root):

    splash = tk.Toplevel(root)
    splash.overrideredirect(True)

    largura, altura = 620, 360
    x = (splash.winfo_screenwidth() // 2) - (largura // 2)
    y = (splash.winfo_screenheight() // 2) - (altura // 2)
    splash.geometry(f"{largura}x{altura}+{x}+{y}")
    splash.configure(bg="#e9eef5")

    painel = tk.Frame(
        splash,
        width=620,
        height=360,
        bg="#ffffff",
        highlightthickness=1,
        highlightbackground="#cbd6e2",
    )
    painel.place(x=12, y=12)

    faixa = tk.Frame(painel, width=596, height=118, bg="#17324d")
    faixa.place(x=0, y=0)

    canvas_logo = tk.Canvas(
        faixa,
        width=72,
        height=72,
        bg="#17324d",
        highlightthickness=0,
    )
    canvas_logo.place(x=38, y=23)
    canvas_logo.create_oval(4, 4, 68, 68, fill="#2f80ed", outline="#87b8f5", width=2)
    canvas_logo.create_text(
        36,
        36,
        text="EH",
        fill="#ffffff",
        font=("Segoe UI", 20, "bold"),
    )

    tk.Label(
        faixa,
        text="EduHora",
        bg="#17324d",
        fg="#ffffff",
        font=("Segoe UI", 30, "bold"),
    ).place(x=125, y=27)
    tk.Label(
        faixa,
        text="Gerador profissional de horários escolares",
        bg="#17324d",
        fg="#bcd0e4",
        font=("Segoe UI", 10),
    ).place(x=128, y=72)

    tk.Label(
        painel,
        text="Preparando ambiente",
        bg="#ffffff",
        fg="#263238",
        font=("Segoe UI", 12, "bold"),
    ).place(x=38, y=145)

    lbl_status_splash = tk.Label(
        painel,
        text="Inicializando módulos...",
        bg="#ffffff",
        fg="#78909c",
        font=("Segoe UI", 9),
    )
    lbl_status_splash.place(x=38, y=174)

    splash_progress = ttk.Progressbar(
        painel,
        mode="determinate",
        bootstyle="info",
        length=520,
        maximum=100,
    )
    splash_progress.place(x=38, y=208)
    splash_progress.start(12)

    splash_progress["value"] = 0

    def atualizar_progresso_splash(valor, mensagem):
        splash_progress.configure(value=valor)
        lbl_status_splash.configure(text=mensagem)

    splash.after(100, lambda: atualizar_progresso_splash(18, "Validando bibliotecas locais..."))
    splash.after(600, lambda: atualizar_progresso_splash(46, "Carregando motores de geração..."))
    splash.after(1150, lambda: atualizar_progresso_splash(72, "Preparando interface principal..."))
    splash.after(1800, lambda: atualizar_progresso_splash(92, "Concluindo inicialização..."))

    tk.Frame(painel, width=520, height=1, bg="#e5ebf1").place(x=38, y=246)
    tk.Label(
        painel,
        text=f"Versão {VERSAO_APP}",
        bg="#ffffff",
        fg="#78909c",
        font=("Segoe UI", 8),
    ).place(x=38, y=260)
    tk.Label(
        painel,
        text="prof.samuelapolinario@gmail.com",
        bg="#ffffff",
        fg="#78909c",
        font=("Segoe UI", 8),
    ).place(x=38, y=282)

    def fechar_splash():
        splash_progress.configure(value=100)
        splash_progress.stop()
        splash.destroy()
        AppHorariosPro(root)
        root.deiconify()

    splash.after(2500, fechar_splash)


# ===============================================================
#                   INICIALIZAÇÃO DO SISTEMA
# ===============================================================
if __name__ == "__main__":
    iniciar_com_splash()