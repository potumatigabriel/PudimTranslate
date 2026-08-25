# -*- coding: utf-8 -*-
"""
As duas implementacoes do tradutor tem de andar juntas.

Existem duas de proposito: PudimTradutor.bat prefere a de PowerShell, porque ela
vem de fabrica no Windows e ninguem precisa instalar nada, e cai na de Python se
o PowerShell nao estiver disponivel. No Linux e no macOS a ordem se inverte.

O custo disso apareceu em 24/08. O tratamento do 429 foi escrito so em
pudim_tradutor.py; o jogador roda a de PowerShell, entao para ele nada mudou —
e a evidencia era sutil, porque a mensagem de erro vinha em portugues
("O servidor remoto retornou um erro: (429)"), formato do .NET, e nao no formato
do urllib. Meia hora de diagnostico para descobrir que a correcao estava no
arquivo errado.

Este teste existe para isso nao se repetir: toda correcao de comportamento
precisa entrar NAS DUAS, e aqui e onde o esquecimento aparece.

Rodar:  python tools/test_paridade.py
"""
import io
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
PY = io.open(os.path.join(AQUI, "pudim_tradutor.py"), encoding="utf-8").read()
PS = io.open(os.path.join(AQUI, "pudimtr_comum.ps1"), encoding="utf-8-sig").read()
PS_LOOP = io.open(os.path.join(AQUI, "PudimTradutor.ps1"), encoding="utf-8-sig").read()

falhas = 0


def check(nome, cond, extra=None):
    global falhas
    if cond:
        print("  ok   " + nome)
        return
    falhas += 1
    print("  FAIL " + nome + ("  ->  " + str(extra) if extra is not None else ""))


def num(texto, padrao, rot):
    m = re.search(padrao, texto)
    if not m:
        check("achou " + rot, False, padrao)
        return None
    return float(m.group(1))


print("paridade entre as duas implementacoes")

# ── 1. Constantes de comportamento iguais nos dois lados ───────────────────────
pares = [
    ("tamanho fixo da resposta",
     r"TAMANHO_RESPOSTA\s*=\s*(\d+)", r"TamanhoResposta\s*=\s*(\d+)"),
    ("intervalo minimo entre chamadas",
     r"INTERVALO_MIN_CHAMADA\s*=\s*([\d.]+)", r"IntervaloMinChamada\s*=\s*([\d.]+)"),
    ("recuo inicial do 429",
     r"RECUO_INICIAL\s*=\s*([\d.]+)", r"RecuoInicial\s*=\s*([\d.]+)"),
    ("teto do recuo",
     r"RECUO_MAXIMO\s*=\s*([\d.]+)", r"RecuoMaximo\s*=\s*([\d.]+)"),
]
for rot, rpy, rps in pares:
    a, b = num(PY, rpy, rot + " (py)"), num(PS, rps, rot + " (ps)")
    check(rot + " bate nos dois", a is not None and a == b, "py=%s ps=%s" % (a, b))

