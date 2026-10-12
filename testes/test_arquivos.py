"""Testes da gravação segura e das cópias de segurança (nucleo/arquivos.py)
e de como os dados do navegador usam esse mecanismo.

Tudo roda em pastas temporárias com dados fictícios: nenhum dado real é tocado.

Atenção: estes testes SIMULAM falhas (exceções, processo morto). Eles não
provam resistência a um desligamento físico da máquina; para isso o código
usa fsync do arquivo e da pasta, que dependem do disco e do sistema.
"""

import errno
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from estudos.nucleo import arquivos, caminhos, preferencias, regras, senha, tempo  # noqa: E402
from estudos.nucleo.arquivos import (PoliticaDeCopias, copiar_versao_atual, gravar_atomico,  # noqa: E402
                                     gravar_com_copia, ler_com_recuperacao, listar_copias)

JSON_VALIDO = PoliticaDeCopias(validar=lambda d: isinstance(json.loads(d), dict))


def modo(caminho):
    return os.stat(caminho).st_mode & 0o777


class _PastaTemporaria(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self._tmp.name)
        self.arquivo = self.pasta / "dados.json"

    def tearDown(self):
        for raiz, pastas, _ in os.walk(self.pasta):       # devolve permissões
            for nome in pastas:
                os.chmod(os.path.join(raiz, nome), 0o700)
        os.chmod(self.pasta, 0o700)
        self._tmp.cleanup()

    def temporarios(self):
        return sorted(p.name for p in self.pasta.glob(".*.tmp"))


class TestGravacaoAtomica(_PastaTemporaria):
    # 1. gravação normal
    def test_gravacao_normal(self):
        gravar_atomico(self.arquivo, '{"a": 1}')
        self.assertEqual(self.arquivo.read_text(), '{"a": 1}')
        self.assertEqual(modo(self.arquivo), 0o600)
        self.assertEqual(self.temporarios(), [])

    def test_aceita_bytes_e_acentos(self):
        gravar_atomico(self.arquivo, "Wikipédia ✓".encode("utf-8"))
        self.assertEqual(self.arquivo.read_text(encoding="utf-8"), "Wikipédia ✓")

    # 4. destino inexistente
    def test_destino_inexistente_e_criado(self):
        novo = self.pasta / "novo.txt"
        self.assertFalse(novo.exists())
        gravar_atomico(novo, "x")
        self.assertEqual(novo.read_text(), "x")

    # 2. falha antes da substituição  /  7. preservação do anterior
    def test_falha_antes_da_troca_preserva_original(self):
        gravar_atomico(self.arquivo, "ORIGINAL")
        with mock.patch("estudos.nucleo.arquivos.os.replace", side_effect=OSError(errno.EIO, "falha")):
            with self.assertRaises(OSError):
                gravar_atomico(self.arquivo, "NOVO")
        self.assertEqual(self.arquivo.read_text(), "ORIGINAL")
        self.assertEqual(self.temporarios(), [])

    # 3. interrupção durante a gravação
    def test_interrupcao_durante_a_escrita(self):
        gravar_atomico(self.arquivo, "ORIGINAL")
        with mock.patch("estudos.nucleo.arquivos.os.fsync", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                gravar_atomico(self.arquivo, "NOVO" * 1000)
        self.assertEqual(self.arquivo.read_text(), "ORIGINAL")
        self.assertEqual(self.temporarios(), [])

    def test_processo_morto_no_meio_da_gravacao(self):
        """Mata DE VERDADE (SIGKILL) um processo que está gravando 200 MB."""
        gravar_atomico(self.arquivo, "ORIGINAL")
        script = textwrap.dedent(f"""
            import sys, time; sys.path.insert(0, {str(RAIZ)!r})
            from estudos.nucleo import arquivos
            original = arquivos.os.fsync
            def fsync_lento(fd):
                print("GRAVANDO", flush=True); time.sleep(30); original(fd)
            arquivos.os.fsync = fsync_lento
            arquivos.gravar_atomico({str(self.arquivo)!r}, b"N" * 200_000_000)
        """)
        processo = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, text=True)
        self.assertEqual(processo.stdout.readline().strip(), "GRAVANDO")
        processo.send_signal(signal.SIGKILL)
        processo.wait(10)
        processo.stdout.close()
        self.assertEqual(self.arquivo.read_text(), "ORIGINAL")
        # Um processo morto não consegue apagar o próprio temporário...
        sobras = list(self.pasta.glob(".dados.json.*.tmp"))
        self.assertEqual(len(sobras), 1)
        # ...então a próxima gravação limpa sobras antigas.
        antigo = time.time() - arquivos.TEMPORARIO_ABANDONADO - 60
        os.utime(sobras[0], (antigo, antigo))
        gravar_atomico(self.arquivo, "NOVO")
        self.assertEqual(self.arquivo.read_text(), "NOVO")
        self.assertEqual(self.temporarios(), [])

    # 5. falta de permissão
    def test_sem_permissao_na_pasta(self):
        if os.geteuid() == 0:
            self.skipTest("o usuário root ignora permissões")
        gravar_atomico(self.arquivo, "ORIGINAL")
        os.chmod(self.pasta, 0o500)
        with self.assertRaises(PermissionError):
            gravar_atomico(self.arquivo, "NOVO")
        os.chmod(self.pasta, 0o700)
        self.assertEqual(self.arquivo.read_text(), "ORIGINAL")
        self.assertEqual(self.temporarios(), [])

    # 6. disco cheio (simulado)
    def test_disco_cheio(self):
        gravar_atomico(self.arquivo, "ORIGINAL")
        cheio = OSError(errno.ENOSPC, "No space left on device")
        with mock.patch("estudos.nucleo.arquivos.os.fsync", side_effect=cheio):
            with self.assertRaises(OSError) as erro:
                gravar_atomico(self.arquivo, "NOVO")
        self.assertEqual(erro.exception.errno, errno.ENOSPC)
        self.assertEqual(self.arquivo.read_text(), "ORIGINAL")
        self.assertEqual(self.temporarios(), [])

    def test_temporario_recente_nao_e_apagado(self):
        recente = self.pasta / ".dados.json.abc.tmp"
        recente.write_text("em uso")
        gravar_atomico(self.arquivo, "x")
        self.assertTrue(recente.exists())


