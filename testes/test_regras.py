"""Testes do filtro de sites. Rode com:  python3 -m unittest discover testes"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gi  # noqa: E402

gi.require_version("GLib", "2.0")
from estudos.nucleo.regras import ListaDeSites  # noqa: E402

PADRAO = (Path(__file__).resolve().parent.parent / "recursos" / "sites_padrao.txt").read_text(encoding="utf-8")


class TestFiltro(unittest.TestCase):
    def setUp(self):
        self.lista = ListaDeSites.de_texto(PADRAO)

    def test_lista_padrao_sem_erros(self):
        self.assertEqual(self.lista.erros, [])
        self.assertEqual(len(self.lista.categorias), 5)

    def test_sites_de_estudo_liberados(self):
        for url in ["https://pt.wikipedia.org/wiki/Brasil",
                    "https://en.wikipedia.org/wiki/Physics",
                    "https://upload.wikimedia.org/x.png",
                    "https://www.khanacademy.org/math",
                    "https://developer.mozilla.org/pt-BR/docs/Web",
                    "https://scholar.google.com.br/scholar?q=fotossintese",
                    "https://stackoverflow.com/questions/1"]:
            self.assertTrue(self.lista.permite(url), url)

    def test_redes_sociais_e_outros_bloqueados(self):
        for url in ["https://www.instagram.com/", "https://www.facebook.com/",
                    "https://www.tiktok.com/", "https://x.com/", "https://www.youtube.com/",
                    "https://www.google.com/search?q=jogos", "https://web.whatsapp.com/",
                    "https://www.uol.com.br/",          # Michaelis/Brasil Escola não liberam o UOL todo
                    "https://wikipedia.org.golpe.com/", "https://falsawikipedia.org/",
                    "file:///etc/passwd", "ftp://wikipedia.org/"]:
            self.assertFalse(self.lista.permite(url), url)

    def test_videos_embutidos(self):
        self.assertTrue(self.lista.permite_embutido("https://www.youtube-nocookie.com/embed/abc"))
        self.assertTrue(self.lista.permite_embutido("https://www.youtube.com/embed/abc"))
        self.assertFalse(self.lista.permite_embutido("https://www.youtube.com/watch?v=abc"))
        self.assertFalse(self.lista.permite_embutido("https://www.google.com/search?q=x"))
        # Embutido NÃO vale como página principal.
        self.assertFalse(self.lista.permite("https://www.youtube.com/embed/abc"))

    def test_nome_do_site(self):
        self.assertEqual(self.lista.nome_do_site("https://pt.wikipedia.org/wiki/A"), "Wikipédia")
        self.assertEqual(self.lista.nome_do_site("https://en.wikipedia.org/wiki/A"), "Wikipédia")
        self.assertEqual(self.lista.nome_do_site("https://www.khanacademy.org/"), "Khan Academy")
        self.assertIsNone(self.lista.nome_do_site("https://www.instagram.com/"))

    def test_linhas_invalidas_viram_erro(self):
        lista = ListaDeSites.de_texto("[X]\nisso não é válido\n+ semponto\n"
                                      "[Y]Nome | https://exemplo.com/\n")
        self.assertEqual(len(lista.erros), 3)


if __name__ == "__main__":
    unittest.main()
