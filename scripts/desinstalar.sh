#!/bin/bash
# Remove o atalho do menu. Para apagar também a lista, a senha e o tempo
# estudado, rode com:  ./desinstalar.sh --apagar-dados
rm -f ~/.local/share/applications/br.estudos.Navegador.desktop
rm -f ~/.local/share/icons/hicolor/scalable/apps/br.estudos.Navegador.svg
if [ "$1" = "--apagar-dados" ]; then
    rm -rf ~/.config/navegador-estudos ~/.local/share/navegador-estudos ~/.cache/navegador-estudos
    echo "Atalho e dados removidos."
else
    echo "Atalho removido (seus dados foram mantidos)."
fi