class TestCopias(_PastaTemporaria):
    # 8. integridade dos backups
    def test_copias_da_versao_nova_e_da_anterior(self):
        gravar_com_copia(self.arquivo, '{"v": 1}', JSON_VALIDO)
        self.assertEqual([c.read_text() for c in listar_copias(self.arquivo)], ['{"v": 1}'])
        gravar_com_copia(self.arquivo, '{"v": 2}', JSON_VALIDO)
        copias = listar_copias(self.arquivo)
        # A mais recente é o estado atual; a seguinte, o anterior.
        self.assertEqual([c.read_text() for c in copias], ['{"v": 2}', '{"v": 1}'])
        self.assertEqual(modo(copias[0]), 0o600)
        self.assertEqual(modo(copias[0].parent), 0o700)
        self.assertEqual(self.arquivo.read_text(), '{"v": 2}')

    def test_retencao_de_tres_copias(self):
        for versao in range(1, 8):
            gravar_com_copia(self.arquivo, json.dumps({"v": versao}), JSON_VALIDO)
        copias = listar_copias(self.arquivo)
        self.assertEqual([json.loads(c.read_text())["v"] for c in copias], [7, 6, 5])

    def test_conteudo_igual_nao_gera_copia_repetida(self):
        for _ in range(4):
            gravar_com_copia(self.arquivo, '{"v": 1}', JSON_VALIDO)
        gravar_com_copia(self.arquivo, '{"v": 2}', JSON_VALIDO)
        self.assertEqual(len(listar_copias(self.arquivo)), 2)

    def test_arquivo_corrompido_nunca_vira_copia(self):
        for versao in (1, 2, 3, 4):
            gravar_com_copia(self.arquivo, json.dumps({"v": versao}), JSON_VALIDO)
        self.arquivo.write_text('{"v": 4, "cort')          # corrompido
        copiar_versao_atual(self.arquivo, JSON_VALIDO)
        gravar_com_copia(self.arquivo, '{"v": 5}', JSON_VALIDO)
        conteudos = [c.read_text() for c in listar_copias(self.arquivo)]
        self.assertNotIn('{"v": 4, "cort', conteudos)
        self.assertEqual(conteudos, ['{"v": 5}', '{"v": 4}', '{"v": 3}'])

    def test_intervalo_minimo_entre_copias(self):
        politica = PoliticaDeCopias(validar=JSON_VALIDO.validar, intervalo_minimo=3600)
        for versao in range(1, 6):
            gravar_com_copia(self.arquivo, json.dumps({"v": versao}), politica)
        self.assertEqual(len(listar_copias(self.arquivo)), 1)

    def test_falha_na_copia_nao_impede_a_gravacao(self):
        gravar_com_copia(self.arquivo, '{"v": 1}', JSON_VALIDO)
        shutil.rmtree(self.pasta / "copias")
        (self.pasta / "copias").write_text("um ARQUIVO no lugar da pasta de cópias")
        with mock.patch("sys.stderr"):
            gravar_com_copia(self.arquivo, '{"v": 2}', JSON_VALIDO)
        self.assertEqual(self.arquivo.read_text(), '{"v": 2}')

    def test_validador_com_defeito_nao_derruba(self):
        def explode(_):
            raise RuntimeError("bug")
        gravar_com_copia(self.arquivo, "1", PoliticaDeCopias(validar=explode))
        gravar_com_copia(self.arquivo, "2", PoliticaDeCopias(validar=explode))
        self.assertEqual(self.arquivo.read_text(), "2")

    def test_copias_antigas_por_idade(self):
        for versao in (1, 2, 3):
            gravar_com_copia(self.arquivo, json.dumps({"v": versao}), JSON_VALIDO)
        velha = listar_copias(self.arquivo)[-1]
        antigo = time.time() - 40 * 86400
        os.utime(velha, (antigo, antigo))
        arquivos.apagar_copias_antigas(self.pasta, dias=30)
        self.assertEqual(len(listar_copias(self.arquivo)), 2)
        self.assertTrue(self.arquivo.exists())          # o arquivo principal nunca é apagado


