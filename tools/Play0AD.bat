@echo off
REM PudimTranslate - abre o 0 A.D. com o tradutor de chat ligado.
REM
REM Use este no lugar do atalho normal do 0 A.D. e nao ha mais nada a fazer: o
REM tradutor sobe junto, na ordem certa, e e encerrado quando voce fecha o jogo.
REM
REM Na primeira vez ele cria um atalho "0 A.D. Translator" na area de trabalho,
REM com o icone do jogo. Use esse atalho daqui em diante.
REM
REM Nao precisa instalar nada: usa o Windows PowerShell, que ja vem no Windows.
REM O -ExecutionPolicy Bypass vale so para esta chamada e nao altera nenhuma
REM configuracao do sistema.

title PudimTranslate - abrindo o jogo
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Play0AD.ps1" %*
