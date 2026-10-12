#!/bin/bash
# Desfaz a Etapa 5: desliga o pam_access no login de texto e tira a regra do aluno.
ETAPA=etapa5-reverter
source "$(dirname "$0")/comum.sh" "$@"
exigir_root
MARCA='# Navegador de Estudos: o aluno não entra por terminal de texto'
guardar /etc/pam.d/login
guardar /etc/security/access.conf
fazer sed -i 's|^account  required       pam_access.so$|# account  required       pam_access.so|' /etc/pam.d/login
if [ "$SIMULAR" = 1 ]; then
    echo "   [simulação] remover a regra do aluno de /etc/security/access.conf"
else
    sed -i "\|^$MARCA\$|,+1d" /etc/security/access.conf
fi
aviso "Etapa 5 desfeita"
