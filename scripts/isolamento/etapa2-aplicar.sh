#!/bin/bash
# Isolamento, Etapa 2: instala o Navegador de Estudos para TODAS as contas,
# em modo protegido.
#
#   Revisar:   bash scripts/isolamento/etapa2-aplicar.sh --simular
#   Aplicar:   sudo bash scripts/isolamento/etapa2-aplicar.sh
#   Desfazer:  sudo bash scripts/isolamento/etapa2-reverter.sh
#
# O que muda no sistema (tudo com cópia de segurança antes):
#   /opt/navegador-estudos/           código (dono root; ninguém mais altera)
#   /etc/navegador-estudos/           lista e preferências (dono root, leitura para todos)
#   /usr/share/polkit-1/actions/      regra: salvar exige senha de administrador
#   /usr/share/applications/          atalho do menu para todas as contas
#   /usr/share/icons/hicolor/...      ícone
#
# Efeito na SUA conta: o modo protegido vale para todos. A lista passa a ser
# uma só (a sua lista atual é o ponto de partida) e alterá-la pede a senha de
# administrador. Não precisa reiniciar.
ETAPA=etapa2
source "$(dirname "$0")/comum.sh" "$@"
exigir_root
exigir_ubuntu_2404

USUARIO="${SUDO_USER:-$(id -un)}"
[ "$USUARIO" != "root" ] || erro "rode com sudo a partir da SUA conta (não como root direto)"
como_usuario() { if [ "$(id -u)" -eq 0 ]; then sudo -u "$USUARIO" "$@"; else "$@"; fi; }

aviso "Conferindo o projeto em $PASTA_REPO"
ramo="$(como_usuario git -C "$PASTA_REPO" rev-parse --abbrev-ref HEAD)"
[ "$ramo" = "main" ] || erro "o projeto precisa estar na branch main (está em \"$ramo\")"
[ -z "$(como_usuario git -C "$PASTA_REPO" status --porcelain)" ] \
    || erro "há alterações não registradas no projeto; só se instala código commitado"
versao="$(como_usuario git -C "$PASTA_REPO" log -1 --format='%h %s')"
echo "   versão a instalar: $versao"

# ---------------------------------------------------------------------------
aviso "1/5 Código em $DESTINO"
if [ -e "$DESTINO" ]; then
    guardar "$DESTINO"
    fazer rm -rf "$DESTINO"
fi
fazer mkdir -p "$DESTINO"
if [ "$SIMULAR" = 1 ]; then
    echo "   [simulação] git archive HEAD | tar -x -C $DESTINO   ($(como_usuario git -C "$PASTA_REPO" ls-files | wc -l) arquivos)"
else
    como_usuario git -C "$PASTA_REPO" archive --format=tar HEAD | tar -x -C "$DESTINO"
    echo "$versao" > "$DESTINO/VERSAO-INSTALADA"
fi
fazer chown -R root:root "$DESTINO"
fazer find "$DESTINO" -type d -exec chmod 755 {} +
fazer find "$DESTINO" -type f -exec chmod 644 {} +
fazer chmod 755 "$DESTINO/navegador_estudos.py" "$DESTINO/scripts/salvar-configuracao" \
    "$DESTINO/scripts/isolamento/preparar_configuracao.py"

# ---------------------------------------------------------------------------
aviso "2/5 Configuração do administrador em $CONFIG_SISTEMA"
PESSOAL="$(getent passwd "$USUARIO" | cut -d: -f6)/.config/navegador-estudos"
if [ -f "$CONFIG_SISTEMA/sites.txt" ]; then
    echo "   já existe uma lista em $CONFIG_SISTEMA; ela é MANTIDA (não sobrescrevo)."
    guardar "$CONFIG_SISTEMA"
elif [ "$SIMULAR" = 1 ]; then
    echo "   [simulação] ponto de partida = sua lista pessoal:"
    python3 -I "$PASTA_REPO/scripts/isolamento/preparar_configuracao.py" "$PESSOAL" --resumo
else
    python3 -I "$DESTINO/scripts/isolamento/preparar_configuracao.py" "$PESSOAL" \
        | python3 -I "$DESTINO/scripts/salvar-configuracao"
    python3 -I "$DESTINO/scripts/isolamento/preparar_configuracao.py" "$PESSOAL" --resumo
fi

# ---------------------------------------------------------------------------
aviso "3/5 Regra do polkit (salvar exige senha de administrador)"
guardar "$REGRA_POLKIT"
fazer install -m 644 -o root -g root "$DESTINO/scripts/sistema/br.estudos.navegador.policy" "$REGRA_POLKIT"

# ---------------------------------------------------------------------------
aviso "4/5 Atalho e ícone para todas as contas"
guardar "$ATALHO"
guardar "$ICONE"
fazer install -D -m 644 -o root -g root "$DESTINO/recursos/icone.svg" "$ICONE"
if [ "$SIMULAR" = 1 ]; then
    echo "   [simulação] criar $ATALHO (Exec=/usr/bin/python3 -I $DESTINO/navegador_estudos.py)"
else
    cat > "$ATALHO" <<FIM
[Desktop Entry]
Type=Application
Name=Navegador de Estudos
Comment=Navegador que abre apenas sites de estudo
Exec=/usr/bin/python3 -I $DESTINO/navegador_estudos.py
Icon=$DESTINO/recursos/icone.svg
Categories=Education;
StartupWMClass=br.estudos.Navegador
Terminal=false
FIM
    chmod 644 "$ATALHO"
fi
fazer update-desktop-database -q /usr/share/applications
fazer gtk-update-icon-cache -q -t /usr/share/icons/hicolor

# ---------------------------------------------------------------------------
if [ "$SIMULAR" = 0 ]; then
    aviso "5/5 Verificação"
    pkaction --action-id br.estudos.navegador.salvar-configuracao >/dev/null \
        && echo "   regra do polkit registrada ✓" || erro "regra do polkit não registrada"
    stat -c '   %n  %a  dono %U' "$DESTINO" "$CONFIG_SISTEMA" "$CONFIG_SISTEMA/sites.txt" \
        "$CONFIG_SISTEMA/preferencias.json"
    if id "$ALUNO" &>/dev/null; then
        sudo -u "$ALUNO" test -w "$CONFIG_SISTEMA/sites.txt" \
            && erro "o aluno consegue alterar a lista!" || echo "   o aluno NÃO consegue alterar a lista ✓"
        sudo -u "$ALUNO" python3 -I -c "import sys; sys.path.insert(0, '$DESTINO'); \
from estudos.nucleo import caminhos; print('   modo protegido na conta do aluno:', caminhos.MODO_PROTEGIDO)"
    else
        echo "   (conta \"$ALUNO\" ainda não existe; rode a Etapa 1 para conferir pelo lado dele)"
    fi
fi
aviso "Etapa 2 concluída. Cópias de segurança (se havia algo antes): $PASTA_BACKUP"
