#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PudimTranslate — Tradutor de chat (programa auxiliar)

ATENCAO: existe uma segunda implementacao, em PowerShell (pudimtr_comum.ps1 e
PudimTradutor.ps1). Nao e duplicacao por descuido — e o que faz o mod funcionar
sem instalar nada em qualquer sistema: no Windows o PowerShell vem de fabrica e
o Python quase nunca esta; no Linux e no macOS e o contrario. Os lancadores
(.bat e .sh) escolhem a que a maquina tem.

As duas falam o MESMO protocolo com o jogo, e mudar um lado sem mudar o outro
quebra metade dos usuarios em silencio. O que precisa bater:
  - pasta e nomes dos arquivos (saves/campaigns/pudim_tr_*.json)
  - resposta com 65536 bytes exatos, completada com espacos
  - "vivo" em segundos desde a epoca, em UTC
  - limpeza das tags do chat antes de traduzir
  - idioma tirado do campo "to" do pedido

Por que este programa existe
----------------------------
O JS da GUI do 0 A.D. nao tem HTTP. Nao existe fetch, XHR nem nada equivalente:
as unicas funcoes de rede expostas ao script sao a lobby (XMPP, em C++) e o
mod.io (URL fixa). Ou seja, o mod nao consegue chamar o Google Tradutor sozinho.

O que da pra fazer pelo script e ler e gravar arquivo (Engine.WriteJSONFile /
Engine.ReadJSONFile / Engine.FileExists — APIs publicas, usadas pelo proprio
jogo para salvar campanha e configuracao de partida). Entao a ponte e por
arquivo: o mod escreve o que quer traduzir, este programa traduz e devolve.

    mod  --escreve-->  pudim_tr_req.json  --le-->  este programa  --HTTP-->  Google
    mod  <----le----   pudim_tr_res.json  <-escreve------'

Os dois moram em <userdata>/saves/campaigns/ — veja o porque logo abaixo, em
"Protocolo da ponte".

Endpoint usado
--------------
translate.googleapis.com/translate_a/single?client=gtx — o mesmo que o site
translate.google.com usa. Gratis, sem chave e sem cadastro. Nao e documentado
pelo Google, entao pode mudar sem aviso; para o volume de um chat de partida
(algumas dezenas de frases curtas) funciona bem e nao esbarra em limite.

Uso
---
    python pudim_tradutor.py              # detecta a pasta do 0 A.D. sozinho
    python pudim_tradutor.py --dir "C:/caminho/para/My Games/0ad"
    python pudim_tradutor.py --to en      # traduzir PARA outro idioma

Deixe rodando numa janela enquanto joga. Sem ele o mod continua funcionando;
so nao traduz (o botao avisa que o tradutor esta desligado).
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

# ─── Protocolo da ponte ───────────────────────────────────────────────────────
# Os arquivos ficam em <userdata>/saves/campaigns/. A pasta nao foi escolhida
# por gosto: o ReadJSONFile/WriteJSONFile da GUI do jogo so aceita uma lista
# fechada de caminhos — "gui/", "simulation/", "maps/", "campaigns/",
# "saves/campaigns/", "config/matchsettings.json" e
# "config/matchsettings.mp.json". Qualquer outro lugar responde "Restricted
# access to ...". Dessa lista, "saves/campaigns/" e a unica pasta do usuario em
# que da para gravar, entao e onde a ponte mora.
#
# Isso nao atrapalha as campanhas: o jogo lista so "*.0adcampaign" ali, e os
# nossos arquivos sao ".json".

SUBDIR = os.path.join("saves", "campaigns")
REQ_FILE = "pudim_tr_req.json"
RES_FILE = "pudim_tr_res.json"
CACHE_FILE = "pudim_tr_cache.json"

POLL_SECONDS = 0.3
CACHE_MAX = 4000

# Tamanho fixo do arquivo de resposta, em bytes. Ver gravar_resposta() para o
# porque. 64 KB cabem algumas centenas de falas traduzidas — muito mais do que
# uma partida produz — e ocupam nada no disco.
TAMANHO_RESPOSTA = 65536

GTX_URL = "https://translate.googleapis.com/translate_a/single"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
HTTP_TIMEOUT = 8


# ─── Localizacao da pasta de dados do 0 A.D. ──────────────────────────────────

