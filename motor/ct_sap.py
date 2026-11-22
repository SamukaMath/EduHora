from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import random


@dataclass
class GeneAula:
    disciplina: str
    professor: str
    sala: str
    horario: Tuple[int, int]
    grupo_alunos: str


@dataclass
class ResultadoCTSAP:
    cromossomo: List[GeneAula]
    fitness: float
    hard_penalties: int
    soft_penalties: int


class CTSAPProblem:
    """
    Representa o CT-SAP independente do motor genético.
    Pode ser usado com ou sem salas/alunos cadastrados.
    """

    def __init__(
        self,
        dias: Sequence[str],
        aulas_manha: int,
        aulas_tarde: int,
        turmas: Dict[str, str],
        professores: Dict[str, dict],
        requerimentos: Sequence[dict],
        salas: Optional[Dict[str, object]] = None,
        alunos: Optional[Dict[str, dict]] = None,
        preferencias_alunos: Optional[Dict[str, dict]] = None,
        rng: Optional[random.Random] = None,
    ):
        self.dias = list(dias)
        self.aulas_manha = int(aulas_manha)
        self.aulas_tarde = int(aulas_tarde)
        self.total_aulas_dia = self.aulas_manha + self.aulas_tarde
        self.turmas = dict(turmas)
        self.professores = dict(professores)
        self.requerimentos = list(requerimentos)
        self.salas = dict(salas or {})
        self.alunos = dict(alunos or {})
        self.preferencias_alunos = dict(preferencias_alunos or {})
        self.rng = rng or random

        self.capacidade_turma = {
            str(grupo): len(dados.get("alunos", []))
            if isinstance(dados, dict)
            else int(dados or 0)
            for grupo, dados in self.alunos.items()
        }

    @classmethod
    def from_eduhora(
        cls,
        dias_semana,
        aulas_manha,
        aulas_tarde,
        turmas,
        professores,
        requerimentos,
        salas=None,
        alunos=None,
        preferencias_alunos=None,
    ):
        return cls(
            dias=dias_semana,
            aulas_manha=aulas_manha,
            aulas_tarde=aulas_tarde,
            turmas=turmas,
            professores=professores,
            requerimentos=requerimentos,
            salas=salas,
            alunos=alunos,
            preferencias_alunos=preferencias_alunos,
        )

    def faixas_turno(self, turma):
        turno = str(self.turmas.get(turma, "Manhã")).strip().lower()
        if turno.startswith("m"):
            return range(self.aulas_manha)
        return range(self.aulas_manha, self.total_aulas_dia)

    def horario_valido_para_turma(self, turma, horario):
        dia, aula = horario
        return 0 <= dia < len(self.dias) and aula in self.faixas_turno(turma)

    def professor_bloqueado(self, professor, horario):
        dados = self.professores.get(professor, {})
        dia, aula = horario

        for d_raw in dados.get("manha", []):
            d = self._normalizar_dia(d_raw)
            if d == dia and aula < self.aulas_manha:
                return True
        for d_raw in dados.get("tarde", []):
            d = self._normalizar_dia(d_raw)
            if d == dia and aula >= self.aulas_manha:
                return True
        for bloqueio in dados.get("bloqueios", []):
            d = self._normalizar_dia(bloqueio.get("dia", -1))
            aula_local = int(bloqueio.get("aula", -1))
            turno = str(bloqueio.get("turno", "")).upper()
            aula_global = aula_local
            if turno.startswith("T"):
                aula_global = self.aulas_manha + aula_local
            if d == dia and aula_global == aula:
                return True
        return False

    def _normalizar_dia(self, d_raw):
        if isinstance(d_raw, int):
            return d_raw
        texto = str(d_raw).strip().lower()
        if texto.isdigit():
            return int(texto)
        for indice, nome in enumerate(self.dias):
            if texto == str(nome).strip().lower():
                return indice
        return -1

    def aulas_do_grupo(self, grupo):
        return [
            horario
            for horario in self.horarios_possiveis(grupo)
        ]

    def horarios_possiveis(self, grupo=None):
        if grupo is not None:
            return [
                (dia, aula)
                for dia in range(len(self.dias))
                for aula in self.faixas_turno(grupo)
            ]
        return [
            (dia, aula)
            for dia in range(len(self.dias))
            for aula in range(self.total_aulas_dia)
        ]

    def genes_exigidos(self) -> List[GeneAula]:
        genes = []
        for req in self.requerimentos:
            for _ in range(int(req["aulas"])):
                genes.append(
                    GeneAula(
                        disciplina=str(req["disciplina"]),
                        professor=str(req["professor"]),
                        sala=self.escolher_sala_inicial(req["turma"]),
                        horario=(0, self.primeira_aula_do_turno(req["turma"])),
                        grupo_alunos=str(req["turma"]),
                    )
                )
        return genes

    def primeira_aula_do_turno(self, turma):
        return next(iter(self.faixas_turno(turma)), 0)

    def escolher_sala_inicial(self, grupo):
        capacidade = self.capacidade_turma.get(str(grupo), 0)
        candidatas = list(self.salas.keys())
        if not candidatas:
            return "SEM_SALA"
        validas = []
        for nome in candidatas:
            dados = self.salas[nome]
            capacidade_sala = int(dados.get("capacidade", 0)) if isinstance(dados, dict) else int(dados)
            if capacidade <= 0 or capacidade_sala >= capacidade:
                validas.append(nome)
        return validas[0] if validas else candidatas[0]


