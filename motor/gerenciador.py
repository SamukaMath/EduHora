from motor.analisador import AnalisadorGrade
from motor.solver_cpsat import executar_cpsat
from motor.solver_genetico import executar_genetico


class SolverUniversalAdapter:
    def __init__(self, alocacoes_ativas):
        self._ativas = alocacoes_ativas

    def Value(self, var_key):
        return 1 if var_key in self._ativas else 0


def _auditar_grade(analisador, grade):
    cont = {r: 0 for r in range(len(analisador.requerimentos))}
    uso_prof = {}
    choques, folgas, avulsos = 0, 0, 0

    for (turma, d, a), r_idx in grade.items():
        if r_idx is None:
            continue
        cont[r_idx] += 1
        prof = analisador.requerimentos[r_idx]["professor"]
        if (prof, d, a) in analisador.dias_proibidos_prof:
            folgas += 1
        elif (prof, d, a) in analisador.bloqueios_aula_prof:
            avulsos += 1
        if (prof, d, a) in uso_prof:
            choques += 1
        else:
            uso_prof[(prof, d, a)] = turma

    faltas = sum(max(0, int(req["aulas"]) - cont[r]) for r, req in enumerate(analisador.requerimentos))
    custo = faltas * 1_000_000 + folgas * 500_000 + choques * 250_000 + avulsos * 10_000
    return custo, faltas, choques, folgas


