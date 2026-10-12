#!/bin/bash
# Desfaz a Etapa 3: devolve os programas, o cron, o GNOME e os arquivos de
# inicialização do aluno ao normal. O aluno precisa sair e entrar de novo.
ETAPA=etapa3-reverter
source "$(dirname "$0")/comum.sh" "$@"
exigir_root
confirmar "desfazer etapa 3"

aviso "Programas"
if [ -f "$REGISTRO/etapa3-statoverride.txt" ]; then
    while read -r programa; do
        fazer dpkg-statoverride --remove "$programa" || true
        [ -e "$programa" ] && fazer chown root:root "$programa" && fazer chmod 755 "$programa"
        echo "   liberado: $programa"
    done < "$REGISTRO/etapa3-statoverride.txt"
    fazer rm -f "$REGISTRO/etapa3-statoverride.txt"
fi

aviso "Cron"
if [ -f "$REGISTRO/etapa3-criou-cron.allow" ]; then
    guardar /etc/cron.allow
    fazer rm -f /etc/cron.allow "$REGISTRO/etapa3-criou-cron.allow"
else
    echo "   /etc/cron.allow já existia antes; a cópia anterior está em /var/backups/navegador-estudos/"
fi

aviso "GNOME do aluno"
for alvo in "$GERADOR" "$DCONF_PERFIL" "$DCONF_BANCO"; do
    [ -e "$alvo" ] && guardar "$alvo" && fazer rm -rf "$alvo"
done
fazer rm -f /etc/dconf/db/aluno
fazer dconf update

aviso "Arquivos de inicialização do aluno"
if [ -f "$REGISTRO/etapa3-travados.txt" ]; then
    while read -r alvo; do
        [ -e "$alvo" ] || continue
        fazer chattr -i "$alvo"
        fazer chown "$ALUNO:$ALUNO" "$alvo"
        echo "   destravado: $alvo"
    done < "$REGISTRO/etapa3-travados.txt"
    fazer rm -f "$REGISTRO/etapa3-travados.txt"
fi
aviso "Etapa 3 desfeita"
