from collections import defaultdict
import random
import time
from ortools.sat.python import cp_model

# Pesos reduzidos proporcionalmente (divididos por 2.500) para estabilidade numérica
PESO_FALTA = 20_000
PESO_CONCESSAO = 800
PESO_EXCESSO_DIA = 6
BONUS_TRIPLA = -1


class _ParadaRapidaCallback(cp_model.CpSolverSolutionCallback):

    def __init__(self, var_total_faltas, var_total_conc, min_inevitavel):
        super().__init__()
        self.var_total_faltas = var_total_faltas
        self.var_total_conc = var_total_conc
        self.min_inevitavel = min_inevitavel

    def on_solution_callback(self):
        # Leitura O(1) direto do C++, sem loops em Python
        faltas = self.Value(self.var_total_faltas)
        if faltas > 0:
            return

        conc = self.Value(self.var_total_conc)
        if conc <= self.min_inevitavel:
            custo_base = (faltas * PESO_FALTA) + (conc * PESO_CONCESSAO)
            # Sem ruído: se (Objetivo - custo_base) <= 0, não há nenhum excesso diário!
            if (self.ObjectiveValue() - custo_base) <= 0:
                self.StopSearch()


def executar_cpsat(
    analisador, nucleos_cpu, callback_progresso=None, agrupar_triplas=False
):
    modelo = cp_model.CpModel()
    alocacoes = {}
    vars_concessao = []

    # defaultdict é mais rápido que dict.setdefault() em loops intensos
    vars_turma_slot = defaultdict(list)
    vars_prof_slot = defaultdict(list)
    vars_por_req = defaultdict(list)

    semente = random.randint(1, 999_999)
    indices_reqs = list(range(len(analisador.requerimentos)))
    random.shuffle(indices_reqs)

    # 1. Criação podada de variáveis
    for r_idx in indices_reqs:
        req = analisador.requerimentos[r_idx]
        turma, prof = req["turma"], req["professor"]
        faixas = analisador.faixas_turma(turma)

        for d in range(analisador.dias):
            for a in faixas:
                if (prof, d, a) in analisador.dias_proibidos_prof:
                    continue

                eh_bloq_av = (prof, d, a) in analisador.bloqueios_aula_prof
                if (
                    eh_bloq_av
                    and (d, a) not in analisador.horarios_com_deficit_fisico
                ):
                    continue

                var = modelo.NewBoolVar(f"R{r_idx}_D{d}_A{a}")
                alocacoes[(r_idx, d, a)] = var
                vars_turma_slot[(turma, d, a)].append(var)
                vars_prof_slot[(prof, d, a)].append(var)
                vars_por_req[r_idx].append(var)

                if eh_bloq_av:
                    vars_concessao.append(var)

    # 2. Restrições físicas de unicidade
    for lista_v in vars_turma_slot.values():
        if len(lista_v) > 1:
            modelo.AddAtMostOne(lista_v)

    for lista_v in vars_prof_slot.values():
        if len(lista_v) > 1:
            modelo.AddAtMostOne(lista_v)

    lista_faltas = []
    for r_idx, req in enumerate(analisador.requerimentos):
        nec = int(req["aulas"])
        vars_r = vars_por_req[r_idx]
        falta = modelo.NewIntVar(0, nec, f"f_{r_idx}")
        # LinearExpr.Sum é muito mais rápido que sum() nativo
        modelo.Add(cp_model.LinearExpr.Sum(vars_r) + falta == nec)
        lista_faltas.append(falta)

    # Variáveis agregadoras para acelerar o Callback e o Corte
    total_aulas_nec = sum(
        int(r["aulas"]) for r in analisador.requerimentos
    )  # Max teórico
    var_total_faltas = modelo.NewIntVar(0, total_aulas_nec, "total_faltas")
    var_total_conc = modelo.NewIntVar(0, len(vars_concessao), "total_conc")

    modelo.Add(var_total_faltas == cp_model.LinearExpr.Sum(lista_faltas))
    modelo.Add(var_total_conc == cp_model.LinearExpr.Sum(vars_concessao))

    # 3. Corte matemático de limite inferior
    min_inevitavel = sum(analisador.deficit_por_slot.values())
    if min_inevitavel > 0:
        modelo.Add(var_total_faltas + var_total_conc >= min_inevitavel)

    # 4. Construção do Objetivo (usando listas de variáveis e pesos para WeightedSum)
    obj_vars = [var_total_faltas, var_total_conc]
    obj_weights = [PESO_FALTA, PESO_CONCESSAO]

    # Aprendizado leve entre períodos: aumenta a preferência por encaixes já usados
    # com sucesso, sem permitir violar folgas, bloqueios ou choque de professores.
    for (r_idx, d, a), var in alocacoes.items():
        req = analisador.requerimentos[r_idx]
        ocorrencias = analisador.bonus_aprendizado(
            req["turma"], req["disciplina"], req["professor"], d, a
        )
        if ocorrencias > 0:
            obj_vars.append(var)
            obj_weights.append(-min(ocorrencias * 2, 40))

    for (turma, disc), lista in analisador.req_por_disciplina.items():
        faixas = list(analisador.faixas_turma(turma))
        total_aulas_disc = sum(
            int(analisador.requerimentos[r]["aulas"]) for r in lista
        )

        for d in range(analisador.dias):
            vars_slot_disc = []
            for a in faixas:
                v_s = [
                    alocacoes[(r_idx, d, a)]
                    for r_idx in lista
                    if (r_idx, d, a) in alocacoes
                ]
                if len(v_s) == 1:
                    vars_slot_disc.append(v_s[0])
                elif len(v_s) > 1:
                    v_comb = modelo.NewBoolVar(f"sd_{turma}_{disc}_{d}_{a}")
                    modelo.Add(cp_model.LinearExpr.Sum(v_s) == v_comb)
                    vars_slot_disc.append(v_comb)
                else:
                    vars_slot_disc.append(None)

            vars_validas_dia = [v for v in vars_slot_disc if v is not None]
            qtd_validas = len(vars_validas_dia)

            if qtd_validas > 3:
                # Limite superior ajustado para (qtd_validas - 3)
                exc = modelo.NewIntVar(
                    0, qtd_validas - 3, f"ed_{turma}_{disc}_{d}"
                )
                modelo.Add(cp_model.LinearExpr.Sum(vars_validas_dia) <= 3 + exc)
                obj_vars.append(exc)
                obj_weights.append(PESO_EXCESSO_DIA)

            if (
                agrupar_triplas
                and total_aulas_disc >= 3
                and len(vars_slot_disc) >= 3
            ):
                for i in range(len(vars_slot_disc) - 2):
                    v1, v2, v3 = (
                        vars_slot_disc[i],
                        vars_slot_disc[i + 1],
                        vars_slot_disc[i + 2],
                    )
                    if v1 is not None and v2 is not None and v3 is not None:
                        trio = modelo.NewBoolVar(f"trio_{turma}_{disc}_{d}_{i}")
                        # Cláusula Booleana direta é mais rápida no pré-processamento
                        modelo.AddBoolAnd([v1, v2, v3]).OnlyEnforceIf(trio)
                        obj_vars.append(trio)
                        obj_weights.append(BONUS_TRIPLA)

    # Minimização vetorizada em C++
    modelo.Minimize(cp_model.LinearExpr.WeightedSum(obj_vars, obj_weights))

    if callback_progresso:
        callback_progresso(
            45,
            f"Status: [CP-SAT ({nucleos_cpu} threads)] A calcular encaixe exato...",
        )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 12.0
    solver.parameters.num_search_workers = min(8, max(1, nucleos_cpu))
    solver.parameters.random_seed = semente
    solver.parameters.randomize_search = True

    # Parâmetros extras de performance para problemas de Grade Horária:
    solver.parameters.linearization_level = (
        2  # Melhora o limite inferior (bound) mais rápido
    )

    cb = _ParadaRapidaCallback(var_total_faltas, var_total_conc, min_inevitavel)
    status = solver.Solve(modelo, cb)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return False, {}, set(), []

    grade = {}
    ativas = set()
    concessoes = []
    for (r_idx, d, a), var in alocacoes.items():
        if solver.BooleanValue(
            var
        ):  # BooleanValue é ligeiramente mais rápido que Value() == 1
            req = analisador.requerimentos[r_idx]
            prof = req["professor"]
            grade[(req["turma"], d, a)] = r_idx
            ativas.add((r_idx, d, a))
            if (prof, d, a) in analisador.bloqueios_aula_prof:
                dia_s = (
                    analisador.dias_semana[d]
                    if d < len(analisador.dias_semana)
                    else f"Dia {d+1}"
                )
                aula_s = (
                    f"{a+1}ª Aula (Manhã)"
                    if a < analisador.aulas_manha
                    else f"{a - analisador.aulas_manha + 1}ª Aula (Tarde)"
                )
                concessoes.append(
                    f"- {dia_s} | {aula_s}: Prof. {prof} no {req['turma']} ({req['disciplina']})"
                )

    return True, grade, ativas, concessoes