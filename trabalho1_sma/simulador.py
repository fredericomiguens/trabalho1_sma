import heapq
import sys
from pathlib import Path
import yaml

# =============================================================================
# Gerador pseudoaleatório — MINSTD / Park-Miller
# =============================================================================
# Mantido separado da lógica da simulação para que a mesma semente produza
# sempre a mesma sequência de valores.

LCG_A = 16807
LCG_M = 2147483647


class GeradorAleatorio:
    def __init__(self, seed: int):
        self.estado = int(seed)
        self.consumidos = 0

    def proximo(self) -> float:
        self.estado = (LCG_A * self.estado) % LCG_M
        self.consumidos += 1
        return self.estado / LCG_M

    def uniforme(self, minimo: float, maximo: float) -> float:
        return minimo + (maximo - minimo) * self.proximo()


# =============================================================================
# Evento
# =============================================================================

class Evento:
    CHEGADA = "CHEGADA"
    PASSAGEM = "PASSAGEM"
    SAIDA = "SAIDA"

    def __init__(self, tipo, tempo, origem=None, destino=None, ordem=0):
        self.tipo = tipo
        self.tempo = tempo
        self.origem = origem
        self.destino = destino
        self.ordem = ordem

    def __lt__(self, outro):
        # Tempo é o critério principal. A ordem de criação resolve empates.
        if self.tempo != outro.tempo:
            return self.tempo < outro.tempo
        return self.ordem < outro.ordem

    def __repr__(self):
        return (
            f"Evento({self.tipo}, t={self.tempo:.6f}, "
            f"orig={self.origem}, dest={self.destino})"
        )


# =============================================================================
# Escalonador
# =============================================================================

class Escalonador:
    def __init__(self):
        self._heap = []
        self._ordem = 0

    def adicionar(self, evento):
        evento.ordem = self._ordem
        self._ordem += 1
        heapq.heappush(self._heap, evento)

    def proximo(self):
        return heapq.heappop(self._heap)

    def vazio(self):
        return not self._heap


# =============================================================================
# Fila
# =============================================================================

class Fila:
    """Representa uma fila G/G/c[/K]."""

    def __init__(
        self,
        nome,
        servidores,
        atend_min,
        atend_max,
        capacidade=None,
        chegada_min=None,
        chegada_max=None,
    ):
        self.nome = nome
        self.servidores = int(servidores)
        self.capacidade = None if capacidade is None else int(capacidade)
        self.atend_min = float(atend_min)
        self.atend_max = float(atend_max)
        self.chegada_min = None if chegada_min is None else float(chegada_min)
        self.chegada_max = None if chegada_max is None else float(chegada_max)

        self.estado = 0
        self.perdas = 0

        # Para fila infinita, o vetor cresce somente quando um novo estado
        # aparece. Para fila finita, já sabemos todos os estados possíveis.
        tamanho = 1 if self.capacidade is None else self.capacidade + 1
        self.tempo_acumulado = [0.0] * tamanho

    def tem_chegada_externa(self):
        return self.chegada_min is not None and self.chegada_max is not None

    def cabe(self):
        return self.capacidade is None or self.estado < self.capacidade

    def entrar(self):
        self.estado += 1

    def sair(self):
        if self.estado <= 0:
            raise RuntimeError(f"Tentativa de retirar cliente de {self.nome} vazia")
        self.estado -= 1

    def acumular(self, delta):
        if delta <= 0:
            return
        if self.estado >= len(self.tempo_acumulado):
            self.tempo_acumulado.extend(
                [0.0] * (self.estado - len(self.tempo_acumulado) + 1)
            )
        self.tempo_acumulado[self.estado] += delta

    def distribuicao(self, tempo_total):
        if tempo_total <= 0:
            return [0.0] * len(self.tempo_acumulado)
        return [t / tempo_total for t in self.tempo_acumulado]

    def descricao(self):
        if self.capacidade is None:
            return f"G/G/{self.servidores}"
        return f"G/G/{self.servidores}/{self.capacidade}"


# =============================================================================
# Carregamento do YAML
# =============================================================================