class CTSAPFitness:
    PENALIDADE_CONFLITO_PROFESSOR = 10000
    PENALIDADE_CONFLITO_ALUNO = 10000
    PENALIDADE_CAPACIDADE_SALA = 12000
    PENALIDADE_PROFESSOR_BLOQUEADO = 9000
    PENALIDADE_SALA_CONFLITO = 8000

    def avaliar(self, problema: CTSAPProblem, cromossomo: Sequence[GeneAula]):
        hard = 0
        soft = 0

        uso_professor = set()
        uso_grupo = set()
        uso_sala = set()
        uso_alunos = {}
        aulas_por_professor = {}

        for gene in cromossomo:
            horario = gene.horario
            if not problema.horario_valido_para_turma(gene.grupo_alunos, horario):
                hard += 3000

            chave_prof = (gene.professor, horario)
            if chave_prof in uso_professor:
                hard += self.PENALIDADE_CONFLITO_PROFESSOR
            uso_professor.add(chave_prof)

            chave_grupo = (gene.grupo_alunos, horario)
            if chave_grupo in uso_grupo:
                hard += self.PENALIDADE_CONFLITO_ALUNO
            uso_grupo.add(chave_grupo)

            dados_grupo = problema.alunos.get(gene.grupo_alunos, {})
            if isinstance(dados_grupo, dict):
                ids_alunos = set(map(str, dados_grupo.get("alunos", [])))
            else:
                ids_alunos = set(map(str, dados_grupo or []))
            if not ids_alunos:
                ids_alunos = {str(gene.grupo_alunos)}

            alunos_no_horario = uso_alunos.setdefault(horario, set())
            if ids_alunos & alunos_no_horario:
                hard += self.PENALIDADE_CONFLITO_ALUNO
            alunos_no_horario.update(ids_alunos)

            if gene.sala != "SEM_SALA":
                chave_sala = (gene.sala, horario)
                if chave_sala in uso_sala:
                    hard += self.PENALIDADE_SALA_CONFLITO
                uso_sala.add(chave_sala)

                dados_sala = problema.salas.get(gene.sala, {})
                capacidade_sala = int(dados_sala.get("capacidade", 0)) if isinstance(dados_sala, dict) else int(dados_sala or 0)
                capacidade_grupo = problema.capacidade_turma.get(str(gene.grupo_alunos), 0)
                if capacidade_sala > 0 and capacidade_grupo > 0 and capacidade_grupo > capacidade_sala:
                    hard += self.PENALIDADE_CAPACIDADE_SALA

            if problema.professor_bloqueado(gene.professor, horario):
                hard += self.PENALIDADE_PROFESSOR_BLOQUEADO

            aulas_por_professor.setdefault(gene.professor, []).append(horario)

        for professor, horarios in aulas_por_professor.items():
            por_dia = {}
            for dia, aula in horarios:
                por_dia.setdefault(dia, []).append(aula)
            for aulas in por_dia.values():
                aulas = sorted(set(aulas))
                for anterior, atual in zip(aulas, aulas[1:]):
                    janela = atual - anterior - 1
                    if janela > 0:
                        soft += 120 * janela

        for grupo, preferencias in problema.preferencias_alunos.items():
            disciplinas = (
                preferencias.get("disciplinas", [])
                if isinstance(preferencias, dict)
                else preferencias
            )
            if isinstance(disciplinas, dict):
                disciplinas = [
                    disciplina
                    for disciplina, prioridade in disciplinas.items()
                    if int(prioridade) > 0
                ]
            disciplinas_preferidas = set(map(str, disciplinas))
            disciplinas_presentes = {
                gene.disciplina
                for gene in cromossomo
                if gene.grupo_alunos == str(grupo)
            }
            soft += len(disciplinas_preferidas - disciplinas_presentes) * 50

        return -hard - soft, hard, soft


