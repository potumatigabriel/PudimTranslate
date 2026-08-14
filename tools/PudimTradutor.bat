@echo off
REM PudimMod - atalho para ligar o tradutor de chat.
REM Deixe esta janela aberta enquanto joga. Feche com Ctrl+C ou no X.

title PudimMod - Tradutor de chat
cd /d "%~dp0"

REM O py.exe (Python Launcher) e a forma mais confiavel no Windows: acha a
REM versao instalada mesmo quando "python" nao esta no PATH.
where py >nul 2>&1
if %errorlevel%==0 (
	py -3 pudim_tradutor.py %*
	goto fim
)

where python >nul 2>&1
if %errorlevel%==0 (
	python pudim_tradutor.py %*
	goto fim
)

echo.
echo  Python nao encontrado.
echo  Instale em https://python.org/downloads (marque "Add Python to PATH")
echo  e rode este arquivo de novo.
echo.

:fim
echo.
pause