# ── 2. Comportamentos que so existem se estiverem nos dois ─────────────────────
comportamentos = [
    ("trata o 429 separado dos outros erros",
     r"429", r"429"),
    ("recuo dobra ate um teto, POR PORTA",
     r"min\(RECUO_MAXIMO, _ritmo\[.recuo.\]\[cliente\] \* 2\)",
     r"\[Math\]::Min\(\$script:RecuoMaximo, \$script:Recuo\[\$cliente\] \* 2\)"),
    ("sucesso zera o recuo daquela porta",
     r"_ritmo\[.recuo.\]\[cliente\] = RECUO_INICIAL",
     r"\$script:Recuo\[\$cliente\] = \$script:RecuoInicial"),
    ("as tres portas do Google estao listadas",
     r'GTX_CLIENTES = \("gtx", "at", "dict-chrome-ex"\)',
     r'\$script:GtxClientes = @\("gtx", "at", "dict-chrome-ex"\)'),
    ("um 429 bloqueia SO aquela porta e a tentativa segue na proxima",
     r'_ritmo\["bloqueado_ate"\]\[cliente\] = time\.time\(\)[\s\S]{0,600}?continue',
     r'\$script:BloqueadoAte\[\$cliente\] = \(Get-Date\)[\s\S]{0,900}?continue'),
    ("o recuo e por porta, nao global",
     r'"bloqueado_ate": \{c: 0\.0 for c in GTX_CLIENTES\}',
     r'\$script:BloqueadoAte = @\{\}'),
    # Durante a pausa nao se toca no GOOGLE. O plano B pode ser chamado — e o
    # motivo de ele existir — entao a propriedade certa e que a checagem de pausa
    # venha ANTES de montar a URL do gtx, e que a funcao retorne ali.
    ("porta em recuo e pulada antes de montar a chamada",
     r'if _ritmo\["bloqueado_ate"\]\[cliente\] > time\.time\(\):[\s\S]{0,60}?continue',
     r'if \(\$script:BloqueadoAte\[\$cliente\] -gt \(Get-Date\)\) \{ continue \}'),
    ("respeita o intervalo minimo antes de chamar",
     r"INTERVALO_MIN_CHAMADA - \(time\.time\(\)", r"\$desde -lt \$script:IntervaloMinChamada"),
    ("reescreve a resposta no lugar, sem trocar a entrada de diretorio",
     r"def gravar_bytes_no_lugar", r"function Write-PudimBytesNoLugar"),
    ("cai no replace quando o tamanho nao bate",
     r"if os\.path\.getsize\(caminho\) != len\(bruto\)", r"if \(\$info\.Length -ne \$Bytes\.Length\)"),
]
for rot, rpy, rps in comportamentos:
    tpy, tps = bool(re.search(rpy, PY)), bool(re.search(rps, PS))
    check(rot, tpy and tps, "py=%s ps=%s" % (tpy, tps))

# ── 3. O laco principal dos dois sai cedo durante a pausa ──────────────────────
# O laco NAO pode mais sair cedo na pausa: quem resolve ali e o plano B, dentro da
# funcao de traducao. Sair antes tornava o plano B codigo morto — foi o que aconteceu
# em 24/08, com as duas mudancas do mesmo dia se anulando.
check("o laco Python NAO abandona o ciclo durante a pausa",
      "if em_pausa() and time.time() - ultimo_sinal" in PY)
check("o laco PowerShell NAO abandona o ciclo durante a pausa",
      re.search(r"\$pausa -gt 0 -and \(\(Get-Date\) - \$ultimoSinal\)", PS_LOOP) is not None)
check("nenhum dos dois abandona o ciclo logo apos detectar a pausa",
      not re.search(r"if em_pausa\(\):[\s\S]{0,300}?continue\b", PY) and
      not re.search(r"if \(\$pausa -gt 0\) \{[\s\S]{0,400}?continue", PS_LOOP))

# ── 4. O 429 e reconhecido pelo CODIGO, nunca pelo texto ───────────────────────
# A mensagem do .NET vem traduzida para o idioma do Windows, entao comparar
# string quebraria em qualquer maquina que nao esteja em ingles.
check("PowerShell le o codigo de status, nao a mensagem",
      re.search(r"\[int\]\s*\$_\.Exception\.Response\.StatusCode", PS) is not None)
check("Python usa HTTPError.code, nao a mensagem",
      re.search(r"erro\.code == 429", PY) is not None)
# So o CODIGO conta: a frase aparece em comentario explicando o problema, e isso
# nao e comparacao. O que nao pode e um if em cima da mensagem.
def sem_comentario(txt, marca):
    return "\n".join(l for l in txt.split("\n")
                     if not l.lstrip().startswith(marca))
check("nenhum dos dois compara o texto do erro",
      "Too Many Requests" not in sem_comentario(PY, "#") and
      "Too Many Requests" not in sem_comentario(PS, "#"))