def documentos_do_registro():
    """
    Pasta Documentos real, lida do registro do Windows.

    Precisa ser a primeira tentativa: quando o OneDrive assume a pasta
    Documentos, o caminho vira algo como D:\\OneDrive\\Documentos e o
    C:\\Users\\<nome>\\Documents costuma continuar existindo com restos de
    instalacao antiga. Adivinhar pelo nome acerta a pasta errada; o registro
    tem a resposta certa.
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
            valor, _ = winreg.QueryValueEx(chave, "Personal")
        return os.path.expandvars(valor)
    except Exception:
        return None


def candidatos_userdata():
    """Caminhos onde o 0 A.D. costuma guardar dados do usuario, em ordem de confianca."""
    saidas = []

    documentos = documentos_do_registro()
    if documentos:
        saidas.append(os.path.join(documentos, "My Games", "0ad"))

    home = os.path.expanduser("~")
    bases = [home]
    for var in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        valor = os.environ.get(var)
        if valor:
            bases.append(valor)

    for base in bases:
        for doc in ("Documents", "Documentos"):
            saidas.append(os.path.join(base, doc, "My Games", "0ad"))
        # Alguns OneDrive ja apontam direto para a pasta de documentos.
        saidas.append(os.path.join(base, "My Games", "0ad"))

    # Linux/macOS.
    saidas.append(os.path.join(home, ".local", "share", "0ad"))
    saidas.append(os.path.join(home, "Library", "Application Support", "0ad"))

    return saidas


def achar_userdata(preferido=None):
    if preferido:
        if os.path.isdir(preferido):
            return os.path.abspath(preferido)
        sys.exit(f"[erro] pasta informada em --dir nao existe: {preferido}")

    vistos = set()
    for caminho in candidatos_userdata():
        chave = os.path.normcase(os.path.abspath(caminho))
        if chave in vistos:
            continue
        vistos.add(chave)
        # A pasta 'mods' e a assinatura: 'saves' pode nem existir ainda.
        if os.path.isdir(os.path.join(caminho, "mods")):
            return os.path.abspath(caminho)

    sys.exit(
        "[erro] nao encontrei a pasta de dados do 0 A.D.\n"
        "       Rode de novo apontando o caminho, por exemplo:\n"
        '       python pudim_tradutor.py --dir "D:/OneDrive/Documentos/My Games/0ad"'
    )


# ─── Tradução ─────────────────────────────────────────────────────────────────

def traduzir(texto, destino, origem="auto"):
    """
    Devolve o texto traduzido, ou None se a chamada falhar.

    A resposta do endpoint gtx e um array aninhado; o primeiro elemento e uma
    lista de pedacos e o texto traduzido de cada pedaco e o indice 0. Juntar os
    pedacos importa: frases longas voltam quebradas em varios deles.
    """
    parametros = urllib.parse.urlencode({
        "client": "gtx",
        "sl": origem,
        "tl": destino,
        "dt": "t",
        "q": texto,
    })
    requisicao = urllib.request.Request(
        f"{GTX_URL}?{parametros}",
        headers={"User-Agent": USER_AGENT},
    )

    try:
        with urllib.request.urlopen(requisicao, timeout=HTTP_TIMEOUT) as resposta:
            dados = json.loads(resposta.read().decode("utf-8", "replace"))
    except Exception as erro:
        print(f"  ! falha ao traduzir: {erro}")
        return None

    try:
        pedacos = dados[0]
        return "".join(p[0] for p in pedacos if p and p[0])
    except Exception:
        print("  ! resposta em formato inesperado")
        return None


# ─── Limpeza do texto vindo do jogo ───────────────────────────────────────────

# O chat do 0 A.D. carrega tags de cor no formato [color="255 0 0"]...[/color].
# Mandar isso para o tradutor suja o resultado, entao tiramos antes.
TAGS = re.compile(r"\[/?(?:color|font|icon|imgleft|imgright)[^\]]*\]")


def limpar(texto):
    return TAGS.sub("", texto).strip()


def criar_atalho_area_de_trabalho():
    """
    Cria o atalho do tradutor na area de trabalho, uma vez so.

    A criacao mora em jogar_0ad.py, que ja sabe achar o executavel do jogo (o
    icone do atalho vem de la). O import e feito aqui dentro, e nao no topo do
    arquivo, porque jogar_0ad.py tambem importa este modulo — no topo, os dois
    se importariam em circulo.

    @returns o caminho do atalho criado, ou None se ja existia ou nao deu.
    """
    try:
        import importlib.util
        caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jogar_0ad.py")
        spec = importlib.util.spec_from_file_location("jogar_0ad", caminho)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        return modulo.criar_atalho_do_tradutor()
    except Exception:
        # Nao conseguir criar um atalho de conveniencia nao pode impedir o
        # tradutor de funcionar.
        return None


def normalizar_idioma(codigo):
    """
    Converte o codigo de idioma do jogo para o formato do tradutor.

    O 0 A.D. escreve locale com underscore ("pt_BR"); o Google espera hifen
    ("pt-BR"). Ambos aceitam a forma curta ("pt"), que e o que o mod costuma
    mandar — a conversao so garante que a forma longa tambem funcione.

    Devolve None quando nao ha codigo, para o chamador cair no padrao.
    """
    if not codigo:
        return None
    return str(codigo).strip().replace("_", "-")


# ─── Arquivos de cache e resposta ─────────────────────────────────────────────

def ler_json(caminho, padrao):
    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except Exception:
        return padrao


def gravar_json_atomico(caminho, dados):
    """
    Grava num arquivo temporario e so entao renomeia por cima do definitivo.

    Sem isso o jogo consegue ler o arquivo pela metade — ele fica lendo em loop
    e a chance de pegar uma escrita no meio e real. os.replace e atomico no
    Windows e no Linux.
    """
    gravar_bytes_atomico(caminho, json.dumps(dados, ensure_ascii=False).encode("utf-8"))


def gravar_bytes_atomico(caminho, bruto):
    temporario = caminho + ".tmp"
    with open(temporario, "wb") as arquivo:
        arquivo.write(bruto)
    os.replace(temporario, caminho)


def gravar_resposta(caminho, respostas, vivo):
    """
    Grava a resposta SEMPRE com o mesmo tamanho em bytes, completando com
    espacos ate TAMANHO_RESPOSTA.

    Isto nao e capricho. O VFS do 0 A.D. guarda o tamanho do arquivo de quando
    indexou a pasta; quando o arquivo cresce, a leitura para no tamanho antigo e
    o jogo recebe o JSON cortado no meio — "JSON.parse: unterminated string".
    Com tamanho fixo, o valor guardado nunca fica errado.

    Espaco depois do JSON e valido: JSON.parse ignora espaco em branco no fim.

    Se as traducoes nao couberem, as mais antigas sao descartadas. O jogo guarda
    em memoria tudo o que ja recebeu, entao perder as antigas daqui nao apaga
    nada da tela — e o que ainda estiver pendente vai ser pedido de novo.
    """
    itens = list(respostas.items())

    while True:
        bruto = json.dumps({"done": dict(itens), "vivo": vivo},
                           ensure_ascii=False).encode("utf-8")
        if len(bruto) <= TAMANHO_RESPOSTA or not itens:
            break
        # Descarta um quarto dos mais antigos por vez, para nao ficar tentando
        # um item de cada vez num arquivo grande.
        itens = itens[max(1, len(itens) // 4):]

    if len(bruto) > TAMANHO_RESPOSTA:
        # So acontece se uma unica traducao for gigante; melhor mandar vazio do
        # que mandar cortado.
        bruto = json.dumps({"done": {}, "vivo": vivo}).encode("utf-8")

    gravar_bytes_atomico(caminho, bruto + b" " * (TAMANHO_RESPOSTA - len(bruto)))


def podar_cache(cache):
    """Mantem o cache num tamanho sensato, descartando o comeco (mais antigo)."""
    if len(cache) <= CACHE_MAX:
        return cache
    chaves = list(cache.keys())[-CACHE_MAX:]
    return {chave: cache[chave] for chave in chaves}


# ─── Laço principal ───────────────────────────────────────────────────────────

def main():
    # O console do Windows costuma abrir em cp1252. Sem isto, imprimir uma
    # traducao com acento levanta UnicodeEncodeError e derruba o tradutor.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    analisador = argparse.ArgumentParser(
        description="Traduz o chat do 0 A.D. para o PudimTranslate."
    )
    analisador.add_argument("--dir", help="Pasta de dados do 0 A.D. (onde ficam mods/ e saves/)")
    analisador.add_argument("--to", default="pt", help="Idioma de destino (padrao: pt)")
    analisador.add_argument("--from", dest="origem", default="auto",
                            help="Idioma de origem (padrao: auto)")
    analisador.add_argument("--sem-atalho", action="store_true",
                            help="Nao criar o atalho na area de trabalho")
    argumentos = analisador.parse_args()

    userdata = achar_userdata(argumentos.dir)
    pasta = os.path.join(userdata, SUBDIR)
    os.makedirs(pasta, exist_ok=True)

    caminho_req = os.path.join(pasta, REQ_FILE)
    caminho_res = os.path.join(pasta, RES_FILE)
    caminho_cache = os.path.join(pasta, CACHE_FILE)

    cache = ler_json(caminho_cache, {})
    respostas = ler_json(caminho_res, {}).get("done", {})
    # O cache de disco alimenta a resposta: reiniciar o tradutor no meio de uma
    # partida nao pode fazer o jogo perder o que ja tinha sido traduzido.
    for chave, valor in cache.items():
        respostas.setdefault(chave, valor)

    print("PudimTranslate — tradutor de chat")
    print(f"  pasta do jogo : {userdata}")
    print(f"  ponte         : {pasta}")
    print(f"  idioma destino: {argumentos.to} (o jogo pode pedir outro)")
    print(f"  cache         : {len(cache)} frase(s) ja conhecidas")

    if not argumentos.sem_atalho:
        atalho = criar_atalho_area_de_trabalho()
        if atalho:
            print()
            print(f"  Atalho pronto na sua area de trabalho: {os.path.basename(atalho)}")
            print("  Use ele para jogar: abre o tradutor e o 0 A.D. juntos, na ordem certa.")

    print()
    print("  Deixe esta janela aberta enquanto joga. Ctrl+C para sair.")
    print("  Se o 0 A.D. ja estiver aberto, feche e abra de novo — o jogo so")
    print("  enxerga a ponte se ela existir quando ele inicia.\n")

    # Deixa um res.json valido no lugar ja na largada. O mod precisa que o
    # arquivo exista antes de tentar ler.
    gravar_resposta(caminho_res, respostas, int(time.time()))

    ultima_modificacao = 0
    ultimo_sinal = 0
    ultimo_destino = None

    while True:
        try:
            agora = time.time()

            # Sinal de vida a cada 5s: e assim que o mod sabe que o tradutor
            # esta ligado e pode mostrar o botao habilitado.
            if agora - ultimo_sinal >= 5:
                gravar_resposta(caminho_res, respostas, int(agora))
                ultimo_sinal = agora

            try:
                modificacao = os.path.getmtime(caminho_req)
            except OSError:
                time.sleep(POLL_SECONDS)
                continue

            if modificacao == ultima_modificacao:
                time.sleep(POLL_SECONDS)
                continue

            ultima_modificacao = modificacao
            pedido = ler_json(caminho_req, None)
            if not pedido or not isinstance(pedido.get("items"), list):
                time.sleep(POLL_SECONDS)
                continue

            # O idioma vem no pedido, escolhido pelo jogo — quem sabe em que
            # lingua o 0 A.D. esta rodando e ele, nao este programa. O --to so
            # vale quando o pedido nao diz nada (mod antigo, ou teste manual).
            destino = normalizar_idioma(pedido.get("to")) or argumentos.to

            novidade = False
            for item in pedido["items"]:
                chave = str(item.get("id", ""))
                texto = limpar(str(item.get("text", "")))
                if not chave or not texto or chave in respostas:
                    continue

                # O idioma so e anunciado quando ha traducao de verdade para
                # fazer. Anunciar a cada pedido lido confundia: um req.json
                # parado de uma sessao anterior fazia o programa dizer um idioma
                # que ninguem tinha pedido agora.
                if destino != ultimo_destino:
                    print(f"  traduzindo para: {destino}")
                    ultimo_destino = destino

                print(f"  > {texto}")
                traduzido = traduzir(texto, destino, argumentos.origem)
                if traduzido is None:
                    continue

                print(f"  < {traduzido}")
                respostas[chave] = traduzido
                cache[chave] = traduzido
                novidade = True

            if novidade:
                cache = podar_cache(cache)
                gravar_json_atomico(caminho_cache, cache)
                gravar_resposta(caminho_res, respostas, int(time.time()))
                ultimo_sinal = time.time()

            time.sleep(POLL_SECONDS)

        except KeyboardInterrupt:
            print("\nEncerrando. Ate a proxima partida.")
            gravar_json_atomico(caminho_cache, podar_cache(cache))
            return 0
        except Exception as erro:
            # Um erro inesperado nao pode derrubar o tradutor no meio do jogo.
            print(f"  ! erro no laco principal: {erro}")
            time.sleep(1)


if __name__ == "__main__":
    sys.exit(main())
