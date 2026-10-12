"""Testes da contagem de estudo: inatividade e estatísticas agrupadas."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from estudos.nucleo.regras import ListaDeSites  # noqa: E402
import datetime  # noqa: E402

from estudos.nucleo.tempo import ContadorDeTempo, deve_contar, texto_do_relogio  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent


class TestInatividade(unittest.TestCase):
    def test_regras(self):
        limite = 300
        self.assertTrue(deve_contar(True, 10, False, limite))
        self.assertFalse(deve_contar(True, 301, False, limite))          # saiu do computador
        self.assertTrue(deve_contar(True, 3600, True, limite))           # vídeo-aula tocando
        self.assertFalse(deve_contar(False, 0, True, limite))            # janela em segundo plano
        self.assertTrue(deve_contar(True, None, False, limite))          # sem como saber: conta


class TestRelogio(unittest.TestCase):
    def test_formato(self):
        self.assertEqual(texto_do_relogio(datetime.datetime(2026, 10, 12, 9, 5)),
                         ("09:05", "Segunda-feira, 12 de outubro de 2026"))
        self.assertEqual(texto_do_relogio(datetime.datetime(2026, 3, 1, 23, 59))[0], "23:59")
        self.assertEqual(texto_do_relogio(datetime.datetime(2026, 3, 1, 0, 0)),
                         ("00:00", "Domingo, 1 de março de 2026"))


class TestApelidos(unittest.TestCase):
    def test_sintaxe(self):
        lista = ListaDeSites.de_texto("[X]\nSciELO | https://www.scielo.br/\n+ scielo.org = SciELO\n")
        self.assertEqual(lista.erros, [])
        self.assertIn("scielo.org", lista.dominios)
        self.assertEqual(lista.nome_do_site("https://www.scielo.org/x"), "SciELO")
        self.assertEqual(lista.nome_do_site("https://www.scielo.br/x"), "SciELO")

    def test_apelido_em_exclusao_e_erro(self):
        self.assertEqual(len(ListaDeSites.de_texto("+ a.com\n- b.a.com = Nome\n").erros), 1)

    def test_dominio_mais_especifico_vence(self):
        lista = ListaDeSites.de_texto("[X]\nGemini | https://gemini.google.com/\n"
                                      "+ scholar.google.com = Google Acadêmico\n")
        self.assertEqual(lista.nome_do_site("https://scholar.google.com/"), "Google Acadêmico")
        self.assertEqual(lista.nome_do_site("https://gemini.google.com/app"), "Gemini")

    def test_lista_padrao(self):
        lista = ListaDeSites.de_texto((RAIZ / "recursos" / "sites_padrao.txt").read_text())
        self.assertEqual(lista.erros, [])
        casos = {"https://www.scielo.org/": "SciELO", "https://scholar.google.com/": "Google Acadêmico",
                 "https://help.openai.com/": "ChatGPT", "https://copilot.microsoft.com/": "Copilot",
                 "https://commons.wikimedia.org/": "Wikipédia", "https://auth.openai.com/": None}
        for url, nome in casos.items():
            self.assertEqual(lista.nome_do_site(url), nome, url)


class TestMusicaNaoContaComoEstudo(unittest.TestCase):
    def setUp(self):
        self.lista = ListaDeSites.de_texto(
            "[Vídeos e música]\nYouTube | https://www.youtube.com/\n"
            "YouTube Music | https://music.youtube.com/\nSpotify | https://open.spotify.com/\n"
            "+ spotify.com\n~ music.youtube.com\n~ spotify.com\n")

    def test_musica_liberada_mas_nao_conta(self):
        self.assertEqual(self.lista.erros, [])
        for url in ["https://music.youtube.com/watch?v=x", "https://open.spotify.com/album/1"]:
            self.assertTrue(self.lista.permite(url), url)           # continua liberado
            self.assertIsNone(self.lista.nome_do_site(url), url)    # mas não conta

    def test_youtube_normal_continua_contando(self):
        self.assertEqual(self.lista.nome_do_site("https://www.youtube.com/watch?v=x"), "YouTube")

    def test_til_sozinho_nao_libera_nada(self):
        lista = ListaDeSites.de_texto("+ exemplo.com\n~ spotify.com\n")
        self.assertFalse(lista.permite("https://open.spotify.com/"))

    def test_til_invalido_e_erro(self):
        self.assertEqual(len(ListaDeSites.de_texto("~ com.br\n").erros), 1)


class TestEstatisticasAgrupadas(unittest.TestCase):
    def setUp(self):
        self.lista = ListaDeSites.de_texto(
            "[X]\nSciELO | https://www.scielo.br/\nYouTube | https://www.youtube.com/\n"
            "+ scielo.org = SciELO\n+ khanacademy.org\n")
        self.contador = ContadorDeTempo.__new__(ContadorDeTempo)   # sem tocar em arquivos
        self.contador.por_site = {"SciELO": 22, "scielo.org": 13, "youtube.com": 35,
                                  "khanacademy.org": 7, "Wikipédia": 74, "site.removido.com": 5}

    def test_juntam_na_exibicao(self):
        ranking = dict(self.contador.ranking(self.lista.nome_para_estatistica))
        self.assertEqual(ranking["SciELO"], 35)
        self.assertEqual(ranking["YouTube"], 35)
        self.assertEqual(ranking["Wikipédia"], 74)
        self.assertEqual(ranking["khanacademy.org"], 7)          # domínio sem atalho: fica igual
        self.assertEqual(ranking["site.removido.com"], 5)        # fora da lista: fica igual
        self.assertNotIn("scielo.org", ranking)

    def test_dados_e_total_nao_mudam(self):
        antes = dict(self.contador.por_site)
        self.contador.ranking(self.lista.nome_para_estatistica)
        self.assertEqual(self.contador.por_site, antes)
        self.assertEqual(sum(s for _, s in self.contador.ranking(self.lista.nome_para_estatistica)),
                         sum(antes.values()))

    def test_sem_agrupar_continua_como_antes(self):
        self.assertEqual(dict(self.contador.ranking()), self.contador.por_site)


if __name__ == "__main__":
    unittest.main()
