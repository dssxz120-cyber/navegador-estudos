"""Testes do MODO PROTEGIDO (configuração do administrador em /etc).

Nada aqui usa root nem pkexec de verdade: a pasta "do sistema" é temporária
e o pkexec é simulado. O programa auxiliar roda como usuário comum com a
opção de teste --pasta.
"""

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apoio_webkit import tela_disponivel  # noqa: E402

from estudos.nucleo import caminhos, preferencias, protegido  # noqa: E402
from estudos.nucleo.arquivos import listar_copias  # noqa: E402
from estudos.nucleo.regras import ListaDeSites  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
AJUDANTE = RAIZ / "scripts" / "salvar-configuracao"
LISTA_BOA = "[Estudo]\nWiki | https://pt.wikipedia.org/\n+ youtube.com\n~ spotify.com\n"


def modo(caminho):
    return caminho.stat().st_mode & 0o777


class _Pasta(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self._tmp.name) / "etc-navegador"

    def tearDown(self):
        for raiz, pastas, _ in os.walk(self._tmp.name):
            for nome in pastas:
                os.chmod(os.path.join(raiz, nome), 0o700)
        self._tmp.cleanup()


class TestAplicarConfiguracao(_Pasta):
    def test_grava_legivel_para_todos_e_com_copias(self):
        lista, prefs = protegido.aplicar_configuracao(
            {"sites": LISTA_BOA, "preferencias": {"meta_minutos": 90}}, self.pasta)
        self.assertIn("youtube.com", lista.dominios)
        self.assertEqual((self.pasta / "sites.txt").read_text(), LISTA_BOA)
        self.assertEqual(json.loads((self.pasta / "preferencias.json").read_text()),
                         {"meta_minutos": 90, "inatividade_minutos": 5})
        self.assertEqual(modo(self.pasta / "sites.txt"), 0o644)      # o aluno precisa ler
        self.assertEqual(modo(self.pasta / "preferencias.json"), 0o644)
        self.assertTrue(listar_copias(self.pasta / "sites.txt"))
        self.assertEqual(modo(self.pasta / "copias"), 0o700)          # cópias só do admin

    def test_recusa_sem_gravar_nada(self):
        invalidos = [
            "não é um dicionário",
            {"sites": 123},
            {"sites": "+ com.br\n"},                                   # sufixo público
            {"sites": "linha sem sentido\n"},
            {"sites": "# só comentário\n"},                            # nenhum site
            {"sites": "+ a.com\n" + "#" * (protegido.TAMANHO_MAXIMO + 1)},
            {"sites": LISTA_BOA, "preferencias": ["não", "é", "dict"]},
        ]
        for dados in invalidos:
            with self.subTest(dados=str(dados)[:40]):
                with self.assertRaises(protegido.ConfiguracaoInvalida):
                    protegido.aplicar_configuracao(dados, self.pasta)
                self.assertFalse(self.pasta.exists())

    def test_preferencias_absurdas_sao_limitadas(self):
        _, prefs = protegido.aplicar_configuracao(
            {"sites": LISTA_BOA, "preferencias": {"meta_minutos": 10**9, "inatividade_minutos": -5,
                                                  "chave_estranha": "x"}}, self.pasta)
        self.assertEqual(prefs, {"meta_minutos": 600, "inatividade_minutos": 1})