class CTSAP_GeneticSolver:
    def __init__(
        self,
        problema: CTSAPProblem,
        tamanho_populacao=60,
        max_geracoes=200,
        taxa_mutacao=0.18,
        taxa_crossover=0.85,
        elite=5,
        seed=None,
    ):
        self.problema = problema
        self.tamanho_populacao = tamanho_populacao
        self.max_geracoes = max_geracoes
        self.taxa_mutacao = taxa_mutacao
        self.taxa_crossover = taxa_crossover
        self.elite = elite
        self.rng = random.Random(seed)
        self.fitness = CTSAPFitness()

    def criar_individuo(self):
        individuo = self.problema.genes_exigidos()
        horarios_por_grupo = {}
        for gene in individuo:
            horarios = horarios_por_grupo.setdefault(
                gene.grupo_alunos,
                list(self.problema.horarios_possiveis(gene.grupo_alunos)),
            )
            validos = [
                horario
                for horario in horarios
                if not self.problema.professor_bloqueado(gene.professor, horario)
            ]
            gene.horario = self.rng.choice(validos or horarios)
            if self.problema.salas:
                candidatas = list(self.problema.salas)
                gene.sala = self.rng.choice(candidatas)
        return individuo

    def avaliar(self, cromossomo):
        return self.fitness.avaliar(self.problema, cromossomo)

    def crossover_por_dias(self, pai_a, pai_b):
        if len(pai_a) != len(pai_b):
            raise ValueError("Os cromossomos precisam conter o mesmo número de genes.")

        corte = self.rng.randrange(max(1, len(self.problema.dias)))
        filho = []
        for gene_a, gene_b in zip(pai_a, pai_b):
            origem = gene_a if gene_a.horario[0] <= corte else gene_b
            filho.append(
                GeneAula(
                    disciplina=origem.disciplina,
                    professor=origem.professor,
                    sala=origem.sala,
                    horario=origem.horario,
                    grupo_alunos=origem.grupo_alunos,
                )
            )
        return self.reparar_duplicacoes(filho)

    def reparar_duplicacoes(self, cromossomo):
        reparado = []
        usados_grupo_horario = set()
        usados_professor_horario = set()
        usados_sala_horario = set()

        esperados = self.problema.genes_exigidos()
        faltantes = {
            (gene.disciplina, gene.professor, gene.grupo_alunos): 0
            for gene in esperados
        }
        for gene in esperados:
            chave = (gene.disciplina, gene.professor, gene.grupo_alunos)
            faltantes[chave] += 1

        for gene in cromossomo:
            chave = (gene.disciplina, gene.professor, gene.grupo_alunos)
            horario = gene.horario
            nova = True
            if chave not in faltantes or faltantes[chave] <= 0:
                nova = False
            if (gene.grupo_alunos, horario) in usados_grupo_horario:
                nova = False
            if (gene.professor, horario) in usados_professor_horario:
                nova = False
            if gene.sala != "SEM_SALA" and (gene.sala, horario) in usados_sala_horario:
                nova = False
            if nova:
                reparado.append(gene)
                faltantes[chave] -= 1
                usados_grupo_horario.add((gene.grupo_alunos, horario))
                usados_professor_horario.add((gene.professor, horario))
                if gene.sala != "SEM_SALA":
                    usados_sala_horario.add((gene.sala, horario))

        for gene in esperados:
            chave = (gene.disciplina, gene.professor, gene.grupo_alunos)
            if faltantes[chave] <= 0:
                continue
            copia = GeneAula(
                disciplina=gene.disciplina,
                professor=gene.professor,
                sala=gene.sala,
                horario=gene.horario,
                grupo_alunos=gene.grupo_alunos,
            )
            for horario in self.problema.horarios_possiveis(copia.grupo_alunos):
                if (copia.grupo_alunos, horario) in usados_grupo_horario:
                    continue
                if (copia.professor, horario) in usados_professor_horario:
                    continue
                if self.problema.professor_bloqueado(copia.professor, horario):
                    continue
                copia.horario = horario
                break
            reparado.append(copia)
            faltantes[chave] -= 1
        return reparado

    def mutacao(self, cromossomo):
        mutante = [
            GeneAula(
                disciplina=gene.disciplina,
                professor=gene.professor,
                sala=gene.sala,
                horario=gene.horario,
                grupo_alunos=gene.grupo_alunos,
            )
            for gene in cromossomo
        ]
        if not mutante:
            return mutante

        indice = self.rng.randrange(len(mutante))
        gene = mutante[indice]

        if self.problema.salas and self.rng.random() < 0.35:
            gene.sala = self.rng.choice(list(self.problema.salas))
        else:
            horarios = list(self.problema.horarios_possiveis(gene.grupo_alunos))
            candidatos = [
                horario
                for horario in horarios
                if not self.problema.professor_bloqueado(gene.professor, horario)
            ]
            if candidatos and self.rng.random() < 0.60:
                gene.horario = self.rng.choice(candidatos)
            elif len(mutante) > 1:
                outro = self.rng.choice([g for i, g in enumerate(mutante) if i != indice])
                gene.horario, outro.horario = outro.horario, gene.horario

        return self.reparar_duplicacoes(mutante)

    def selecao_torneio(self, populacao, tamanho=3):
        candidatos = self.rng.sample(populacao, min(tamanho, len(populacao)))
        return max(candidatos, key=lambda item: item[0])[1]

    def rodar(self, callback=None):
        populacao = []
        for _ in range(self.tamanho_populacao):
            individuo = self.criar_individuo()
            fitness, hard, soft = self.avaliar(individuo)
            populacao.append((fitness, individuo, hard, soft))

        for geracao in range(1, self.max_geracoes + 1):
            populacao.sort(key=lambda item: item[0], reverse=True)
            nova_populacao = populacao[:self.elite]

            while len(nova_populacao) < self.tamanho_populacao:
                pai_a = self.selecao_torneio(populacao)
                pai_b = self.selecao_torneio(populacao)

                if self.rng.random() < self.taxa_crossover:
                    filho = self.crossover_por_dias(pai_a, pai_b)
                else:
                    filho = [
                        GeneAula(
                            disciplina=gene.disciplina,
                            professor=gene.professor,
                            sala=gene.sala,
                            horario=gene.horario,
                            grupo_alunos=gene.grupo_alunos,
                        )
                        for gene in pai_a
                    ]

                if self.rng.random() < self.taxa_mutacao:
                    filho = self.mutacao(filho)

                fitness, hard, soft = self.avaliar(filho)
                nova_populacao.append((fitness, filho, hard, soft))

                if callback:
                    callback(geracao, nova_populacao[0])

            populacao = nova_populacao

        populacao.sort(key=lambda item: item[0], reverse=True)
        fitness, cromossomo, hard, soft = populacao[0]
        return ResultadoCTSAP(cromossomo, fitness, hard, soft)
