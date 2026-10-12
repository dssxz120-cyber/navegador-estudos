"""Testes do timer Pomodoro, com um relógio falso (sem esperar 25 minutos)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from estudos.nucleo import pomodoro  # noqa: E402
from estudos.nucleo.pomodoro import ESTUDO, PAUSA, PAUSA_LONGA, Pomodoro  # noqa: E402


class RelogioFalso:
    def __init__(self, inicio=1_000_000.0):
        self.agora = inicio

    def __call__(self):
        return self.agora


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.arquivo = Path(self._tmp.name) / "pomodoro.json"
        self.relogio = RelogioFalso()
        self.fases = []

    def tearDown(self):
        self._tmp.cleanup()

    def novo(self, arquivo=None):
        p = Pomodoro(lambda: None, lambda acabou, comeca: self.fases.append((acabou, comeca)),
                     arquivo=arquivo, relogio=self.relogio)
        self.addCleanup(p._parar_relogio)
        return p

    def passar(self, p, segundos):
        """Avança o relógio e dá um tique (como o GLib faria)."""
        self.relogio.agora += segundos
        p._tique()


class TestContagem(_Base):
    def test_estado_inicial(self):
        p = self.novo()
        self.assertEqual((p.fase, p.texto(), p.ciclos_feitos, p.rodando), (ESTUDO, "25:00", 0, False))

    def test_conta_pelo_relogio(self):
        p = self.novo()
        p.iniciar_ou_pausar()
        self.passar(p, 61.2)
        self.assertEqual(p.texto(), "23:59")

    def test_ciclo_completo_com_pausa_longa(self):
        p = self.novo()
        p.iniciar_ou_pausar()
        esperado = []
        for ciclo in range(1, 5):
            self.passar(p, pomodoro.DURACAO[ESTUDO])
            pausa = PAUSA_LONGA if ciclo == 4 else PAUSA
            esperado.append((ESTUDO, pausa))
            self.passar(p, pomodoro.DURACAO[pausa])
            esperado.append((pausa, ESTUDO))
        self.assertEqual(self.fases, esperado)
        self.assertEqual(p.ciclos_feitos, 4)

    def test_pausar_congela_o_tempo(self):
        p = self.novo()
        p.iniciar_ou_pausar()
        self.passar(p, 100)
        p.iniciar_ou_pausar()                 # pausa
        self.relogio.agora += 3600            # uma hora parado
        self.assertEqual(p.restante, 25 * 60 - 100)
        p.iniciar_ou_pausar()
        self.passar(p, 10)
        self.assertEqual(p.restante, 25 * 60 - 110)

    def test_suspender_o_computador(self):
        """Suspendeu com 5 min restando e voltou 2 h depois: a fase acaba na hora."""
        p = self.novo()
        p.iniciar_ou_pausar()
        self.passar(p, 20 * 60)
        self.passar(p, 2 * 3600)              # um único tique depois de acordar
        self.assertEqual(self.fases, [(ESTUDO, PAUSA)])
        self.assertEqual(p.restante, 5 * 60)  # a pausa começa a partir de agora

    def test_zerar(self):
        p = self.novo()
        p.iniciar_ou_pausar()
        self.passar(p, pomodoro.DURACAO[ESTUDO])
        p.zerar()
        self.assertEqual((p.fase, p.restante, p.ciclos_feitos, p.rodando), (ESTUDO, 1500, 0, False))


class TestPersistencia(_Base):
    def test_continua_rodando_ao_reabrir(self):
        p = self.novo(self.arquivo)
        p.iniciar_ou_pausar()
        self.passar(p, 300)
        p._parar_relogio()                    # "fechou o navegador"
        self.relogio.agora += 120             # reabriu 2 min depois
        q = self.novo(self.arquivo)
        self.assertTrue(q.rodando)
        self.assertEqual(q.restante, 25 * 60 - 420)

    def test_pausado_continua_pausado(self):
        p = self.novo(self.arquivo)
        p.iniciar_ou_pausar()
        self.passar(p, 90)
        p.iniciar_ou_pausar()
        self.relogio.agora += 86400
        q = self.novo(self.arquivo)
        self.assertFalse(q.rodando)
        self.assertEqual(q.restante, 25 * 60 - 90)

    def test_fase_acabou_com_o_navegador_fechado(self):
        p = self.novo(self.arquivo)
        p.iniciar_ou_pausar()
        p._parar_relogio()
        self.relogio.agora += 3 * 3600
        q = self.novo(self.arquivo)
        self.assertEqual((q.fase, q.ciclos_feitos, q.rodando, q.restante), (PAUSA, 1, False, 300))

    def test_arquivo_estragado_ou_absurdo_comeca_do_zero(self):
        for conteudo in ["{lixo", json.dumps({"fase": "dormir", "ciclos": 1, "restante": 10}),
                         json.dumps({"fase": ESTUDO, "ciclos": -5, "restante": 10}),
                         json.dumps({"fase": ESTUDO, "ciclos": 0, "restante": 999999})]:
            self.arquivo.write_text(conteudo)
            q = self.novo(self.arquivo)
            self.assertEqual((q.fase, q.restante, q.rodando), (ESTUDO, 1500, False), conteudo)

    def test_relogio_mexido_para_tras_nao_trava(self):
        self.arquivo.write_text(json.dumps({"fase": ESTUDO, "ciclos": 0, "rodando": True,
                                            "fim": self.relogio.agora + 10**7, "restante": 1500}))
        q = self.novo(self.arquivo)
        self.assertFalse(q.rodando)
        self.assertEqual(q.restante, 1500)

    def test_arquivo_e_privado(self):
        p = self.novo(self.arquivo)
        p.iniciar_ou_pausar()
        self.assertEqual(self.arquivo.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
