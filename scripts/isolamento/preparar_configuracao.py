#!/usr/bin/python3 -I
"""Monta o pedido inicial para /etc/navegador-estudos a partir da lista
pessoal do responsável (usado pela Etapa 2 do isolamento).

    preparar_configuracao.py <pasta ~/.config/navegador-estudos> [--resumo]

Sem --resumo, imprime o JSON que o auxiliar `salvar-configuracao` recebe.
Com --resumo, só descreve o que seria instalado (para a simulação).
Sai com erro se a lista tiver problemas: a instalação não continua.
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from estudos.nucleo import preferencias  # noqa: E402
from estudos.nucleo.regras import ListaDeSites  # noqa: E402


def montar(pasta):
    arquivo = Path(pasta) / "sites.txt"
    if arquivo.is_file():
        texto, origem = arquivo.read_text(encoding="utf-8"), str(arquivo)
    else:
        texto = (RAIZ / "recursos" / "sites_padrao.txt").read_text(encoding="utf-8")
        origem = "lista padrão (não havia lista pessoal)"
    try:
        prefs = json.loads((Path(pasta) / "preferencias.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        prefs = {}
    return {"sites": texto, "preferencias": preferencias.normalizar(prefs)}, origem


def main(argumentos):
    if not argumentos:
        print(__doc__, file=sys.stderr)
        return 2
    pedido, origem = montar(argumentos[0])
    lista = ListaDeSites.de_texto(pedido["sites"])
    if lista.erros or not lista.dominios:
        print("A lista tem problemas e não será instalada:", *lista.erros[:5], sep="\n  ",
              file=sys.stderr)
        return 1
    if "--resumo" in argumentos:
        print(f"   lista: {origem}")
        print(f"   {len(lista.dominios)} domínios liberados, {len(lista.excluidos)} excluídos, "
              f"{sum(len(c.atalhos) for c in lista.categorias)} atalhos")
        print(f"   preferências: {pedido['preferencias']}")
        return 0
    print(json.dumps(pedido))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
