"""Teste OPCIONAL com a internet: as IAs, o YouTube e as páginas de login
continuam abrindo com todas as camadas de proteção ligadas?

Só roda quando pedido, porque depende da internet e dos sites:
    ESTUDOS_TESTE_ONLINE=1 python3 -m unittest testes.test_servicos_online -v

Verifica que a página principal abre sem ser barrada. NÃO verifica login
completo (isso exige contas e senhas reais).
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from apoio_webkit import JanelaFalsa, esperar, tela_disponivel  # noqa: E402

from estudos.interface.motor import Motor  # noqa: E402
from estudos.nucleo.regras import ListaDeSites  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent

# Serviços fixos: IAs, YouTube (página, vídeo e busca) e páginas de login.
SERVICOS_FIXOS = [
    "https://chatgpt.com/", "https://gemini.google.com/app", "https://claude.ai/login",
    "https://www.perplexity.ai/", "https://copilot.com/",
    "https://www.youtube.com/", "https://www.youtube.com/watch?v=jNQXAC9IVRw",
    "https://www.youtube.com/results?search_query=fotoss%C3%ADntese",
    "https://accounts.google.com/", "https://login.live.com/", "https://auth.openai.com/log-in",
]


def _servicos(lista):
    """Os fixos + todos os atalhos da lista padrão (plataformas educacionais)."""
    urls = list(SERVICOS_FIXOS)
    for categoria in lista.categorias:
        urls += [a.url for a in categoria.atalhos if a.url not in urls]
    return urls


@unittest.skipUnless(os.environ.get("ESTUDOS_TESTE_ONLINE") == "1", "defina ESTUDOS_TESTE_ONLINE=1")
class TestServicosOnline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not tela_disponivel():
            raise unittest.SkipTest("sem tela disponível para o WebKit")
        cls.pasta = tempfile.TemporaryDirectory()
        base = Path(cls.pasta.name)
        (base / "d").mkdir()
        (base / "c").mkdir()
        texto = (RAIZ / "recursos" / "sites_padrao.txt").read_text() + "\n+ youtube.com\n"
        cls.lista = ListaDeSites.de_texto(texto)
        cls.motor = Motor(base / "d", base / "c")
        cls.motor.aplicar_lista(cls.lista)

    @classmethod
    def tearDownClass(cls):
        cls.pasta.cleanup()

    def test_servicos_abrem(self):
        for url in _servicos(self.lista):
            with self.subTest(url=url):
                janela = JanelaFalsa(self.motor, self.lista)
                barrados = janela.barrados_pelo_webkit
                aba = janela.nova_aba(None)
                aba.load_uri(url)
                esperar(lambda: not aba.is_loading() and aba.get_title(), 40)
                final = aba.get_uri()
                print(f"\n  {url}\n    -> {final} | título: {aba.get_title()!r}", flush=True)
                self.assertEqual(barrados, [], f"barrado pelo bloqueador: {barrados}")
                self.assertNotEqual(aba.get_title(), "Site bloqueado")
                self.assertTrue(self.lista.permite(final), f"terminou fora da lista: {final}")
                janela.fechar_tudo()


@unittest.skipUnless(os.environ.get("ESTUDOS_TESTE_ONLINE") == "1", "defina ESTUDOS_TESTE_ONLINE=1")
class TestSecoesBarradasOnline(TestServicosOnline):
    """Seções excluídas são barradas pelo bloqueador ANTES do pedido."""

    def test_servicos_abrem(self):
        pass   # já coberto pela classe mãe

    def test_secoes_excluidas(self):
        for url in ["https://sora.chatgpt.com/", "https://community.openai.com/"]:
            with self.subTest(url=url):
                janela = JanelaFalsa(self.motor, self.lista)
                barrados = janela.barrados_pelo_webkit
                aba = janela.nova_aba(None)
                aba.load_uri(url)
                esperar(lambda: aba.get_title() == "Site bloqueado", 15)
                print(f"\n  {url} -> barrado pelo bloqueador: {bool(barrados)} | título: {aba.get_title()!r}")
                self.assertEqual(barrados, [url])
                self.assertEqual(aba.get_title(), "Site bloqueado")
                janela.fechar_tudo()


if __name__ == "__main__":
    unittest.main()
