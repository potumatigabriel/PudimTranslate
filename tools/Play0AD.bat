@echo off
REM PudimTranslate - abre o 0 A.D. com o tradutor de chat ligado.
REM
REM Use este atalho no lugar do atalho normal do 0 A.D. e nao ha mais nada a
REM fazer: o tradutor sobe junto, e e encerrado quando voce fecha o jogo.
REM
REM Dica: clique com o botao direito neste arquivo e escolha "Enviar para >
REM Area de trabalho (criar atalho)" para deixar a mao.

title PudimTranslate - abrindo o jogo
cd /d "%~dp0"

REM O py.exe (Python Launcher) e a forma mais confiavel no Windows: acha a
REM versao instalada mesmo quando "python" nao esta no PATH.
where py >nul 2>&1
if %errorlevel%==0 (
	py -3 jogar_0ad.py %*
	goto fim
)

where python >nul 2>&1
if %errorlevel%==0 (
	python jogar_0ad.py %*
	goto fim
)

echo.
echo  Python nao encontrado.
echo  Instale em https://python.org/downloads (marque "Add Python to PATH")
echo  e rode este arquivo de novo.
echo.
pause

:fim
