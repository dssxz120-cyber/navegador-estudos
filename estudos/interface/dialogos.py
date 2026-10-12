"""Janelas de diálogo: criar senha, pedir senha e editar a lista de sites."""

from dataclasses import dataclass

from gi.repository import GLib, Gtk, Pango

from ..nucleo import caminhos, senha, tentativas
from ..nucleo.regras import ListaDeSites

def _campo_senha(texto_dica):
    campo = Gtk.Entry(visibility=False, input_purpose=Gtk.InputPurpose.PASSWORD,
                      placeholder_text=texto_dica, activates_default=True)
    return campo


def _dialogo_base(pai, titulo, texto_botao):
    dialogo = Gtk.Dialog(title=titulo, transient_for=pai, modal=True,
                         use_header_bar=True)
    dialogo.add_button("Cancelar", Gtk.ResponseType.CANCEL)
    botao = dialogo.add_button(texto_botao, Gtk.ResponseType.OK)
    botao.get_style_context().add_class("suggested-action")
    dialogo.set_default_response(Gtk.ResponseType.OK)
    caixa = dialogo.get_content_area()
    caixa.set_spacing(10)
    for lado in ("top", "bottom", "start", "end"):
        getattr(caixa, f"set_margin_{lado}")(20)
    return dialogo, caixa


def _rotulo(texto, classe=None):
    rotulo = Gtk.Label(label=texto, xalign=0, wrap=True, max_width_chars=48)
    rotulo.set_use_markup(True)
    if classe:
        rotulo.get_style_context().add_class(classe)
    return rotulo


def _perguntar_nova_senha(pai, titulo, explicacao, texto_botao):
    """Pede uma senha nova duas vezes e devolve o texto (ou None se cancelou).

    Não grava nada: quem chamou decide quando aplicar.
    """
    dialogo, caixa = _dialogo_base(pai, titulo, texto_botao)
    caixa.add(_rotulo(explicacao))
    campo1 = _campo_senha(f"Nova senha (mínimo de {senha.TAMANHO_MINIMO} caracteres)")
    campo2 = _campo_senha("Repita a senha")
    aviso = _rotulo("", "erro")
    for widget in (campo1, campo2, aviso):
        caixa.add(widget)
    dialogo.show_all()
    try:
        while dialogo.run() == Gtk.ResponseType.OK:
            problema = senha.problema_na_nova_senha(campo1.get_text(), campo2.get_text())
            if problema:
                aviso.set_text(problema)
            else:
                return campo1.get_text()
        return None
    finally:
        dialogo.destroy()


def criar_senha(pai):
    """Primeira execução: cria a senha. Devolve True se uma senha foi gravada."""
    nova = _perguntar_nova_senha(
        pai, "Crie a senha do responsável",
        "<b>Esta senha protege a lista de sites permitidos.</b>\n"
        "Só quem souber a senha poderá liberar ou remover sites. "
        "Guarde-a bem: o aluno não deve conhecê-la.", "Salvar senha")
    if nova is None:
        return False
    senha.definir(nova)
    return True


def _mensagem(pai, titulo, texto):
    dialogo = Gtk.MessageDialog(transient_for=pai, modal=True, message_type=Gtk.MessageType.WARNING,
                                buttons=Gtk.ButtonsType.OK, text=titulo)
    dialogo.format_secondary_markup(texto)
    dialogo.run()
    dialogo.destroy()


@dataclass
class Entrada:
    """Resultado de pedir_senha quando a senha confere."""
    senha_curta: bool     # senha antiga, criada antes do mínimo de 8 caracteres


