"""Modo protegido: a configuração do administrador em /etc/navegador-estudos.

Na conta do aluno, a lista de sites e as preferências ficam numa pasta do
sistema (dona: root). O aluno lê, mas não altera. Para salvar mudanças, a
Área do responsável chama o programa auxiliar `scripts/salvar-configuracao`
pelo `pkexec`, que pede a SENHA DE ADMINISTRADOR do Ubuntu (regra do polkit
em scripts/sistema/). Só depois disso o auxiliar, rodando como root, valida
e grava os arquivos.

Este módulo tem as duas pontas:
  - salvar_via_pkexec(): chamada pela janela (lado do usuário);
  - aplicar_configuracao(): chamada pelo auxiliar (lado do root).
"""

import json
import subprocess

from . import caminhos, preferencias
from .arquivos import gravar_com_copia
from .regras import POLITICA_DE_COPIAS, ListaDeSites

MODO_LEITURA_PARA_TODOS = 0o644      # o aluno precisa LER a lista e as preferências
TAMANHO_MAXIMO = 512 * 1024          # bytes: uma lista real tem poucos KB
AJUDANTE = caminhos.PASTA_RAIZ / "scripts" / "salvar-configuracao"

# Códigos de saída do pkexec quando a senha não é confirmada.
PKEXEC_NEGADO = (126, 127)


class ConfiguracaoInvalida(ValueError):
    """A configuração enviada ao auxiliar não passou na validação."""


def aplicar_configuracao(dados, pasta):
    """LADO DO ROOT: valida `dados` e grava em `pasta` (/etc/navegador-estudos).

    dados = {"sites": "<texto do sites.txt>", "preferencias": {...}}
    Lança ConfiguracaoInvalida sem gravar nada se algo estiver errado.
    """
    if not isinstance(dados, dict) or not isinstance(dados.get("sites"), str):
        raise ConfiguracaoInvalida("formato inesperado")
    texto = dados["sites"]
    if len(texto.encode("utf-8")) > TAMANHO_MAXIMO:
        raise ConfiguracaoInvalida("lista grande demais")
    lista = ListaDeSites.de_texto(texto)
    if lista.erros:
        raise ConfiguracaoInvalida("a lista tem erros: " + "; ".join(lista.erros[:3]))
    if not lista.dominios:
        raise ConfiguracaoInvalida("a lista precisa ter pelo menos um site")
    prefs = dados.get("preferencias", {})
    if not isinstance(prefs, dict):
        raise ConfiguracaoInvalida("preferências em formato inesperado")
    prefs = preferencias.normalizar(prefs)

    pasta.mkdir(mode=0o755, exist_ok=True)
    gravar_com_copia(pasta / "sites.txt", texto, POLITICA_DE_COPIAS,
                     modo=MODO_LEITURA_PARA_TODOS)
    gravar_com_copia(pasta / "preferencias.json", json.dumps(prefs, indent=1),
                     preferencias.POLITICA, modo=MODO_LEITURA_PARA_TODOS)
    return lista, prefs


def salvar_via_pkexec(texto_da_lista, prefs, executar=subprocess.run):
    """LADO DO USUÁRIO: pede a senha de administrador e salva.

    Devolve None se deu certo, ou uma mensagem explicando o problema.
    `executar` existe para os testes (sem pedir senha de verdade).
    """
    pedido = json.dumps({"sites": texto_da_lista, "preferencias": prefs})
    try:
        resultado = executar(["pkexec", str(AJUDANTE)], input=pedido, text=True,
                             capture_output=True, timeout=300)
    except FileNotFoundError:
        return "O pkexec não está disponível neste sistema."
    except subprocess.TimeoutExpired:
        return "Tempo esgotado esperando a senha de administrador."
    if resultado.returncode == 0:
        return None
    if resultado.returncode in PKEXEC_NEGADO:
        return "A senha de administrador não foi confirmada. Nada foi alterado."
    detalhe = (resultado.stderr or "").strip().splitlines()[-1:] or ["erro desconhecido"]
    return f"Não foi possível salvar: {detalhe[0]}"
