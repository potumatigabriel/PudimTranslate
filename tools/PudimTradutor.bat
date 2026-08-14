@echo off
REM PudimTranslate - liga so o tradutor de chat.
REM
REM Para jogar, prefira o Play0AD.bat: ele abre o tradutor E o jogo, na ordem
REM certa. Este aqui e para quem quer os dois separados.
REM
REM Nao precisa instalar nada: usa o Windows PowerShell, que ja vem no Windows.
REM O -ExecutionPolicy Bypass vale so para esta chamada e nao altera nenhuma
REM configuracao do sistema.

title PudimTranslate - Tradutor de chat
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0PudimTradutor.ps1" %*

if errorlevel 1 (
	echo.
	echo  O tradutor terminou com erro. A mensagem acima diz o motivo.
	pause
)
