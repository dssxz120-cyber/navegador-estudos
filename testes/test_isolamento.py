"""Testes dos scripts de isolamento (sem root: só o que dá para provar sem sudo).

A aplicação de verdade das etapas é feita pelo responsável com sudo; aqui
conferimos sintaxe, a montagem da configuração inicial e o navegador em
modo isolado do Python (-I).
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apoio_webkit import tela_disponivel  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "scripts" / "isolamento"
PREPARAR = PASTA / "preparar_configuracao.py"


class TestScripts(unittest.TestCase):
    def test_sintaxe_de_todos_os_scripts(self):
        for script in sorted(PASTA.glob("*.sh")):
            r = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f"{script.name}: {r.stderr}")

    def test_scripts_exigem_root_fora_da_simulacao(self):
        if os.geteuid() == 0:
            self.skipTest("rodando como root")
        for script in ["etapa1-aplicar.sh", "etapa1-reverter.sh", "etapa2-aplicar.sh",
                       "etapa2-reverter.sh"]:
            r = subprocess.run(["bash", str(PASTA / script)], capture_output=True, text=True,
                               timeout=30)
            self.assertNotEqual(r.returncode, 0, script)
            self.assertIn("sudo", r.stderr, script)

    def test_verificacao_de_administrador_independe_do_idioma(self):
        self.assertIn('LC_ALL=C sudo -l -U "$ALUNO"', (PASTA / "etapa1-aplicar.sh").read_text())

    def test_atalho_do_sistema_usa_modo_isolado(self):
        self.assertIn("Exec=/usr/bin/python3 -I $DESTINO/navegador_estudos.py",
                      (PASTA / "etapa2-aplicar.sh").read_text())


class TestEtapa3(unittest.TestCase):
    SISTEMA = PASTA / "sistema"

    def test_banco_dconf_do_aluno_compila(self):
        with tempfile.TemporaryDirectory() as pasta:
            r = subprocess.run(["dconf", "compile", f"{pasta}/aluno", str(self.SISTEMA / "dconf-aluno.d")],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_toda_chave_alterada_esta_travada(self):
        chaves, secao = set(), None
        for linha in (self.SISTEMA / "dconf-aluno.d" / "00-navegador-estudos").read_text().splitlines():
            linha = linha.strip()
            if linha.startswith("["):
                secao = linha[1:-1]
            elif "=" in linha and not linha.startswith("#"):
                chaves.add(f"/{secao}/{linha.split('=')[0]}")
        travas = set((self.SISTEMA / "dconf-aluno.d" / "locks" / "00-navegador-estudos").read_text().split())
        self.assertEqual(chaves, travas)

    def test_gerador_nao_faz_nada_em_outras_contas(self):
        r = subprocess.run([str(self.SISTEMA / "99-navegador-estudos-ambiente")],
                           capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_gerador_para_o_aluno(self):
        with tempfile.TemporaryDirectory() as pasta:          # "id" falso que responde "aluno"
            Path(pasta, "id").write_text("#!/bin/sh\necho aluno\n")
            os.chmod(Path(pasta, "id"), 0o755)
            r = subprocess.run([str(self.SISTEMA / "99-navegador-estudos-ambiente")], capture_output=True,
                               text=True, env=dict(os.environ, PATH=f"{pasta}:/usr/bin:/bin"))
        linhas = r.stdout.splitlines()
        self.assertEqual(linhas[0], "DCONF_PROFILE=aluno")
        for variavel in ("LD_PRELOAD=", "PYTHONPATH=", "PYTHONSTARTUP="):
            self.assertIn(variavel, linhas)

    def test_python3_nunca_e_bloqueado(self):
        texto = (PASTA / "etapa3-aplicar.sh").read_text()
        bloco = texto[texto.index("BLOQUEAR=("):texto.index(")", texto.index("BLOQUEAR=("))]
        self.assertNotIn("python", bloco)
        self.assertIn("/usr/bin/snap", bloco)


class TestInstalador(unittest.TestCase):
    INSTALADOR = RAIZ / "instalar.sh"

    def test_sintaxe_e_executavel(self):
        self.assertEqual(subprocess.run(["bash", "-n", str(self.INSTALADOR)]).returncode, 0)
        self.assertTrue(os.access(self.INSTALADOR, os.X_OK))

    def test_simulacao_modo_simples(self):
        r = subprocess.run(["bash", str(self.INSTALADOR), "--simular", "--simples"],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("simulação", r.stdout)
        self.assertIn("Pronto", r.stdout)

    def test_opcao_desconhecida(self):
        r = subprocess.run(["bash", str(self.INSTALADOR), "--qualquer"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)

    def test_nao_usa_curl_pipe_bash(self):
        """O comando único baixa com git e roda o instalador local (revisável)."""
        leia = (RAIZ / "README.md").read_text()
        self.assertIn("git clone https://github.com/dssxz120-cyber/navegador-estudos.git", leia)
        self.assertIn("bash ~/navegador-estudos/instalar.sh", leia)
        self.assertNotRegex(leia, r"curl[^\n]*\|\s*(sudo\s+)?bash")


class TestPrepararConfiguracao(unittest.TestCase):
    def rodar(self, pasta, *extra):
        return subprocess.run([str(PREPARAR), str(pasta), *extra], capture_output=True,
                              text=True, timeout=30)

    def test_usa_a_lista_pessoal(self):
        with tempfile.TemporaryDirectory() as pasta:
            Path(pasta, "sites.txt").write_text("[X]\nWiki | https://pt.wikipedia.org/\n+ youtube.com\n")
            Path(pasta, "preferencias.json").write_text('{"meta_minutos": 90}')
            r = self.rodar(pasta)
            self.assertEqual(r.returncode, 0, r.stderr)
            pedido = json.loads(r.stdout)
            self.assertIn("+ youtube.com", pedido["sites"])
            self.assertEqual(pedido["preferencias"], {"meta_minutos": 90, "inatividade_minutos": 5})

    def test_sem_lista_pessoal_usa_a_padrao(self):
        with tempfile.TemporaryDirectory() as pasta:
            r = self.rodar(pasta, "--resumo")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("lista padrão", r.stdout)

    def test_lista_com_erros_impede_a_instalacao(self):
        with tempfile.TemporaryDirectory() as pasta:
            Path(pasta, "sites.txt").write_text("+ com.br\n")
            r = self.rodar(pasta)
            self.assertEqual(r.returncode, 1)
            self.assertEqual(r.stdout, "")

    def test_saida_e_aceita_pelo_auxiliar(self):
        with tempfile.TemporaryDirectory() as pasta:
            Path(pasta, "sites.txt").write_text("[X]\nWiki | https://pt.wikipedia.org/\n")
            pedido = self.rodar(pasta).stdout
            destino = Path(pasta, "etc")
            r = subprocess.run([str(RAIZ / "scripts" / "salvar-configuracao"), "--pasta", str(destino)],
                               input=pedido, capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((destino / "sites.txt").is_file())


class TestNavegadorEmModoIsolado(unittest.TestCase):
    def test_abre_com_python_menos_I(self):
        """O atalho do sistema roda "python3 -I navegador_estudos.py"."""
        if not tela_disponivel():
            self.skipTest("sem tela disponível")
        with tempfile.TemporaryDirectory() as pasta:
            ambiente = dict(os.environ, XDG_CONFIG_HOME=f"{pasta}/c", XDG_DATA_HOME=f"{pasta}/d",
                            XDG_CACHE_HOME=f"{pasta}/k")
            # Senha já criada, para não abrir o diálogo da primeira execução.
            subprocess.run([sys.executable, "-I", "-c",
                            f"import sys; sys.path.insert(0, {str(RAIZ)!r}); "
                            "from estudos.nucleo import caminhos, senha; "
                            "caminhos.criar_pastas(); senha.definir('senha-de-teste-1')"],
                           env=ambiente, check=True, timeout=30)
            processo = subprocess.Popen([sys.executable, "-I", str(RAIZ / "navegador_estudos.py")],
                                        env=ambiente, stderr=subprocess.PIPE, text=True)
            time.sleep(6)
            ainda_rodando = processo.poll() is None
            processo.terminate()
            erros = processo.communicate(timeout=10)[1]
            self.assertTrue(ainda_rodando, f"o navegador fechou sozinho: {erros[-500:]}")
            self.assertNotIn("Traceback", erros)
            self.assertNotIn("ModuleNotFoundError", erros)


if __name__ == "__main__":
    unittest.main()