# ── 4b. Plano B e log: adicionados em 24/08, tem de existir nos dois ───────────
extras = [
    ("plano B pela MyMemory",
     r"MYMEMORY_URL\s*=", r"\$script:UrlMyMemory\s*="),
    ("plano B so aceita traducao de MAQUINA (created-by MT!)",
     r'created-by"\)\) == "MT!"', r'"created-by" -eq "MT!"'),
    ("o plano B entra so com TODAS as portas em recuo",
     r"alternativa = traduzir_plano_b\(texto, destino, origem\)",
     r"\$alternativa = Invoke-PudimPlanoB -Texto \$Texto"),
    ("log de erros com corte nas ultimas linhas",
     r"LOG_MAX_LINHAS\s*=\s*500", r"\$script:LogMaxLinhas\s*=\s*500"),
    ("o 429 vai para o log, com a porta e o tamanho do texto",
     r'registrar\("429 na porta %s', r'Write-PudimLog \("429 na porta \{0\}'),
    ("o log nunca derruba o tradutor",
     r"except Exception:[\s\S]{0,20}?pass", r"\} catch \{ \}"),
]
for rot, rpy, rps in extras:
    tpy, tps = bool(re.search(rpy, PY)), bool(re.search(rps, PS))
    check(rot, tpy and tps, "py=%s ps=%s" % (tpy, tps))

# ── 4c. Dicionario de bolso: idem, tem de existir nos dois ────────────────────
# Ele nao e enfeite: e o unico caminho que funciona com a rede fora, e e o que acerta as
# girias. Se ele existir so num lado, metade dos jogadores fica sem.
dicionario = [
    ("le o mesmo arquivo de dicionario",
     r'DICIONARIO_ARQUIVO = "pudimtr_dicionario\.json"',
     r'\$script:ArqDicionario = "pudimtr_dicionario\.json"'),
    ("busca gulosa do maior grupo para o menor",
     r"for tam in range\(min\(DIC_MAX_PALAVRAS", r"for \(\$tam = \$maxTam; \$tam -ge 1; \$tam--\)"),
    ("normaliza tirando acento e pontuacao",
     r"def _dic_normalizar", r"function Get-PudimPalavraNormalizada"),
    ("descobre a origem testando os tres idiomas",
     r'for idioma in \("en", "pt", "es"\):[\s\S]{0,200}?if idioma == destino',
     r'foreach \(\$idioma in @\("en", "pt", "es"\)\) \{[\s\S]{0,200}?if \(\$idioma -eq \$dest\)'),
    ("devolve a pontuacao final colada na palavra traduzida",
     r"cauda = ultimo\[-1\] \+ cauda", r"\$cauda = \$ultimo\[-1\] \+ \$cauda"),
    ("o atalho offline vem ANTES das portas do Google",
     r"pronto = traduzir_offline_completo\(texto, destino\)[\s\S]{0,200}?for cliente in GTX_CLIENTES",
     r"\$pronto = Invoke-PudimDicionarioCompleto[\s\S]{0,260}?foreach \(\$cliente in \$script:GtxClientes\)"),
    ("e o dicionario parcial e o ultimo recurso, depois do plano B",
     r"alternativa = traduzir_plano_b[\s\S]{0,900}?parcial, n, total = traduzir_pelo_dicionario",
     r"Invoke-PudimPlanoB[\s\S]{0,600}?\$parcial = Invoke-PudimDicionario "),
    ("o plano C exige ao menos uma palavra reconhecida",
     r"if n > 0:", r"if \(\$parcial\.traduzidas -gt 0\)"),
]
for rot, rpy, rps in dicionario:
    tpy, tps = bool(re.search(rpy, PY)), bool(re.search(rps, PS))
    check(rot, tpy and tps, "py=%s ps=%s" % (tpy, tps))

check("o limite do atalho e o mesmo nos dois",
      num(PY, r"DIC_MAX_ATALHO = (\d+)", "atalho (py)") ==
      num(PS, r"\$script:DicMaxAtalho = (\d+)", "atalho (ps)"))
