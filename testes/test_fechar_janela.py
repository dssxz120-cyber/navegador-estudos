"""O navegador fecha quando o usuário clica em fechar a janela?

Defeito real da v2.1.2: o fechamento devolvia o resultado de salvar() (True)
e o GTK entende True como "não feche". Este teste abre o navegador DE VERDADE
(numa pasta de dados temporária), pede para fechar a janela como o botão X
faz, e confere que o programa termina e o tempo de estudo foi salvo.
"""

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apoio_webkit import tela_disponivel  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent

SCRIPT = textwrap.dedent("""
    import sys
    sys.path.insert(0, {raiz!r})
    import gi
    gi.require_version("Gtk", "3.0"); gi.require_version("Gdk", "3.0"); gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib
    from estudos.nucleo import caminhos, senha
    from estudos.nucleo.regras import ListaDeSites
    from estudos.nucleo.tempo import ContadorDeTempo
    from estudos.interface.aplicativo import Aplicativo
    caminhos.criar_pastas()
    senha.definir("senha-de-teste-1")
    app = Aplicativo(ListaDeSites.carregar(), ContadorDeTempo(), unico=False)

    def fechar():
        app.contador.somar("Teste", 7)
        app.janela.close()          # o mesmo que clicar no X da janela
        return False

    app.connect("activate", lambda *_: GLib.timeout_add(1500, fechar))
    GLib.timeout_add_seconds(20, lambda: (print("NAO_FECHOU", flush=True), app.quit()))
    app.run([])
    print("FECHOU", flush=True)
""")


class TestFecharJanela(unittest.TestCase):
    def test_clicar_em_fechar_encerra_o_programa(self):
        if not tela_disponivel():
            self.skipTest("sem tela disponível")
        with tempfile.TemporaryDirectory() as pasta:
            ambiente = dict(os.environ, XDG_CONFIG_HOME=f"{pasta}/c", XDG_DATA_HOME=f"{pasta}/d",
                            XDG_CACHE_HOME=f"{pasta}/k", PYTHONDONTWRITEBYTECODE="1")
            saida = subprocess.run([sys.executable, "-c", SCRIPT.format(raiz=str(RAIZ))],
                                   env=ambiente, capture_output=True, text=True, timeout=60).stdout
            self.assertIn("FECHOU", saida)
            self.assertNotIn("NAO_FECHOU", saida, "a janela recusou fechar")
            dias = list(Path(pasta, "d", "navegador-estudos", "tempo").glob("*.json"))
            self.assertEqual(len(dias), 1)
            self.assertIn('"Teste": 7', dias[0].read_text())     # salvou ao fechar


if __name__ == "__main__":
    unittest.main()