def pedir_senha(pai):
    """Pede a senha atual. Devolve Entrada se estiver correta, ou None.

    Depois de 3 erros, cada erro impõe uma espera crescente (veja
    nucleo/tentativas.py). A janela continua respondendo durante a espera.
    """
    if senha.estado() == senha.DANIFICADA:
        _mensagem(pai, "O arquivo da senha está danificado",
                  "Não foi possível ler a senha do responsável e não há cópia de segurança "
                  "válida. Por segurança, ela <b>não</b> pode ser redefinida por aqui.\n\n"
                  "Veja “Recuperar a senha” no manual (docs/MANUAL.md).")
        return None

    dialogo, caixa = _dialogo_base(pai, "Área do responsável", "Entrar")
    caixa.add(_rotulo("Digite a senha do responsável para alterar a lista de sites."))
    campo = _campo_senha("Senha")
    aviso = _rotulo("", "erro")
    caixa.add(campo)
    caixa.add(aviso)
    relogio = {"id": None}

    def atualizar_espera():
        restante = int(tentativas.espera_restante() + 0.999)
        bloqueado = restante > 0
        campo.set_sensitive(not bloqueado)
        dialogo.set_response_sensitive(Gtk.ResponseType.OK, not bloqueado)
        if bloqueado:
            minutos, segundos = divmod(restante, 60)
            aviso.set_text(f"Muitas tentativas erradas. Aguarde {minutos}:{segundos:02d} "
                           "para tentar de novo.")
            return True       # continua contando a cada segundo
        if aviso.get_text().startswith("Muitas tentativas"):
            aviso.set_text("Pode tentar de novo.")
        campo.grab_focus()
        relogio["id"] = None
        return False

    def comecar_contagem():
        if relogio["id"] is None and atualizar_espera():
            relogio["id"] = GLib.timeout_add_seconds(1, atualizar_espera)

    dialogo.show_all()
    comecar_contagem()
    try:
        while dialogo.run() == Gtk.ResponseType.OK:
            if tentativas.espera_restante() > 0:
                continue          # Enter durante a espera: ignorado
            digitada = campo.get_text()
            campo.set_text("")
            if senha.confere(digitada):
                tentativas.registrar_acerto()
                return Entrada(senha_curta=len(digitada) < senha.TAMANHO_MINIMO)
            tentativas.registrar_falha()
            aviso.set_text("Senha incorreta. Tente novamente.")
            comecar_contagem()
        return None
    finally:
        if relogio["id"] is not None:
            GLib.source_remove(relogio["id"])
        dialogo.destroy()


