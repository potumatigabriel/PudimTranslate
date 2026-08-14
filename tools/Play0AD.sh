#!/bin/sh
# PudimTranslate - abre o 0 A.D. com o tradutor de chat ligado. Linux e macOS.
#
# Use este no lugar do atalho normal do 0 A.D.: o tradutor sobe junto, na ordem
# certa, e e encerrado quando voce fecha o jogo. A ordem importa de verdade — o
# 0 A.D. indexa as pastas de dados uma vez, ao iniciar, e nunca percebe arquivo
# que apareca depois.
#
# Ha duas implementacoes, Python e PowerShell, e este arquivo escolhe a que a
# maquina tem. Aqui o Python vem primeiro, porque e o que ja existe na maioria
# dos Linux e no macOS.
#
# Se este arquivo nao abrir com dois cliques, de permissao de execucao uma vez:
#     chmod +x Play0AD.sh

aqui=$(cd "$(dirname "$0")" && pwd)

if command -v python3 >/dev/null 2>&1; then
	exec python3 "$aqui/jogar_0ad.py" "$@"
fi

if command -v pwsh >/dev/null 2>&1; then
	exec pwsh -NoProfile -File "$aqui/Play0AD.ps1" "$@"
fi

echo
echo " Nao encontrei o Python 3 neste computador."
echo " Instale pelo gerenciador de pacotes da sua distribuicao, por exemplo:"
echo "   sudo apt install python3        (Debian, Ubuntu)"
echo "   sudo dnf install python3        (Fedora)"
echo " No macOS, rode: xcode-select --install"
echo
exit 1
