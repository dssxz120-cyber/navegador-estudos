#!/bin/bash
# Cria o atalho do Navegador de Estudos no menu de aplicativos do Ubuntu.
# Não precisa de sudo: tudo fica dentro da sua pasta pessoal.
set -e
PASTA="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p ~/.local/share/applications ~/.local/share/icons/hicolor/scalable/apps
cp "$PASTA/recursos/icone.svg" ~/.local/share/icons/hicolor/scalable/apps/br.estudos.Navegador.svg
cat > ~/.local/share/applications/br.estudos.Navegador.desktop <<FIM
[Desktop Entry]
Type=Application
Name=Navegador de Estudos
Comment=Navegador que abre apenas sites de estudo
Exec=python3 "$PASTA/navegador_estudos.py"
Icon=$PASTA/recursos/icone.svg
Categories=Education;
StartupWMClass=br.estudos.Navegador
Terminal=false
FIM
update-desktop-database ~/.local/share/applications 2>/dev/null || true
echo "Pronto! Procure por \"Navegador de Estudos\" no menu de aplicativos."