class TestProgramaAuxiliar(_Pasta):
    def rodar(self, entrada, *args, ambiente=None):
        return subprocess.run([str(AJUDANTE), *args], input=entrada, text=True,
                              capture_output=True, timeout=30, env=ambiente)

    def test_grava_quando_valido(self):
        r = self.rodar(json.dumps({"sites": LISTA_BOA}), "--pasta", str(self.pasta))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.pasta / "sites.txt").read_text(), LISTA_BOA)

    def test_recusa_invalido(self):
        for entrada in ["{lixo", json.dumps({"sites": "+ com.br"})]:
            r = self.rodar(entrada, "--pasta", str(self.pasta))
            self.assertEqual(r.returncode, 4)
            self.assertIn("recusada", r.stderr)
        self.assertFalse(self.pasta.exists())

    def test_sem_root_exige_pasta_de_teste(self):
        self.assertEqual(self.rodar(json.dumps({"sites": LISTA_BOA})).returncode, 2)

    def test_pedido_grande_demais(self):
        r = self.rodar("x" * (protegido.TAMANHO_MAXIMO * 2 + 10), "--pasta", str(self.pasta))
        self.assertEqual(r.returncode, 3)

    def test_ignora_modulos_injetados_pelo_ambiente(self):
        """Modo isolado (-I): um "json.py" falso no PYTHONPATH não é carregado.

        O auxiliar importa json antes de tudo; sem -I, o Python pegaria o
        json.py falso (o PYTHONPATH vem antes da biblioteca padrão) e o código
        do invasor rodaria como root.
        """
        falso = Path(self._tmp.name) / "falso"
        falso.mkdir()
        (falso / "json.py").write_text("print('CODIGO_INJETADO'); raise SystemExit(99)\n")
        ambiente = dict(os.environ, PYTHONPATH=str(falso))
        r = self.rodar(json.dumps({"sites": LISTA_BOA}), "--pasta", str(self.pasta),
                       ambiente=ambiente)
        self.assertNotIn("CODIGO_INJETADO", r.stderr + r.stdout)
        self.assertEqual(r.returncode, 0)

    def test_arquivo_comeca_em_modo_isolado(self):
        self.assertEqual(AJUDANTE.read_text().splitlines()[0], "#!/usr/bin/python3 -I")
        self.assertTrue(os.access(AJUDANTE, os.X_OK))


class TestSalvarViaPkexec(unittest.TestCase):
    def falso(self, codigo, stderr=""):
        chamadas = []

        def executar(comando, **opcoes):
            chamadas.append((comando, opcoes))
            return subprocess.CompletedProcess(comando, codigo, "", stderr)
        return executar, chamadas

    def test_sucesso_e_comando_correto(self):
        executar, chamadas = self.falso(0)
        self.assertIsNone(protegido.salvar_via_pkexec(LISTA_BOA, {"meta_minutos": 60}, executar))
        comando, opcoes = chamadas[0]
        self.assertEqual(comando, ["pkexec", str(protegido.AJUDANTE)])
        self.assertEqual(json.loads(opcoes["input"])["sites"], LISTA_BOA)

    def test_senha_nao_confirmada(self):
        for codigo in (126, 127):
            executar, _ = self.falso(codigo)
            self.assertIn("não foi confirmada", protegido.salvar_via_pkexec(LISTA_BOA, {}, executar))

    def test_erro_do_auxiliar_aparece(self):
        executar, _ = self.falso(4, "configuração recusada: a lista tem erros\n")
        self.assertIn("a lista tem erros", protegido.salvar_via_pkexec(LISTA_BOA, {}, executar))

    def test_sem_pkexec(self):
        def executar(*_a, **_k):
            raise FileNotFoundError
        self.assertIn("pkexec", protegido.salvar_via_pkexec(LISTA_BOA, {}, executar))


class TestLeituraSomenteNoModoProtegido(_Pasta):
    def setUp(self):
        super().setUp()
        self.pasta.mkdir()
        self.remendos = [mock.patch.object(caminhos, "MODO_PROTEGIDO", True),
                         mock.patch.object(caminhos, "ARQUIVO_SITES", self.pasta / "sites.txt"),
                         mock.patch.object(caminhos, "ARQUIVO_PREFERENCIAS",
                                           self.pasta / "preferencias.json"),
                         mock.patch("sys.stderr")]
        for r in self.remendos:
            r.start()

    def tearDown(self):
        for r in self.remendos:
            r.stop()
        super().tearDown()

    def conteudo_da_pasta(self):
        return sorted((p.name, p.read_bytes()) for p in self.pasta.iterdir())

    def test_le_a_lista_do_administrador_sem_gravar(self):
        (self.pasta / "sites.txt").write_text(LISTA_BOA)
        os.chmod(self.pasta, 0o555)                       # como /etc para o aluno
        antes = self.conteudo_da_pasta()
        lista = ListaDeSites.carregar()
        self.assertIn("pt.wikipedia.org", lista.dominios)
        self.assertEqual(self.conteudo_da_pasta(), antes)

    def test_lista_estragada_usa_a_padrao_sem_tocar_no_arquivo(self):
        (self.pasta / "sites.txt").write_bytes(b"\xff\xfe lixo")
        os.chmod(self.pasta, 0o555)
        antes = self.conteudo_da_pasta()
        lista = ListaDeSites.carregar()
        self.assertIn("wikipedia.org", lista.dominios)
        self.assertEqual(self.conteudo_da_pasta(), antes)

    def test_preferencias_do_administrador(self):
        (self.pasta / "preferencias.json").write_text('{"meta_minutos": 45, "x": 1}')
        self.assertEqual(preferencias.carregar(), {"meta_minutos": 45, "inatividade_minutos": 5})
        (self.pasta / "preferencias.json").write_text("{lixo")
        self.assertEqual(preferencias.carregar(), preferencias.PADRAO)


