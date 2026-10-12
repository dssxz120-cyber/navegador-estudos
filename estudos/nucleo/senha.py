"""Senha do responsável, que protege a edição da lista de sites.

A senha NUNCA é guardada como texto. Guardamos só um "hash": uma impressão
digital calculada a partir dela (PBKDF2, 300 mil rodadas). Dá para conferir
se uma senha digitada está certa, mas não dá para descobrir a senha olhando
o arquivo.
"""

import hashlib
import hmac
import json
import secrets

from . import caminhos
from .arquivos import (PoliticaDeCopias, gravar_com_copia, ler_com_recuperacao,
                       ultima_copia_valida)

RODADAS = 300_000
TAMANHO_MINIMO = 8          # para senhas NOVAS; as já criadas continuam valendo

# Estado do arquivo da senha (função estado()).
SEM_SENHA, OK, DANIFICADA = "sem_senha", "ok", "danificada"


def _calcular(senha, sal):
    return hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), sal, RODADAS)


def _senha_valida(dados):
    """Formato do senha.json (só o hash e o sal; nunca a senha em texto)."""
    conteudo = json.loads(dados.decode("utf-8"))
    bytes.fromhex(conteudo["sal"])
    bytes.fromhex(conteudo["hash"])
    return isinstance(conteudo.get("rodadas", RODADAS), int)


# Cópias das senhas anteriores (até 3), usadas para recuperar um arquivo danificado.
POLITICA = PoliticaDeCopias(validar=_senha_valida)


def problema_na_nova_senha(nova, repetida):
    """Devolve None se a senha nova serve, ou a explicação do problema."""
    if len(nova) < TAMANHO_MINIMO:
        return f"A senha precisa ter pelo menos {TAMANHO_MINIMO} caracteres."
    if nova.strip() != nova:
        return "A senha não pode começar nem terminar com espaço."
    if len(set(nova)) < 3:
        return "A senha é muito repetitiva; misture letras, números ou símbolos."
    if nova != repetida:
        return "As duas senhas não são iguais."
    return None


def _ler():
    """Conteúdo válido do senha.json, recuperando de uma cópia se preciso.

    Segurança: se o arquivo estiver danificado e NÃO houver cópia válida, ele
    fica onde está (o programa continua pedindo a senha, que não confere).
    Assim, estragar o arquivo de propósito não abre caminho para o aluno
    criar uma senha nova.
    """
    arquivo = caminhos.ARQUIVO_SENHA
    try:
        dados = arquivo.read_bytes()
    except FileNotFoundError:
        return None
    except OSError:
        return None
    try:
        if _senha_valida(dados):
            return json.loads(dados.decode("utf-8"))
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        pass
    if ultima_copia_valida(arquivo, POLITICA) is None:
        return None          # danificada e sem cópia: mantém como está
    recuperado = ler_com_recuperacao(arquivo, POLITICA)   # guarda o ruim e restaura
    return json.loads(recuperado.decode("utf-8")) if recuperado else None


def estado():
    """SEM_SENHA (nunca criada), OK, ou DANIFICADA (existe mas não dá para usar)."""
    if not caminhos.ARQUIVO_SENHA.exists():
        return SEM_SENHA
    return OK if _ler() is not None else DANIFICADA


def existe():
    return caminhos.ARQUIVO_SENHA.exists()


def definir(senha):
    sal = secrets.token_bytes(16)   # valor aleatório que deixa cada hash único
    dados = {"sal": sal.hex(), "hash": _calcular(senha, sal).hex(),
             "rodadas": RODADAS}
    gravar_com_copia(caminhos.ARQUIVO_SENHA, json.dumps(dados), POLITICA)


def confere(senha):
    dados = _ler()
    if dados is None:
        return False
    try:
        esperado = bytes.fromhex(dados["hash"])
        calculado = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"),
                                        bytes.fromhex(dados["sal"]),
                                        dados.get("rodadas", RODADAS))
    except (ValueError, KeyError, TypeError):
        return False
    # compare_digest evita pistas pelo tempo de comparação.
    return hmac.compare_digest(esperado, calculado)
