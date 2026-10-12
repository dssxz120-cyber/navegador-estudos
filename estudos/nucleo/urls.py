"""Leitura RÍGIDA de endereços (URLs).

Por que isso existe:
  O Python (urllib) e o WebKit (que segue o padrão WHATWG dos navegadores)
  nem sempre entendem um endereço do mesmo jeito. Exemplo real:

      https://instagram.com\\@pt.wikipedia.org/

  O urllib acha que o site é "pt.wikipedia.org"; o WebKit troca a barra
  invertida por "/" e abre "instagram.com". Se o filtro e o navegador
  discordam, o filtro pode ser enganado.

A solução: só aceitamos endereços em uma forma simples, na qual os dois
lados com certeza concordam. Qualquer coisa ambígua (barra invertida,
usuário@senha, "%" ou letras acentuadas no nome do site, espaços...) é
considerada inválida e, portanto, bloqueada. Na dúvida, bloqueia.
"""

import re
from dataclasses import dataclass

# Caracteres que o padrão WHATWG remove das pontas do endereço
# (controles ASCII 0x00–0x1F e o espaço) e os que remove de qualquer lugar.
_PONTAS = "".join(chr(c) for c in range(0x21))
_REMOVIDOS_EM_QUALQUER_LUGAR = str.maketrans("", "", "\t\n\r")

_ESQUEMA = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.\-]*):(.*)$", re.DOTALL)
# Nome de site simples: letras ASCII, números, ponto e hífen. Porta opcional.
_AUTORIDADE = re.compile(r"^([a-z0-9.\-]+)(?::([0-9]{1,5}))?$")


@dataclass(frozen=True)
class Endereco:
    esquema: str      # "https", "estudos", "about"...
    host: str         # "pt.wikipedia.org" (vazio em esquemas sem site)
    porta: int = None
    resto: str = ""   # caminho, consulta e fragmento ("/wiki/A?x=1#y")


def analisar(url):
    """Devolve um Endereco, ou None se o endereço for inválido ou ambíguo."""
    if not isinstance(url, str):
        return None
    texto = url.strip(_PONTAS).translate(_REMOVIDOS_EM_QUALQUER_LUGAR)
    combina = _ESQUEMA.match(texto)
    if not combina:
        return None
    esquema, resto = combina.group(1).lower(), combina.group(2)

    if esquema not in ("http", "https", "ws", "wss", "ftp", "file"):
        # Esquemas sem "site" (estudos:, about:, data:, javascript:...).
        return Endereco(esquema, "", None, resto)

    # Esquemas com site: exigimos exatamente "//" seguido do nome do site.
    if not resto.startswith("//") or resto.startswith("///"):
        return None
    resto = resto[2:]
    # A autoridade (nome do site + porta) termina no primeiro / ? #.
    # Para o WebKit ela também termina em "\" — por isso "\" é proibida.
    fim = len(resto)
    for separador in "/?#":
        posicao = resto.find(separador)
        if posicao != -1:
            fim = min(fim, posicao)
    autoridade, caminho = resto[:fim], resto[fim:]
    if "\\" in autoridade or "@" in autoridade:
        return None   # barra invertida ou usuário:senha@ → ambíguo
    combina = _AUTORIDADE.match(autoridade.lower())
    if not combina:
        return None   # "%", acentos, espaços, colchetes (IPv6)... → ambíguo
    host, porta = combina.group(1), combina.group(2)
    if host.endswith("."):
        host = host[:-1]   # "site.com." é o mesmo site que "site.com"
    if not host or host.startswith(".") or ".." in host:
        return None
    if porta is not None:
        porta = int(porta)
        if not 0 < porta < 65536:
            return None
    return Endereco(esquema, host, porta, caminho)
