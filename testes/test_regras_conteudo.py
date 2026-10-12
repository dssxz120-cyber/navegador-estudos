"""Testes das regras de bloqueio de conteúdo geradas para o WebKit."""

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from estudos.nucleo.regras import ListaDeSites  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent


def _como_python(filtro):
    """O formato do WebKit é um subconjunto de regex que o Python entende."""
    return re.compile(filtro, re.IGNORECASE)


def decidir(regras, url, tipo="document", contexto="top-frame"):
    """Simula a ordem de aplicação do WebKit: devolve True se bloqueia."""
    bloqueia = False
    for regra in regras:
        gatilho = regra["trigger"]
        if tipo not in gatilho["resource-type"]:
            continue
        if "load-context" in gatilho and contexto not in gatilho["load-context"]:
            continue
        if not _como_python(gatilho["url-filter"]).search(url):
            continue
        bloqueia = regra["action"]["type"] == "block"
    return bloqueia


class TestRegras(unittest.TestCase):
    def setUp(self):
        texto = (RAIZ / "recursos" / "sites_padrao.txt").read_text()
        self.lista = ListaDeSites.de_texto(texto + "\n+ youtube.com\n")
        self.regras = self.lista.regras_de_conteudo()

    def test_ordem_bloqueia_primeiro_e_reforca_no_fim(self):
        self.assertEqual(self.regras[0]["action"]["type"], "block")
        self.assertEqual(self.regras[0]["trigger"]["url-filter"], ".*")
        self.assertEqual(self.regras[-1]["action"]["type"], "block")
        self.assertIn("@", self.regras[-1]["trigger"]["url-filter"])

    def test_regras_e_lista_concordam(self):
        casos = ["https://chatgpt.com/", "https://auth.openai.com/log-in", "https://gemini.google.com/app",
                 "https://claude.ai/new", "https://www.perplexity.ai/", "https://copilot.com/",
                 "https://www.youtube.com/watch?v=x", "https://m.youtube.com/", "https://accounts.google.com/x",
                 "https://login.microsoftonline.com/common", "https://pt.wikipedia.org/wiki/A",
                 "https://www.instagram.com/", "https://www.google.com/search?q=x", "https://www.tiktok.com/",
                 "https://community.openai.com/", "https://sora.chatgpt.com/explore", "https://chat.stackoverflow.com/", "https://stackoverflow.com/q/1",
                 "https://wikipedia.org.golpe.com/", "https://golpe.com/wikipedia.org/",
                 "https://wikipedia.org:x@golpe.com/", "https://u@pt.wikipedia.org/",
                 "http://pt.wikipedia.org/", "estudos://inicio", "about:blank"]
        for url in casos:
            self.assertEqual(decidir(self.regras, url), not self.lista.permite(url), url)

    def test_embutidos_so_em_iframe(self):
        video = "https://www.youtube-nocookie.com/embed/abc"
        self.assertTrue(decidir(self.regras, video, contexto="top-frame"))
        self.assertFalse(decidir(self.regras, video, contexto="child-frame"))
        self.assertFalse(decidir(self.regras, "data:text/html,x", contexto="child-frame"))
        self.assertTrue(decidir(self.regras, "data:text/html,x", contexto="top-frame"))

    def test_webkit_aceita_as_regras(self):
        try:
            import gi
            gi.require_version("WebKit2", "4.1")
            from gi.repository import GLib, WebKit2
        except (ImportError, ValueError):
            self.skipTest("WebKit2 4.1 indisponível")
        with tempfile.TemporaryDirectory() as pasta:
            loja = WebKit2.UserContentFilterStore.new(pasta)
            resultado, laco = {}, GLib.MainLoop()

            def pronto(l, r):
                try:
                    resultado["ok"] = l.save_finish(r) is not None
                except GLib.Error as erro:
                    resultado["erro"] = erro.message
                laco.quit()
            loja.save("teste", GLib.Bytes.new(json.dumps(self.regras).encode()), None, pronto)
            GLib.timeout_add_seconds(20, laco.quit)
            laco.run()
        self.assertTrue(resultado.get("ok"), resultado.get("erro"))


if __name__ == "__main__":
    unittest.main()