def _polir_blocos_consecutivos(analisador, grade, agrupar_triplas=False):
    """
    Agrupa aulas da mesma disciplina em blocos consecutivos:
    - Sempre junta aulas separadas no mesmo dia (dobradinhas).
    - Se `agrupar_triplas=True`, puxa uma 3ª aula da mesma disciplina (de outro horário ou outro dia)
      para formar 3 aulas seguidas quando possível, respeitando o limite máximo de 3 aulas/dia.
    """
    prof_ocup = {
        (analisador.requerimentos[r]["professor"], d, a): t
        for (t, d, a), r in grade.items() if r is not None
    }

    def pode_mover(prof, d, a):
        return (
            (prof, d, a) not in analisador.dias_proibidos_prof
            and (prof, d, a) not in analisador.bloqueios_aula_prof
            and (prof, d, a) not in prof_ocup
        )

    def trocar_slots(turma, d1, a1, d2, a2):
        r1 = grade.get((turma, d1, a1))
        r2 = grade.get((turma, d2, a2))
        if r1 is None or r2 is None:
            return False
        p1 = analisador.requerimentos[r1]["professor"]
        p2 = analisador.requerimentos[r2]["professor"]

        if p1 == p2:
            grade[(turma, d1, a1)], grade[(turma, d2, a2)] = r2, r1
            return True

        if pode_mover(p1, d2, a2) and pode_mover(p2, d1, a1):
            grade[(turma, d1, a1)], grade[(turma, d2, a2)] = r2, r1
            del prof_ocup[(p1, d1, a1)]
            del prof_ocup[(p2, d2, a2)]
            prof_ocup[(p1, d2, a2)] = turma
            prof_ocup[(p2, d1, a1)] = turma
            return True
        return False

    # Passo 1: Compacta aulas da mesma disciplina dentro do mesmo dia (evita 1ª e 4ª aula separadas)
    for turma in analisador.turmas:
        faixas = list(analisador.faixas_turma(turma))
        for d in range(analisador.dias):
            for i in range(len(faixas) - 2):
                a1, a2 = faixas[i], faixas[i + 1]
                r1, r2 = grade.get((turma, d, a1)), grade.get((turma, d, a2))
                if r1 is None or r2 is None:
                    continue
                disc1 = analisador.requerimentos[r1]["disciplina"]
                if analisador.requerimentos[r2]["disciplina"] == disc1:
                    continue
                for k in range(i + 2, len(faixas)):
                    ak = faixas[k]
                    rk = grade.get((turma, d, ak))
                    if rk is not None and analisador.requerimentos[rk]["disciplina"] == disc1:
                        if trocar_slots(turma, d, a2, d, ak):
                            break

    # Passo 2: Formação de Triplas (3 aulas seguidas) para disciplinas com >= 3 aulas semanais
    if agrupar_triplas:
        for (turma, disc), lista_reqs in analisador.req_por_disciplina.items():
            total_sem = sum(int(analisador.requerimentos[r]["aulas"]) for r in lista_reqs)
            if total_sem < 3:
                continue

            faixas = list(analisador.faixas_turma(turma))
            if len(faixas) < 3:
                continue

            # Verifica se a turma já tem um trio seguido desta disciplina
            ja_tem_trio = False
            for d in range(analisador.dias):
                for i in range(len(faixas) - 2):
                    r_trio = [grade.get((turma, d, faixas[i + offset])) for offset in range(3)]
                    if all(r is not None and analisador.requerimentos[r]["disciplina"] == disc for r in r_trio):
                        ja_tem_trio = True
                        break
                if ja_tem_trio:
                    break

            if ja_tem_trio:
                continue

            # Procura uma dobradinha existente (2 seguidas) e tenta puxar uma 3ª aula de outro dia para colar nela!
            formou = False
            for d_alvo in range(analisador.dias):
                aulas_no_dia_alvo = [
                    a for a in faixas
                    if grade.get((turma, d_alvo, a)) is not None
                    and analisador.requerimentos[grade[(turma, d_alvo, a)]]["disciplina"] == disc
                ]
                if len(aulas_no_dia_alvo) != 2:
                    continue

                for i in range(len(faixas) - 2):
                    a1, a2, a3 = faixas[i], faixas[i + 1], faixas[i + 2]
                    r1, r2, r3 = grade.get((turma, d_alvo, a1)), grade.get((turma, d_alvo, a2)), grade.get((turma, d_alvo, a3))
                    if r1 is None or r2 is None or r3 is None:
                        continue

                    d1_ok = analisador.requerimentos[r1]["disciplina"] == disc
                    d2_ok = analisador.requerimentos[r2]["disciplina"] == disc
                    d3_ok = analisador.requerimentos[r3]["disciplina"] == disc

                    # Identifica qual dos 3 slots adjacentes precisa receber a 3ª aula
                    slot_para_trocar = None
                    if d1_ok and d2_ok and not d3_ok:
                        slot_para_trocar = a3
                    elif not d1_ok and d2_ok and d3_ok:
                        slot_para_trocar = a1

                    if slot_para_trocar is None:
                        continue

                    # Procura uma aula avulsa desta disciplina em OUTRO dia (d_origem) para trazer para slot_para_trocar
                    for d_origem in range(analisador.dias):
                        if d_origem == d_alvo:
                            continue
                        aulas_origem = [
                            a for a in faixas
                            if grade.get((turma, d_origem, a)) is not None
                            and analisador.requerimentos[grade[(turma, d_origem, a)]]["disciplina"] == disc
                        ]
                        # Só tira de d_origem se lá tiver 1 aula isolada (ou 3, para não quebrar outra dobradinha)
                        if len(aulas_origem) in (1, 3):
                            for a_orig in aulas_origem:
                                if trocar_slots(turma, d_alvo, slot_para_trocar, d_origem, a_orig):
                                    formou = True
                                    break
                        if formou:
                            break
                    if formou:
                        break
                if formou:
                    break

    return grade

