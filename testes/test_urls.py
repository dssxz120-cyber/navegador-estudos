"""Testes do leitor rígido de endereços (estudos/nucleo/urls.py).

Regra de ouro: quando o endereço é ambíguo, o leitor devolve None e o
navegador bloqueia. Ele nunca pode "achar" um site diferente do WebKit.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from estudos.nucleo.regras import ListaDeSites  # noqa: E402
from estudos.nucleo.urls import analisar  # noqa: E402

LISTA = ListaDeSites.de_texto("[X]\nWiki | https://pt.wikipedia.org/\n+ wikipedia.org\n")


class TestAnalisar(unittest.TestCase):
    def test_enderecos_comuns(self):
        e = analisar("https://pt.wikipedia.org/wiki/Brasil?x=1#topo")
        self.assertEqual((e.esquema, e.host, e.porta, e.resto),
                         ("https", "pt.wikipedia.org", None, "/wiki/Brasil?x=1#topo"))
        self.assertEqual(analisar("HTTPS://PT.Wikipedia.ORG:8443/").host, "pt.wikipedia.org")
        self.assertEqual(analisar("https://pt.wikipedia.org:8443/").porta, 8443)
        self.assertEqual(analisar("https://pt.wikipedia.org./").host, "pt.wikipedia.org")
        self.assertEqual(analisar("  https://pt.wikipedia.org/\n").host, "pt.wikipedia.org")

    def test_barra_invertida_e_ambigua(self):
        for url in ["https://instagram.com\\@pt.wikipedia.org/",
                    "https://instagram.com\\.wikipedia.org/",
                    "https:\\\\instagram.com/", "https://pt.wikipedia.org\\x"]:
            self.assertIsNone(analisar(url), url)
            self.assertFalse(LISTA.permite(url), url)

    def test_usuario_e_senha_sao_recusados(self):
        for url in ["https://wikipedia.org@instagram.com/", "https://x@pt.wikipedia.org/",
                    "https://wikipedia.org:x@instagram.com/"]:
            self.assertIsNone(analisar(url), url)

    def test_nomes_de_site_estranhos_sao_recusados(self):
        for url in ["https://pt%2ewikipedia.org/", "https://evil.com%2f.wikipedia.org/",
                    "https://wikipedіa.org/", "https://ｗｉｋｉｐｅｄｉａ.org/",
                    "https://instagram.com。wikipedia.org/", "https://[::1]/",
                    "https://pt..wikipedia.org/", "https://.wikipedia.org/",
                    "https://pt.wikipedia.org:99999/", "https://pt.wikipedia.org:/",
                    "https:/pt.wikipedia.org/", "https:pt.wikipedia.org", "https:///pt.wikipedia.org/",
                    "https://pt.wikipedia .org/", "https://", "", None, 42]:
            self.assertIsNone(analisar(url), repr(url))

    def test_esquemas_sem_site(self):
        self.assertEqual(analisar("estudos://inicio").esquema, "estudos")
        self.assertEqual(analisar("about:blank").esquema, "about")
        self.assertEqual(analisar("JavaScript:alert(1)").esquema, "javascript")


class TestConsistenciaComFiltro(unittest.TestCase):
    def test_parecidos_e_subdominios(self):
        permitidos = ["https://pt.wikipedia.org/", "https://en.m.wikipedia.org/wiki/A",
                      "https://wikipedia.org/"]
        bloqueados = ["https://wikipedia.org.golpe.com/", "https://falsawikipedia.org/",
                      "https://wikipedia.org-golpe.com/", "https://wikipedia.orgx/",
                      "https://golpe.com/pt.wikipedia.org/", "https://golpe.com/?pt.wikipedia.org",
                      "https://golpe.com/#.wikipedia.org"]
        for url in permitidos:
            self.assertTrue(LISTA.permite(url), url)
        for url in bloqueados:
            self.assertFalse(LISTA.permite(url), url)

    def test_https_disponivel_preserva_caminho_e_porta(self):
        self.assertEqual(LISTA.https_disponivel("HTTP://pt.wikipedia.org:8080/wiki/A?b=1"),
                         "https://pt.wikipedia.org:8080/wiki/A?b=1")
        self.assertIsNone(LISTA.https_disponivel("http://instagram.com/"))


if __name__ == "__main__":
    unittest.main()