class TestRecuperacao(_PastaTemporaria):
    # 9. recuperação de uma versão válida
    def test_recupera_ultima_copia_valida(self):
        for versao in (1, 2, 3):
            gravar_com_copia(self.arquivo, json.dumps({"v": versao}), JSON_VALIDO)
        self.arquivo.write_text('{"v": 3, "cortad')
        with mock.patch("sys.stderr"):
            dados = ler_com_recuperacao(self.arquivo, JSON_VALIDO)
        self.assertEqual(json.loads(dados), {"v": 3})          # o último estado bom
        self.assertEqual(json.loads(self.arquivo.read_text()), {"v": 3})
        guardados = list(self.pasta.glob("dados.json.corrompido-*"))
        self.assertEqual(len(guardados), 1)
        self.assertEqual(guardados[0].read_text(), '{"v": 3, "cortad')   # nada foi apagado

    def test_pula_copias_corrompidas(self):
        for versao in (1, 2, 3):
            gravar_com_copia(self.arquivo, json.dumps({"v": versao}), JSON_VALIDO)
        listar_copias(self.arquivo)[0].write_text("lixo")
        self.arquivo.write_text("lixo")
        with mock.patch("sys.stderr"):
            self.assertEqual(json.loads(ler_com_recuperacao(self.arquivo, JSON_VALIDO)), {"v": 2})

    def test_corrompido_sem_copia_e_preservado(self):
        self.arquivo.write_text("lixo sem cópia")
        with mock.patch("sys.stderr"):
            self.assertIsNone(ler_com_recuperacao(self.arquivo, JSON_VALIDO))
        self.assertFalse(self.arquivo.exists())
        self.assertEqual(next(self.pasta.glob("dados.json.corrompido-*")).read_text(), "lixo sem cópia")

    def test_arquivo_valido_e_inexistente(self):
        self.assertIsNone(ler_com_recuperacao(self.arquivo, JSON_VALIDO))
        gravar_atomico(self.arquivo, '{"ok": true}')
        self.assertEqual(json.loads(ler_com_recuperacao(self.arquivo, JSON_VALIDO)), {"ok": True})

    def test_ilegivel_e_preservado(self):
        if os.geteuid() == 0:
            self.skipTest("o usuário root ignora permissões")
        self.arquivo.write_text('{"v": 1}')
        os.chmod(self.arquivo, 0o000)
        with mock.patch("sys.stderr"):
            self.assertIsNone(ler_com_recuperacao(self.arquivo, JSON_VALIDO))
        guardado = next(self.pasta.glob("dados.json.ilegivel-*"))
        os.chmod(guardado, 0o600)
        self.assertEqual(guardado.read_text(), '{"v": 1}')


