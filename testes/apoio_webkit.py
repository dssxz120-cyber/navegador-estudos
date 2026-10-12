"""Apoio para os testes que usam o WebKit de verdade.

- ServidorDeTeste: servidor HTTP local que ANOTA cada pedido recebido.
  Assim o teste prova que um site bloqueado não recebeu nada — não basta a
  página não aparecer.
- Os nomes *.localhost apontam para o próprio computador, então
  "permitido.localhost" e "bloqueado.localhost" são o mesmo servidor, e o
  servidor sabe qual nome foi pedido pelo cabeçalho Host.
- As abas ficam numa janela invisível (Gtk.OffscreenWindow): nada aparece na
  tela durante os testes.
"""

import socket
import socketserver
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

TITULO_BLOQUEIO = "Site bloqueado"


def tela_disponivel():
    """Os testes de navegação precisam de uma tela (X11/Wayland), mesmo invisível."""
    return Gdk.Display.get_default() is not None


def esperar(condicao, segundos):
    """Roda o laço de eventos do GTK até a condição ser verdadeira (ou acabar o tempo)."""
    limite = time.monotonic() + segundos
    contexto = GLib.MainContext.default()
    while time.monotonic() < limite:
        while contexto.pending():
            contexto.iteration(False)
        if condicao():
            return True
        time.sleep(0.02)
    return condicao()


def deixar_rodar(segundos):
    esperar(lambda: False, segundos)


class _Servidor(ThreadingHTTPServer):
    address_family = socket.AF_INET6   # *.localhost resolve para ::1 e 127.0.0.1
    daemon_threads = True

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        # Pula o getfqdn() do HTTPServer, que é lento com IPv6.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = "localhost", self.server_address[1]


class ServidorDeTeste:
    def __init__(self):
        self.pedidos = []          # [(host, método, caminho)]
        self._trava = threading.Lock()
        servidor = self

        class Atendente(BaseHTTPRequestHandler):
            def _registrar(self):
                host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
                with servidor._trava:
                    servidor.pedidos.append((host, self.command, self.path))
                return host

            def do_GET(self):
                self._responder(self._registrar())

            def do_POST(self):
                tamanho = int(self.headers.get("Content-Length") or 0)
                self.rfile.read(tamanho)
                self._responder(self._registrar())

            def _responder(self, _host):
                status, cabecalhos, corpo = servidor.pagina(self.path)
                self.send_response(status)
                for nome, valor in cabecalhos:
                    self.send_header(nome, valor)
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)

            def log_message(self, *_):
                pass

        self._http = _Servidor(("::", 0), Atendente)
        self.porta = self._http.server_address[1]
        threading.Thread(target=self._http.serve_forever, daemon=True).start()

    def url(self, host, caminho="/"):
        return f"http://{host}:{self.porta}{caminho}"

    def pedidos_para(self, host):
        with self._trava:
            return [p for p in self.pedidos if p[0] == host]

    def limpar(self):
        with self._trava:
            self.pedidos.clear()

    def parar(self):
        self._http.shutdown()
        self._http.server_close()

    # ---- páginas de teste ----

    def pagina(self, caminho):
        b = self.url("bloqueado.localhost")
        html = "text/html; charset=utf-8"
        paginas = {
            "/ok": "<title>OK</title><p>página permitida</p>",
            "/alvo": "<title>ALVO</title><script>try{parent.postMessage('vazou','*')}catch(e){}</script>",
            "/link": f"<title>link</title><a id=a href='{b}/alvo'>x</a>"
                     "<script>setTimeout(()=>a.click(),200)</script>",
            "/jsredir": f"<title>jsredir</title><script>location='{b}/alvo'</script>",
            "/meta": f"<title>meta</title><meta http-equiv=refresh content='0;url={b}/alvo'>",
            "/form-get": f"<title>form</title><form id=f action='{b}/alvo'></form>"
                         "<script>setTimeout(()=>f.submit(),200)</script>",
            "/form-post": f"<title>form</title><form id=f method=post action='{b}/alvo'>"
                          "<input name=x value=1></form><script>setTimeout(()=>f.submit(),200)</script>",
            "/iframe": f"<title>iframe</title><script>onmessage=()=>document.title='VAZOU'</script>"
                       f"<iframe src='{b}/alvo'></iframe>",
            "/iframe-permitido": f"<title>iframe-ok</title><script>onmessage=()=>document.title='IFRAME_CARREGOU'</script>"
                                 f"<iframe src='{self.url('sub.permitido.localhost', '/alvo')}'></iframe>",
            "/iframe-embutido": "<title>embutido</title>"
                                f"<iframe src='{self.url('embed.localhost', '/embed/video')}'></iframe>",
            "/popup": f"<title>popup</title><script>var w=window.open('{b}/alvo');"
                      "document.title=w?'POPUP_ABRIU':'popup_negado'</script>",
            "/blank": f"<title>blank</title><a id=a target=_blank href='{b}/alvo'>x</a>"
                      "<script>setTimeout(()=>a.click(),200)</script>",
            "/fetch-interno": "<title>fetch</title><script>fetch('estudos://inicio').then(r=>r.text())"
                              ".then(t=>document.title='LEU:'+t).catch(e=>document.title='fetch_negado')</script>",
            "/iframe-interno": "<title>iframe-interno</title><iframe id=f src='estudos://inicio'></iframe>"
                               "<script>setTimeout(()=>{try{document.title='LEU:'+f.contentDocument.body.innerText}"
                               "catch(e){document.title='iframe_negado'}},800)</script>",
        }
        if caminho == "/302":
            return 302, [("Location", f"{b}/alvo")], b""
        if caminho == "/302-cookie":
            return 302, [("Location", f"{b}/cookie")], b""
        if caminho == "/cookie":
            return 200, [("Content-Type", html), ("Set-Cookie", "rastreio=GRAVADO; Path=/; Max-Age=600")], \
                b"<title>ALVO</title>"
        corpo = paginas.get(caminho.split("?")[0], "<title>OK</title>")
        return 200, [("Content-Type", html)], corpo.encode("utf-8")


