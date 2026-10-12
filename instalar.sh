#!/bin/bash
# Instalador do Navegador de Estudos (Ubuntu 24.04).
#
# Uso:
#   bash instalar.sh               pergunta o modo
#   bash instalar.sh --simples     uma pessoa, para focar nos estudos
#   bash instalar.sh --protegido   computador com uma conta de aluno travada
#   bash instalar.sh --simular     mostra o que faria, sem mudar nada
#
# O que ele faz:
#   1. confere o sistema (Ubuntu 24.04);
#   2. instala os pacotes que faltarem, do repositório oficial do Ubuntu
#      (mostra a lista e pede confirmação antes);
#   3. instala o navegador no modo escolhido.
#
# Rode como o SEU usuário (não com sudo): quando precisar, ele pede a senha.
set -euo pipefail

PASTA="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACOTES=(python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1 publicsuffix
         gstreamer1.0-plugins-good gstreamer1.0-libav git)

MODO=""
SIMULAR=0
for argumento in "$@"; do
    case "$argumento" in
        --simples)   MODO="simples" ;;
        --protegido) MODO="protegido" ;;
        --simular)   SIMULAR=1 ;;
        -h|--help)   sed -n '2,16p' "$0"; exit 0 ;;
        *) echo "Opção desconhecida: $argumento (use --help)"; exit 2 ;;
    esac
done

titulo() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
erro()   { printf '\nERRO: %s\n' "$*" >&2; exit 1; }
pergunta_sim() {
    local resposta
    read -r -p "$1 [S/n] " resposta
    [[ -z "$resposta" || "$resposta" =~ ^[sS] ]]
}

echo
echo "  📚 Navegador de Estudos — instalação"
echo "  ─────────────────────────────────────"
[ "$SIMULAR" = 1 ] && echo "(modo simulação: nada será alterado)"

# ---------------------------------------------------------------- 1. sistema
titulo "1/3 Conferindo o sistema"
[ "$(id -u)" -ne 0 ] || erro "rode sem sudo:  bash instalar.sh  (ele pede a senha quando precisar)"
grep -q 'VERSION_ID="24.04"' /etc/os-release \
    || erro "este instalador foi feito para o Ubuntu 24.04 (o seu é: $(. /etc/os-release; echo "$PRETTY_NAME"))"
echo "   Ubuntu 24.04 ✓"

# ---------------------------------------------------------------- 2. pacotes
titulo "2/3 Pacotes necessários"
faltando=()
for pacote in "${PACOTES[@]}"; do
    dpkg-query -W -f='${Status}' "$pacote" 2>/dev/null | grep -q "ok installed" || faltando+=("$pacote")
done
if [ ${#faltando[@]} -eq 0 ]; then
    echo "   todos já instalados ✓"
else
    echo "   Vão ser instalados do repositório oficial do Ubuntu: ${faltando[*]}"
    if [ "$SIMULAR" = 1 ]; then
        echo "   [simulação] sudo apt-get update && sudo apt-get install ${faltando[*]}"
    else
        pergunta_sim "   Instalar agora?" || erro "instalação cancelada (nada foi alterado)"
        sudo apt-get update
        sudo apt-get install -y "${faltando[@]}"
    fi
fi

# ---------------------------------------------------------------- 3. modo
if [ -z "$MODO" ]; then
    titulo "Como o navegador vai ser usado?"
    echo "   1) Simples   — uma pessoa, para focar nos estudos (lista protegida por senha)"
    echo "   2) Protegido — computador com uma conta \"aluno\" travada: só o navegador"
    echo "                  funciona nela, e mudar a lista pede a senha de administrador"
    read -r -p "   Escolha 1 ou 2: " escolha
    case "$escolha" in
        1) MODO="simples" ;;
        2) MODO="protegido" ;;
        *) erro "opção inválida" ;;
    esac
fi

if [ "$MODO" = "simples" ]; then
    titulo "3/3 Instalando no modo simples"
    if [ "$SIMULAR" = 1 ]; then
        echo "   [simulação] bash scripts/instalar.sh   (atalho no menu de aplicativos)"
    else
        bash "$PASTA/scripts/instalar.sh"
    fi
    titulo "Pronto! Procure \"Navegador de Estudos\" no menu de aplicativos."
    echo "   Na primeira vez, ele pede para criar a senha do responsável."
    exit 0
fi

titulo "3/3 Instalando no modo protegido"
cat <<'TEXTO'
   Isto vai, com a sua senha de administrador:
     • criar a conta "aluno" (você define a senha dela);
     • instalar o navegador para todas as contas, com a lista em /etc;
     • bloquear para o aluno: outros navegadores, terminal, Flatpak,
       Alt+F2 e login por terminal de texto.
   A SUA conta continua normal. Tudo pode ser desfeito com os scripts
   scripts/isolamento/etapa*-reverter.sh.
TEXTO
opcao=()
[ "$SIMULAR" = 1 ] && opcao=(--simular)
if [ "$SIMULAR" = 0 ]; then
    pergunta_sim "   Continuar?" || erro "instalação cancelada (nada foi alterado)"
fi
for etapa in etapa1 etapa2 etapa3 etapa5; do
    if [ "$SIMULAR" = 1 ]; then
        bash "$PASTA/scripts/isolamento/$etapa-aplicar.sh" "${opcao[@]}"
    else
        sudo bash "$PASTA/scripts/isolamento/$etapa-aplicar.sh"
    fi
done
titulo "Pronto! Entre na conta \"aluno\" para conferir."
echo "   A lista de sites começa com a lista padrão. Para liberar outros sites,"
echo "   abra o navegador → ☰ → Área do responsável (pede a senha de administrador)."
