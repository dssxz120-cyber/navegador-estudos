#!/bin/bash
# Isolamento, Etapa 1: cria a conta padrão "aluno" (sem administrador).
#
#   Revisar:   bash scripts/isolamento/etapa1-aplicar.sh --simular
#   Aplicar:   sudo bash scripts/isolamento/etapa1-aplicar.sh
#   Desfazer:  sudo bash scripts/isolamento/etapa1-reverter.sh
#
# Não precisa reiniciar. Não altera a sua conta.
ETAPA=etapa1
source "$(dirname "$0")/comum.sh" "$@"
exigir_root
exigir_ubuntu_2404

aviso "Etapa 1: conta \"$ALUNO\""
if id "$ALUNO" &>/dev/null; then
    echo "   A conta \"$ALUNO\" já existe; nada a criar."
else
    fazer adduser --disabled-password --comment "Aluno" "$ALUNO"
    aviso "Defina agora a senha do aluno (é com ela que ele entra no computador)"
    fazer passwd "$ALUNO"
fi

aviso "Garantindo que o aluno NÃO é administrador"
for grupo in sudo adm lpadmin; do
    if id -nG "$ALUNO" 2>/dev/null | tr ' ' '\n' | grep -qx "$grupo"; then
        fazer deluser "$ALUNO" "$grupo"
    else
        echo "   fora do grupo $grupo ✓"
    fi
done
[ -d "/home/$ALUNO" ] && fazer chmod 750 "/home/$ALUNO"

if [ "$SIMULAR" = 0 ]; then
    aviso "Verificação"
    id "$ALUNO"
    stat -c '   pasta pessoal: %n  permissão %a  dono %U' "/home/$ALUNO"
    # LC_ALL=C: a mensagem em inglês ("may run"), seja qual for o idioma do sistema
    if LC_ALL=C sudo -l -U "$ALUNO" 2>/dev/null | grep -q "may run"; then
        erro "o aluno ainda tem permissão de administrador!"
    fi
    echo "   sem permissão de administrador ✓"
fi
aviso "Etapa 1 concluída"
