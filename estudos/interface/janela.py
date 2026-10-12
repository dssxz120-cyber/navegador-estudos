"""A janela do navegador: barra superior, abas, Pomodoro e "Hoje".

As regras de segurança ficam em filtro.py; aqui é só a parte visual.
"""

import datetime

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango  # noqa: E402

from .. import NOME_APP, VERSAO  # noqa: E402
from ..nucleo import caminhos, pomodoro, preferencias, protegido  # noqa: E402
from ..nucleo.tempo import formatar, texto_do_relogio  # noqa: E402
from . import dialogos  # noqa: E402
from .filtro import PAGINA_INICIAL, Filtro  # noqa: E402


def _margens(widget, valor):
    for lado in ("top", "bottom", "start", "end"):
        getattr(widget, f"set_margin_{lado}")(valor)


def _classe(widget, *classes):
    for classe in classes:
        widget.get_style_context().add_class(classe)
    return widget


# --------------------------------------------------------------------------
#  Uma aba
# --------------------------------------------------------------------------

class Aba(Gtk.Box):
    """Uma aba: guarda a WebView e o "rótulo" (ícone + título + botão X)."""

    def __init__(self, janela, webview):
        super().__init__()
        self.janela = janela
        self.webview = webview
        self.pack_start(webview, True, True, 0)

        self.icone = Gtk.Image.new_from_icon_name("text-html-symbolic", Gtk.IconSize.MENU)
        self.girando = Gtk.Spinner()
        self.titulo = Gtk.Label(label="Nova aba", ellipsize=Pango.EllipsizeMode.END,
                                width_chars=16, max_width_chars=16, xalign=0)
        fechar = Gtk.Button.new_from_icon_name("window-close-symbolic", Gtk.IconSize.MENU)
        fechar.set_relief(Gtk.ReliefStyle.NONE)
        fechar.set_tooltip_text("Fechar aba (Ctrl+W)")
        fechar.connect("clicked", lambda *_: janela.fechar_aba(self))
        self.rotulo = Gtk.Box(spacing=8)
        self.rotulo.pack_start(self.icone, False, False, 0)
        self.rotulo.pack_start(self.girando, False, False, 0)
        self.rotulo.pack_start(self.titulo, True, True, 0)
        self.rotulo.pack_start(fechar, False, False, 0)
        self.rotulo.show_all()
        self.girando.hide()

        webview.connect("notify::title", self._atualizar_titulo)
        webview.connect("notify::favicon", self._atualizar_icone)
        webview.connect("notify::is-loading", self._atualizar_carregando)
        self.show_all()

    def _atualizar_titulo(self, *_):
        titulo = self.webview.get_title() or "Carregando…"
        self.titulo.set_text(titulo)
        self.rotulo.set_tooltip_text(titulo)
        self.janela.atualizar_barra(self)

    def _atualizar_icone(self, *_):
        superficie = self.webview.get_favicon()
        if superficie is None:
            self.icone.set_from_icon_name("text-html-symbolic", Gtk.IconSize.MENU)
            return
        imagem = Gdk.pixbuf_get_from_surface(superficie, 0, 0, superficie.get_width(),
                                             superficie.get_height())
        if imagem:
            self.icone.set_from_pixbuf(
                imagem.scale_simple(16, 16, GdkPixbuf.InterpType.BILINEAR))

    def _atualizar_carregando(self, *_):
        carregando = self.webview.is_loading()
        self.girando.set_visible(carregando)
        self.icone.set_visible(not carregando)
        (self.girando.start if carregando else self.girando.stop)()
        self.janela.atualizar_barra(self)


# --------------------------------------------------------------------------
#  A janela
# --------------------------------------------------------------------------

