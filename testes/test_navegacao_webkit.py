"""Testes de navegação com o WebKit DE VERDADE e um servidor local.

Para cada truque de fuga, o teste confere duas coisas:
  1. o servidor "bloqueado.localhost" NÃO recebeu nenhum pedido;
  2. a aba mostra a tela de bloqueio (ou a página permitida segue intacta).

Precisam de uma tela (mesmo que nada apareça nela). Sem tela, são pulados.
Rode com:  python3 -m unittest discover testes
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from apoio_webkit import (TITULO_BLOQUEIO, JanelaFalsa, ServidorDeTeste, deixar_rodar,
                          esperar, servir_pagina_interna_de_teste, tela_disponivel)

from estudos.interface.motor import Motor
from estudos.nucleo.regras import ListaDeSites

BLOQUEADO = "bloqueado.localhost"


def lista_de_teste(servidor):
    texto = (f"[Teste]\nLocal | {servidor.url('permitido.localhost', '/ok')}\n"
             "- excluido.permitido.localhost\n")
    return ListaDeSites.de_texto(texto, somente_https=False,
                                 embutidos=[("embed.localhost", "/embed/")])


class _BaseNavegacao(unittest.TestCase):
    COM_REGRAS = True

    @classmethod
    def setUpClass(cls):
        if not tela_disponivel():
            raise unittest.SkipTest("sem tela disponível para o WebKit")
        cls.pasta = tempfile.TemporaryDirectory()
        base = Path(cls.pasta.name)
        (base / "dados").mkdir()
        (base / "cache").mkdir()
        cls.servidor = ServidorDeTeste()
        cls.lista = lista_de_teste(cls.servidor)
        assert cls.lista.erros == [], cls.lista.erros
        cls.motor = Motor(base / "dados", base / "cache", servir_pagina_interna_de_teste)
        if cls.COM_REGRAS:
            cls.motor.aplicar_lista(cls.lista)

    @classmethod
    def tearDownClass(cls):
        cls.servidor.parar()
        cls.pasta.cleanup()

    def setUp(self):
        self.servidor.limpar()
        self.janela = JanelaFalsa(self.motor, self.lista)

    def tearDown(self):
        self.janela.fechar_tudo()

    # ---- ajudantes ----

    def abrir(self, host, caminho, espera=4):
        aba = self.janela.nova_aba(self.servidor.url(host, caminho))
        deixar_rodar(espera)
        return aba

    def assertSemPedido(self, host=BLOQUEADO):
        self.assertEqual(self.servidor.pedidos_para(host), [],
                         f"o servidor {host} recebeu pedidos")

    def assertBloqueada(self, aba):
        self.assertTrue(esperar(lambda: aba.get_title() == TITULO_BLOQUEIO, 3),
                        f"esperava a tela de bloqueio, veio {aba.get_title()!r} em {aba.get_uri()}")

    def titulos(self):
        return [aba.get_title() for aba in self.janela.abas]


class TestFugasComTodasAsCamadas(_BaseNavegacao):
    """O navegador completo: nenhum pedido pode chegar ao site bloqueado."""

    def test_pagina_permitida_abre(self):
        aba = self.abrir("permitido.localhost", "/ok", 2)
        self.assertTrue(esperar(lambda: aba.get_title() == "OK", 3))
        self.assertEqual(len(self.servidor.pedidos_para("permitido.localhost")), 1)

    def test_subdominio_de_permitido_abre(self):
        aba = self.abrir("sub.permitido.localhost", "/ok", 2)
        self.assertTrue(esperar(lambda: aba.get_title() == "OK", 3))

    def test_acesso_direto(self):
        self.assertBloqueada(self.abrir(BLOQUEADO, "/alvo", 2))
        self.assertSemPedido()

    def test_link_clicado(self):
        self.assertBloqueada(self.abrir("permitido.localhost", "/link"))
        self.assertSemPedido()

    def test_redirecionamento_javascript(self):
        self.assertBloqueada(self.abrir("permitido.localhost", "/jsredir"))
        self.assertSemPedido()

    def test_redirecionamento_http_302(self):
        self.assertBloqueada(self.abrir("permitido.localhost", "/302"))
        self.assertSemPedido()

    def test_meta_refresh(self):
        self.assertBloqueada(self.abrir("permitido.localhost", "/meta"))
        self.assertSemPedido()

    def test_formulario_get(self):
        self.assertBloqueada(self.abrir("permitido.localhost", "/form-get"))
        self.assertSemPedido()

    def test_formulario_post(self):
        self.assertBloqueada(self.abrir("permitido.localhost", "/form-post"))
        self.assertSemPedido()

    def test_iframe_bloqueado_fica_vazio(self):
        aba = self.abrir("permitido.localhost", "/iframe")
        self.assertEqual(aba.get_title(), "iframe")      # a página permitida continua
        self.assertSemPedido()

    def test_iframe_permitido_carrega(self):
        aba = self.abrir("permitido.localhost", "/iframe-permitido")
        self.assertTrue(esperar(lambda: aba.get_title() == "IFRAME_CARREGOU", 3))

    def test_embutido_so_dentro_de_iframe(self):
        self.abrir("permitido.localhost", "/iframe-embutido")
        self.assertEqual(len(self.servidor.pedidos_para("embed.localhost")), 1,
                         "o vídeo embutido deveria carregar dentro da página")
        self.servidor.limpar()
        self.assertBloqueada(self.abrir("embed.localhost", "/embed/video", 2))
        self.assertSemPedido("embed.localhost")

    def test_popup_automatico(self):
        aba = self.abrir("permitido.localhost", "/popup")
        self.assertEqual(aba.get_title(), "popup_negado")
        self.assertSemPedido()

    def test_link_nova_aba(self):
        self.abrir("permitido.localhost", "/blank")
        self.assertNotIn("ALVO", self.titulos())
        self.assertSemPedido()

    def test_subdominio_excluido(self):
        aba = self.janela.nova_aba(None)
        url = self.servidor.url("excluido.permitido.localhost", "/ok")
        aba.load_uri(url)          # como um link ou script, sem passar pelo filtro.abrir
        deixar_rodar(2)
        self.assertBloqueada(aba)
        self.assertEqual(self.janela.barrados_pelo_webkit, [url], "deveria barrar na camada 1")
        self.assertSemPedido("excluido.permitido.localhost")

    def test_redirecionamento_barrado_pela_camada_1(self):
        self.assertBloqueada(self.abrir("permitido.localhost", "/302"))
        self.assertEqual(len(self.janela.barrados_pelo_webkit), 1)
        self.assertSemPedido()

    def test_dominios_parecidos(self):
        for host in ("permitido.localhost.bloqueado.localhost", "falsopermitido.localhost"):
            with self.subTest(host=host):
                self.assertBloqueada(self.abrir(host, "/alvo", 2))
                self.assertSemPedido(host)

    def test_barra_invertida_digitada(self):
        url = (f"http://{BLOQUEADO}:{self.servidor.porta}\\@permitido.localhost:"
               f"{self.servidor.porta}/ok")
        aba = self.janela.nova_aba(url)
        deixar_rodar(2)
        self.assertBloqueada(aba)
        self.assertSemPedido()

    def test_barra_invertida_carregada_direto_no_webkit(self):
        # Sem passar pelo filtro.abrir: simula um link ou script da página.
        aba = self.janela.nova_aba(None)
        aba.load_uri(f"http://{BLOQUEADO}:{self.servidor.porta}\\@permitido.localhost:"
                     f"{self.servidor.porta}/ok")
        deixar_rodar(2)
        self.assertBloqueada(aba)
        self.assertSemPedido()

    def test_usuario_e_senha_no_endereco(self):
        p = self.servidor.porta
        for url in (f"http://permitido.localhost:{p}@{BLOQUEADO}:{p}/alvo",
                    f"http://usuario@permitido.localhost:{p}/ok"):
            with self.subTest(url=url):
                aba = self.janela.nova_aba(None)
                aba.load_uri(url)
                deixar_rodar(2)
                self.assertBloqueada(aba)
        self.assertSemPedido()
        self.assertSemPedido("permitido.localhost")

    def test_cookie_de_site_bloqueado_nao_e_gravado(self):
        self.assertBloqueada(self.abrir("permitido.localhost", "/302-cookie"))
        self.assertSemPedido()
        resultado = {}
        gerente = self.motor.contexto.get_cookie_manager()
        gerente.get_cookies(self.servidor.url(BLOQUEADO, "/"), None,
                            lambda g, r: resultado.setdefault("cookies", g.get_cookies_finish(r)))
        esperar(lambda: "cookies" in resultado, 3)
        self.assertEqual(resultado.get("cookies"), [])

    def test_site_nao_le_pagina_interna_por_fetch(self):
        aba = self.abrir("permitido.localhost", "/fetch-interno", 2)
        self.assertNotIn("SEGREDO", aba.get_title() or "")
        self.assertEqual(aba.get_title(), "fetch_negado")

    def test_site_nao_le_pagina_interna_por_iframe(self):
        aba = self.abrir("permitido.localhost", "/iframe-interno", 2)
        self.assertNotIn("SEGREDO", aba.get_title() or "")

    def test_aba_que_cai_mostra_aviso_em_vez_de_ficar_em_branco(self):
        aba = self.abrir("permitido.localhost", "/ok", 2)
        self.assertEqual(aba.get_title(), "OK")
        url = aba.get_uri()
        aba.terminate_web_process()          # simula a queda do processo da aba
        self.assertTrue(esperar(lambda: aba.get_title() == "Aba interrompida", 5))
        self.assertTrue(any("parou de funcionar" in a for a in self.janela.avisos))
        resultado = {}
        aba.evaluate_javascript("[...document.querySelectorAll('a.botao')].map(a => a.href).join(' ')",
                                -1, None, None, None,
                                lambda v, r: resultado.setdefault("links", v.evaluate_javascript_finish(r).to_string()))
        esperar(lambda: "links" in resultado, 3)
        self.assertIn(url, resultado["links"])                 # "Tentar de novo"
        self.assertIn("estudos://inicio", resultado["links"])  # "Página inicial"

    def test_pagina_interna_abre(self):
        aba = self.janela.nova_aba("estudos://inicio")
        self.assertTrue(esperar(lambda: aba.get_title() == "INTERNO", 3))


class TestCamadasComplementaresSemRegras(_BaseNavegacao):
    """Sem as regras do WebKit (camada 1), as camadas 2 e 3 ainda impedem a
    página de APARECER — mas o pedido chega ao servidor. Isso documenta por
    que a camada 1 é necessária."""

    COM_REGRAS = False

    def test_redirecionamento_ainda_mostra_bloqueio(self):
        self.assertBloqueada(self.abrir("permitido.localhost", "/jsredir"))
        self.assertGreater(len(self.servidor.pedidos_para(BLOQUEADO)), 0,
                           "sem a camada 1, o pedido chega ao servidor (comportamento da v2.0)")

    def test_clique_e_digitacao_barrados_sem_pedido(self):
        self.assertBloqueada(self.abrir(BLOQUEADO, "/alvo", 2))
        self.assertBloqueada(self.abrir("permitido.localhost", "/link"))
        self.assertSemPedido()


class TestTrocaDeLista(_BaseNavegacao):
    """Quando o responsável salva uma lista nova, as regras mudam na hora."""

    def test_liberar_e_bloquear_de_novo(self):
        self.assertBloqueada(self.abrir(BLOQUEADO, "/alvo", 2))
        self.assertSemPedido()

        nova = ListaDeSites.de_texto(f"+ permitido.localhost\n+ {BLOQUEADO}\n", somente_https=False)
        self.motor.aplicar_lista(nova)
        self.janela.app.lista = nova
        aba = self.abrir(BLOQUEADO, "/alvo", 2)
        self.assertTrue(esperar(lambda: aba.get_title() == "ALVO", 3))

        self.motor.aplicar_lista(self.lista)      # volta a lista original
        self.janela.app.lista = self.lista
        self.servidor.limpar()
        self.assertBloqueada(self.abrir(BLOQUEADO, "/alvo", 2))
        self.assertSemPedido()


if __name__ == "__main__":
    unittest.main()
