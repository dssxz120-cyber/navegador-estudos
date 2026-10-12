#!/bin/bash
# Isolamento, Etapa 5: o aluno não entra por terminal de texto (Ctrl+Alt+F3).
#
#   Revisar:   bash scripts/isolamento/etapa5-aplicar.sh --simular
#   Aplicar:   sudo bash scripts/isolamento/etapa5-aplicar.sh
#   Desfazer:  sudo bash scripts/isolamento/etapa5-reverter.sh
#
# Liga o pam_access SÓ no login de terminal de texto (/etc/pam.d/login) e
# nega a conta do aluno ali. A tela de login gráfica e a sua conta não mudam.
# Não precisa reiniciar.
ETAPA=etapa5
source "$(dirname "$0")/comum.sh" "$@"
exigir_root
exigir_ubuntu_2404

LINHA_DESLIGADA='# account  required       pam_access.so'
LINHA_LIGADA='account  required       pam_access.so'
MARCA='# Navegador de Estudos: o aluno não entra por terminal de texto'

aviso "1/2 Ligando o pam_access no login de terminal de texto"
guardar /etc/pam.d/login
if grep -qx "$LINHA_LIGADA" /etc/pam.d/login; then
    echo "   já estava ligado"
elif grep -qx "$LINHA_DESLIGADA" /etc/pam.d/login; then
    fazer sed -i "s|^$LINHA_DESLIGADA\$|$LINHA_LIGADA|" /etc/pam.d/login
    echo "   ligado"
else
    erro "não encontrei a linha esperada em /etc/pam.d/login; nada foi alterado"
fi

aviso "2/2 Negando o aluno em /etc/security/access.conf"
guardar /etc/security/access.conf
if grep -qxF "$MARCA" /etc/security/access.conf; then
    echo "   regra já existe"
elif [ "$SIMULAR" = 1 ]; then
    echo "   [simulação] acrescentar: -:$ALUNO:ALL"
else
    printf '\n%s\n-:%s:ALL\n' "$MARCA" "$ALUNO" >> /etc/security/access.conf
    echo "   regra acrescentada"
fi

if [ "$SIMULAR" = 0 ]; then
    aviso "Verificação"
    grep -qx "$LINHA_LIGADA" /etc/pam.d/login && echo "   pam_access ligado no login de texto ✓"
    grep -qx -- "-:$ALUNO:ALL" /etc/security/access.conf && echo "   aluno negado no terminal de texto ✓"
    grep -l pam_access /etc/pam.d/* | grep -v "^/etc/pam.d/login$" | grep -q . \
        && echo "   atenção: outros serviços também usam pam_access" \
        || echo "   só o login de texto usa a regra (a tela de login gráfica não muda) ✓"
fi
aviso "Etapa 5 concluída. Teste: Ctrl+Alt+F3, entre como aluno (deve ser recusado), Ctrl+Alt+F1 ou F2 volta."
