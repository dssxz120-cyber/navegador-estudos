"""Timer Pomodoro: 25 min de estudo, 5 min de pausa e, a cada 4 ciclos,
uma pausa longa de 15 min.

Esta classe só cuida da contagem. Quem desenha o timer na tela é a janela,
que é avisada pelas funções ao_mudar e ao_trocar_fase.

Duas garantias:
  - O tempo é medido pelo RELÓGIO (horário de término), não contando tiques.
    Assim o timer fica certo mesmo se o computador suspender ou ficar lento.
  - O estado é salvo em pomodoro.json. Ao reabrir o navegador, o timer
    continua de onde estava. Se a fase terminou com o navegador fechado,
    ele passa para a fase seguinte, pausado, esperando o aluno.
"""

import json
import math
import time

from gi.repository import GLib

from .arquivos import gravar_atomico

ESTUDO, PAUSA, PAUSA_LONGA = "estudo", "pausa", "pausa_longa"
DURACAO = {ESTUDO: 25 * 60, PAUSA: 5 * 60, PAUSA_LONGA: 15 * 60}
NOME_FASE = {ESTUDO: "Estudo", PAUSA: "Pausa", PAUSA_LONGA: "Pausa longa"}


class Pomodoro:
    def __init__(self, ao_mudar, ao_trocar_fase, arquivo=None, relogio=time.time):
        self.ao_mudar = ao_mudar              # chamada a cada segundo
        self.ao_trocar_fase = ao_trocar_fase  # chamada quando uma fase acaba
        self.arquivo = arquivo                # None = não salva (testes)
        self._agora = relogio
        self.fase = ESTUDO
        self.ciclos_feitos = 0
        self._parado_com = DURACAO[ESTUDO]    # segundos restantes quando pausado
        self._fim = None                      # horário de término quando rodando
        self._relogio = None                  # id do timer do GLib
        self._restaurar()

    # ---------------- estado ----------------

    @property
    def rodando(self):
        return self._fim is not None

    @property
    def restante(self):
        if self._fim is None:
            return self._parado_com
        return max(0, math.ceil(self._fim - self._agora()))

    def texto(self):
        minutos, segundos = divmod(self.restante, 60)
        return f"{minutos:02d}:{segundos:02d}"

    # ---------------- ações ----------------

    def iniciar_ou_pausar(self):
        if self.rodando:
            self._parado_com = self.restante
            self._fim = None
            self._parar_relogio()
        else:
            self._fim = self._agora() + self._parado_com
            self._ligar_relogio()
        self._salvar()
        self.ao_mudar()

    def zerar(self):
        self._parar_relogio()
        self._fim = None
        self.fase, self.ciclos_feitos, self._parado_com = ESTUDO, 0, DURACAO[ESTUDO]
        self._salvar()
        self.ao_mudar()

    # ---------------- relógio ----------------

    def _ligar_relogio(self):
        if self._relogio is None:
            self._relogio = GLib.timeout_add_seconds(1, self._tique)

    def _parar_relogio(self):
        if self._relogio is not None:
            GLib.source_remove(self._relogio)
            self._relogio = None

    def _proxima_fase(self):
        if self.fase == ESTUDO:
            self.ciclos_feitos += 1
            return PAUSA_LONGA if self.ciclos_feitos % 4 == 0 else PAUSA
        return ESTUDO

    def _tique(self):
        if self.rodando and self.restante <= 0:
            fase_que_acabou = self.fase
            self.fase = self._proxima_fase()
            self._fim = self._agora() + DURACAO[self.fase]   # a próxima fase já começa
            self._salvar()
            self.ao_trocar_fase(fase_que_acabou, self.fase)
        self.ao_mudar()
        return self.rodando   # False desliga o timer do GLib

    # ---------------- salvar e restaurar ----------------

    def _salvar(self):
        if self.arquivo is None:
            return
        estado = {"fase": self.fase, "ciclos": self.ciclos_feitos,
                  "rodando": self.rodando, "fim": self._fim, "restante": self._parado_com}
        try:
            gravar_atomico(self.arquivo, json.dumps(estado))
        except OSError:
            pass     # o timer continua funcionando; só não será lembrado

    def _restaurar(self):
        if self.arquivo is None:
            return
        try:
            estado = json.loads(self.arquivo.read_text(encoding="utf-8"))
            fase = estado["fase"]
            ciclos = int(estado["ciclos"])
            duracao = DURACAO[fase]
            restante = int(estado["restante"])
            fim = float(estado["fim"]) if estado.get("rodando") else None
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return       # sem estado salvo (ou estragado): começa do zero
        if ciclos < 0 or not 0 < restante <= duracao:
            return
        self.fase, self.ciclos_feitos, self._parado_com = fase, ciclos, restante
        if fim is None:
            return
        falta = fim - self._agora()
        if 0 < falta <= duracao:
            self._fim = fim               # continua rodando de onde estava
            self._ligar_relogio()
        elif falta <= 0:
            # A fase terminou com o navegador fechado: vai para a próxima, pausado.
            self.fase = self._proxima_fase()
            self._parado_com = DURACAO[self.fase]
            self._salvar()
        # falta > duração: horário inválido (relógio mexido); fica pausado
