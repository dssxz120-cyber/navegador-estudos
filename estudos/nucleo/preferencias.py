"""Preferências que o responsável ajusta (hoje: a meta diária de estudo).

Ficam em ~/.config/navegador-estudos/preferencias.json, por exemplo:
  {"meta_minutos": 60}
"""

import json
from . import caminhos
from .arquivos import PoliticaDeCopias, gravar_com_copia, ler_com_recuperacao

PADRAO = {"meta_minutos": 60,
          "inatividade_minutos": 5}   # parar de contar após X min sem teclado/mouse


def _valido(dados):
    return isinstance(json.loads(dados.decode("utf-8")), dict)


POLITICA = PoliticaDeCopias(validar=_valido)


LIMITES = {"meta_minutos": (10, 600), "inatividade_minutos": (1, 60)}


def normalizar(preferencias):
    """Só as chaves conhecidas, como números inteiros dentro dos limites."""
    resultado = dict(PADRAO)
    for chave, (minimo, maximo) in LIMITES.items():
        valor = preferencias.get(chave, PADRAO[chave])
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            continue
        resultado[chave] = int(min(max(valor, minimo), maximo))
    return resultado


def carregar():
    if caminhos.MODO_PROTEGIDO:
        # Preferências do administrador (/etc): só leitura, sem tentar consertar.
        try:
            dados = caminhos.ARQUIVO_PREFERENCIAS.read_bytes()
            return normalizar(json.loads(dados.decode("utf-8")))
        except (OSError, ValueError, AttributeError):
            return dict(PADRAO)
    dados = ler_com_recuperacao(caminhos.ARQUIVO_PREFERENCIAS, POLITICA)
    preferencias = json.loads(dados.decode("utf-8")) if dados is not None else {}
    return {**PADRAO, **preferencias}


def salvar(preferencias):
    gravar_com_copia(caminhos.ARQUIVO_PREFERENCIAS, json.dumps(preferencias, indent=1),
                     POLITICA)
