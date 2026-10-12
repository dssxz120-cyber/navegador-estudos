"""Testes da segurança do responsável: senha nova, tentativas e recuperação.

Pastas temporárias e senhas fictícias: a senha real nunca é tocada.
"""

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from estudos.nucleo import caminhos, senha, tentativas  # noqa: E402
from estudos.nucleo.arquivos import listar_copias  # noqa: E402


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self._tmp.name)
        self.remendos = [mock.patch.object(caminhos, "PASTA_CONFIG", self.pasta),
                         mock.patch.object(caminhos, "ARQUIVO_SENHA", self.pasta / "senha.json"),
                         mock.patch("sys.stderr")]
        for remendo in self.remendos:
            remendo.start()

    def tearDown(self):
        for remendo in self.remendos:
            remendo.stop()
        self._tmp.cleanup()


class TestNovaSenha(unittest.TestCase):
    def test_regras(self):
        self.assertIsNone(senha.problema_na_nova_senha("girassol-azul", "girassol-azul"))
        self.assertIsNone(senha.problema_na_nova_senha("abc12345", "abc12345"))
        casos = {("abc123", "abc123"): "pelo menos 8",
                 ("aaaaaaaa", "aaaaaaaa"): "repetitiva",
                 ("abababab", "abababab"): "repetitiva",
                 (" abc12345", " abc12345"): "espaço",
                 ("abc12345", "abc12346"): "não são iguais"}
        for (nova, repetida), trecho in casos.items():
            self.assertIn(trecho, senha.problema_na_nova_senha(nova, repetida), nova)


class TestSenhaExistente(_Base):
    def test_senha_antiga_de_4_caracteres_continua_valendo(self):
        senha.definir("1234")          # como as senhas criadas antes desta versão
        self.assertTrue(senha.confere("1234"))
        self.assertFalse(senha.confere("12345"))
        self.assertEqual(senha.estado(), senha.OK)

    def test_estados(self):
        self.assertEqual(senha.estado(), senha.SEM_SENHA)
        senha.definir("girassol-azul")
        self.assertEqual(senha.estado(), senha.OK)


class TestRecuperacaoDaSenha(_Base):
    def test_arquivo_danificado_recupera_a_senha_ATUAL(self):
        senha.definir("senha-antiga-1")
        senha.definir("senha-atual-22")
        caminhos.ARQUIVO_SENHA.write_text('{"sal": "ab", "hash"')       # danificado
        self.assertTrue(senha.confere("senha-atual-22"))
        self.assertFalse(senha.confere("senha-antiga-1"))
        self.assertEqual(senha.estado(), senha.OK)
        self.assertTrue(list(self.pasta.glob("senha.json.corrompido-*")))

    def test_danificado_sem_copia_nao_permite_redefinir(self):
        caminhos.ARQUIVO_SENHA.write_text("lixo")
        self.assertEqual(senha.estado(), senha.DANIFICADA)
        self.assertTrue(senha.existe())          # o programa NÃO pede para criar outra
        self.assertFalse(senha.confere("qualquer"))
        self.assertEqual(caminhos.ARQUIVO_SENHA.read_text(), "lixo")      # nada foi movido
        self.assertEqual(list(self.pasta.glob("senha.json.*")), [])

    def test_copias_validas_e_sem_senha_em_texto(self):
        senha.definir("primeira-senha-1")
        senha.definir("segunda-senha-2")
        for arquivo in [caminhos.ARQUIVO_SENHA, *listar_copias(caminhos.ARQUIVO_SENHA)]:
            conteudo = arquivo.read_text()
            self.assertNotIn("primeira", conteudo)
            self.assertNotIn("segunda", conteudo)
            self.assertEqual(set(json.loads(conteudo)), {"sal", "hash", "rodadas"})


class TestTentativas(_Base):
    def test_tres_livres_e_depois_espera_que_dobra(self):
        agora = 1_000_000.0
        esperas = [tentativas.registrar_falha(agora) for _ in range(10)]
        self.assertEqual(esperas, [0, 0, 0, 30, 60, 120, 240, 480, 900, 900])
        self.assertEqual(tentativas.espera_restante(agora), 900)
        self.assertEqual(tentativas.espera_restante(agora + 899), 1)
        self.assertEqual(tentativas.espera_restante(agora + 901), 0)

    def test_espera_sobrevive_a_reabrir_o_programa(self):
        agora = time.time()
        for _ in range(4):
            tentativas.registrar_falha(agora)
        # "Reabrir" = ler de novo do disco.
        dados = json.loads((self.pasta / "tentativas.json").read_text())
        self.assertEqual(dados["falhas"], 4)
        self.assertGreater(tentativas.espera_restante(), 25)

    def test_acerto_zera(self):
        for _ in range(5):
            tentativas.registrar_falha()
        tentativas.registrar_acerto()
        self.assertEqual(tentativas.espera_restante(), 0)
        self.assertEqual(tentativas.registrar_falha(), 0)

    def test_valores_absurdos_sao_limitados(self):
        (self.pasta / "tentativas.json").write_text(
            json.dumps({"falhas": 10**9, "liberado_em": time.time() + 10**9}))
        self.assertLessEqual(tentativas.espera_restante(), tentativas.ESPERA_MAXIMA)
        inicio = time.monotonic()
        self.assertEqual(tentativas.registrar_falha(), tentativas.ESPERA_MAXIMA)
        self.assertLess(time.monotonic() - inicio, 1)       # sem conta gigantesca

    def test_arquivo_corrompido_nao_trava(self):
        (self.pasta / "tentativas.json").write_text("{lixo")
        self.assertEqual(tentativas.espera_restante(), 0)
        self.assertEqual(tentativas.registrar_falha(), 0)

    def test_permissao_do_arquivo(self):
        tentativas.registrar_falha()
        self.assertEqual((self.pasta / "tentativas.json").stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
