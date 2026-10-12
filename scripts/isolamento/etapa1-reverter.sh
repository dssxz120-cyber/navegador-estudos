#!/bin/bash
# Desfaz a Etapa 1: apaga a conta "aluno" e a pasta pessoal dela.
# Antes, guarda uma cópia compactada da pasta em /var/backups/navegador-estudos/.
ETAPA=etapa1-reverter
source "$(dirname "$0")/comum.sh" "$@"
exigir_root

id "$ALUNO" &>/dev/null || { echo "A conta \"$ALUNO\" não existe; nada a desfazer."; exit 0; }
aviso "Isto APAGA a conta \"$ALUNO\" e todos os arquivos dela (com cópia de segurança antes)"
confirmar "apagar aluno"
fazer mkdir -p "$PASTA_BACKUP"
fazer tar -czf "$PASTA_BACKUP/home-$ALUNO.tar.gz" -C /home "$ALUNO"
echo "   cópia de segurança: $PASTA_BACKUP/home-$ALUNO.tar.gz"
fazer deluser --remove-home "$ALUNO"
aviso "Conta \"$ALUNO\" removida"
