@echo off
REM PudimTranslate - abre o 0 A.D. com o tradutor de chat ligado.
REM
REM Use este no lugar do atalho normal do 0 A.D. e nao ha mais nada a fazer: o
REM tradutor sobe junto, na ordem certa, e e encerrado quando voce fecha o jogo.
REM
REM Na primeira vez ele cria um atalho "0 A.D. Translator" na area de trabalho,
REM com o icone do jogo. Use esse atalho daqui em diante.
REM
REM Ha duas implementacoes, PowerShell e Python, e este arquivo escolhe a que a
REM maquina tem. No Windows o PowerShell vem de fabrica, entao vem primeiro e
REM nao e preciso instalar nada.
REM
REM O -ExecutionPolicy Bypass vale so para esta chamada e nao altera nenhuma
REM configuracao do sistema.

title PudimTranslate - abrindo o jogo

where powershell >nul 2>&1
if %errorlevel%==0 (
	powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Play0AD.ps1" %*
	goto fim
)

where py >nul 2>&1
if %errorlevel%==0 (
	py -3 "%~dp0jogar_0ad.py" %*
	goto fim
)

where python >nul 2>&1
if %errorlevel%==0 (
	python "%~dp0jogar_0ad.py" %*
	goto fim
)

echo.
echo  Nao encontrei nem o PowerShell nem o Python neste computador.
echo  O PowerShell vem com o Windows 10 e 11; se ele sumiu, instale o Python
echo  em https://python.org/downloads (marque "Add Python to PATH").
echo.
pause

:fim
