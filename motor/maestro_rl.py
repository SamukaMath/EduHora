import random


class QLearningMaestro:
    """
    Hiper-heurística leve baseada em Q-Learning.
    A tabela aprende quais operadores funcionam em cada estado da busca.
    """

    ESTADO_MELHORIA = 0
    ESTADO_ESTAGNACAO = 1
    ESTADO_CONVERGENCIA = 2

    ACAO_EXPLORACAO = 0
    ACAO_EXPLOTACAO = 1
    ACAO_LOCAL = 2

    def __init__(
        self,
        q_table=None,
        epsilon=0.20,
        alpha=0.25,
        gamma=0.90,
        sementes_estados=3,
        semente=None,
    ):
        self.q_table = q_table if isinstance(q_table, dict) else {}
        self.epsilon = float(epsilon)
        self.alpha = float(alpha)
        self.gamma = float(gamma)
        self.sementes_estados = int(sementes_estados)
        self.rng = random.Random(semente)

        for estado in range(3):
            self.inicializar_estado(estado)

    def inicializar_tabela(self):
        for estado in range(3):
            self.inicializar_estado(estado)

    def inicializar_estado(self, estado):
        valores = self.q_table.setdefault(str(estado), {})
        for acao in range(3):
            valores.setdefault(str(acao), 0.0)

    def escolher_acao(self, estado):
        self.inicializar_estado(estado)
        valores = self.q_table[str(estado)]
        if self.rng.random() < self.epsilon:
            return self.rng.randint(0, 2)

        melhor_valor = max(valores.values())
        melhores = [
            acao
            for acao in range(3)
            if valores[str(acao)] == melhor_valor
        ]
        return self.rng.choice(melhores)

    def learn(self, estado, acao, recompensa, estado_proximo):
        self.inicializar_estado(estado)
        self.inicializar_estado(estado_proximo)

        chave_estado = str(estado)
        chave_acao = str(acao)
        chave_proximo = str(estado_proximo)
        valor_atual = float(self.q_table[chave_estado][chave_acao])
        melhor_proximo = max(
            float(valor)
            for valor in self.q_table[chave_proximo].values()
        )
        novo_valor = valor_atual + self.alpha * (
            float(recompensa) + self.gamma * melhor_proximo - valor_atual
        )
        self.q_table[chave_estado][chave_acao] = round(novo_valor, 6)

    def observar_estado(
        self,
        melhorias_consecutivas,
        geracoes_sem_melhora,
        diversidade,
    ):
        if melhorias_consecutivas >= self.sementes_estados:
            return self.ESTADO_MELHORIA
        if geracoes_sem_melhora >= 15 or diversidade < 0.15:
            return self.ESTADO_CONVERGENCIA
        return self.ESTADO_ESTAGNACAO

    def calcular_recompensa(
        self,
        recorde_quebrado,
        melhor_pen_anterior,
        melhor_pen_atual,
        media_anterior,
        media_atual,
        estado,
    ):
        if recorde_quebrado:
            return 10.0
        if media_atual < media_anterior:
            return 0.0
        if estado == self.ESTADO_CONVERGENCIA:
            return -5.0
        if melhor_pen_atual >= melhor_pen_anterior:
            return -3.0
        return -2.0

    def obter_tabela(self):
        return self.q_table
