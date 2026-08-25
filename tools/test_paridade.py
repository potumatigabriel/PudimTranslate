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
    ("recuo dobra ate um teto",
     r"min\(RECUO_MAXIMO,\s*_ritmo\[.recuo.\]\s*\*\s*2\)",
     r"\[Math\]::Min\(\$script:RecuoMaximo,\s*\$script:Recuo\s*\*\s*2\)"),
    ("sucesso zera o recuo",
     r"_ritmo\[.recuo.\]\s*=\s*RECUO_INICIAL", r"\$script:Recuo\s*=\s*\$script:RecuoInicial"),
    # Durante a pausa nao se toca no GOOGLE. O plano B pode ser chamado — e o
    # motivo de ele existir — entao a propriedade certa e que a checagem de pausa
    # venha ANTES de montar a URL do gtx, e que a funcao retorne ali.
    ("a pausa e checada antes de montar a chamada ao Google",
     r"if em_pausa\(\):[\s\S]{0,200}?return alternativa[\s\S]{0,600}?GTX_URL",
     r"if \(\(Get-PudimPausa\) -gt 0\) \{[\s\S]{0,300}?return \$alternativa[\s\S]{0,600}?\$script:UrlGtx"),
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
check("o laco Python sai cedo na pausa", "if em_pausa():" in PY and "continue" in PY)
check("o laco PowerShell sai cedo na pausa",
      re.search(r"\$pausa = Get-PudimPausa[\s\S]{0,800}?continue", PS_LOOP) is not None)

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
    ("o plano B entra quando o Google esta em recuo",
     r"if em_pausa\(\):[\s\S]{0,40}?alternativa = traduzir_plano_b",
     r"if \(\(Get-PudimPausa\) -gt 0\) \{[\s\S]{0,60}?\$alternativa = Invoke-PudimPlanoB"),
    ("log de erros com corte nas ultimas linhas",
     r"LOG_MAX_LINHAS\s*=\s*500", r"\$script:LogMaxLinhas\s*=\s*500"),
    ("o 429 vai para o log, com o tamanho do texto",
     r'registrar\("429 do Google', r'Write-PudimLog \("429 do Google'),
    ("o log nunca derruba o tradutor",
     r"except Exception:[\s\S]{0,20}?pass", r"\} catch \{ \}"),
]
for rot, rpy, rps in extras:
    tpy, tps = bool(re.search(rpy, PY)), bool(re.search(rps, PS))
    check(rot, tpy and tps, "py=%s ps=%s" % (tpy, tps))

check("o limite de 500 linhas e o mesmo nos dois",
      re.search(r"LOG_MAX_LINHAS\s*=\s*(\d+)", PY).group(1) ==
      re.search(r"\$script:LogMaxLinhas\s*=\s*(\d+)", PS).group(1))

# ── 5. Os dois falam a mesma coisa na tela ─────────────────────────────────────
# O jogador le a janela do tradutor; a mensagem nao pode depender de qual
# implementacao a maquina escolheu.
for frase in ("Google limitou o ritmo", "aguardando o limite do Google passar", "(plano B)"):
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
