import random
import time
from motor.maestro_rl import QLearningMaestro

P_FOLGA = 80_000
P_CHOQUE = 50_000
P_AVULSO = 8_000
P_EXC_DD = 400
B_BLOCO = 15  # Bônus interno para manter aulas da mesma disciplina juntas


def executar_genetico(
    analisador,
    tempo_limite=12.0,
    callback_progresso=None,
    agrupar_triplas=False,
    callback_grade=None,
):
    t0 = time.time()

    # =========================================================================
    # 1. PRÉ-COMPILAÇÃO EM ARRAYS DE INTEIROS O(1) (Zero Dict/Tuple no Hot Loop)
    # =========================================================================
    turmas_nomes = list(analisador.turmas.keys())
    num_turmas = len(turmas_nomes)
    mapa_turma = {t: i for i, t in enumerate(turmas_nomes)}

    profs_set = {r["professor"] for r in analisador.requerimentos}
    mapa_prof = {p: i for i, p in enumerate(profs_set)}
    num_profs = len(mapa_prof)

    discs_set = {r["disciplina"] for r in analisador.requerimentos}
    mapa_disc = {d: i for i, d in enumerate(discs_set)}
    num_discs = len(mapa_disc)

    num_dias = analisador.dias
    max_aula = (
        max(
            (a for t in turmas_nomes for a in analisador.faixas_turma(t)),
            default=0,
        )
        + 1
    )
    num_g_slots = num_dias * max_aula

    num_reqs = len(analisador.requerimentos)
    req_prof = [mapa_prof[r["professor"]] for r in analisador.requerimentos]
    req_disc = [mapa_disc[r["disciplina"]] for r in analisador.requerimentos]
    req_aulas = [int(r["aulas"]) for r in analisador.requerimentos]

    # Dificuldade de cada professor (para ordenar alocação inicial)
    peso_dificuldade_req = [0] * num_reqs
    for r_idx, r in enumerate(analisador.requerimentos):
        p_nome = r["professor"]
        proib = sum(
            1 for (p, _, _) in analisador.dias_proibidos_prof if p == p_nome
        )
        bloq = sum(
            1 for (p, _, _) in analisador.bloqueios_aula_prof if p == p_nome
        )
        peso_dificuldade_req[r_idx] = proib * 10 + bloq * 2 + req_aulas[r_idx]

    slots_por_turma = []
    genes_base = []
    slot_dia = []
    slot_global = []
    viz_esq = []
    viz_dir = []
    mapa_gslot_para_local = [
        [-1] * num_g_slots for _ in range(num_turmas)
    ]

    for t_id, turma in enumerate(turmas_nomes):
        slots_t = [
            (d, a)
            for d in range(num_dias)
            for a in analisador.faixas_turma(turma)
        ]
        slots_por_turma.append(slots_t)
        n_s = len(slots_t)

        s_dia = [d for d, _ in slots_t]
        s_glob = [d * max_aula + a for d, a in slots_t]
        slot_dia.append(s_dia)
        slot_global.append(s_glob)

        for idx_s, g in enumerate(s_glob):
            mapa_gslot_para_local[t_id][g] = idx_s

        # Vizinhos adjacentes no mesmo dia para formar dobradinhas/triplas
        v_e = [-1] * n_s
        v_d = [-1] * n_s
        for i in range(n_s):
            if (
                i > 0
                and slots_t[i - 1][0] == slots_t[i][0]
                and slots_t[i - 1][1] == slots_t[i][1] - 1
            ):
                v_e[i] = i - 1
            if (
                i + 1 < n_s
                and slots_t[i + 1][0] == slots_t[i][0]
                and slots_t[i + 1][1] == slots_t[i][1] + 1
            ):
                v_d[i] = i + 1
        viz_esq.append(v_e)
        viz_dir.append(v_d)

        # Usa -1 para representar slot vago (mais rápido que None)
        genes = [
            r_idx
            for r_idx, req in enumerate(analisador.requerimentos)
            if req["turma"] == turma
            for _ in range(req_aulas[r_idx])
        ]
        while len(genes) < n_s:
            genes.append(-1)
        genes_base.append(genes[:n_s])

    # Tabelas O(1) por requerimento e slot local
    custo_fixo_req = [[] for _ in range(num_reqs)]
    ocup_idx_req = [[] for _ in range(num_reqs)]
    dd_idx_req = [[] for _ in range(num_reqs)]

    for r_idx, req in enumerate(analisador.requerimentos):
        t_id = mapa_turma[req["turma"]]
        p_nome = req["professor"]
        p_id = req_prof[r_idx]
        d_id = req_disc[r_idx]
        slots_t = slots_por_turma[t_id]

        cf_list = [0] * len(slots_t)
        oc_list = [0] * len(slots_t)
        dd_list = [0] * len(slots_t)

        for idx_s, (d, a) in enumerate(slots_t):
            if (p_nome, d, a) in analisador.dias_proibidos_prof:
                cf_list[idx_s] = P_FOLGA
            elif (p_nome, d, a) in analisador.bloqueios_aula_prof:
                cf_list[idx_s] = P_AVULSO
            oc_list[idx_s] = p_id * num_g_slots + (d * max_aula + a)
            dd_list[idx_s] = d * num_discs + d_id

        custo_fixo_req[r_idx] = cf_list
        ocup_idx_req[r_idx] = oc_list
        dd_idx_req[r_idx] = dd_list

    min_inevitavel = sum(analisador.deficit_por_slot.values())
    pen_min_teorico = min_inevitavel * P_AVULSO
    max_bloco_dia = 3 if agrupar_triplas else 2

    # =========================================================================
    # 2. CONSTRUÇÃO GULOSA COM AGRUPAMENTO DE BLOCOS (Geração 0 de Alta Qualidade)
    # =========================================================================
    def criar_individuo():
        ind = [None] * num_turmas
        ocup = [0] * (num_profs * num_g_slots)
        ordem_turmas = list(range(num_turmas))
        random.shuffle(ordem_turmas)

        for t_id in ordem_turmas:
            n_s = len(slots_por_turma[t_id])
            aulas_t = genes_base[t_id][:]
            random.shuffle(aulas_t)
            # Ordena colocando professores mais restritos primeiro e agrupando mesma disciplina
            aulas_t.sort(
                key=lambda r: (
                    (peso_dificuldade_req[r], r) if r >= 0 else (-1, -1)
                ),
                reverse=True,
            )

            aloc_t = [-1] * n_s
            usados = [False] * n_s
            dd_t = [0] * (num_dias * num_discs)
            v_e, v_d = viz_esq[t_id], viz_dir[t_id]

            for r_idx in aulas_t:
                if r_idx < 0:
                    continue
                cf_r = custo_fixo_req[r_idx]
                oc_r = ocup_idx_req[r_idx]
                dd_r = dd_idx_req[r_idx]
                disc = req_disc[r_idx]

                melhor_s, melhor_c = -1, 999_999_999
                cands = [i for i in range(n_s) if not usados[i]]
                random.shuffle(cands)

                for i_s in cands:
                    c = cf_r[i_s]
                    if ocup[oc_r[i_s]] > 0:
                        c += P_CHOQUE
                    qtd_dia = dd_t[dd_r[i_s]]
                    if qtd_dia >= 3:
                        c += P_EXC_DD
                    elif qtd_dia >= max_bloco_dia:
                        c += 30  # Evita colocar mais que o tamanho de bloco ideal se houver outro dia livre

                    req = analisador.requerimentos[r_idx]
                    d_slot, a_slot = slots_por_turma[t_id][i_s]
                    ocorrencias = analisador.bonus_aprendizado(
                        req["turma"], req["disciplina"], req["professor"], d_slot, a_slot
                    )
                    c -= min(ocorrencias * 12, 240)

                    # Bônus se colar em aula da mesma matéria no mesmo dia
                    ve, vd = v_e[i_s], v_d[i_s]
                    if (
                        ve >= 0
                        and aloc_t[ve] >= 0
                        and req_disc[aloc_t[ve]] == disc
                    ) or (
                        vd >= 0
                        and aloc_t[vd] >= 0
                        and req_disc[aloc_t[vd]] == disc
                    ):
                        c -= B_BLOCO

                    if c < melhor_c:
                        melhor_c, melhor_s = c, i_s
                        if c == -B_BLOCO:
                            break

                aloc_t[melhor_s] = r_idx
                usados[melhor_s] = True
                ocup[oc_r[melhor_s]] += 1
                dd_t[dd_r[melhor_s]] += 1

            ind[t_id] = aloc_t
        return ind

    # =========================================================================
    # 3. AVALIAÇÃO RÁPIDA E BUSCA MEMÉTICA INCREMENTAL + CADEIAS DE KEMPE
    # =========================================================================
    def construir_estado_e_reparar(ind, iteracoes_busca=45):
        ocup = [0] * (num_profs * num_g_slots)
        dd_por_turma = [[0] * (num_dias * num_discs) for _ in range(num_turmas)]

        for t_id, aloc_t in enumerate(ind):
            dd_t = dd_por_turma[t_id]
            for idx_s, r_idx in enumerate(aloc_t):
                if r_idx >= 0:
                    ocup[ocup_idx_req[r_idx][idx_s]] += 1
                    dd_t[dd_idx_req[r_idx][idx_s]] += 1

        def bonus_vizinhanca(
            aloc_t, v_e, v_d, idx_s, disc, idx_ignorar=-1, disc_subst=-1
        ):
            if disc < 0:
                return 0
            b = 0
            ve = v_e[idx_s]
            if ve >= 0:
                r_v = aloc_t[ve]
                d_v = (
                    disc_subst
                    if ve == idx_ignorar
                    else (req_disc[r_v] if r_v >= 0 else -1)
                )
                if d_v == disc:
                    b += B_BLOCO
            vd = v_d[idx_s]
            if vd >= 0:
                r_v = aloc_t[vd]
                d_v = (
                    disc_subst
                    if vd == idx_ignorar
                    else (req_disc[r_v] if r_v >= 0 else -1)
                )
                if d_v == disc:
                    b += B_BLOCO
            return b

        # Coleta apenas slots com conflito real (Folga, Choque, Avulso ou Excesso Diário)
        conflitos = []
        for t_id, aloc_t in enumerate(ind):
            dd_t = dd_por_turma[t_id]
            for idx_s, r_idx in enumerate(aloc_t):
                if r_idx >= 0:
                    if (
                        custo_fixo_req[r_idx][idx_s] > 0
                        or ocup[ocup_idx_req[r_idx][idx_s]] > 1
                        or dd_t[dd_idx_req[r_idx][idx_s]] > 3
                    ):
                        conflitos.append((t_id, idx_s))

        # Loop de Reparo Incremental (Delta Evaluation O(1))
        for _ in range(iteracoes_busca):
            if not conflitos:
                break
            t_id, idx_1 = random.choice(conflitos)
            aloc_t = ind[t_id]
            r_1 = aloc_t[idx_1]
            if r_1 < 0:
                continue

            dd_t = dd_por_turma[t_id]
            cf_1 = custo_fixo_req[r_1][idx_1]
            oc_1_idx = ocup_idx_req[r_1][idx_1]
            dd_1_idx = dd_idx_req[r_1][idx_1]

            # Verifica se o conflito neste slot já foi resolvido por uma troca anterior
            if cf_1 == 0 and ocup[oc_1_idx] <= 1 and dd_t[dd_1_idx] <= 3:
                continue

            n_s = len(aloc_t)
            s_dia = slot_dia[t_id]
            v_e, v_d = viz_esq[t_id], viz_dir[t_id]
            d1 = s_dia[idx_1]
            p1, disc1 = req_prof[r_1], req_disc[r_1]

            melhor_2 = -1
            maior_ganho = 0
            candidato_kempe = None

            cands = list(range(n_s))
            random.shuffle(cands)

            for idx_2 in cands:
                if idx_2 == idx_1:
                    continue
                r_2 = aloc_t[idx_2]
                if r_1 == r_2:
                    continue

                d2 = s_dia[idx_2]
                p2 = req_prof[r_2] if r_2 >= 0 else -1
                disc2 = req_disc[r_2] if r_2 >= 0 else -1

                # 1. Delta de Custos Fixos (Folga / Avulso)
                antes_fixo = cf_1 + (
                    custo_fixo_req[r_2][idx_2] if r_2 >= 0 else 0
                )
                depois_fixo = custo_fixo_req[r_1][idx_2] + (
                    custo_fixo_req[r_2][idx_1] if r_2 >= 0 else 0
                )
                ganho = antes_fixo - depois_fixo

                # 2. Delta Exato de Choques de Professor
                if p1 != p2:
                    if ocup[oc_1_idx] > 1:
                        ganho += P_CHOQUE
                    if ocup[ocup_idx_req[r_1][idx_2]] >= 1:
                        ganho -= P_CHOQUE
                    if r_2 >= 0:
                        if ocup[ocup_idx_req[r_2][idx_2]] > 1:
                            ganho += P_CHOQUE
                        if ocup[ocup_idx_req[r_2][idx_1]] >= 1:
                            ganho -= P_CHOQUE

                # 3. Delta Exato de Excesso Diário (> 3 aulas/dia)
                if d1 != d2 and disc1 != disc2:
                    if dd_t[dd_1_idx] > 3:
                        ganho += P_EXC_DD
                    if dd_t[dd_idx_req[r_1][idx_2]] >= 3:
                        ganho -= P_EXC_DD
                    if r_2 >= 0:
                        if dd_t[dd_idx_req[r_2][idx_2]] > 3:
                            ganho += P_EXC_DD
                        if dd_t[dd_idx_req[r_2][idx_1]] >= 3:
                            ganho -= P_EXC_DD

                # 4. Delta de Adjacência (Dobradinhas / Triplas)
                b_antes = bonus_vizinhanca(
                    aloc_t, v_e, v_d, idx_1, disc1
                ) + bonus_vizinhanca(aloc_t, v_e, v_d, idx_2, disc2)
                b_depois = bonus_vizinhanca(
                    aloc_t, v_e, v_d, idx_2, disc1, idx_1, disc2
                ) + bonus_vizinhanca(
                    aloc_t, v_e, v_d, idx_1, disc2, idx_2, disc1
                )
                ganho += b_depois - b_antes

                if ganho > maior_ganho:
                    maior_ganho = ganho
                    melhor_2 = idx_2
                elif (
                    candidato_kempe is None
                    and r_2 >= 0
                    and p1 != p2
                    and depois_fixo == 0
                ):
                    # Guarda candidato para Cadeia de Kempe (se a única barreira for 1 choque em outra turma)
                    if (
                        ocup[ocup_idx_req[r_1][idx_2]] == 0
                        and ocup[ocup_idx_req[r_2][idx_1]] == 1
                    ):
                        candidato_kempe = idx_2

            if melhor_2 >= 0:
                # Aplica a troca 1-Swap e atualiza o estado em O(1)
                r_2 = aloc_t[melhor_2]
                ocup[oc_1_idx] -= 1
                ocup[ocup_idx_req[r_1][melhor_2]] += 1
                dd_t[dd_1_idx] -= 1
                dd_t[dd_idx_req[r_1][melhor_2]] += 1

                if r_2 >= 0:
                    ocup[ocup_idx_req[r_2][melhor_2]] -= 1
                    ocup[ocup_idx_req[r_2][idx_1]] += 1
                    dd_t[dd_idx_req[r_2][melhor_2]] -= 1
                    dd_t[dd_idx_req[r_2][idx_1]] += 1

                aloc_t[idx_1], aloc_t[melhor_2] = r_2, r_1

            elif candidato_kempe is not None:
                # CADEIA DE KEMPE (Ejeção Inter-Turmas):
                # Libera o slot na outra turma que estava bloqueando r_2 de ir para idx_1
                idx_2 = candidato_kempe
                r_2 = aloc_t[idx_2]
                p2 = req_prof[r_2]
                g_slot_1 = slot_global[t_id][idx_1]

                # Localiza qual turma (t_outra) está ocupando p2 no horário g_slot_1
                for t_outra in range(num_turmas):
                    if t_outra == t_id:
                        continue
                    idx_outra_1 = mapa_gslot_para_local[t_outra][g_slot_1]
                    if idx_outra_1 < 0:
                        continue
                    r_outra_1 = ind[t_outra][idx_outra_1]
                    if r_outra_1 >= 0 and req_prof[r_outra_1] == p2:
                        # Procura um slot limpo em t_outra para mover r_outra_1
                        aloc_o = ind[t_outra]
                        dd_o = dd_por_turma[t_outra]
                        for idx_outra_2 in range(len(aloc_o)):
                            if idx_outra_2 == idx_outra_1:
                                continue
                            r_outra_2 = aloc_o[idx_outra_2]
                            if (
                                custo_fixo_req[r_outra_1][idx_outra_2] == 0
                                and ocup[ocup_idx_req[r_outra_1][idx_outra_2]]
                                == 0
                                and dd_o[dd_idx_req[r_outra_1][idx_outra_2]] < 3
                            ):
                                if r_outra_2 < 0 or (
                                    custo_fixo_req[r_outra_2][idx_outra_1] == 0
                                    and ocup[
                                        ocup_idx_req[r_outra_2][idx_outra_1]
                                    ]
                                    == 0
                                    and dd_o[dd_idx_req[r_outra_2][idx_outra_1]]
                                    < 3
                                ):
                                    # Executa a troca dupla (em t_outra e em t_id)!
                                    ocup[
                                        ocup_idx_req[r_outra_1][idx_outra_1]
                                    ] -= 1
                                    ocup[
                                        ocup_idx_req[r_outra_1][idx_outra_2]
                                    ] += 1
                                    dd_o[
                                        dd_idx_req[r_outra_1][idx_outra_1]
                                    ] -= 1
                                    dd_o[
                                        dd_idx_req[r_outra_1][idx_outra_2]
                                    ] += 1
                                    if r_outra_2 >= 0:
                                        ocup[
                                            ocup_idx_req[r_outra_2][idx_outra_2]
                                        ] -= 1
                                        ocup[
                                            ocup_idx_req[r_outra_2][idx_outra_1]
                                        ] += 1
                                        dd_o[
                                            dd_idx_req[r_outra_2][idx_outra_2]
                                        ] -= 1
                                        dd_o[
                                            dd_idx_req[r_outra_2][idx_outra_1]
                                        ] += 1
                                    aloc_o[idx_outra_1], aloc_o[idx_outra_2] = (
                                        r_outra_2,
                                        r_outra_1,
                                    )

                                    ocup[oc_1_idx] -= 1
                                    ocup[ocup_idx_req[r_1][idx_2]] += 1
                                    dd_t[dd_1_idx] -= 1
                                    dd_t[dd_idx_req[r_1][idx_2]] += 1
                                    ocup[ocup_idx_req[r_2][idx_2]] -= 1
                                    ocup[ocup_idx_req[r_2][idx_1]] += 1
                                    dd_t[dd_idx_req[r_2][idx_2]] -= 1
                                    dd_t[dd_idx_req[r_2][idx_1]] += 1
                                    aloc_t[idx_1], aloc_t[idx_2] = r_2, r_1
                                    break
                        break

        # Calcula a penalidade final exata a partir do estado incremental
        pen = 0
        for t_id, aloc_t in enumerate(ind):
            for idx_s, r_idx in enumerate(aloc_t):
                if r_idx >= 0:
                    pen += custo_fixo_req[r_idx][idx_s]
            for qtd in dd_por_turma[t_id]:
                if qtd > 3:
                    pen += (qtd - 3) * P_EXC_DD

        for qtd in ocup:
            if qtd > 1:
                pen += (qtd - 1) * P_CHOQUE

        return pen

    # =========================================================================
    # 4. LOOP EVOLUTIVO COM CROSSOVER GUIADO E PERTURBAÇÃO LNS
    # =========================================================================
    TAM_POP = 28
    pop = []
    for _ in range(TAM_POP):
        ind = criar_individuo()
        pen = construir_estado_e_reparar(ind, iteracoes_busca=35)
        pop.append([pen, ind])
        if pen <= pen_min_teorico:
            break

    pop.sort(key=lambda x: x[0])
    melhor_pen = pop[0][0]
    melhor_ind = [l[:] for l in pop[0][1]]
    geracoes_sem_melhora = 0
    melhorias_consecutivas = 0

    historico_rl = getattr(analisador, "historico_aprendizado", {}) or {}
    periodos_aprendidos = int(historico_rl.get("periodos", 0))
    epsilon_atual = max(0.05, 0.20 - periodos_aprendidos * 0.01)
    maestro_rl = QLearningMaestro(
        q_table=historico_rl.get("q_table"),
        epsilon=epsilon_atual,
        alpha=0.25,
        gamma=0.90,
    )

    for ger in range(1, 301):
        if melhor_pen <= pen_min_teorico or (time.time() - t0) > tempo_limite:
            break

        if callback_progresso and ger % 20 == 0:
            callback_progresso(
                min(85, 20 + int((ger / 300) * 65)),
                f"Status: [Memético] Geração {ger} (Custo: {melhor_pen})...",
            )

        if callback_grade and ger % 5 == 0:
            grade_preview = {}
            for t_id_preview, aloc_t_preview in enumerate(melhor_ind):
                turma_preview = turmas_nomes[t_id_preview]
                slots_preview = slots_por_turma[t_id_preview]
                for idx_preview, r_idx_preview in enumerate(aloc_t_preview):
                    if r_idx_preview >= 0:
                        d_preview, a_preview = slots_preview[idx_preview]
                        grade_preview[(turma_preview, d_preview, a_preview)] = r_idx_preview
            callback_grade(grade_preview)

        media_anterior = sum(ind[0] for ind in pop) / max(1, len(pop))
        fingerprints = {
            tuple(tuple(aloc_t) for aloc_t in ind[1])
            for ind in pop
        }
        diversidade = len(fingerprints) / max(1, len(pop))
        estado = maestro_rl.observar_estado(
            melhorias_consecutivas,
            geracoes_sem_melhora,
            diversidade,
        )
        acao = maestro_rl.escolher_acao(estado)

        nova_pop = [pop[0], pop[1]]

        # Se estagnar por 15 gerações, aplica Ruin & Recreate (LNS) no melhor indivíduo
        if geracoes_sem_melhora >= 15:
            clonado = [l[:] for l in melhor_ind]
            for t_id in random.sample(
                range(num_turmas), max(1, num_turmas // 4)
            ):
                aloc_t = clonado[t_id]
                if len(aloc_t) >= 4:
                    i1, i2 = random.sample(range(len(aloc_t)), 2)
                    aloc_t[i1], aloc_t[i2] = aloc_t[i2], aloc_t[i1]
            pen_c = construir_estado_e_reparar(clonado, iteracoes_busca=80)
            nova_pop.append([pen_c, clonado])
            geracoes_sem_melhora = 0

        # Ação 2 (Local Search): refinamento direto dos melhores indivíduos.
        if acao == QLearningMaestro.ACAO_LOCAL:
            for pai in pop[:4]:
                mutante = [l[:] for l in pai[1]]
                for _ in range(2):
                    t_id = random.randrange(num_turmas)
                    aloc_t = mutante[t_id]
                    if len(aloc_t) >= 2:
                        i1, i2 = random.sample(range(len(aloc_t)), 2)
                        aloc_t[i1], aloc_t[i2] = aloc_t[i2], aloc_t[i1]
                pen_mut = construir_estado_e_reparar(mutante, iteracoes_busca=100)
                nova_pop.append([pen_mut, mutante])
                if len(nova_pop) >= TAM_POP:
                    break

        while len(nova_pop) < TAM_POP:
            # Ação 0 (Exploração): maioria mutação/LNS e pouca recombinação.
            if acao == QLearningMaestro.ACAO_EXPLORACAO:
                if random.random() < 0.70:
                    base = random.choice(pop[:max(3, len(pop) // 2)])[1]
                    mutante = [l[:] for l in base]
                    trocas = random.randint(2, max(2, min(8, num_turmas * 2)))
                    for _ in range(trocas):
                        t_id = random.randrange(num_turmas)
                        aloc_t = mutante[t_id]
                        if len(aloc_t) >= 2:
                            i1, i2 = random.sample(range(len(aloc_t)), 2)
                            aloc_t[i1], aloc_t[i2] = aloc_t[i2], aloc_t[i1]
                    pen_mut = construir_estado_e_reparar(mutante, iteracoes_busca=75)
                    nova_pop.append([pen_mut, mutante])
                    continue

            # Ação 1 (Explotação) e o remanescente da ação 2 usam crossover agressivo.
            p1 = min(random.sample(pop[:14], 3), key=lambda x: x[0])[1]
            p2 = min(random.sample(pop[:14], 3), key=lambda x: x[0])[1]

            # Crossover Inteligente: escolhe a turma do pai que gera menos choques acumulados
            filho = [None] * num_turmas
            ocup_parcial = [0] * (num_profs * num_g_slots)
            ordem_t = list(range(num_turmas))
            random.shuffle(ordem_t)

            for t_id in ordem_t:
                g1, g2 = p1[t_id], p2[t_id]
                c1 = sum(
                    custo_fixo_req[r][s]
                    + (P_CHOQUE if ocup_parcial[ocup_idx_req[r][s]] > 0 else 0)
                    for s, r in enumerate(g1)
                    if r >= 0
                )
                c2 = sum(
                    custo_fixo_req[r][s]
                    + (P_CHOQUE if ocup_parcial[ocup_idx_req[r][s]] > 0 else 0)
                    for s, r in enumerate(g2)
                    if r >= 0
                )
                escolhido = (
                    g1[:]
                    if (c1 < c2 or (c1 == c2 and random.random() < 0.5))
                    else g2[:]
                )
                filho[t_id] = escolhido
                for s, r in enumerate(escolhido):
                    if r >= 0:
                        ocup_parcial[ocup_idx_req[r][s]] += 1

            iteracoes_reparo = 90 if acao == QLearningMaestro.ACAO_EXPLOTACAO else 45
            pf = construir_estado_e_reparar(filho, iteracoes_busca=iteracoes_reparo)
            nova_pop.append([pf, filho])
            if pf <= pen_min_teorico:
                break

        pop = sorted(nova_pop, key=lambda x: x[0])
        melhor_pen_anterior = melhor_pen
        recorde_quebrado = pop[0][0] < melhor_pen
        if pop[0][0] < melhor_pen:
            melhor_pen = pop[0][0]
            melhor_ind = [l[:] for l in pop[0][1]]
            geracoes_sem_melhora = 0
            melhorias_consecutivas += 1
        else:
            geracoes_sem_melhora += 1
            melhorias_consecutivas = 0

        media_atual = sum(ind[0] for ind in pop) / max(1, len(pop))
        fingerprints = {
            tuple(tuple(aloc_t) for aloc_t in ind[1])
            for ind in pop
        }
        diversidade_atual = len(fingerprints) / max(1, len(pop))
        estado_proximo = maestro_rl.observar_estado(
            melhorias_consecutivas,
            geracoes_sem_melhora,
            diversidade_atual,
        )
        recompensa = maestro_rl.calcular_recompensa(
            recorde_quebrado=recorde_quebrado,
            melhor_pen_anterior=melhor_pen_anterior,
            melhor_pen_atual=melhor_pen,
            media_anterior=media_anterior,
            media_atual=media_atual,
            estado=estado,
        )
        maestro_rl.learn(estado, acao, recompensa, estado_proximo)

    historico_rl["q_table"] = maestro_rl.obter_tabela()

    # =========================================================================
    # 5. CONVERSÃO PARA O FORMATO PADRÃO DO GERENCIADOR
    # =========================================================================
    grade, ativas, concessoes = {}, set(), []
    for t_id, aloc_t in enumerate(melhor_ind):
        turma = turmas_nomes[t_id]
        slots_t = slots_por_turma[t_id]
        for idx_s, r_idx in enumerate(aloc_t):
            if r_idx >= 0:
                d, a = slots_t[idx_s]
                grade[(turma, d, a)] = r_idx
                ativas.add((r_idx, d, a))
                prof = analisador.requerimentos[r_idx]["professor"]
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
                        f"- {dia_s} | {aula_s}: Prof. {prof} no {turma} ({analisador.requerimentos[r_idx]['disciplina']})"
                    )

    return True, grade, ativas, concessoes