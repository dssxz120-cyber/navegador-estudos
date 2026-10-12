"""Validação dos domínios que o responsável cadastra na lista.

Impede cadastros perigosos ou que não funcionam, como:
  + com.br     -> liberaria TODOS os sites .com.br (é um "sufixo público")
  + github.io  -> liberaria as páginas de qualquer pessoa no GitHub
  + *.com      -> curinga: este navegador não usa curingas
  + "site.com  -> aspas, espaços, acentos...

"Sufixo público" é a parte de um endereço sob a qual qualquer pessoa pode
registrar um site (com, com.br, co.uk, github.io...). A lista oficial é
mantida pela Mozilla e já vem instalada no Ubuntu (pacote "publicsuffix").
"""

import re
from functools import lru_cache
from pathlib import Path

ARQUIVO_SUFIXOS = Path("/usr/share/publicsuffix/public_suffix_list.dat")

# Usado só se o arquivo do Ubuntu não existir: os sufixos mais comuns.
SUFIXOS_RESERVA = {
    "com", "net", "org", "edu", "gov", "io", "ai", "app", "dev", "info", "br", "pt",
    "uk", "us", "com.br", "net.br", "org.br", "edu.br", "gov.br", "blog.br",
    "co.uk", "org.uk", "ac.uk", "com.pt", "github.io", "gitlab.io", "pages.dev",
    "vercel.app", "netlify.app", "web.app", "firebaseapp.com", "blogspot.com",
}

_ROTULO = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")


@lru_cache(maxsize=1)
def _regras_de_sufixo():
    """Lê a lista oficial: (normais, curingas, excecoes)."""
    normais, curingas, excecoes = set(), set(), set()
    try:
        linhas = ARQUIVO_SUFIXOS.read_text(encoding="utf-8").splitlines()
    except OSError:
        return set(SUFIXOS_RESERVA), set(), set()
    for linha in linhas:
        linha = linha.strip()
        if not linha or linha.startswith("//"):
            continue
        regra = linha.split()[0].lower()
        try:
            # Entradas com acentos (ex.: "com.ço") viram a forma "xn--".
            regra = regra.encode("idna").decode("ascii") if not regra.isascii() else regra
        except UnicodeError:
            continue
        if regra.startswith("!"):
            excecoes.add(regra[1:])
        elif regra.startswith("*."):
            curingas.add(regra[2:])
        else:
            normais.add(regra)
    return normais, curingas, excecoes


def eh_sufixo_publico(dominio):
    """True se ninguém "é dono" deste domínio (com.br, co.uk, github.io...)."""
    normais, curingas, excecoes = _regras_de_sufixo()
    if dominio in excecoes:
        return False
    if "." not in dominio:          # regra implícita "*": todo TLD é sufixo
        return True
    if dominio in normais:
        return True
    pai = dominio.split(".", 1)[1]
    return pai in curingas           # ex.: "*.ck" torna "qualquer.ck" sufixo


def validar(dominio):
    """Devolve None se o domínio é aceitável, ou um texto explicando o erro."""
    if not dominio:
        return "domínio vazio"
    if "*" in dominio:
        return "curingas (*) não são aceitos; escreva só o domínio, ex.: exemplo.com"
    if not dominio.isascii():
        return "use só letras sem acento (domínios com acento: forma xn--)"
    if len(dominio) > 253:
        return "domínio longo demais"
    rotulos = dominio.split(".")
    if len(rotulos) < 2:
        return "falta a terminação (ex.: .com, .org, .br)"
    if not all(_ROTULO.match(rotulo) for rotulo in rotulos):
        return "caracteres inválidos (use letras, números, ponto e hífen)"
    if rotulos[-1].isdigit():
        return "endereços numéricos (IP) não são aceitos"
    if eh_sufixo_publico(dominio):
        return f"“{dominio}” é um sufixo público e liberaria milhares de sites"
    return None
