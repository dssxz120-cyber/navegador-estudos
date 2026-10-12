"""O "motor" de páginas (WebKit) já configurado com as proteções.

Fica separado do aplicativo para que os testes automáticos usem EXATAMENTE
a mesma configuração que o navegador de verdade.

Camadas de proteção montadas aqui:
  - regras de bloqueio de conteúdo: barram páginas e iframes fora da lista
    antes de o pedido sair do computador (inclusive redirecionamentos);
  - cookies de terceiros recusados e prevenção de rastreamento (ITP);
  - sem ferramentas de desenvolvedor, câmera, microfone, pop-ups automáticos;
  - downloads cancelados.
As decisões página a página (tela de bloqueio, permissões) ficam em filtro.py.
"""

import json
import sys

import gi

gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, WebKit2  # noqa: E402

ID_DAS_REGRAS = "lista-de-sites"


class ErroNasRegras(Exception):
    """As regras de bloqueio não puderam ser preparadas."""


class Motor:
    def __init__(self, pasta_dados, pasta_cache, servir_pagina_interna=None):
        # Cookies, logins e cache ficam em pastas só deste navegador.
        dados = WebKit2.WebsiteDataManager(base_data_directory=str(pasta_dados),
                                           base_cache_directory=str(pasta_cache))
        dados.set_itp_enabled(True)   # dificulta o rastreamento entre sites
        self.contexto = WebKit2.WebContext(website_data_manager=dados)
        # Cookies de terceiros (usados por propaganda e rastreadores) são recusados.
        self.contexto.get_cookie_manager().set_accept_policy(
            WebKit2.CookieAcceptPolicy.NO_THIRD_PARTY)
        self.contexto.set_favicon_database_directory(None)
        self.contexto.connect("download-started", lambda _c, download: download.cancel())

        if servir_pagina_interna is not None:
            # "estudos://" é tratado como endereço seguro, para que a tela de
            # bloqueio (que fica no endereço do site barrado) possa usar o CSS e a fonte.
            self.contexto.register_uri_scheme("estudos", servir_pagina_interna)
            seguranca = self.contexto.get_security_manager()
            seguranca.register_uri_scheme_as_secure("estudos")
            seguranca.register_uri_scheme_as_cors_enabled("estudos")

        self.ajustes = WebKit2.Settings(
            enable_developer_extras=False,          # sem ferramentas de desenvolvedor
            javascript_can_open_windows_automatically=False,  # sem pop-ups sozinhos
            enable_media_stream=False,              # sem câmera e microfone
            enable_webrtc=False,                    # sem chamadas de vídeo/voz
            enable_smooth_scrolling=True,
            enable_back_forward_navigation_gestures=True,
            enable_write_console_messages_to_stdout=False)

        # Todas as abas compartilham o mesmo "gerenciador de conteúdo", que é
        # onde as regras de bloqueio ficam instaladas.
        self.conteudo = WebKit2.UserContentManager()
        self._loja = WebKit2.UserContentFilterStore.new(str(pasta_cache / "regras"))
        self.regras_ativas = False

    def criar_webview(self, relacionada=None):
        if relacionada is not None:
            # Aba aberta por outra (pop-up de login...): mesma sessão e mesmas regras.
            return WebKit2.WebView(related_view=relacionada, settings=self.ajustes,
                                   user_content_manager=self.conteudo)
        return WebKit2.WebView(web_context=self.contexto, settings=self.ajustes,
                               user_content_manager=self.conteudo)

    def aplicar_lista(self, lista, limite_segundos=15):
        """Compila as regras da lista e as instala em todas as abas.

        O WebKit compila as regras em segundo plano; esperamos terminar antes
        de seguir, para nenhuma página abrir sem proteção.
        Lança ErroNasRegras se não der certo.
        """
        texto = json.dumps(lista.regras_de_conteudo())
        resultado = {}
        laco = GLib.MainLoop()

        def ao_salvar(loja, resposta):
            try:
                resultado["filtro"] = loja.save_finish(resposta)
            except GLib.Error as erro:
                resultado["erro"] = erro.message
            laco.quit()

        def tempo_esgotado():
            resultado.setdefault("erro", "tempo esgotado ao compilar as regras")
            laco.quit()
            return False

        self._loja.save(ID_DAS_REGRAS, GLib.Bytes.new(texto.encode("utf-8")), None, ao_salvar)
        relogio = GLib.timeout_add_seconds(limite_segundos, tempo_esgotado)
        laco.run()
        if "erro" not in resultado:
            GLib.source_remove(relogio)

        if "filtro" not in resultado:
            self.regras_ativas = False
            print("Navegador de Estudos: regras de bloqueio indisponíveis:",
                  resultado.get("erro"), file=sys.stderr)
            raise ErroNasRegras(resultado.get("erro"))
        self.conteudo.remove_all_filters()
        self.conteudo.add_filter(resultado["filtro"])
        self.regras_ativas = True
