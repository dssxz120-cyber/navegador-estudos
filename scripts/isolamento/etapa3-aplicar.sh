#!/bin/bash
# Isolamento, Etapa 3 (versão Padrão): travas na conta do aluno.
#
#   Revisar:   bash scripts/isolamento/etapa3-aplicar.sh --simular
#   Aplicar:   sudo bash scripts/isolamento/etapa3-aplicar.sh
#   Desfazer:  sudo bash scripts/isolamento/etapa3-reverter.sh
#
# Não instala nada. O aluno precisa SAIR E ENTRAR de novo para valer.
# Você (grupo sudo) continua usando todos os programas normalmente.
#
# LIMITE CONHECIDO (versão Padrão): o python3 continua disponível, porque o
# navegador depende dele. Alguém com conhecimento técnico ainda consegue
# burlar, por exemplo criando um programa de inicialização automática.
ETAPA=etapa3
source "$(dirname "$0")/comum.sh" "$@"
exigir_root
exigir_ubuntu_2404
id "$ALUNO" &>/dev/null || [ "$SIMULAR" = 1 ] || erro "a conta \"$ALUNO\" não existe (rode a Etapa 1)"
[ -f /etc/navegador-estudos/sites.txt ] || [ "$SIMULAR" = 1 ] || erro "o navegador não está instalado (rode a Etapa 2)"

# Programas que o aluno NÃO pode executar (o caminho real, sem atalhos).
BLOQUEAR=(
    /usr/bin/snap                           # Firefox, Brave e todos os snaps
    /usr/bin/flatpak                        # apps Flatpak (jogos e outros apps)
    /usr/bin/firefox                        # atalho antigo do Firefox
    /usr/bin/gnome-terminal
    /usr/bin/gnome-terminal.real
    /usr/libexec/gnome-terminal-server      # o terminal "de verdade"
    /usr/bin/curl /usr/bin/wget /usr/bin/w3m  # baixam e mostram páginas
    /usr/bin/x86_64-linux-gnu-gcc-13        # compilador (gcc, cc)
)

aviso "1/4 Programas só para administradores (grupo sudo), via dpkg-statoverride"
echo "   (o dpkg-statoverride mantém a trava mesmo depois de atualizar os pacotes)"
fazer mkdir -p "$REGISTRO"
for programa in "${BLOQUEAR[@]}"; do
    if [ ! -e "$programa" ]; then
        echo "   não existe, ignorado: $programa"
    elif dpkg-statoverride --list "$programa" >/dev/null; then
        echo "   já tem regra própria, NÃO mexo: $programa ($(dpkg-statoverride --list "$programa"))"
    else
        fazer dpkg-statoverride --update --add root sudo 750 "$programa"
        [ "$SIMULAR" = 1 ] || echo "$programa" >> "$REGISTRO/etapa3-statoverride.txt"
        echo "   bloqueado para o aluno: $programa"
    fi
done

aviso "2/4 Agendador de tarefas (cron) só para administradores"
if [ -e /etc/cron.allow ]; then
    guardar /etc/cron.allow
else
    [ "$SIMULAR" = 1 ] || touch "$REGISTRO/etapa3-criou-cron.allow"
fi
for usuario in root $(getent group sudo | cut -d: -f4 | tr ',' ' '); do
    if ! grep -qx "$usuario" /etc/cron.allow 2>/dev/null; then
        if [ "$SIMULAR" = 1 ]; then echo "   [simulação] liberar cron para: $usuario"
        else echo "$usuario" >> /etc/cron.allow; echo "   cron liberado para: $usuario"; fi
    fi
done

aviso "3/4 Travas do GNOME só para o aluno (perfil dconf + gerador de ambiente)"
guardar "$DCONF_PERFIL"
guardar "$DCONF_BANCO"
guardar "$GERADOR"
fazer install -D -m 644 -o root -g root "$SISTEMA/dconf-perfil-aluno" "$DCONF_PERFIL"
fazer install -D -m 644 -o root -g root "$SISTEMA/dconf-aluno.d/00-navegador-estudos" \
    "$DCONF_BANCO/00-navegador-estudos"
fazer install -D -m 644 -o root -g root "$SISTEMA/dconf-aluno.d/locks/00-navegador-estudos" \
    "$DCONF_BANCO/locks/00-navegador-estudos"
fazer install -D -m 755 -o root -g root "$SISTEMA/99-navegador-estudos-ambiente" "$GERADOR"
fazer dconf update

aviso "4/4 Arquivos de inicialização do aluno travados (ninguém além do root altera)"
CASA="/home/$ALUNO"
TRAVAR_ARQUIVOS=(.profile .bashrc .bash_profile .bash_login .pam_environment .xsessionrc .xprofile)
TRAVAR_PASTAS=(.config/environment.d)
for nome in "${TRAVAR_ARQUIVOS[@]}"; do
    alvo="$CASA/$nome"
    if [ "$SIMULAR" = 1 ]; then echo "   [simulação] travar $alvo"; continue; fi
    [ -e "$alvo" ] || { if [ -f "/etc/skel/$nome" ]; then cp "/etc/skel/$nome" "$alvo"; else : > "$alvo"; fi; }
    chown root:root "$alvo"; chmod 644 "$alvo"; chattr +i "$alvo"
    echo "$alvo" >> "$REGISTRO/etapa3-travados.txt"
    echo "   travado: $alvo"
done
for nome in "${TRAVAR_PASTAS[@]}"; do
    alvo="$CASA/$nome"
    if [ "$SIMULAR" = 1 ]; then echo "   [simulação] travar pasta vazia $alvo"; continue; fi
    install -d -m 755 -o "$ALUNO" -g "$ALUNO" "$(dirname "$alvo")"
    [ -d "$alvo" ] || mkdir "$alvo"
    chown root:root "$alvo"; chmod 755 "$alvo"; chattr +i "$alvo"
    echo "$alvo" >> "$REGISTRO/etapa3-travados.txt"
    echo "   travada: $alvo"
done

if [ "$SIMULAR" = 0 ]; then
    aviso "Verificação"
    for programa in /usr/bin/snap /usr/bin/curl /usr/libexec/gnome-terminal-server; do
        sudo -u "$ALUNO" test -x "$programa" && erro "o aluno ainda executa $programa" \
            || echo "   aluno NÃO executa $programa ✓"
    done
    [ -n "${SUDO_USER:-}" ] && sudo -u "$SUDO_USER" test -x /usr/bin/curl \
        && echo "   você ($SUDO_USER) continua executando curl ✓"
    sudo -u "$ALUNO" test -x /usr/bin/python3 && echo "   aluno executa python3 (o navegador precisa) ✓"
    [ "$(sudo -u "$ALUNO" "$GERADOR" | head -1)" = "DCONF_PROFILE=aluno" ] \
        && echo "   gerador ativa o perfil do aluno ✓" || erro "gerador não funcionou"
    [ "$(sudo -u "$ALUNO" env DCONF_PROFILE=aluno dconf read /org/gnome/desktop/lockdown/disable-command-line)" = "true" ] \
        && echo "   Alt+F2 desativado no perfil do aluno ✓" || erro "trava do dconf não aplicada"
    lsattr "$CASA/.profile" | grep -q -- "-i-" && echo "   arquivos de inicialização travados ✓"
fi
aviso "Etapa 3 concluída. O aluno precisa sair e entrar de novo para valer."