class JanelaFalsa:
    """Imita o pedaço da janela que o Filtro usa (abas, avisos, lista)."""

    def __init__(self, motor, lista):
        from estudos.interface.filtro import Filtro
        self.motor = motor
        self.app = type("App", (), {"lista": lista})()
        self.avisos = []
        self.abas = []
        # Endereços que o bloqueador de conteúdo do WebKit (camada 1) barrou.
        self.barrados_pelo_webkit = []
        self._janelas = []
        self.filtro = Filtro(self)

    def mostrar_aviso(self, texto, segundos=4):
        self.avisos.append(texto)

    def nova_aba(self, url="estudos://inicio", webview=None):
        webview = webview or self.motor.criar_webview()
        # Ligado ANTES do filtro: o filtro trata o "load-failed" e encerra o
        # sinal, então um espião ligado depois nunca veria o bloqueio.
        webview.connect("load-failed", self._anotar_falha)
        self.filtro.proteger(webview)
        webview.connect("create", lambda v, _a: self.nova_aba(None, self.motor.criar_webview(v)))
        janela = Gtk.OffscreenWindow()
        janela.add(webview)
        janela.show_all()
        self._janelas.append(janela)
        self.abas.append(webview)
        if url:
            self.filtro.abrir(webview, url)
        return webview

    def _anotar_falha(self, _webview, _evento, url, erro):
        from estudos.interface.filtro import ERRO_BLOQUEADOR_DE_CONTEUDO
        if erro.domain == "WebKitPolicyError" and erro.code == ERRO_BLOQUEADOR_DE_CONTEUDO:
            self.barrados_pelo_webkit.append(url)
        return False

    def fechar_tudo(self):
        for janela in self._janelas:
            janela.destroy()
        self._janelas.clear()
        self.abas.clear()


def servir_pagina_interna_de_teste(pedido):
    """Página interna falsa com um "segredo", para testar se sites conseguem lê-la."""
    dados = GLib.Bytes.new(b"<title>INTERNO</title><body>SEGREDO-DAS-ESTATISTICAS</body>")
    pedido.finish(Gio.MemoryInputStream.new_from_bytes(dados), dados.get_size(), "text/html")
