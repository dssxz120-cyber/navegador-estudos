#!/usr/bin/env python3
"""Ponto de partida do Navegador de Estudos.

Para abrir:  python3 navegador_estudos.py
"""

import sys
from pathlib import Path

# Acha o próprio código mesmo em "python3 -I" (modo isolado, usado na conta do
# aluno para que variáveis como PYTHONPATH não consigam injetar código).
sys.path.insert(0, str(Path(__file__).resolve().parent))

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("WebKit2", "4.1")

from gi.repository import GLib  # noqa: E402

# Nome com que a janela se apresenta ao sistema (WM_CLASS no X11, app_id no
# Wayland). Precisa ser igual ao nome do atalho (br.estudos.Navegador.desktop):
# é assim que o GNOME acha o ícone e o nome certos para a barra lateral.
GLib.set_prgname("br.estudos.Navegador")
GLib.set_application_name("Navegador de Estudos")

from estudos.interface.aplicativo import Aplicativo  # noqa: E402
from estudos.nucleo import caminhos  # noqa: E402
from estudos.nucleo.regras import ListaDeSites  # noqa: E402
from estudos.nucleo.tempo import ContadorDeTempo  # noqa: E402


def main():
    caminhos.criar_pastas()
    lista = ListaDeSites.carregar()
    for erro in lista.erros:
        print("Aviso na lista de sites:", erro, file=sys.stderr)
    app = Aplicativo(lista, ContadorDeTempo())
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
