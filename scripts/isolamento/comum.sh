# Funções comuns aos scripts de isolamento. Não execute este arquivo direto.
#
# Todos os scripts aceitam --simular: mostram o que fariam, sem mudar nada
# e sem precisar de sudo. Use para revisar antes de aplicar de verdade.

set -euo pipefail

SIMULAR=0
for argumento in "$@"; do
    [ "$argumento" = "--simular" ] && SIMULAR=1
done

PASTA_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CARIMBO="$(date +%Y%m%d-%H%M%S)"
PASTA_BACKUP="/var/backups/navegador-estudos/${ETAPA}-${CARIMBO}"
ALUNO="aluno"
DESTINO="/opt/navegador-estudos"
CONFIG_SISTEMA="/etc/navegador-estudos"
REGRA_POLKIT="/usr/share/polkit-1/actions/br.estudos.navegador.policy"
ATALHO="/usr/share/applications/br.estudos.Navegador.desktop"
ICONE="/usr/share/icons/hicolor/scalable/apps/br.estudos.Navegador.svg"
REGISTRO="/var/lib/navegador-estudos"          # o que a Etapa 3 alterou (para desfazer)
GERADOR="/etc/systemd/user-environment-generators/99-navegador-estudos-ambiente"
DCONF_PERFIL="/etc/dconf/profile/aluno"
DCONF_BANCO="/etc/dconf/db/aluno.d"
SISTEMA="$PASTA_REPO/scripts/isolamento/sistema"

aviso() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
erro()  { printf '\nERRO: %s\n' "$*" >&2; exit 1; }

# Executa um comando, ou só o mostra em modo de simulação.
fazer() {
    if [ "$SIMULAR" = 1 ]; then
        printf '   [simulação] %s\n' "$*"
    else
        "$@"
    fi
}

exigir_root() {
    [ "$SIMULAR" = 1 ] && return 0
    [ "$(id -u)" -eq 0 ] || erro "rode com sudo:  sudo bash $0"
}

exigir_ubuntu_2404() {
    grep -q 'VERSION_ID="24.04"' /etc/os-release || erro "estes scripts foram feitos para o Ubuntu 24.04"
}

# Copia um arquivo ou pasta do sistema para o backup ANTES de alterá-lo.
guardar() {
    local alvo="$1"
    [ -e "$alvo" ] || return 0
    fazer mkdir -p "$PASTA_BACKUP$(dirname "$alvo")"
    fazer cp -a "$alvo" "$PASTA_BACKUP$alvo"
    echo "   cópia de segurança: $PASTA_BACKUP$alvo"
}

# Pede para digitar uma frase antes de algo difícil de desfazer.
confirmar() {
    [ "$SIMULAR" = 1 ] && return 0
    local frase="$1" resposta
    read -r -p "   Para continuar, digite \"$frase\": " resposta
    [ "$resposta" = "$frase" ] || erro "cancelado (nada foi alterado)"
}

if [ "$SIMULAR" = 1 ]; then
    aviso "MODO SIMULAÇÃO: nada será alterado"
fi
