import os

class AnalisadorGrade:
    def __init__(self, dias_semana, aulas_manha, aulas_tarde, turmas, professores, requerimentos, historico_aprendizado=None):
        self.dias_semana = dias_semana
        self.dias = len(dias_semana)
        self.aulas_manha = int(aulas_manha)
        self.aulas_tarde = int(aulas_tarde)
        self.total_aulas_dia = self.aulas_manha + self.aulas_tarde
        self.turmas = turmas
        self.professores = professores
        self.requerimentos = requerimentos
        self.historico_aprendizado = historico_aprendizado or {}
        self.preferencias_aprendidas = self.historico_aprendizado.get("preferencias", {})

        self.req_por_turma = {}
        self.req_por_prof = {}
        self.req_por_disciplina = {}

        self.dias_proibidos_prof = set()
        self.bloqueios_aula_prof = set()
        self.horarios_com_deficit_fisico = set()
        self.deficit_por_slot = {}

        self.deficit_rigido_folga = False
        self.estouro_capacidade_prof = False
        self.profs_no_limite_exato = 0

        self._mapear_estruturas()
        self._mapear_bloqueios()
        self._diagnosticar_viabilidade()

    def bonus_aprendizado(self, turma, disciplina, professor, dia, aula):
        chave = f"{turma}|{disciplina}|{professor}"
        ocorrencias = self.preferencias_aprendidas.get(chave, {}).get(f"{dia},{aula}", 0)
        try:
            return max(0, int(ocorrencias))
        except (TypeError, ValueError):
            return 0

    def eh_manha(self, nome_turma):
        return str(self.turmas.get(nome_turma, "Manhã")).strip().lower().startswith("m")

    def faixas_turma(self, nome_turma):
        return range(self.aulas_manha) if self.eh_manha(nome_turma) else range(self.aulas_manha, self.total_aulas_dia)

    def _normalizar_dia(self, d_val):
        if isinstance(d_val, int):
            return d_val
        s = str(d_val).strip().lower()
        if s.isdigit():
            return int(s)
        mapa = {str(n).strip().lower(): i for i, n in enumerate(self.dias_semana)}
        if s in mapa:
            return mapa[s]
        for nome_cad, idx in mapa.items():
            if s in nome_cad or nome_cad in s:
                return idx
        return -1

    def _mapear_estruturas(self):
        for r_idx, req in enumerate(self.requerimentos):
            self.req_por_turma.setdefault(req["turma"], []).append(r_idx)
            self.req_por_prof.setdefault(req["professor"], []).append(r_idx)
            self.req_por_disciplina.setdefault((req["turma"], req["disciplina"]), []).append(r_idx)

    def _mapear_bloqueios(self):
        for prof in self.req_por_prof:
            dados = self.professores.get(prof, {})
            for d_raw in dados.get("manha", []):
                d_idx = self._normalizar_dia(d_raw)
                if 0 <= d_idx < self.dias:
                    for a in range(self.aulas_manha):
                        self.dias_proibidos_prof.add((prof, d_idx, a))

            for d_raw in dados.get("tarde", []):
                d_idx = self._normalizar_dia(d_raw)
                if 0 <= d_idx < self.dias:
                    for a in range(self.aulas_manha, self.total_aulas_dia):
                        self.dias_proibidos_prof.add((prof, d_idx, a))

            for bloq in dados.get("bloqueios", []):
                d_idx = self._normalizar_dia(bloq.get("dia", -1))
                if not (0 <= d_idx < self.dias):
                    continue
                a_idx = int(bloq.get("aula", -1))
                turno = str(bloq.get("turno", "")).strip().upper()
                if turno.startswith("M") and 0 <= a_idx < self.aulas_manha:
                    self.bloqueios_aula_prof.add((prof, d_idx, a_idx))
                elif turno.startswith("T") and 0 <= a_idx < self.aulas_tarde:
                    self.bloqueios_aula_prof.add((prof, d_idx, self.aulas_manha + a_idx))

    def _diagnosticar_viabilidade(self):
        turmas_m = [t for t in self.turmas if self.eh_manha(t)]
        turmas_t = [t for t in self.turmas if not self.eh_manha(t)]
        profs_m = {r["professor"] for r in self.requerimentos if self.eh_manha(r["turma"])}
        profs_t = {r["professor"] for r in self.requerimentos if not self.eh_manha(r["turma"])}

        for d in range(self.dias):
            for a in range(self.aulas_manha):
                disp_total = [p for p in profs_m if (p, d, a) not in self.dias_proibidos_prof and (p, d, a) not in self.bloqueios_aula_prof]
                disp_sem_av = [p for p in profs_m if (p, d, a) not in self.dias_proibidos_prof]
                if len(disp_total) < len(turmas_m):
                    self.horarios_com_deficit_fisico.add((d, a))
                    self.deficit_por_slot[(d, a)] = len(turmas_m) - len(disp_total)
                if len(disp_sem_av) < len(turmas_m):
                    self.deficit_rigido_folga = True

            for a in range(self.aulas_manha, self.total_aulas_dia):
                disp_total = [p for p in profs_t if (p, d, a) not in self.dias_proibidos_prof and (p, d, a) not in self.bloqueios_aula_prof]
                disp_sem_av = [p for p in profs_t if (p, d, a) not in self.dias_proibidos_prof]
                if len(disp_total) < len(turmas_t):
                    self.horarios_com_deficit_fisico.add((d, a))
                    self.deficit_por_slot[(d, a)] = len(turmas_t) - len(disp_total)
                if len(disp_sem_av) < len(turmas_t):
                    self.deficit_rigido_folga = True

        for prof, lista in self.req_por_prof.items():
            for turno_m, faixa in ((True, range(self.aulas_manha)), (False, range(self.aulas_manha, self.total_aulas_dia))):
                aulas_p = sum(int(self.requerimentos[r]["aulas"]) for r in lista if self.eh_manha(self.requerimentos[r]["turma"]) == turno_m)
                livres_p = sum(1 for d in range(self.dias) for a in faixa if (prof, d, a) not in self.dias_proibidos_prof)
                if aulas_p > livres_p:
                    self.estouro_capacidade_prof = True
                elif 0 < aulas_p == livres_p:
                    self.profs_no_limite_exato += 1

    def calcular_ranking_motores(self):
        nucleos = os.cpu_count() or 2
        try:
            import ortools.sat.python.cp_model  # noqa
            cpsat_ok = True
        except Exception:
            cpsat_ok = False

        score_gen = 50
        score_cp = 50 if cpsat_ok else -999

        if nucleos <= 2:
            score_gen += 25
        elif nucleos >= 6:
            score_cp += 15

        if self.deficit_rigido_folga or self.estouro_capacidade_prof:
            score_gen += 60
            score_cp -= 30

        if self.profs_no_limite_exato >= 2 and not self.estouro_capacidade_prof:
            score_cp += 25

        if sum(int(r["aulas"]) for r in self.requerimentos) <= 150:
            score_gen += 20

        return nucleos, cpsat_ok, score_cp, score_gen