class Janela(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=NOME_APP)
        self.app = app
        self.filtro = Filtro(self)
        _classe(self, "navegador")
        self.set_default_size(1280, 840)
        self.set_icon_from_file(str(caminhos.PASTA_RECURSOS / "icone.svg"))

        self._montar_barra_superior()

        self.abas = _classe(Gtk.Notebook(scrollable=True, show_border=False), "abas")
        self.abas.connect_after("switch-page", lambda _nb, aba, _n: self.atualizar_barra(aba))
        nova = Gtk.Button.new_from_icon_name("list-add-symbolic", Gtk.IconSize.MENU)
        nova.set_tooltip_text("Nova aba (Ctrl+T)")
        nova.connect("clicked", lambda *_: self.nova_aba())
        nova.show()
        self.abas.set_action_widget(nova, Gtk.PackType.END)

        # Aviso flutuante ("toast") na parte de baixo da janela.
        self.toast = _classe(Gtk.Label(wrap=True, max_width_chars=64), "aviso-toast")
        self.toast_revelador = Gtk.Revealer(child=self.toast, halign=Gtk.Align.CENTER,
                                            valign=Gtk.Align.END,
                                            transition_type=Gtk.RevealerTransitionType.SLIDE_UP)
        self._toast_relogio = None
        sobreposicao = Gtk.Overlay()
        sobreposicao.add(self.abas)
        sobreposicao.add_overlay(self.toast_revelador)
        sobreposicao.set_overlay_pass_through(self.toast_revelador, True)
        self.add(sobreposicao)

        self._criar_acoes()
        self.connect("delete-event", self._ao_fechar)
        self.show_all()
        self.nova_aba()
        if not self.app.motor.regras_ativas:
            self.mostrar_aviso("Atenção: a proteção extra de bloqueio não pôde ser ativada. "
                               "Sites fora da lista continuam sem abrir.", segundos=12)

    def _ao_fechar(self, *_):
        """Botão de fechar: salva o tempo de estudo e deixa a janela fechar.

        Atenção: no GTK, devolver True aqui CANCELA o fechamento. Por isso o
        resultado de salvar() (True/False) não pode ser devolvido.
        """
        self.app.contador.salvar()
        return False

    # ---------------- barra superior ----------------

    def _botao(self, icone, dica, funcao):
        botao = Gtk.Button.new_from_icon_name(icone, Gtk.IconSize.BUTTON)
        botao.set_tooltip_text(dica)
        botao.connect("clicked", lambda *_: funcao())
        return botao

    def _montar_barra_superior(self):
        barra = _classe(Gtk.HeaderBar(show_close_button=True), "barra")
        self.set_titlebar(barra)

        self.b_voltar = self._botao("go-previous-symbolic", "Voltar (Alt+←)",
                                    lambda: self.view_atual().go_back())
        self.b_avancar = self._botao("go-next-symbolic", "Avançar (Alt+→)",
                                     lambda: self.view_atual().go_forward())
        self.b_recarregar = self._botao("view-refresh-symbolic", "Recarregar (F5)",
                                        self.recarregar_ou_parar)
        inicio = self._botao("go-home-symbolic", "Página inicial (Alt+Home)",
                             lambda: self.view_atual().load_uri(PAGINA_INICIAL))
        for botao in (self.b_voltar, self.b_avancar, self.b_recarregar, inicio):
            barra.pack_start(botao)

        self.endereco = _classe(Gtk.Entry(hexpand=True, width_chars=40, max_width_chars=90,
                                          placeholder_text="Digite um endereço ou pesquise na Wikipédia"),
                                "endereco")
        self.endereco.connect("activate", self._ao_digitar_endereco)
        barra.set_custom_title(self.endereco)

        # Lado direito: menu, "Hoje" e Pomodoro.
        menu = Gtk.MenuButton(image=Gtk.Image.new_from_icon_name(
            "open-menu-symbolic", Gtk.IconSize.BUTTON), tooltip_text="Menu")
        modelo = Gio.Menu()
        modelo.append("Área do responsável…", "win.gerenciar")
        modelo.append("Sobre o Navegador de Estudos", "win.sobre")
        menu.set_menu_model(modelo)
        barra.pack_end(menu)

        self.b_hoje = Gtk.MenuButton(tooltip_text="Tempo de estudo de hoje")
        self.b_hoje.add(Gtk.Image.new_from_icon_name("x-office-calendar-symbolic",
                                                     Gtk.IconSize.BUTTON))
        self.pop_hoje = Gtk.Popover()
        self.pop_hoje.connect("show", lambda *_: self._preencher_hoje())
        self.b_hoje.set_popover(self.pop_hoje)
        barra.pack_end(self.b_hoje)

        self.b_pomodoro = _classe(Gtk.MenuButton(tooltip_text="Timer Pomodoro"), "pomodoro-botao")
        self.b_pomodoro_rotulo = Gtk.Label()
        self.b_pomodoro.add(self.b_pomodoro_rotulo)
        self.b_pomodoro.set_popover(self._montar_popover_pomodoro())
        barra.pack_end(self.b_pomodoro)
        self.atualizar_pomodoro()

        # Relógio: hora atual, com a data por extenso ao passar o mouse.
        self.relogio = _classe(Gtk.Label(), "relogio")
        barra.pack_end(self.relogio)
        self._atualizar_relogio()
        GLib.timeout_add_seconds(1, self._atualizar_relogio)

    def _atualizar_relogio(self):
        hora, data = texto_do_relogio(datetime.datetime.now())
        if self.relogio.get_text() != hora:      # só redesenha quando o minuto muda
            self.relogio.set_text(hora)
            self.relogio.set_tooltip_text(data)
        return True                               # o GLib continua chamando

    def _montar_popover_pomodoro(self):
        pop = Gtk.Popover()
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        _margens(caixa, 20)
        self.p_fase = _classe(Gtk.Label(), "pomodoro-fase")
        self.p_tempo = _classe(Gtk.Label(), "pomodoro-tempo")
        self.p_ciclos = _classe(Gtk.Label(), "dim-label")
        botoes = Gtk.Box(spacing=8, homogeneous=True, margin_top=8)
        self.p_iniciar = _classe(Gtk.Button(), "suggested-action")
        self.p_iniciar.connect("clicked", lambda *_: self.app.pomodoro.iniciar_ou_pausar())
        zerar = Gtk.Button(label="Zerar")
        zerar.connect("clicked", lambda *_: self.app.pomodoro.zerar())
        botoes.add(self.p_iniciar)
        botoes.add(zerar)
        explica = _classe(Gtk.Label(label="25 min de foco e 5 min de pausa.\n"
                                          "A cada 4 ciclos, uma pausa de 15 min.",
                                    justify=Gtk.Justification.CENTER, margin_top=6), "dim-label")
        for widget in (self.p_fase, self.p_tempo, self.p_ciclos, botoes, explica):
            caixa.add(widget)
        caixa.show_all()
        pop.add(caixa)
        return pop

    def atualizar_pomodoro(self):
        p = self.app.pomodoro
        estilo = self.b_pomodoro.get_style_context()
        for classe in ("estudo", "pausa"):
            estilo.remove_class(classe)
        if p.rodando:
            estilo.add_class("estudo" if p.fase == pomodoro.ESTUDO else "pausa")
        self.b_pomodoro_rotulo.set_text(f"🍅 {p.texto()}")
        self.p_fase.set_text(pomodoro.NOME_FASE[p.fase])
        self.p_tempo.set_text(p.texto())
        self.p_ciclos.set_text(f"Ciclos concluídos: {p.ciclos_feitos}")
        self.p_iniciar.set_label("Pausar" if p.rodando else "Iniciar")

    def _preencher_hoje(self):
        filho = self.pop_hoje.get_child()
        if filho:
            filho.destroy()
        contador = self.app.contador
        grade = Gtk.Grid(column_spacing=24, row_spacing=6)
        _margens(grade, 18)
        grade.attach(_classe(Gtk.Label(label="Estudo de hoje", xalign=0), "pomodoro-fase"), 0, 0, 2, 1)
        grade.attach(_classe(Gtk.Label(label=formatar(contador.total()), xalign=0), "hoje-total"),
                     0, 1, 2, 1)
        linha = 2
        for site, segundos in contador.ranking(self.app.lista.nome_para_estatistica):
            grade.attach(Gtk.Label(label=site, xalign=0), 0, linha, 1, 1)
            grade.attach(_classe(Gtk.Label(label=formatar(segundos), xalign=1), "dim-label"),
                         1, linha, 1, 1)
            linha += 1
        if linha == 2:
            grade.attach(_classe(Gtk.Label(label="Nada registrado ainda hoje.", xalign=0),
                                 "dim-label"), 0, 2, 2, 1)
        grade.show_all()
        self.pop_hoje.add(grade)

    # ---------------- atalhos de teclado e menu ----------------

    def _criar_acoes(self):
        acoes = {
            "nova-aba": (["<Control>t"], lambda: self.nova_aba()),
            "fechar-aba": (["<Control>w"], lambda: self.fechar_aba(self.aba_atual())),
            "endereco": (["<Control>l", "F6"], self._focar_endereco),
            "recarregar": (["F5", "<Control>r"], lambda: self.view_atual().reload()),
            "voltar": (["<Alt>Left"], lambda: self.view_atual().go_back()),
            "avancar": (["<Alt>Right"], lambda: self.view_atual().go_forward()),
            "inicio": (["<Alt>Home"], lambda: self.view_atual().load_uri(PAGINA_INICIAL)),
            "zoom-mais": (["<Control>plus", "<Control>equal"], lambda: self._zoom(0.1)),
            "zoom-menos": (["<Control>minus"], lambda: self._zoom(-0.1)),
            "zoom-normal": (["<Control>0"], lambda: self._zoom(None)),
            "gerenciar": ([], self.area_do_responsavel),
            "sobre": ([], self._sobre),
        }
        for nome, (teclas, funcao) in acoes.items():
            acao = Gio.SimpleAction.new(nome, None)
            acao.connect("activate", lambda _a, _p, f=funcao: f())
            self.add_action(acao)
            if teclas:
                self.app.set_accels_for_action(f"win.{nome}", teclas)

    def _focar_endereco(self):
        self.endereco.grab_focus()
        self.endereco.select_region(0, -1)

    def _zoom(self, passo):
        view = self.view_atual()
        view.set_zoom_level(1.0 if passo is None else
                            min(3.0, max(0.3, view.get_zoom_level() + passo)))

    def _sobre(self):
        logo = GdkPixbuf.Pixbuf.new_from_file_at_size(
            str(caminhos.PASTA_RECURSOS / "icone.svg"), 96, 96)
        dialogo = Gtk.AboutDialog(transient_for=self, modal=True, program_name=NOME_APP,
                                  version=VERSAO, logo=logo,
                                  comments="Um navegador que abre apenas sites de estudo.")
        dialogo.run()
        dialogo.destroy()

    def area_do_responsavel(self):
        if caminhos.MODO_PROTEGIDO:
            # Sem senha do navegador: quem salva precisa da senha de administrador.
            resultado = dialogos.editar_sites(self, preferencias.carregar(),
                                              salvar_protegido=protegido.salvar_via_pkexec)
        else:
            entrada = dialogos.pedir_senha(self)
            if entrada is None:
                return
            resultado = dialogos.editar_sites(self, preferencias.carregar(), entrada.senha_curta)
        if resultado:
            nova_lista, novas_preferencias = resultado
            self.app.trocar_lista(nova_lista)
            if not caminhos.MODO_PROTEGIDO:      # no protegido, o auxiliar já gravou
                preferencias.salvar(novas_preferencias)
            self.app.preferencias = novas_preferencias
            self.mostrar_aviso("Configurações salvas ✔")
            for aba in self.abas.get_children():
                if (aba.webview.get_uri() or "").startswith(PAGINA_INICIAL):
                    aba.webview.reload()

    # ---------------- abas ----------------

    def aba_atual(self):
        return self.abas.get_nth_page(self.abas.get_current_page())

    def view_atual(self):
        return self.aba_atual().webview

    def nova_aba(self, url=PAGINA_INICIAL, webview=None):
        webview = webview or self.app.criar_webview()
        self.filtro.proteger(webview)
        webview.connect("create", self._ao_pedir_janela_nova)
        webview.connect("notify::uri", lambda v, _p: self.atualizar_barra(v.get_parent()))
        webview.connect("load-changed", lambda v, _e: self.atualizar_barra(v.get_parent()))
        webview.connect("close", lambda v: self.fechar_aba(v.get_parent()))
        aba = Aba(self, webview)
        indice = self.abas.append_page(aba, aba.rotulo)
        self.abas.set_tab_reorderable(aba, True)
        self.abas.set_current_page(indice)
        if url:
            self.filtro.abrir(webview, url)
        return aba

    def fechar_aba(self, aba):
        if aba is None:
            return
        if self.abas.get_n_pages() == 1:
            # Fechar a última aba volta para a página inicial em vez de sumir.
            aba.webview.load_uri(PAGINA_INICIAL)
            return
        self.abas.remove_page(self.abas.page_num(aba))
        aba.destroy()

    def _ao_pedir_janela_nova(self, webview, _acao):
        # Uma página pediu janela nova (link com target="_blank", janela de login
        # do Google...). Criamos uma aba "parente" que divide a mesma sessão.
        nova = self.app.criar_webview(relacionada=webview)
        self.nova_aba(url=None, webview=nova)
        return nova

    def _ao_digitar_endereco(self, entrada):
        texto = entrada.get_text().strip()
        if not texto:
            return
        parece_endereco = (" " not in texto and "." in texto) or "://" in texto
        if parece_endereco:
            url = texto if "://" in texto else "https://" + texto
        else:
            # Texto comum vira pesquisa na Wikipédia (único buscador liberado).
            url = "https://pt.wikipedia.org/w/index.php?search=" + GLib.uri_escape_string(
                texto, None, False)
        self.filtro.abrir(self.view_atual(), url)
        self.view_atual().grab_focus()

    def atualizar_barra(self, aba):
        """Atualiza endereço, botões e título quando a aba atual muda."""
        if aba is None or aba is not self.aba_atual():
            return
        view = aba.webview
        uri = view.get_uri() or ""
        if not self.endereco.has_focus():
            self.endereco.set_text("" if uri.startswith(PAGINA_INICIAL) else uri)
        if uri.startswith("estudos:"):
            icone, dica = "go-home-symbolic", "Página inicial"
        elif not self.app.lista.permite(uri):
            icone, dica = "action-unavailable-symbolic", "Site bloqueado"
        else:
            icone, dica = "channel-secure-symbolic", "Site permitido · conexão segura"
        self.endereco.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, icone)
        self.endereco.set_icon_tooltip_text(Gtk.EntryIconPosition.PRIMARY, dica)
        self.b_voltar.set_sensitive(view.can_go_back())
        self.b_avancar.set_sensitive(view.can_go_forward())
        self.b_recarregar.get_image().set_from_icon_name(
            "process-stop-symbolic" if view.is_loading() else "view-refresh-symbolic",
            Gtk.IconSize.BUTTON)
        titulo = view.get_title()
        self.set_title(f"{titulo} — {NOME_APP}" if titulo else NOME_APP)

    def recarregar_ou_parar(self):
        view = self.view_atual()
        view.stop_loading() if view.is_loading() else view.reload()

    def mostrar_aviso(self, texto, segundos=4):
        self.toast.set_text(texto)
        self.toast_revelador.set_reveal_child(True)
        if self._toast_relogio:
            GLib.source_remove(self._toast_relogio)

        def esconder():
            self.toast_revelador.set_reveal_child(False)
            self._toast_relogio = None
            return False
        self._toast_relogio = GLib.timeout_add_seconds(segundos, esconder)
