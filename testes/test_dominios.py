"""Testes da validação de domínios da lista (sufixos públicos, curingas...)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from estudos.nucleo import dominios  # noqa: E402
from estudos.nucleo.regras import ListaDeSites  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent


class TestValidacao(unittest.TestCase):
    def test_dominios_normais_sao_aceitos(self):
        for dominio in ["wikipedia.org", "pt.wikipedia.org", "khanacademy.org", "chatgpt.com",
                        "scholar.google.com.br", "michaelis.uol.com.br", "youtube.com",
                        "gemini.google.com", "xn--caf-dma.com", "permitido.localhost"]:
            self.assertIsNone(dominios.validar(dominio), dominio)

    def test_sufixos_publicos_sao_recusados(self):
        for dominio in ["com", "com.br", "co.uk", "gov.br", "edu.br", "github.io",
                        "blogspot.com", "br"]:
            self.assertIsNotNone(dominios.validar(dominio), dominio)

    def test_formatos_invalidos(self):
        for dominio in ["*.com", "*.wikipedia.org", "wiki*.org", "", "exemplo..com",
                        "-exemplo.com", "exemplo-.com", 'exemplo.com"><script>',
                        "exemplo .com", "café.com", "1.2.3.4", "a" * 64 + ".com"]:
            self.assertIsNotNone(dominios.validar(dominio), dominio)

    def test_lista_oficial_do_ubuntu_esta_sendo_usada(self):
        if not dominios.ARQUIVO_SUFIXOS.exists():
            self.skipTest("pacote publicsuffix não instalado")
        normais, curingas, excecoes = dominios._regras_de_sufixo()
        self.assertGreater(len(normais), 5000)
        # Regra com curinga (*.ck) e exceção (!www.ck) da lista oficial:
        self.assertTrue(dominios.eh_sufixo_publico("qualquer.ck"))
        self.assertFalse(dominios.eh_sufixo_publico("www.ck"))


class TestListaDeSites(unittest.TestCase):
    def test_cadastros_perigosos_viram_erro(self):
        for linha in ["+ com.br", "+ .com.br", "+ co.uk", "+ *.com", "+ github.io",
                      "- com", "Site | https://com.br/", "Site | https://exemplo.com\"><script>"]:
            lista = ListaDeSites.de_texto(linha)
            self.assertEqual(len(lista.erros), 1, linha)
            self.assertEqual(lista.dominios, set(), linha)

    def test_exclusao_de_subdominio(self):
        lista = ListaDeSites.de_texto("+ chatgpt.com\n- sora.chatgpt.com\n")
        self.assertTrue(lista.permite("https://chatgpt.com/"))
        self.assertFalse(lista.permite("https://sora.chatgpt.com/explore"))
        self.assertFalse(lista.permite_embutido("https://sora.chatgpt.com/"))
        self.assertEqual(lista.classificar("https://sora.chatgpt.com/"), "excluido")

    def test_sora_pode_ser_reautorizado_pelo_responsavel(self):
        padrao = (RAIZ / "recursos" / "sites_padrao.txt").read_text()
        self.assertFalse(ListaDeSites.de_texto(padrao).permite("https://sora.chatgpt.com/"))
        sem_a_linha = padrao.replace("- sora.chatgpt.com\n", "")
        self.assertNotEqual(sem_a_linha, padrao)
        lista = ListaDeSites.de_texto(sem_a_linha)
        self.assertTrue(lista.permite("https://sora.chatgpt.com/explore"))
        self.assertTrue(lista.permite("https://chatgpt.com/"))

    def test_lista_padrao_e_valida_e_exclui_secoes_sociais(self):
        lista = ListaDeSites.de_texto((RAIZ / "recursos" / "sites_padrao.txt").read_text())
        self.assertEqual(lista.erros, [])
        self.assertFalse(lista.permite("https://community.openai.com/"))
        self.assertEqual(lista.classificar("https://sora.chatgpt.com/explore"), "excluido")
        self.assertFalse(lista.permite_embutido("https://sora.chatgpt.com/"))
        self.assertFalse(lista.permite("https://chat.stackoverflow.com/rooms/1"))
        self.assertTrue(lista.permite("https://stackoverflow.com/questions/1"))
        self.assertTrue(lista.permite("https://chatgpt.com/"))

    def test_login_nao_conta_como_estudo(self):
        lista = ListaDeSites.de_texto((RAIZ / "recursos" / "sites_padrao.txt").read_text())
        for url in ["https://accounts.google.com/signin", "https://auth.openai.com/log-in",
                    "https://login.live.com/"]:
            self.assertEqual(lista.classificar(url), "login", url)
            self.assertTrue(lista.permite(url), url)
            self.assertIsNone(lista.nome_do_site(url), url)


if __name__ == "__main__":
    unittest.main()