def carregar_modelo(caminho):
    """
    Converte o YAML da disciplina em estruturas usadas pelo simulador.

    Formato esperado:
        rndnumbersPerSeed
        seeds
        arrivals
        queues
        network

    A ausência de 'capacity' significa capacidade infinita.
    A probabilidade que faltar para completar 1 representa saída do sistema.
    """
    caminho = Path(caminho)
    texto = caminho.read_text(encoding="utf-8")

    # !PARAMETERS é uma marca usada pelo modelo Java; não é necessária aqui.
    linhas = [linha for linha in texto.splitlines() if linha.strip() != "!PARAMETERS"]
    dados = yaml.safe_load("\n".join(linhas)) or {}

    cfg_filas = dados.get("queues", {}) or {}
    if not cfg_filas:
        raise ValueError(f"Nenhuma fila encontrada em {caminho}")

    filas = {}
    for nome, cfg in cfg_filas.items():
        if "servers" not in cfg:
            raise ValueError(f"Fila {nome}: parâmetro 'servers' ausente")
        if "minService" not in cfg or "maxService" not in cfg:
            raise ValueError(f"Fila {nome}: intervalo de atendimento incompleto")

        filas[nome] = Fila(
            nome=nome,
            servidores=cfg["servers"],
            capacidade=cfg.get("capacity"),
            atend_min=cfg["minService"],
            atend_max=cfg["maxService"],
            chegada_min=cfg.get("minArrival"),
            chegada_max=cfg.get("maxArrival"),
        )

    chegadas = {
        nome: float(tempo)
        for nome, tempo in (dados.get("arrivals", {}) or {}).items()
    }

    for nome in chegadas:
        if nome not in filas:
            raise ValueError(f"Chegada externa aponta para fila inexistente: {nome}")

    # Mantemos somente as rotas explicitamente informadas.
    # A massa restante até 1 é saída para o exterior.
    rede = {nome: [] for nome in filas}
    soma_prob = {nome: 0.0 for nome in filas}

    for entrada in dados.get("network", []) or []:
        origem = entrada["source"]
        destino = entrada["target"]
        prob = float(entrada["probability"])

        if origem not in filas:
            raise ValueError(f"Origem inexistente na rede: {origem}")
        if destino not in filas:
            raise ValueError(f"Destino inexistente na rede: {destino}")
        if prob < 0:
            raise ValueError(f"Probabilidade negativa: {origem} -> {destino}")

        soma_prob[origem] += prob
        if soma_prob[origem] > 1.0 + 1e-12:
            raise ValueError(f"Probabilidades de {origem} ultrapassam 1.0")
        rede[origem].append((prob, destino))

    # Parâmetros globais.
    seeds = dados.get("seeds", [7]) or [7]
    seed = int(seeds[0])
    total_randoms = int(dados.get("rndnumbersPerSeed", 100_000))

    return {
        "filas": filas,
        "rede": rede,
        "chegadas": chegadas,
        "seed": seed,
        "total_randoms": total_randoms,
    }

# =============================================================================
# Simulação
# =============================================================================

def simular(filas, rede, chegadas, total_randoms, seed=7):
    gerador = GeradorAleatorio(seed)
    escalonador = Escalonador()
    tempo_global = 0.0

    # -------------------------------------------------------------------------
    # Sorteios
    # -------------------------------------------------------------------------

    def ainda_pode_sortear():
        return gerador.consumidos < total_randoms

    def sortear_tempo(minimo, maximo):
        if not ainda_pode_sortear():
            return None
        return gerador.uniforme(minimo, maximo)

    def sortear_destino(fila):
        """
        Sorteia o destino de acordo com as probabilidades.

        Uma única rota de probabilidade 1 não consome aleatório.
        Se a soma das probabilidades for menor que 1, a massa restante
        representa saída do sistema.
        """
        rotas = rede.get(fila.nome, [])

        if not rotas:
            return None

        if len(rotas) == 1 and abs(rotas[0][0] - 1.0) < 1e-12:
            return rotas[0][1]

        r = gerador.proximo() if ainda_pode_sortear() else None
        if r is None:
            return None

        acumulado = 0.0
        for prob, destino in rotas:
            acumulado += prob
            if r < acumulado:
                return destino

        return None

    # -------------------------------------------------------------------------
    # Agendamento
    # -------------------------------------------------------------------------

    def agendar_atendimento(fila):
        """
        O destino é determinado no início do atendimento, antes do sorteio
        do tempo de serviço. Essa ordem é compatível com o modelo de referência.
        """
        if not ainda_pode_sortear():
            return

        destino = sortear_destino(fila)
        duracao = sortear_tempo(fila.atend_min, fila.atend_max)
        if duracao is None:
            return

        tipo = Evento.SAIDA if destino is None else Evento.PASSAGEM
        escalonador.adicionar(
            Evento(
                tipo=tipo,
                tempo=tempo_global + duracao,
                origem=fila.nome,
                destino=destino,
            )
        )

    def agendar_chegada(fila):
        if not ainda_pode_sortear():
            return
        intervalo = sortear_tempo(fila.chegada_min, fila.chegada_max)
        if intervalo is None:
            return
        escalonador.adicionar(
            Evento(
                tipo=Evento.CHEGADA,
                tempo=tempo_global + intervalo,
                destino=fila.nome,
            )
        )

    # -------------------------------------------------------------------------
    # Contabilização do tempo
    # -------------------------------------------------------------------------

    def atualizar_tempo(novo_tempo):
        nonlocal tempo_global
        delta = novo_tempo - tempo_global
        if delta < 0:
            raise RuntimeError("Eventos fora de ordem temporal")
        for fila in filas.values():
            fila.acumular(delta)
        tempo_global = novo_tempo

    # -------------------------------------------------------------------------
    # Tratadores
    # -------------------------------------------------------------------------

    def tratar_chegada(fila):
        # A próxima chegada externa é agendada independentemente de a
        # chegada atual ser aceita ou perdida.
        if fila.tem_chegada_externa() and ainda_pode_sortear():
            agendar_chegada(fila)

        if not fila.cabe():
            fila.perdas += 1
            return

        fila.entrar()
        if fila.estado <= fila.servidores and ainda_pode_sortear():
            agendar_atendimento(fila)

    def tratar_saida(fila):
        fila.sair()
        if fila.estado >= fila.servidores and ainda_pode_sortear():
            agendar_atendimento(fila)

    def tratar_passagem(origem, destino):
        origem.sair()
        if origem.estado >= origem.servidores and ainda_pode_sortear():
            agendar_atendimento(origem)

        if not destino.cabe():
            destino.perdas += 1
            return

        destino.entrar()
        if destino.estado <= destino.servidores and ainda_pode_sortear():
            agendar_atendimento(destino)

    # -------------------------------------------------------------------------
    # Primeiras chegadas externas — os tempos vêm do YAML.
    # -------------------------------------------------------------------------

    for nome, instante in chegadas.items():
        escalonador.adicionar(
            Evento(Evento.CHEGADA, float(instante), destino=nome)
        )

    # -------------------------------------------------------------------------
    # Simulação enquanto ainda houver números aleatórios disponíveis.
    # -------------------------------------------------------------------------

    while ainda_pode_sortear() and not escalonador.vazio():
        evento = escalonador.proximo()
        atualizar_tempo(evento.tempo)

        if evento.tipo == Evento.CHEGADA:
            tratar_chegada(filas[evento.destino])
        elif evento.tipo == Evento.SAIDA:
            tratar_saida(filas[evento.origem])
        elif evento.tipo == Evento.PASSAGEM:
            tratar_passagem(filas[evento.origem], filas[evento.destino])

    # -------------------------------------------------------------------------
    # Drena eventos já agendados sem criar novos eventos/sorteios.
    # Isso permite contabilizar até o último evento já programado.
    # -------------------------------------------------------------------------

    while not escalonador.vazio():
        evento = escalonador.proximo()
        atualizar_tempo(evento.tempo)

        if evento.tipo == Evento.CHEGADA:
            fila = filas[evento.destino]
            if fila.cabe():
                fila.entrar()
            else:
                fila.perdas += 1
        elif evento.tipo == Evento.SAIDA:
            filas[evento.origem].sair()
        elif evento.tipo == Evento.PASSAGEM:
            origem = filas[evento.origem]
            destino = filas[evento.destino]
            origem.sair()
            if destino.cabe():
                destino.entrar()
            else:
                destino.perdas += 1

    return {
        "tempo_global": tempo_global,
        "filas": filas,
        "randoms_consumidos": gerador.consumidos,
    }