def gerar_grade_inteligente(
    dias_semana,
    aulas_manha,
    aulas_tarde,
    turmas,
    professores,
    requerimentos,
    callback_progresso=None,
    agrupar_triplas=False,
    historico_aprendizado=None,
    ctsap_problem=None,
    ctsap_populacao=20,
    ctsap_geracoes=60,
    callback_grade=None,
):
    analisador = AnalisadorGrade(
        dias_semana,
        aulas_manha,
        aulas_tarde,
        turmas,
        professores,
        requerimentos,
        historico_aprendizado=historico_aprendizado,
    )
    nucleos, cpsat_ok, score_cp, score_gen = analisador.calcular_ranking_motores()

    fila = []
    if score_gen >= score_cp:
        fila.append(("Genético Evolutivo", lambda: executar_genetico(analisador, callback_progresso=callback_progresso, callback_grade=callback_grade)))
        if cpsat_ok:
            fila.append(("CP-SAT (OR-Tools)", lambda: executar_cpsat(analisador, nucleos, callback_progresso=callback_progresso)))
    else:
        fila.append(("CP-SAT (OR-Tools)", lambda: executar_cpsat(analisador, nucleos, callback_progresso=callback_progresso)))
        fila.append(("Genético Evolutivo", lambda: executar_genetico(analisador, callback_progresso=callback_progresso, callback_grade=callback_grade)))

    if ctsap_problem is None:
        from motor.ct_sap import CTSAPProblem
        ctsap_problem = CTSAPProblem.from_eduhora(
            dias_semana,
            aulas_manha,
            aulas_tarde,
            turmas,
            professores,
            requerimentos,
        )

    if ctsap_problem is not None:
        def executar_ctsap_genetico():
            from motor.ct_sap import CTSAP_GeneticSolver

            solver = CTSAP_GeneticSolver(
                ctsap_problem,
                tamanho_populacao=ctsap_populacao,
                max_geracoes=ctsap_geracoes,
            )

            def converter_resultado_ctsap(cromossomo):
                grade_ctsap = {}
                requisicoes_restantes = list(range(len(requerimentos)))
                for gene in cromossomo:
                    dia, aula = gene.horario
                    r_idx = None
                    for candidato in requisicoes_restantes:
                        req = requerimentos[candidato]
                        if (
                            req["turma"] == gene.grupo_alunos
                            and req["disciplina"] == gene.disciplina
                            and req["professor"] == gene.professor
                        ):
                            r_idx = candidato
                            break
                    if r_idx is not None:
                        grade_ctsap[(gene.grupo_alunos, dia, aula)] = r_idx
                if callback_grade:
                    callback_grade(grade_ctsap)

            resultado = solver.rodar(
                callback=lambda geracao, melhor: converter_resultado_ctsap(melhor[1])
            )
            grade = {}
            ativas = set()
            concessoes = []

            requisicoes_restantes = list(range(len(requerimentos)))
            for gene in resultado.cromossomo:
                dia, aula = gene.horario
                r_idx = None
                for candidato in requisicoes_restantes:
                    req = requerimentos[candidato]
                    if (
                        req["turma"] == gene.grupo_alunos
                        and req["disciplina"] == gene.disciplina
                        and req["professor"] == gene.professor
                    ):
                        r_idx = candidato
                        break
                if r_idx is None:
                    continue

                chave = (gene.grupo_alunos, dia, aula)
                if chave not in grade:
                    grade[chave] = r_idx
                    ativas.add((r_idx, dia, aula))

            return bool(grade), grade, ativas, concessoes

        fila.append(("CT-SAP Genético", executar_ctsap_genetico))

    melhor = None
    for nome_motor, fn_motor in fila:
        try:
            ok, grade, ativas, conc = fn_motor()
        except Exception:
            ok = False

        if ok and grade:
            custo, faltas, choques, folgas = _auditar_grade(analisador, grade)
            if melhor is None or custo < melhor[0]:
                melhor = (custo, nome_motor, grade, ativas, conc)
            if faltas == 0 and choques == 0 and folgas == 0:
                break

    if melhor is None:
        return None

    _, motor_vencedor, grade_final, _, concessoes = melhor
    grade_final = _polir_blocos_consecutivos(analisador, grade_final, agrupar_triplas=agrupar_triplas)

    ativas_finais = {(r_idx, d, a) for (t, d, a), r_idx in grade_final.items() if r_idx is not None}
    alocacoes_completas = {
        (r_idx, d, a): (r_idx, d, a)
        for r_idx, req in enumerate(requerimentos)
        for d in range(analisador.dias)
        for a in analisador.faixas_turma(req["turma"])
    }

    return {
        "motor": motor_vencedor,
        "grade": grade_final,
        "concessoes": concessoes,
        "adapter": SolverUniversalAdapter(ativas_finais),
        "alocacoes": alocacoes_completas,
        "analisador": analisador,
    }