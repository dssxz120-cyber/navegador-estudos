"""Limite de tentativas da senha do responsável.

As 3 primeiras tentativas erradas são livres. A partir daí, cada erro impõe
uma espera que dobra: 30 s, 1 min, 2 min, 4 min... até no máximo 15 min.
Acertar a senha zera o contador.

O estado fica em ~/.config/navegador-estudos/tentativas.json, para que fechar
e abrir o navegador não zere a espera.
  {"falhas": 4, "liberado_em": 1791830000.0}

Limitação conhecida: na MESMA conta do Linux, quem apagar esse arquivo zera
o contador. A proteção completa depende do isolamento da conta do aluno.
"""

import json
import time

from . import caminhos
from .arquivos import gravar_atomico

TENTATIVAS_LIVRES = 3
ESPERA_INICIAL = 30          # segundos
ESPERA_MAXIMA = 15 * 60


def _arquivo():
    return caminhos.PASTA_CONFIG / "tentativas.json"


def _ler():
    try:
        dados = json.loads(_arquivo().read_text(encoding="utf-8"))
        return int(dados.get("falhas", 0)), float(dados.get("liberado_em", 0))
    except (OSError, ValueError, TypeError, AttributeError):
        return 0, 0.0


def _gravar(falhas, liberado_em):
    try:
        gravar_atomico(_arquivo(), json.dumps({"falhas": falhas, "liberado_em": liberado_em}))
    except OSError:
        pass     # sem disco: a espera ainda vale enquanto o programa estiver aberto


def espera_restante(agora=None):
    """Segundos que ainda faltam para poder tentar de novo (0 = pode tentar)."""
    agora = time.time() if agora is None else agora
    _falhas, liberado_em = _ler()
    restante = liberado_em - agora
    # Um valor absurdo (relógio mexido, arquivo editado) é limitado ao máximo.
    return max(0.0, min(restante, ESPERA_MAXIMA))


def registrar_falha(agora=None):
    """Conta um erro e devolve a espera imposta (em segundos)."""
    agora = time.time() if agora is None else agora
    falhas = _ler()[0] + 1
    espera = 0
    if falhas > TENTATIVAS_LIVRES:
        # Expoente limitado: um "falhas" enorme (arquivo editado) não pode gerar
        # uma conta gigantesca; o resultado já passa do máximo em 2**5.
        expoente = min(falhas - TENTATIVAS_LIVRES - 1, 10)
        espera = min(ESPERA_INICIAL * 2 ** expoente, ESPERA_MAXIMA)
    _gravar(falhas, agora + espera)
    return espera


def registrar_acerto():
    _gravar(0, 0.0)
