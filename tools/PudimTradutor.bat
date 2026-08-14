@echo off
REM PudimTranslate - liga so o tradutor de chat.
REM
REM Para jogar, prefira o Play0AD.bat: ele abre o tradutor E o jogo, na ordem
REM certa. Este aqui e para quem quer os dois separados.
REM
REM Existem duas implementacoes do tradutor, uma em PowerShell e outra em
REM Python, e este arquivo escolhe a que a maquina tem. No Windows o PowerShell
REM vem de fabrica, entao ele vem primeiro e ninguem precisa instalar nada; o
REM Python so entra se por algum motivo o PowerShell nao estiver disponivel.
REM (No Linux e no macOS a ordem se inverte — veja PudimTradutor.sh.)
REM
REM O -ExecutionPolicy Bypass vale so para esta chamada e nao altera nenhuma
REM configuracao do sistema.

title PudimTranslate - Tradutor de chat

where powershell >nul 2>&1
if %errorlevel%==0 (
	powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0PudimTradutor.ps1" %*
	goto fim
)

where py >nul 2>&1
if %errorlevel%==0 (
	py -3 "%~dp0pudim_tradutor.py" %*
	goto fim
)

where python >nul 2>&1
if %errorlevel%==0 (
	python "%~dp0pudim_tradutor.py" %*
	goto fim
)

echo.
echo  Nao encontrei nem o PowerShell nem o Python neste computador.
echo  O PowerShell vem com o Windows 10 e 11; se ele sumiu, instale o Python
echo  em https://python.org/downloads (marque "Add Python to PATH").
echo.
pause

:fim