class TestDadosDoNavegador(_PastaTemporaria):
    """Os quatro tipos de dado usando o mecanismo, com caminhos falsos."""

    def setUp(self):
        super().setUp()
        self.config = self.pasta / "config"
        self.dados = self.pasta / "dados" / "tempo"
        self.config.mkdir()
        self.dados.mkdir(parents=True)
        self.remendos = [
            # Testes da lista PESSOAL: desliga o modo protegido mesmo que esta
            # máquina tenha /etc/navegador-estudos instalado.
            mock.patch.object(caminhos, "MODO_PROTEGIDO", False),
            mock.patch.object(caminhos, "ARQUIVO_SITES", self.config / "sites.txt"),
            mock.patch.object(caminhos, "ARQUIVO_SENHA", self.config / "senha.json"),
            mock.patch.object(caminhos, "ARQUIVO_PREFERENCIAS", self.config / "preferencias.json"),
            mock.patch.object(caminhos, "PASTA_TEMPO", self.dados),
            mock.patch("sys.stderr"),
        ]
        for remendo in self.remendos:
            remendo.start()

    def tearDown(self):
        for remendo in self.remendos:
            remendo.stop()
        super().tearDown()

    def test_senha_com_copias_e_sem_texto_puro(self):
        senha.definir("primeira-senha")
        senha.definir("segunda-senha")
        self.assertTrue(senha.confere("segunda-senha"))
        copias = listar_copias(caminhos.ARQUIVO_SENHA)
        self.assertEqual(len(copias), 2)
        for arquivo in [caminhos.ARQUIVO_SENHA, *copias]:
            self.assertEqual(modo(arquivo), 0o600)
            self.assertNotIn("senha", arquivo.read_text().replace('"', ""))  # só sal e hash

    def test_preferencias_recuperadas(self):
        preferencias.salvar({"meta_minutos": 90})
        preferencias.salvar({"meta_minutos": 120})
        caminhos.ARQUIVO_PREFERENCIAS.write_text('{"meta_min')
        self.assertEqual(preferencias.carregar()["meta_minutos"], 120)   # o último estado bom

    def test_tempo_corrompido_nao_apaga_estatisticas(self):
        contador = tempo.ContadorDeTempo()
        contador.somar("Wikipédia", 120)
        contador.salvar()
        arquivo = contador._arquivo()
        arquivo.write_text('{"Wikipédia": 12')            # corrompido
        novo = tempo.ContadorDeTempo()
        self.assertEqual(novo.por_site, {"Wikipédia": 120})        # recuperado da cópia
        guardado = next(self.dados.glob("*.corrompido-*"))          # e o ruim foi guardado
        self.assertEqual(guardado.read_text(), '{"Wikipédia": 12')

    def test_tempo_corrompido_sem_copia_e_preservado(self):
        hoje = self.dados / f"{tempo.datetime.date.today().isoformat()}.json"
        hoje.write_text('{"Wikipédia": 12')                 # corrompido e sem cópia
        novo = tempo.ContadorDeTempo()
        self.assertEqual(novo.por_site, {})
        novo.somar("Khan Academy", 5)
        novo.salvar()
        self.assertEqual(next(self.dados.glob("*.corrompido-*")).read_text(), '{"Wikipédia": 12')

    def test_falha_ao_salvar_tempo_nao_lanca_excecao(self):
        contador = tempo.ContadorDeTempo()
        contador.somar("Khan Academy", 30)
        with mock.patch("estudos.nucleo.tempo.gravar_com_copia",
                        side_effect=OSError(errno.ENOSPC, "No space left on device")):
            self.assertFalse(contador.salvar())
        self.assertEqual(contador.por_site, {"Khan Academy": 30})     # continua na memória
        self.assertTrue(contador.salvar())

    def test_lista_de_sites_editada_com_copia_e_recuperada(self):
        regras.ListaDeSites.carregar()                      # cria a partir da padrão
        regras.ListaDeSites.salvar_texto("+ exemplo.com\n")
        regras.ListaDeSites.salvar_texto("+ exemplo.com\n+ outro.org\n")
        caminhos.ARQUIVO_SITES.write_bytes(b"\xff\xfe lixo")   # corrompido (UTF-8 inválido)
        lista = regras.ListaDeSites.carregar()
        self.assertEqual(lista.dominios, {"exemplo.com", "outro.org"})   # a última edição
        self.assertTrue(list(self.config.glob("sites.txt.corrompido-*")))

    def test_lista_corrompida_sem_copia_volta_a_padrao(self):
        caminhos.ARQUIVO_SITES.write_bytes(b"\xff\xfe lixo")
        lista = regras.ListaDeSites.carregar()
        self.assertIn("wikipedia.org", lista.dominios)
        self.assertTrue(list(self.config.glob("sites.txt.corrompido-*")))

    # 10. compatibilidade com os dados da v2.1.1
    def test_le_arquivos_no_formato_da_v211(self):
        # Exatamente como a v2.1.1 gravava (write_text, sem cópias).
        sal, hash_ = "00" * 16, senha._calcular("1234", bytes(16)).hex()
        caminhos.ARQUIVO_SENHA.write_text(json.dumps({"sal": sal, "hash": hash_, "rodadas": 300000}))
        caminhos.ARQUIVO_PREFERENCIAS.write_text(json.dumps({"meta_minutos": 45}, indent=1))
        hoje = self.dados / f"{tempo.datetime.date.today().isoformat()}.json"
        hoje.write_text(json.dumps({"Wikipédia": 16, "SciELO": 15}, ensure_ascii=False, indent=1))
        caminhos.ARQUIVO_SITES.write_text("[X]\nWiki | https://pt.wikipedia.org/\n+ youtube.com")
        os.chmod(hoje, 0o664)

        self.assertTrue(senha.confere("1234"))
        self.assertEqual(preferencias.carregar()["meta_minutos"], 45)
        contador = tempo.ContadorDeTempo()
        self.assertEqual(contador.por_site, {"Wikipédia": 16, "SciELO": 15})
        self.assertIn("youtube.com", regras.ListaDeSites.carregar().dominios)

        # Ao gravar de novo: mesmo formato de antes, agora com permissão 600.
        contador.somar("Wikipédia", 4)
        contador.salvar()
        self.assertEqual(hoje.read_text(encoding="utf-8"),
                         json.dumps({"Wikipédia": 20, "SciELO": 15}, ensure_ascii=False, indent=1))
        self.assertEqual(modo(hoje), 0o600)


if __name__ == "__main__":
    unittest.main()
