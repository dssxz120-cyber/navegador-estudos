"""Conta quanto tempo foi passado em cada site, dia a dia.

Cada dia vira um arquivo, por exemplo:
  ~/.local/share/navegador-estudos/tempo/2026-10-12.json
  {"Wikipédia": 1260, "Khan Academy": 845}     (valores em segundos)
"""

import datetime
import json
import sys

from . import caminhos
from .arquivos import (PoliticaDeCopias, apagar_copias_antigas, gravar_com_copia,
                       ler_com_recuperacao)

DIAS_DE_COPIAS = 30     # cópias do tempo de estudo mais velhas que isso são apagadas


def _tempo_valido(dados):
    conteudo = json.loads(dados.decode("utf-8"))
    return isinstance(conteudo, dict) and all(
        isinstance(site, str) and isinstance(segundos, (int, float)) and segundos >= 0
        for site, segundos in conteudo.items())


# O tempo é salvo a cada 15 s; uma cópia por hora já basta.
POLITICA = PoliticaDeCopias(validar=_tempo_valido, intervalo_minimo=3600)


def deve_contar(janela_ativa, segundos_parado, tocando_audio, limite_segundos):
    """Este segundo conta como estudo?

    - Janela do navegador não está em primeiro plano: não conta.
    - Tocando áudio (vídeo-aula, música): conta, mesmo sem mexer no mouse.
    - Sem teclado/mouse há mais tempo que o limite: não conta (o aluno saiu).
    - Não dá para saber (segundos_parado = None): conta, como antes.
    """
    if not janela_ativa:
        return False
    if tocando_audio or segundos_parado is None:
        return True
    return segundos_parado < limite_segundos


DIAS_DA_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
                  "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]


def texto_do_relogio(agora):
    """(hora, data) para o relógio da barra: ("14:05", "Segunda-feira, 12 de outubro de 2026")."""
    data = (f"{DIAS_DA_SEMANA[agora.weekday()].capitalize()}, {agora.day} de "
            f"{MESES[agora.month - 1]} de {agora.year}")
    return f"{agora.hour:02d}:{agora.minute:02d}", data


def formatar(segundos):
    """3725 -> '1 h 02 min';  95 -> '1 min';  20 -> 'menos de 1 min'."""
    minutos = int(segundos) // 60
    if minutos == 0:
        return "menos de 1 min"
    horas, minutos = divmod(minutos, 60)
    return f"{horas} h {minutos:02d} min" if horas else f"{minutos} min"


class ContadorDeTempo:
    def __init__(self):
        self.dia = None
        self.por_site = {}
        self._carregar_hoje()

    def _arquivo(self):
        return caminhos.PASTA_TEMPO / f"{self.dia.isoformat()}.json"

    def _carregar_hoje(self):
        self.dia = datetime.date.today()
        # Se o arquivo de hoje estiver corrompido, ele é preservado com outro
        # nome e a última cópia válida é usada (nada é sobrescrito em silêncio).
        dados = ler_com_recuperacao(self._arquivo(), POLITICA)
        self.por_site = json.loads(dados.decode("utf-8")) if dados is not None else {}

    def somar(self, site, segundos=1):
        if datetime.date.today() != self.dia:   # virou o dia: começa do zero
            self.salvar()
            self._carregar_hoje()
        self.por_site[site] = self.por_site.get(site, 0) + segundos

    def salvar(self):
        """Grava o tempo de hoje. Devolve False se não conseguiu.

        Nunca lança exceção: ela é chamada por um relógio do GTK, e uma exceção
        ali desligaria a contagem de tempo para sempre. Se falhar (ex.: disco
        cheio), os dados continuam na memória e a próxima tentativa grava tudo.
        """
        try:
            gravar_com_copia(self._arquivo(),
                             json.dumps(self.por_site, ensure_ascii=False, indent=1), POLITICA)
        except OSError as erro:
            print(f"Navegador de Estudos: não foi possível salvar o tempo de estudo "
                  f"({erro.strerror}); nova tentativa em seguida", file=sys.stderr)
            return False
        apagar_copias_antigas(caminhos.PASTA_TEMPO, DIAS_DE_COPIAS)
        return True

    def total(self):
        return sum(self.por_site.values())

    def dias_seguidos(self, minimo_segundos=10 * 60):
        """Quantos dias seguidos, até hoje, tiveram pelo menos 10 min de estudo.

        Hoje só entra na conta quando já bateu o mínimo; se ainda não bateu,
        a sequência de ontem para trás continua valendo (não "quebra" de manhã).
        """
        dias = 1 if self.total() >= minimo_segundos else 0
        dia = self.dia - datetime.timedelta(days=1)
        while True:
            arquivo = caminhos.PASTA_TEMPO / f"{dia.isoformat()}.json"
            try:
                total = sum(json.loads(arquivo.read_text(encoding="utf-8")).values())
            except (OSError, ValueError):
                break
            if total < minimo_segundos:
                break
            dias += 1
            dia -= datetime.timedelta(days=1)
        return dias

    def ranking(self, agrupar=None):
        """Lista [(site, segundos)] do mais usado para o menos usado.

        agrupar: função opcional chave -> nome; chaves com o mesmo nome são
        somadas (ex.: "scielo.org" e "SciELO" viram uma linha só).
        """
        somas = {}
        for chave, segundos in self.por_site.items():
            nome = agrupar(chave) if agrupar else chave
            somas[nome] = somas.get(nome, 0) + segundos
        return sorted(somas.items(), key=lambda item: -item[1])
