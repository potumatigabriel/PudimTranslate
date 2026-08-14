#!/bin/sh
# PudimTranslate - liga so o tradutor de chat. Linux e macOS.
#
# Para jogar, prefira o Play0AD.sh: ele abre o tradutor E o jogo, na ordem
# certa. Este aqui e para quem quer os dois separados.
#
# Existem duas implementacoes do tradutor, uma em Python e outra em PowerShell,
# e este arquivo escolhe a que a maquina tem. Aqui o Python vem primeiro: ele
# acompanha praticamente toda distribuicao Linux e vem com as ferramentas de
# linha de comando do macOS, enquanto o PowerShell precisa ser instalado. No
# Windows a ordem se inverte — veja PudimTradutor.bat.
#
# Se este arquivo nao abrir com dois cliques, de permissao de execucao uma vez:
#     chmod +x PudimTradutor.sh

aqui=$(cd "$(dirname "$0")" && pwd)

if command -v python3 >/dev/null 2>&1; then
	exec python3 "$aqui/pudim_tradutor.py" "$@"
fi

if command -v pwsh >/dev/null 2>&1; then
	exec pwsh -NoProfile -File "$aqui/PudimTradutor.ps1" "$@"
fi

echo
echo " Nao encontrei o Python 3 neste computador."
echo " Instale pelo gerenciador de pacotes da sua distribuicao, por exemplo:"
echo "   sudo apt install python3        (Debian, Ubuntu)"
echo "   sudo dnf install python3        (Fedora)"
echo " No macOS, rode: xcode-select --install"
echo
exit 1
