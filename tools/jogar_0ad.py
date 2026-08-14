#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PudimTranslate — abre o 0 A.D. com o tradutor ligado.

Por que existe
--------------
O mod nao consegue ligar o tradutor sozinho: o JS da GUI do 0 A.D. nao executa
programa nenhum — nao ha API para isso, e nem deveria haver. Entao a forma de
"ligar junto com o jogo" e inverter a ordem: em vez do jogo abrir o tradutor,
este atalho abre os dois.

    liga o tradutor  ->  abre o 0 A.D.  ->  espera voce fechar  ->  encerra o tradutor

Use este atalho no lugar do atalho normal do 0 A.D. e nao ha mais nada a fazer.
O tradutor nao fica sobrando depois que voce fecha o jogo.

Uso
---
    Jogar0AD.bat                       (o normal: e so dar dois cliques)
    python jogar_0ad.py --jogo "C:/caminho/para/pyrogenesis.exe"
    python jogar_0ad.py -- -mod=mod -mod=public   (o que vier depois de -- vai para o jogo)

Se o executavel nao for encontrado sozinho, informe uma vez com --jogo: o
caminho fica guardado em caminho_do_jogo.txt, ao lado deste arquivo, e nas
proximas vezes nao precisa mais.
"""

import argparse
import importlib.util
import os
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_CAMINHO = os.path.join(AQUI, "caminho_do_jogo.txt")
TRADUTOR = os.path.join(AQUI, "pudim_tradutor.py")

EXECUTAVEL = "pyrogenesis.exe" if os.name == "nt" else "pyrogenesis"


# ─── Onde esta o 0 A.D. ───────────────────────────────────────────────────────

def caminhos_provaveis():
    """Locais onde o 0 A.D. costuma ser instalado, em ordem de probabilidade."""
    saidas = []

    for var in ("LOCALAPPDATA", "ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(var)
        if not base:
            continue
        for pasta in ("0 A.D. Empires Ascendant", "0 A.D.", "0ad"):
            saidas.append(os.path.join(base, pasta, "binaries", "system", EXECUTAVEL))

    # Steam, incluindo bibliotecas em outras unidades.
    for var in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(var)
        if base:
            saidas.append(os.path.join(base, "Steam", "steamapps", "common", "0 A.D",
                                       "binaries", "system", EXECUTAVEL))
    for unidade in "CDEFG":
        saidas.append(f"{unidade}:\\SteamLibrary\\steamapps\\common\\0 A.D"
                      f"\\binaries\\system\\{EXECUTAVEL}")

    # Linux e macOS.
    saidas += ["/usr/games/0ad", "/usr/bin/0ad", "/usr/local/bin/0ad"]

    return saidas


def do_atalho_do_menu_iniciar():
    """
    Le o alvo do atalho do 0 A.D. no menu Iniciar.

    E a fonte mais confiavel quando a instalacao nao esta em nenhum lugar
    obvio: o proprio instalador criou o atalho apontando para o lugar certo.
    Resolver um .lnk sem biblioteca extra exige o WScript.Shell, entao vai pelo
    PowerShell mesmo.
    """
    if os.name != "nt":
        return None

    script = (
        "$ws = New-Object -ComObject WScript.Shell; "
        "Get-ChildItem -Path "
        "\"$env:APPDATA\\Microsoft\\Windows\\Start Menu\\Programs\","
        "\"$env:ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\" "
        "-Filter *.lnk -Recurse -ErrorAction SilentlyContinue | "
        "Where-Object { $_.Name -match '0.?A' } | "
        "ForEach-Object { $ws.CreateShortcut($_.FullName).TargetPath }"
    )

    try:
        saida = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True, timeout=60,
        ).stdout
    except Exception:
        return None

    for linha in saida.splitlines():
        linha = linha.strip()
        if linha.lower().endswith(EXECUTAVEL.lower()) and os.path.isfile(linha):
            return linha

    return None


def achar_jogo(preferido=None):
    if preferido:
        if os.path.isfile(preferido):
            return os.path.abspath(preferido)
        sys.exit(f"[erro] nao existe: {preferido}")

    # O que ja foi descoberto antes vale mais que qualquer palpite.
    if os.path.isfile(ARQUIVO_CAMINHO):
        try:
            with open(ARQUIVO_CAMINHO, encoding="utf-8") as arquivo:
                guardado = arquivo.read().strip()
            if guardado and os.path.isfile(guardado):
                return guardado
        except Exception:
            pass

    for caminho in caminhos_provaveis():
        if os.path.isfile(caminho):
            return os.path.abspath(caminho)

    do_menu = do_atalho_do_menu_iniciar()
    if do_menu:
        return do_menu

    return None


def pasta_area_de_trabalho():
    """
    Area de trabalho real, lida do registro do Windows.

    Pelo mesmo motivo da pasta Documentos: com o OneDrive ligado, a area de
    trabalho vira algo como D:\\OneDrive\\Area de Trabalho, e o
    C:\\Users\\<nome>\\Desktop continua existindo, vazio. Adivinhar pelo nome
    criaria o atalho numa pasta que o usuario nunca ve.
    """
    if os.name != "nt":
        return None
    try:
        import winreg
        chave = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
        )
        with chave:
            valor, _ = winreg.QueryValueEx(chave, "Desktop")
        caminho = os.path.expandvars(valor)
        return caminho if os.path.isdir(caminho) else None
    except Exception:
        return None


NOME_ATALHO = "0 A.D. Translator.lnk"


def criar_atalho_do_tradutor():
    """
    Cria, uma vez so, um atalho do tradutor na area de trabalho.

    Leva o icone do proprio 0 A.D. para ficar reconhecivel ao lado do atalho do
    jogo, e o caminho absoluto desta maquina — assim funciona de onde o usuario
    tiver posto a pasta do mod.

    @returns o caminho do atalho criado, ou None se ja existia ou nao deu.
    """
    if os.name != "nt":
        return None

    area = pasta_area_de_trabalho()
    if not area:
        return None

    atalho = os.path.join(area, NOME_ATALHO)
    if os.path.exists(atalho):
        return None

    alvo = os.path.join(AQUI, "PudimTradutor.bat")
    if not os.path.isfile(alvo):
        return None

    # O icone do jogo e um extra: se o executavel nao for encontrado, o atalho e
    # criado do mesmo jeito, apenas com o icone padrao.
    jogo = achar_jogo(None)
    linha_icone = f'$s.IconLocation = "{jogo},0"; ' if jogo else ""

    script = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f'$s = $ws.CreateShortcut("{atalho}"); '
        f'$s.TargetPath = "{alvo}"; '
        f'$s.WorkingDirectory = "{AQUI}"; '
        f"{linha_icone}"
        '$s.Description = "Tradutor de chat do 0 A.D. - abra ANTES do jogo"; '
        "$s.Save()"
    )

    try:
        resultado = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        return None

    return atalho if resultado.returncode == 0 and os.path.exists(atalho) else None


def userdata_do_tradutor():
    """
    Pasta de dados do 0 A.D., pela mesma logica que o tradutor usa.

    Reaproveita achar_userdata de pudim_tradutor.py em vez de repetir a
    deteccao: uma copia divergente daria dois palpites diferentes na mesma
    maquina, e o atalho ficaria esperando um arquivo em pasta errada.
    """
    try:
        spec = importlib.util.spec_from_file_location("pudim_tradutor", TRADUTOR)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        return modulo.achar_userdata(None)
    except Exception:
        return ""


def guardar_caminho(caminho):
    try:
        with open(ARQUIVO_CAMINHO, "w", encoding="utf-8") as arquivo:
            arquivo.write(caminho)
    except Exception:
        # Nao achar onde guardar nao pode impedir o jogo de abrir; apenas
        # significa procurar de novo na proxima vez.
        pass


# ─── Principal ────────────────────────────────────────────────────────────────

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    analisador = argparse.ArgumentParser(
        description="Abre o 0 A.D. com o tradutor de chat do PudimTranslate ligado."
    )
    analisador.add_argument("--jogo", help="Caminho do pyrogenesis.exe, se a busca falhar")
    analisador.add_argument("--to", help="Forca o idioma de destino (normalmente o jogo decide)")
    analisador.add_argument("resto", nargs=argparse.REMAINDER,
                            help="Depois de --, argumentos repassados ao 0 A.D.")
    argumentos = analisador.parse_args()

    jogo = achar_jogo(argumentos.jogo)
    if not jogo:
        print("Nao encontrei o 0 A.D. neste computador.")
        print()
        print("Abra o Prompt de Comando nesta pasta e rode uma vez, com o caminho certo:")
        print('  python jogar_0ad.py --jogo "C:/caminho/para/pyrogenesis.exe"')
        print()
        print("O caminho fica guardado e nas proximas vezes o atalho funciona sozinho.")
        input("\nEnter para sair.")
        return 1

    guardar_caminho(jogo)

    print("PudimTranslate")
    print(f"  jogo    : {jogo}")
    print(f"  tradutor: {TRADUTOR}")
    print()

    comando_tradutor = [sys.executable, TRADUTOR]
    if argumentos.to:
        comando_tradutor += ["--to", argumentos.to]

    # Em janela propria, para o log de traducao ficar visivel — e util para
    # conferir que esta funcionando. No Windows so ha CREATE_NEW_CONSOLE.
    criacao = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    try:
        tradutor = subprocess.Popen(comando_tradutor, creationflags=criacao) if criacao \
            else subprocess.Popen(comando_tradutor)
    except Exception as erro:
        print(f"[aviso] nao consegui ligar o tradutor: {erro}")
        print("        O jogo abre assim mesmo, so nao traduz.")
        tradutor = None

    # Um instante antes de abrir o jogo, de proposito. O VFS do 0 A.D. indexa a
    # pasta ao iniciar e nao enxerga arquivo que nasca depois; se o jogo subir
    # antes de o tradutor criar o arquivo de resposta, ele nunca vai encontra-lo
    # nesta sessao. Esperar o arquivo aparecer resolve, e no caso normal isso
    # leva alguns centesimos.
    if tradutor:
        caminho_resposta = os.path.join(
            userdata_do_tradutor(), "saves", "campaigns", "pudim_tr_res.json")
        for _ in range(40):  # no maximo 4s; depois abre assim mesmo
            if os.path.isfile(caminho_resposta):
                break
            time.sleep(0.1)

    # O que vier depois de "--" e do jogo, nao nosso.
    extras = [a for a in argumentos.resto if a != "--"]

    print("Abrindo o 0 A.D. Esta janela se fecha sozinha quando voce sair do jogo.")
    try:
        subprocess.run([jogo] + extras, cwd=os.path.dirname(jogo))
    except Exception as erro:
        print(f"[erro] nao consegui abrir o jogo: {erro}")
        input("\nEnter para sair.")

    # O tradutor nao tem razao de existir sem o jogo aberto.
    if tradutor and tradutor.poll() is None:
        print("Jogo fechado. Encerrando o tradutor.")
        tradutor.terminate()
        try:
            tradutor.wait(timeout=5)
        except Exception:
            tradutor.kill()

    return 0


if __name__ == "__main__":
    sys.exit(main())
