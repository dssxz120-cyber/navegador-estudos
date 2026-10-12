"""O filtro: decide o que cada aba pode abrir e o que os sites podem pedir.

Conceito importante — "decide-policy":
  Toda vez que uma página quer abrir algum endereço, o WebKit (o motor que
  desenha as páginas) pergunta ao nosso programa se pode. A pergunta chega
  em três momentos:
    NAVIGATION_ACTION -> "vou navegar para X" (página ou iframe; não dá para
                         saber qual dos dois neste momento)
    NEW_WINDOW_ACTION -> "a página quer abrir X numa janela nova"
    RESPONSE          -> "o servidor respondeu com X" (aqui já sabemos se é a
                         página principal ou um iframe, e já passamos por
                         todos os redirecionamentos)
  São três camadas:
    1. regras de bloqueio de conteúdo (motor.py): o WebKit barra páginas e
       iframes fora da lista ANTES de enviar o pedido, inclusive em
       redirecionamentos. Quando barra a página principal, o sinal
       "load-failed" chega aqui e mostramos a tela de bloqueio;
    2. NAVIGATION_ACTION: cliques do usuário para fora da lista são recusados
       na hora, sem pedido nenhum;
    3. RESPONSE: checagem final, caso algo tenha passado pelas anteriores.
"""

import gi

gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, WebKit2  # noqa: E402

from . import paginas  # noqa: E402

PAGINA_INICIAL = "estudos://inicio"

# Código de erro que o WebKit usa quando uma regra de bloqueio de conteúdo
# barra um endereço ("The URL was blocked by a content blocker").
ERRO_BLOQUEADOR_DE_CONTEUDO = 104
Decisao = WebKit2.PolicyDecisionType
TipoNav = WebKit2.NavigationType

# Navegações que quase sempre são da página principal e vêm de uma ação do
# usuário (clique, envio de formulário, voltar/avançar).
NAVEGACOES_DO_USUARIO = (TipoNav.LINK_CLICKED, TipoNav.FORM_SUBMITTED, TipoNav.BACK_FORWARD)

# Itens do menu do botão direito que removemos (baixar arquivos e as
# ferramentas de desenvolvedor, que permitiriam mexer na página).
ITENS_PROIBIDOS = {
    WebKit2.ContextMenuAction.DOWNLOAD_LINK_TO_DISK,
    WebKit2.ContextMenuAction.DOWNLOAD_IMAGE_TO_DISK,
    WebKit2.ContextMenuAction.DOWNLOAD_VIDEO_TO_DISK,
    WebKit2.ContextMenuAction.DOWNLOAD_AUDIO_TO_DISK,
    WebKit2.ContextMenuAction.INSPECT_ELEMENT,
}

# Nome amigável de cada tipo de permissão que um site pode pedir.
PERMISSOES = [
    ("GeolocationPermissionRequest", "sua localização"),
    ("UserMediaPermissionRequest", "câmera ou microfone"),
    ("NotificationPermissionRequest", "enviar notificações"),
    ("ClipboardPermissionRequest", "ler a área de transferência"),
    ("DeviceInfoPermissionRequest", "informações dos dispositivos"),
    ("MediaKeySystemPermissionRequest", "conteúdo protegido"),
    ("PointerLockPermissionRequest", "prender o cursor do mouse"),
    ("WebsiteDataAccessPermissionRequest", "dados de outros sites"),
]