# =============================================================================
# Resultados
# =============================================================================

def imprimir_resultados(resultado, titulo):
    print("=" * 68)
    print(f"  SIMULADOR DE REDES DE FILAS — {titulo}")
    print("=" * 68)
    print(f"Tempo total de simulação: {resultado['tempo_global']:.4f}")
    print(f"Números aleatórios consumidos: {resultado['randoms_consumidos']}")
    print()

    for fila in resultado["filas"].values():
        probs = fila.distribuicao(resultado["tempo_global"])

        print(f"--- {fila.nome} ({fila.descricao()}) ---")
        if fila.tem_chegada_externa():
            print(f"  Chegada:     {fila.chegada_min:.1f} .. {fila.chegada_max:.1f}")
        else:
            print("  Chegada:     interna")
        print(f"  Atendimento: {fila.atend_min:.1f} .. {fila.atend_max:.1f}")
        print(f"  Perdas:      {fila.perdas}")
        print(f"  {'Estado':<8} {'Tempo acumulado':<20} {'Probabilidade':<15}")
        print("  " + "-" * 48)

        for estado, (tempo, prob) in enumerate(zip(fila.tempo_acumulado, probs)):
            print(f"  {estado:<8} {tempo:<20.4f} {prob:<15.4f}")

        print("  " + "-" * 48)
        print(f"  {'TOTAL':<8} {sum(fila.tempo_acumulado):<20.4f} {sum(probs):<15.4f}")
        print()

# =============================================================================
# Execução de modelos
# =============================================================================

def executar_modelo(caminho):
    caminho = Path(caminho)
    cfg = carregar_modelo(caminho)

    resultado = simular(
        filas=cfg["filas"],
        rede=cfg["rede"],
        chegadas=cfg["chegadas"],
        total_randoms=cfg["total_randoms"],
        seed=cfg["seed"],
    )

    imprimir_resultados(resultado, caminho.stem)
    return resultado

def main():
    """
    Uso:
        python simulador.py modelos/trab1.yml
        python simulador.py modelos/cenario1_gg1_5.yml modelos/cenario4_rede.yml

    Sem argumentos, executa todos os .yml encontrados em ./modelos.
    """
    argumentos = sys.argv[1:]

    if argumentos:
        modelos = [Path(arg) for arg in argumentos]
    else:
        modelos = sorted(Path(__file__).parent.joinpath("modelos").glob("*.yml"))

    if not modelos:
        print("Nenhum arquivo .yml foi encontrado.")
        return

    for modelo in modelos:
        executar_modelo(modelo)

if __name__ == "__main__":
    main()
