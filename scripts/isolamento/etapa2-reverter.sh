#!/bin/bash
# Desfaz a Etapa 2: remove o navegador instalado para todas as contas, a
# configuração do administrador, a regra do polkit, o atalho e o ícone.
# Tudo é MOVIDO para /var/backups/navegador-estudos/ (nada se perde).
# Depois disso, cada conta volta a usar a própria lista em ~/.config.
ETAPA=etapa2-reverter
source "$(dirname "$0")/comum.sh" "$@"
exigir_root

aviso "Isto remove a instalação para todas as contas e a lista de $CONFIG_SISTEMA"
confirmar "remover instalação"
for alvo in "$DESTINO" "$CONFIG_SISTEMA" "$REGRA_POLKIT" "$ATALHO" "$ICONE"; do
    if [ -e "$alvo" ]; then
        fazer mkdir -p "$PASTA_BACKUP$(dirname "$alvo")"
        fazer mv "$alvo" "$PASTA_BACKUP$alvo"
        echo "   movido para $PASTA_BACKUP$alvo"
    fi
done
fazer update-desktop-database -q /usr/share/applications
fazer gtk-update-icon-cache -q -t /usr/share/icons/hicolor
aviso "Etapa 2 desfeita"