class Filtro:
    """Liga os sinais de segurança em cada aba nova.

    `janela` precisa oferecer: app.lista, mostrar_aviso(texto) e
    nova_aba(url=..., webview=...).
    """

    def __init__(self, janela):
        self.janela = janela

    @property
    def lista(self):
        return self.janela.app.lista

    def proteger(self, webview):
        webview.connect("decide-policy", self._ao_decidir)
        webview.connect("context-menu", self._ao_abrir_menu)
        webview.connect("permission-request", self._ao_pedir_permissao)
        webview.connect("load-failed", self._ao_falhar)
        webview.connect("web-process-terminated", self._ao_interromper)

    # ---------------- ações ----------------

    def abrir(self, webview, url):
        """Abre um endereço digitado ou escolhido, já aplicando as regras."""
        seguro = self.lista.https_disponivel(url)
        if seguro:
            url = seguro                       # http://site -> https://site
        if self.lista.permite(url):
            webview.load_uri(url)
        else:
            self.bloquear(webview, url)

    def bloquear(self, webview, url, motivo=None):
        if motivo is None:
            tipo = self.lista.classificar(url)
            motivo = (tipo if tipo in ("sem_criptografia", "excluido", "invalido")
                      else "fora_da_lista")
        # idle_add: espera o WebKit terminar o que está fazendo antes de trocar a página.
        GLib.idle_add(webview.load_alternate_html,
                      paginas.pagina_bloqueada(url, motivo), url, None)

    # ---------------- camada 1: regras de bloqueio ----------------

    def _ao_falhar(self, webview, _evento, url, erro):
        """A página principal não carregou. Foi o bloqueador de conteúdo?"""
        if erro.domain != "WebKitPolicyError" or erro.code != ERRO_BLOQUEADOR_DE_CONTEUDO:
            return False   # outro erro (sem internet etc.): o WebKit mostra o aviso dele
        # Se o endereço que falhou é permitido, quem foi barrado foi o destino
        # de um redirecionamento (o WebKit informa o endereço de origem).
        self.bloquear(webview, url, "redirecionamento" if self.lista.permite(url) else None)
        return True

    def _ao_interromper(self, webview, _motivo):
        """O processo que desenha a aba caiu: mostra uma tela explicando, em vez
        de deixar a aba em branco. Não recarrega sozinho, para não entrar em
        ciclo se a queda se repetir."""
        url = webview.get_uri() or ""
        pode_voltar = self.lista.permite(url) and not url.startswith("estudos:")
        GLib.idle_add(webview.load_alternate_html,
                      paginas.pagina_aba_interrompida(url, pode_voltar),
                      url or PAGINA_INICIAL, None)
        self.janela.mostrar_aviso("Uma aba parou de funcionar e foi interrompida.")

    # ---------------- camadas 2 e 3: decisões ----------------

    def _ao_decidir(self, webview, decisao, tipo):
        if tipo == Decisao.NAVIGATION_ACTION:
            return self._navegacao(webview, decisao)
        if tipo == Decisao.NEW_WINDOW_ACTION:
            return self._janela_nova(decisao)
        if tipo == Decisao.RESPONSE:
            return self._resposta(webview, decisao)
        return False

    def _navegacao(self, webview, decisao):
        acao = decisao.get_navigation_action()
        url = acao.get_request().get_uri()
        do_usuario = acao.is_user_gesture() or acao.get_navigation_type() in NAVEGACOES_DO_USUARIO

        if url.startswith("estudos:"):
            if do_usuario:
                # Clique em "Voltar para a página inicial" na tela de bloqueio:
                # o WebKit não deixa um site pular para um endereço interno,
                # então nós mesmos abrimos a página inicial.
                decisao.ignore()
                GLib.idle_add(webview.load_uri, PAGINA_INICIAL)
            else:
                decisao.use()
            return True

        if self.lista.permite_embutido(url):
            decisao.use()
            return True

        if do_usuario:
            decisao.ignore()
            seguro = self.lista.https_disponivel(url)
            if seguro:
                GLib.idle_add(webview.load_uri, seguro)   # troca http por https
            else:
                self.bloquear(webview, url)
            return True

        # Pode ser um iframe ou um redirecionamento automático (não dá para
        # saber aqui). As regras de bloqueio (camada 1) já barram o pedido
        # antes de sair; a resposta (camada 3) confere de novo.
        decisao.use()
        return True

    def _janela_nova(self, decisao):
        url = decisao.get_navigation_action().get_request().get_uri()
        if self.lista.permite(url) or url in ("", "about:blank"):
            decisao.use()        # o sinal "create" da janela vai abrir uma aba
        else:
            decisao.ignore()
            self.janela.nova_aba(url)   # mostra a tela de bloqueio numa aba nova
        return True

    def _resposta(self, webview, decisao):
        url = decisao.get_response().get_uri()
        if decisao.is_main_frame_main_resource():
            if not self.lista.permite(url):
                decisao.ignore()
                self.bloquear(webview, url)
                return True
            if not decisao.is_mime_type_supported():
                decisao.ignore()   # seria um download
                self.janela.mostrar_aviso("Downloads estão desativados no Navegador de Estudos.")
                return True
        elif not self.lista.permite_embutido(url):
            decisao.ignore()       # iframe de fora da lista fica vazio
            return True
        return False

    # ---------------- menu e permissões ----------------

    def _ao_abrir_menu(self, _webview, menu, _evento, _resultado):
        for item in list(menu.get_items()):
            if item.get_stock_action() in ITENS_PROIBIDOS:
                menu.remove(item)
        return False

    def _ao_pedir_permissao(self, _webview, pedido):
        """Nega TODO pedido de permissão (câmera, microfone, localização...)."""
        pedido.deny()
        nome = "um acesso especial"
        for classe, descricao in PERMISSOES:
            tipo = getattr(WebKit2, classe, None)
            if tipo is not None and isinstance(pedido, tipo):
                nome = descricao
                break
        self.janela.mostrar_aviso(f"O site pediu acesso a {nome}. Pedido recusado por segurança.")
        return True
