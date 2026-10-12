"""Onde o navegador guarda seus arquivos.

Seguimos o padrão do Linux (XDG):
  ~/.config/navegador-estudos/       -> lista de sites e senha
  ~/.local/share/navegador-estudos/  -> tempo estudado, cookies, cache
"""

import os
from pathlib import Path

from gi.repository import GLib

# Pasta raiz do programa e pasta de recursos (ícone, fonte, lista padrão, CSS).
PASTA_RAIZ = Path(__file__).resolve().parents[2]
PASTA_RECURSOS = PASTA_RAIZ / "recursos"

PASTA_CONFIG = Path(GLib.get_user_config_dir()) / "navegador-estudos"
PASTA_DADOS = Path(GLib.get_user_data_dir()) / "navegador-estudos"

# MODO PROTEGIDO (conta de aluno separada):
# se o administrador instalou a configuração em /etc/navegador-estudos/, a
# lista de sites e as preferências vêm de lá — o aluno pode ler, mas não
# alterar. Alterações passam pela senha de ADMINISTRADOR do Ubuntu (veja
# nucleo/protegido.py). O caminho é fixo de propósito: não há variável de
# ambiente para trocá-lo, senão o aluno poderia apontar para uma lista dele.
PASTA_SISTEMA = Path("/etc/navegador-estudos")
MODO_PROTEGIDO = (PASTA_SISTEMA / "sites.txt").is_file()

ARQUIVO_SITES = PASTA_CONFIG / "sites.txt"
ARQUIVO_SENHA = PASTA_CONFIG / "senha.json"
ARQUIVO_PREFERENCIAS = PASTA_CONFIG / "preferencias.json"
ARQUIVO_POMODORO = PASTA_CONFIG / "pomodoro.json"
if MODO_PROTEGIDO:
    ARQUIVO_SITES = PASTA_SISTEMA / "sites.txt"
    ARQUIVO_PREFERENCIAS = PASTA_SISTEMA / "preferencias.json"
PASTA_TEMPO = PASTA_DADOS / "tempo"
PASTA_NAVEGACAO = PASTA_DADOS / "navegacao"   # cookies e logins dos sites
PASTA_CACHE = Path(GLib.get_user_cache_dir()) / "navegador-estudos"


def criar_pastas():
    """Cria as pastas na primeira execução (se já existirem, não faz nada)."""
    for pasta in (PASTA_CONFIG, PASTA_TEMPO, PASTA_NAVEGACAO, PASTA_CACHE):
        pasta.mkdir(parents=True, exist_ok=True)
    # A pasta de configuração fica visível só para o próprio usuário.
    os.chmod(PASTA_CONFIG, 0o700)


def recurso_seguro(relativo):
    """Caminho de um arquivo dentro de recursos/, ou None se for inválido.

    Impede truques como 'estudos://recursos/../../.config/senha.json', que
    tentariam ler arquivos fora da pasta de recursos.
    """
    base = PASTA_RECURSOS.resolve()
    arquivo = (base / relativo).resolve()
    if base in arquivo.parents and arquivo.is_file():
        return arquivo
    return None