check("o tamanho maximo da forma composta e o mesmo nos dois",
      num(PY, r"DIC_MAX_PALAVRAS = (\d+)", "grupo (py)") ==
      num(PS, r"\$script:DicMaxPalavras = (\d+)", "grupo (ps)"))

# ── 4d. Vocabulario geral do WikDict ──────────────────────────────────────────
wikdict = [
    ("le a mesma pasta de dicionarios",
     r'WIKDICT_PASTA = "dicionario"', r'\$script:WikdictPasta = "dicionario"'),
    ("carrega SO a direcao pedida, sob demanda",
     r"def carregar_wikdict\(origem, destino\)", r"function Import-PudimWikdict"),
    ("descomprime gzip",
     r"gzip\.open\(caminho", r"GzipStream"),
    ("minusculo na saida quando a chave era minuscula",
     r"v\.lower\(\) if k == k\.lower\(\) else v",
     r"if \(\$p\.Name -ceq \$p\.Name\.ToLowerInvariant\(\)\)"),
    ("a giria e consultada ANTES do vocabulario geral",
     r"if chave and chave in tabela:[\s\S]{0,200}?elif tam == 1 and chave and chave in geral:",
     r"if \(\$chave -and \$tabela\.ContainsKey\(\$chave\)\) \{[\s\S]{0,300}?\} elseif \(\$tam -eq 1"),
    ("o vocabulario geral SO entra com a flag ligada",
     r"carregar_wikdict\(idioma, destino\) if usar_geral else \{\}",
     r"if \(\$UsarGeral\) \{ Import-PudimWikdict"),
    ("e o plano C e quem liga",
     r"traduzir_pelo_dicionario\(texto, destino, usar_geral=True\)",
     r"Invoke-PudimDicionario -Texto \$Texto -Destino \$Destino -UsarGeral \$true"),
    ("texto ja no idioma de destino nao e traduzido",
     r"TEXTO QUE JA ESTA NO IDIOMA DE DESTINO",
     r"TEXTO QUE JA ESTA NO IDIOMA DE DESTINO"),
    ("e existe a funcao de vocabulario do idioma",
     r"def vocabulario_do_idioma", r"function Get-PudimVocabulario"),
    ("avisa que a carga demora",
     r"carregando vocabulario geral", r"carregando vocabulario geral"),
]
for rot, rpy, rps in wikdict:
    tpy, tps = bool(re.search(rpy, PY)), bool(re.search(rps, PS))
    check(rot, tpy and tps, "py=%s ps=%s" % (tpy, tps))

# Os dados tem licenca diferente da do mod; o aviso tem de estar no repositorio.
import os
_attr = os.path.join(AQUI, "dicionario", "ATTRIBUTION.md")
check("a atribuicao do WikDict acompanha os dados", os.path.isfile(_attr))

check("o limite de 500 linhas e o mesmo nos dois",
      re.search(r"LOG_MAX_LINHAS\s*=\s*(\d+)", PY).group(1) ==
      re.search(r"\$script:LogMaxLinhas\s*=\s*(\d+)", PS).group(1))

# ── 5. Os dois falam a mesma coisa na tela ─────────────────────────────────────
# O jogador le a janela do tradutor; a mensagem nao pode depender de qual
# implementacao a maquina escolheu.
for frase in ("limitada (429)", "tentando a proxima", "(plano B)", "(dicionario)"):
    npy = PY.count(frase)
    nps = PS.count(frase) + PS_LOOP.count(frase)
    check('a frase "%s" existe nos dois' % frase[:34], npy >= 1 and nps >= 1,
          "py=%d ps=%d" % (npy, nps))

# ── 6. E o lembrete esta escrito nos dois arquivos ─────────────────────────────
for nome, texto in (("pudim_tradutor.py", PY), ("pudimtr_comum.ps1", PS)):
    check(nome + " avisa que a correcao vai nas duas",
          "test_paridade" in texto or "nas duas implementacoes" in texto.lower())

print("\nTODOS OS TESTES PASSARAM" if falhas == 0 else "\n%d TESTE(S) FALHARAM" % falhas)
sys.exit(0 if falhas == 0 else 1)
