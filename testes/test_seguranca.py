"""Testes das regras de segurança novas (versão 2.0).

Rode todos os testes com:  python3 -m unittest discover testes
"""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import gi  # noqa: E402

gi.require_version("GLib", "2.0")
from estudos.interface import paginas  # noqa: E402
from estudos.nucleo import caminhos, regras, tempo  # noqa: E402
from estudos.nucleo.regras import ListaDeSites  # noqa: E402

PADRAO = (RAIZ / "recursos" / "sites_padrao.txt").read_text(encoding="utf-8")


class TestIAeLogin(unittest.TestCase):
    def setUp(self):
        self.lista = ListaDeSites.de_texto(PADRAO)

    def test_lista_padrao_sem_erros(self):
        self.assertEqual(self.lista.erros, [])

    def test_ias_liberadas(self):
        for url in ["https://chatgpt.com/", "https://chatgpt.com/c/abc",
                    "https://auth.openai.com/log-in", "https://cdn.oaistatic.com/x.js",
                    "https://files.oaiusercontent.com/f", "https://gemini.google.com/app",
                    "https://claude.ai/new", "https://www.perplexity.ai/",
                    "https://copilot.microsoft.com/", "https://copilot.com/pt-br/"]:
            self.assertTrue(self.lista.permite(url), url)

    def test_paginas_de_login_liberadas(self):
        for url in ["https://accounts.google.com/v3/signin", "https://login.live.com/",
                    "https://login.microsoftonline.com/common/oauth2"]:
            self.assertTrue(self.lista.permite(url), url)

    def test_resto_do_google_e_microsoft_bloqueado(self):
        for url in ["https://www.google.com/search?q=jogos", "https://google.com/",
                    "https://mail.google.com/", "https://www.youtube.com/",
                    "https://www.bing.com/", "https://www.microsoft.com/",
                    "https://outlook.live.com/", "https://sora.chatgpt.com.golpe.net/"]:
            self.assertFalse(self.lista.permite(url), url)


class TestHttps(unittest.TestCase):
    def setUp(self):
        self.lista = ListaDeSites.de_texto(PADRAO)

    def test_http_nao_abre_como_pagina(self):
        self.assertFalse(self.lista.permite("http://pt.wikipedia.org/wiki/A"))

    def test_http_vira_https(self):
        self.assertEqual(self.lista.https_disponivel("http://pt.wikipedia.org/wiki/A"),
                         "https://pt.wikipedia.org/wiki/A")
        self.assertIsNone(self.lista.https_disponivel("http://instagram.com/"))

    def test_atalhos_http_sao_convertidos(self):
        lista = ListaDeSites.de_texto("[X]\nSite | http://exemplo.com/\n")
        self.assertEqual(lista.categorias[0].atalhos[0].url, "https://exemplo.com/")

    def test_esquemas_perigosos_nao_abrem_como_pagina(self):
        for url in ["data:text/html,<h1>oi</h1>", "javascript:alert(1)", "file:///etc/passwd",
                    "blob:https://chatgpt.com/123", "view-source:https://chatgpt.com/",
                    "ftp://wikipedia.org/"]:
            self.assertFalse(self.lista.permite(url), url)

    def test_verificacao_cloudflare_so_embutida(self):
        url = "https://challenges.cloudflare.com/cdn-cgi/challenge-platform/x"
        self.assertTrue(self.lista.permite_embutido(url))
        self.assertFalse(self.lista.permite(url))


class TestArquivos(unittest.TestCase):
    def test_recurso_seguro_bloqueia_fuga_da_pasta(self):
        self.assertIsNotNone(caminhos.recurso_seguro("paginas/mosaico.css"))
        for truque in ["../estudos/__init__.py", "../../../../etc/passwd",
                       "/etc/passwd", "paginas/../../LEIA-ME.md", "paginas"]:
            self.assertIsNone(caminhos.recurso_seguro(truque), truque)

    def test_lista_antiga_nao_editada_e_atualizada(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "sites.txt"
            antigo = subprocess.run(["git", "-C", str(RAIZ), "show", "v1.0:sites_padrao.txt"],
                                    capture_output=True, check=True).stdout
            self.assertIn(hashlib.sha256(antigo).hexdigest(), regras.PADROES_ANTIGOS)
            arquivo.write_bytes(antigo)
            with mock.patch.object(caminhos, "ARQUIVO_SITES", arquivo), \
                    mock.patch.object(caminhos, "MODO_PROTEGIDO", False):
                lista = ListaDeSites.carregar()
            self.assertTrue(lista.permite("https://chatgpt.com/"))
            self.assertEqual(arquivo.with_suffix(".txt.anterior").read_bytes(), antigo)

    def test_lista_editada_pelo_responsavel_nao_e_tocada(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "sites.txt"
            arquivo.write_text("[Minha]\nSó isso | https://exemplo.com/\n", encoding="utf-8")
            with mock.patch.object(caminhos, "ARQUIVO_SITES", arquivo), \
                    mock.patch.object(caminhos, "MODO_PROTEGIDO", False):
                lista = ListaDeSites.carregar()
            self.assertFalse(lista.permite("https://chatgpt.com/"))
            self.assertFalse(arquivo.with_suffix(".txt.anterior").exists())


class TestTempoEPaginas(unittest.TestCase):
    def test_dias_seguidos(self):
        import datetime
        with tempfile.TemporaryDirectory() as pasta, \
                mock.patch.object(caminhos, "PASTA_TEMPO", Path(pasta)):
            hoje = datetime.date.today()
            for atras, segundos in [(1, 900), (2, 1200), (3, 60), (4, 5000)]:
                dia = hoje - datetime.timedelta(days=atras)
                (Path(pasta) / f"{dia.isoformat()}.json").write_text(json.dumps({"x": segundos}))
            contador = tempo.ContadorDeTempo()
            self.assertEqual(contador.dias_seguidos(), 2)   # o dia 3 quebrou a sequência
            contador.somar("x", 700)
            self.assertEqual(contador.dias_seguidos(), 3)   # hoje passou de 10 min

    def test_nomes_sao_escapados_no_html(self):
        lista = ListaDeSites.de_texto('[<b>X</b>]\n<script>alert(1)</script> | https://exemplo.com/\n')
        contador = mock.Mock(total=lambda: 0, ranking=lambda agrupar=None: [], dias_seguidos=lambda: 0)
        html = paginas.pagina_inicial(lista, contador, {"meta_minutos": 60})
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)
        bloqueio = paginas.pagina_bloqueada('https://"><script>x</script>.com/')
        self.assertNotIn("<script>x", bloqueio)

    def test_tela_de_bloqueio_nao_mostra_o_site_de_fachada(self):
        html = paginas.pagina_bloqueada("https://instagram.com\\@pt.wikipedia.org/", "invalido")
        self.assertIn("inválido ou está disfarçado", html)
        self.assertNotIn(">pt.wikipedia.org<", html)
        html = paginas.pagina_bloqueada("https://www.instagram.com/x")
        self.assertIn(">www.instagram.com<", html)


if __name__ == "__main__":
    unittest.main()