class TestNavegadorAbreEmModoProtegido(unittest.TestCase):
    """Abre o navegador DE VERDADE em modo protegido: sem pedir senha do
    navegador, usando a lista do "sistema" (uma pasta temporária)."""

    SCRIPT = textwrap.dedent("""
        import sys
        sys.path.insert(0, {raiz!r})
        from pathlib import Path
        import gi
        gi.require_version("Gtk", "3.0"); gi.require_version("Gdk", "3.0"); gi.require_version("WebKit2", "4.1")
        from gi.repository import GLib
        from estudos.nucleo import caminhos
        sistema = Path({sistema!r})
        caminhos.MODO_PROTEGIDO = True
        caminhos.ARQUIVO_SITES = sistema / "sites.txt"
        caminhos.ARQUIVO_PREFERENCIAS = sistema / "preferencias.json"
        from estudos.nucleo import senha
        from estudos.nucleo.regras import ListaDeSites
        from estudos.nucleo.tempo import ContadorDeTempo
        from estudos.interface.aplicativo import Aplicativo
        caminhos.criar_pastas()
        app = Aplicativo(ListaDeSites.carregar(), ContadorDeTempo(), unico=False)

        def verificar():
            print("JANELA_ABERTA", app.janela is not None, flush=True)
            print("SENHA_DO_NAVEGADOR_EXISTE", senha.existe(), flush=True)
            print("DOMINIOS", sorted(app.lista.dominios), flush=True)
            print("META", app.preferencias["meta_minutos"], flush=True)
            app.janela.close()
            return False

        app.connect("activate", lambda *_: GLib.timeout_add(1500, verificar))
        GLib.timeout_add_seconds(20, lambda: (print("TEMPO_ESGOTADO", flush=True), app.quit()))
        app.run([])
    """)

    def test_abre_sem_senha_do_navegador(self):
        if not tela_disponivel():
            self.skipTest("sem tela disponível")
        with tempfile.TemporaryDirectory() as pasta:
            sistema = Path(pasta, "etc")
            protegido.aplicar_configuracao({"sites": LISTA_BOA, "preferencias": {"meta_minutos": 77}},
                                           sistema)
            os.chmod(sistema, 0o555)
            ambiente = dict(os.environ, XDG_CONFIG_HOME=f"{pasta}/c", XDG_DATA_HOME=f"{pasta}/d",
                            XDG_CACHE_HOME=f"{pasta}/k", PYTHONDONTWRITEBYTECODE="1")
            saida = subprocess.run(
                [sys.executable, "-c", self.SCRIPT.format(raiz=str(RAIZ), sistema=str(sistema))],
                env=ambiente, capture_output=True, text=True, timeout=60).stdout
            os.chmod(sistema, 0o755)
            self.assertIn("JANELA_ABERTA True", saida)          # não ficou preso pedindo senha
            self.assertIn("SENHA_DO_NAVEGADOR_EXISTE False", saida)
            self.assertIn("'pt.wikipedia.org'", saida)
            self.assertIn("META 77", saida)
            self.assertNotIn("TEMPO_ESGOTADO", saida)


if __name__ == "__main__":
    unittest.main()
