"""O aplicativo: prepara o motor de páginas com as proteções, serve as páginas
internas (estudos://...) e cuida do Pomodoro e do contador de tempo.
"""

import ctypes
import ctypes.util
import mimetypes
import subprocess

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from .. import ID_APP  # noqa: E402
from ..nucleo import caminhos, pomodoro, preferencias, senha  # noqa: E402
from . import dialogos, paginas  # noqa: E402
from ..nucleo.tempo import deve_contar  # noqa: E402
from .inatividade import MonitorDeInatividade  # noqa: E402
from .janela import Janela  # noqa: E402
from .motor import ErroNasRegras, Motor  # noqa: E402


def carregar_fonte_do_programa():
    """Deixa a fonte Bricolage disponível SÓ para este programa.

    Usa a biblioteca fontconfig (a mesma que o Ubuntu usa para achar fontes),
    sem instalar nada no sistema.
    """
    nome = ctypes.util.find_library("fontconfig")
    if not nome:
        return
    fontconfig = ctypes.CDLL(nome)
    fontconfig.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    arquivo = caminhos.PASTA_RECURSOS / "fontes" / "BricolageGrotesque.ttf"
    fontconfig.FcConfigAppFontAddFile(None, str(arquivo).encode())


class Aplicativo(Gtk.Application):
    def __init__(self, lista, contador, unico=True):
        # unico=True: abrir o programa de novo só traz a janela já aberta para a
        # frente. Os testes usam unico=False para rodar uma cópia separada.
        bandeiras = (Gio.ApplicationFlags.FLAGS_NONE if unico
                     else Gio.ApplicationFlags.NON_UNIQUE)
        super().__init__(application_id=ID_APP, flags=bandeiras)
        self.lista = lista
        self.contador = contador
        self.janela = None
        self.preferencias = preferencias.carregar()
        self.pomodoro = pomodoro.Pomodoro(self._ao_mudar_pomodoro, self._ao_trocar_fase,
                                          arquivo=caminhos.ARQUIVO_POMODORO)
        self.inatividade = MonitorDeInatividade()
        self._segundos_sem_salvar = 0

    # ---------------- início e fim ----------------

    def do_startup(self):
        Gtk.Application.do_startup(self)
        carregar_fonte_do_programa()
        estilo = Gtk.CssProvider()
        estilo.load_from_path(str(caminhos.PASTA_RECURSOS / "interface.css"))
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), estilo, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        # O motor de páginas, com as camadas de proteção (veja motor.py).
        self.motor = Motor(caminhos.PASTA_NAVEGACAO, caminhos.PASTA_CACHE,
                           self._servir_pagina_interna)
        self.contexto = self.motor.contexto
        try:
            self.motor.aplicar_lista(self.lista)
        except ErroNasRegras:
            # As outras duas camadas (filtro.py) continuam impedindo que a
            # página apareça; a janela avisa que a proteção extra está fora.
            pass

        # A cada segundo, soma tempo para o site aberto na aba atual.
        GLib.timeout_add_seconds(1, self._contar_tempo)
        self.hold()   # mantém o programa vivo enquanto o diálogo de senha aparece

    def do_activate(self):
        if self.janela is None:
            # Primeira vez: o responsável cria a senha antes de tudo. No modo
            # protegido não há senha do navegador (vale a de administrador).
            if (not caminhos.MODO_PROTEGIDO and not senha.existe()
                    and not dialogos.criar_senha(None)):
                self.release()   # cancelou: o programa fecha sem abrir a janela
                return
            self.janela = Janela(self)
            self.release()
        self.janela.present()

    def do_shutdown(self):
        self.contador.salvar()
        Gtk.Application.do_shutdown(self)

    def criar_webview(self, relacionada=None):
        return self.motor.criar_webview(relacionada)

    def trocar_lista(self, lista):
        """Instala uma lista nova (depois de o responsável salvar)."""
        self.lista = lista
        try:
            self.motor.aplicar_lista(lista)
        except ErroNasRegras:
            pass

    # ---------------- páginas internas ----------------

    def _servir_pagina_interna(self, pedido):
        """Responde a endereços estudos://inicio e estudos://recursos/..."""
        uri = pedido.get_uri()
        if uri.startswith("estudos://recursos/"):
            # Só entrega arquivos de dentro da pasta recursos/ (nada de "../").
            relativo = GLib.uri_unescape_string(
                uri[len("estudos://recursos/"):].split("?")[0].split("#")[0], None) or ""
            arquivo = caminhos.recurso_seguro(relativo)
            if arquivo is None:
                pedido.finish_error(GLib.Error.new_literal(
                    Gio.io_error_quark(), "não encontrado", Gio.IOErrorEnum.NOT_FOUND))
                return
            conteudo = arquivo.read_bytes()
            tipo = mimetypes.guess_type(arquivo.name)[0] or "application/octet-stream"
        else:
            conteudo = paginas.pagina_inicial(self.lista, self.contador,
                                              preferencias.carregar()).encode("utf-8")
            tipo = "text/html"
        dados = GLib.Bytes.new(conteudo)
        pedido.finish(Gio.MemoryInputStream.new_from_bytes(dados), dados.get_size(), tipo)

    # ---------------- tempo e Pomodoro ----------------

    def _contar_tempo(self):
        janela = self.janela
        if not janela or not janela.abas.get_n_pages():
            return True
        view = janela.view_atual()
        limite = 60 * self.preferencias.get("inatividade_minutos", 5)
        # Conta só com a janela em primeiro plano e o aluno presente (mexeu no
        # teclado/mouse nos últimos minutos, ou há áudio tocando, como num vídeo).
        if deve_contar(janela.is_active(), self.inatividade.segundos_parado(),
                       view.is_playing_audio(), limite):
            site = self.lista.nome_do_site(view.get_uri() or "")
            if site:
                self.contador.somar(site)
                self._segundos_sem_salvar += 1
                if self._segundos_sem_salvar >= 15:
                    self.contador.salvar()
                    self._segundos_sem_salvar = 0
        return True

    def _ao_mudar_pomodoro(self):
        if self.janela:
            self.janela.atualizar_pomodoro()

    def _ao_trocar_fase(self, acabou, comeca):
        if acabou == pomodoro.ESTUDO:
            titulo = "Hora da pausa! ☕"
            corpo = (f"Ótimo trabalho! Descanse {pomodoro.DURACAO[comeca] // 60} minutos: "
                     "levante, beba água, olhe para longe da tela.")
            som = "complete"
        else:
            titulo = "Pausa encerrada 📚"
            corpo = "Bora voltar a estudar! Mais 25 minutos de foco."
            som = "alarm-clock-elapsed"
        notificacao = Gio.Notification.new(titulo)
        notificacao.set_body(corpo)
        self.send_notification("pomodoro", notificacao)
        if self.janela:
            self.janela.mostrar_aviso(f"{titulo}  {corpo}", segundos=10)
        try:
            subprocess.Popen(["canberra-gtk-play", "-i", som],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            Gdk.beep()