def editar_sites(pai, preferencias, senha_curta=False, salvar_protegido=None):
    """Área do responsável: lista de sites, meta diária e troca de senha.

    Tudo só vale ao clicar em Salvar; Cancelar descarta inclusive a senha nova.
    Devolve (nova ListaDeSites, novas preferências), ou None se cancelou.

    salvar_protegido: no MODO PROTEGIDO, função(texto, preferências) que pede a
    senha de administrador e grava (devolve None ou uma mensagem de erro).
    Nesse modo não existe senha do navegador, então "Trocar senha" some.
    """
    dialogo, caixa = _dialogo_base(pai, "Área do responsável", "Salvar")
    dialogo.set_default_size(720, 620)
    dialogo.set_default_response(Gtk.ResponseType.NONE)   # Enter = nova linha
    caixa.add(_rotulo(
        "Cada linha <tt>Nome | https://endereço</tt> cria um atalho e libera o site. "
        "Linhas <tt>+ dominio.com</tt> só liberam o domínio e "
        "<tt>- sub.dominio.com</tt> barram um subdomínio. "
        "<tt>~ dominio.com</tt> não conta como estudo (ex.: música). "
        "<tt>[Categoria]</tt> agrupa atalhos e <tt>#</tt> marca comentários."))

    texto = Gtk.TextView(monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR,
                         top_margin=10, bottom_margin=10, left_margin=12, right_margin=12)
    texto.get_buffer().set_text(caminhos.ARQUIVO_SITES.read_text(encoding="utf-8"))
    rolagem = Gtk.ScrolledWindow(vexpand=True, shadow_type=Gtk.ShadowType.IN)
    rolagem.add(texto)
    caixa.add(rolagem)

    aviso = _rotulo("", "erro")
    aviso.set_ellipsize(Pango.EllipsizeMode.END)
    caixa.add(aviso)

    meta = Gtk.SpinButton.new_with_range(10, 600, 10)
    meta.set_value(preferencias.get("meta_minutos", 60))
    linha_meta = Gtk.Box(spacing=10)
    linha_meta.pack_start(Gtk.Label(label="Meta diária de estudo (minutos):"), False, False, 0)
    linha_meta.pack_start(meta, False, False, 0)
    parado = Gtk.SpinButton.new_with_range(1, 60, 1)
    parado.set_value(preferencias.get("inatividade_minutos", 5))
    linha_meta.pack_start(Gtk.Label(label="   Parar de contar após (min sem uso):"), False, False, 0)
    linha_meta.pack_start(parado, False, False, 0)
    caixa.add(linha_meta)

    pendente = {"senha": None}
    situacao_senha = _rotulo("")
    if salvar_protegido is not None:
        situacao_senha.set_markup("🔒 <b>Modo protegido:</b> ao salvar, será pedida a "
                                  "<b>senha de administrador</b> do Ubuntu.")
    elif senha_curta:
        situacao_senha.set_markup(
            f"<b>Recomendado:</b> a senha atual tem menos de {senha.TAMANHO_MINIMO} "
            "caracteres. Use “Trocar senha…” para uma mais forte.")
    caixa.add(situacao_senha)

    def trocar_senha(*_):
        nova = _perguntar_nova_senha(dialogo, "Trocar senha",
                                     "Digite a nova senha do responsável. "
                                     "Ela só passa a valer quando você clicar em <b>Salvar</b>.",
                                     "Usar esta senha")
        if nova is not None:
            pendente["senha"] = nova
            situacao_senha.set_markup("✔ Senha nova pronta. Ela será aplicada ao clicar em "
                                      "<b>Salvar</b> (Cancelar mantém a senha atual).")

    extras = Gtk.Box(spacing=8)
    trocar = Gtk.Button(label="Trocar senha…")
    trocar.connect("clicked", trocar_senha)
    restaurar = Gtk.Button(label="Restaurar lista padrão")
    restaurar.connect("clicked", lambda *_: texto.get_buffer().set_text(
        (caminhos.PASTA_RECURSOS / "sites_padrao.txt").read_text(encoding="utf-8")))
    if salvar_protegido is None:
        extras.pack_start(trocar, False, False, 0)
    extras.pack_start(restaurar, False, False, 0)
    caixa.add(extras)

    dialogo.show_all()
    try:
        while dialogo.run() == Gtk.ResponseType.OK:
            buffer = texto.get_buffer()
            conteudo = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
            nova = ListaDeSites.de_texto(conteudo)
            if nova.erros:
                aviso.set_text("Corrija antes de salvar — " + "; ".join(nova.erros[:3]))
                continue
            if not nova.dominios:
                aviso.set_text("A lista precisa ter pelo menos um site.")
                continue
            novas_preferencias = {**preferencias, "meta_minutos": int(meta.get_value()),
                                  "inatividade_minutos": int(parado.get_value())}
            if salvar_protegido is not None:
                problema = salvar_protegido(conteudo, novas_preferencias)
                if problema:
                    aviso.set_text(problema)
                    continue
                return nova, novas_preferencias
            if pendente["senha"] is not None:
                try:
                    senha.definir(pendente["senha"])
                except OSError as erro:
                    aviso.set_text(f"Não foi possível trocar a senha ({erro.strerror}). "
                                   "Nada foi alterado.")
                    continue
                pendente["senha"] = None
                situacao_senha.set_markup("✔ Senha trocada.")
            try:
                ListaDeSites.salvar_texto(conteudo)
            except OSError as erro:
                aviso.set_text(f"Não foi possível salvar a lista ({erro.strerror}). "
                               "A lista anterior continua valendo.")
                continue
            return nova, novas_preferencias
        return None
    finally:
        dialogo.destroy()
