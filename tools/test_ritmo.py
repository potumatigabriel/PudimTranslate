# -*- coding: utf-8 -*-
"""
Testa o controle de ritmo das chamadas ao Google.

Relato de 19/08: "pudim translator nao esta funcionando". Ele estava rodando,
achava os pedidos e tentava traduzir; toda chamada voltava

    ! falha ao traduzir: HTTP Error 429: Too Many Requests

O endpoint gtx e gratuito e limita por IP. O problema nao era o primeiro 429 —
era o que vinha depois: sem nenhum tratamento, a frase continuava pendente e o
laco tentava de novo a cada POLL_SECONDS (0,3 s). Tres chamadas por segundo
MANTEM o bloqueio de pe em vez de esperar ele passar.

Rodar:  python tools/test_ritmo.py
"""
import os
import sys
import time
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pudim_tradutor as tr

falhas = 0


def check(nome, cond, extra=None):
    global falhas
    if cond:
        print("  ok   " + nome)
        return
    falhas += 1
    print("  FAIL " + nome + ("  ->  " + str(extra) if extra is not None else ""))


def zerar(recuo=None):
    tr._ritmo.update({
        "ultima_chamada": 0.0,
        "bloqueado_ate": 0.0,
        "recuo": tr.RECUO_INICIAL if recuo is None else recuo,
    })


def responder_429(*a, **k):
    raise urllib.error.HTTPError("u", 429, "Too Many Requests", None, None)


class RespostaFalsa:
    """Imita o formato do gtx: array aninhado, texto traduzido no indice 0."""
    def __init__(self, bruto):
        self.bruto = bruto

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.bruto


# O log NAO pode ser o de producao: as primeiras entradas do log real de 24/08 eram
# deste teste ("texto (2 ch): oi", "rede caiu"), e elas atrapalham quem for diagnosticar
# um problema de verdade.
import tempfile
tr.LOG_ARQUIVO = os.path.join(tempfile.mkdtemp(prefix="pudimtr_"), "log.txt")

print("ritmo das chamadas ao Google")

original_urlopen = tr.urllib.request.urlopen
# O plano B usa a mesma urlopen, entao os stubs abaixo ja o cobrem; onde ele
# atrapalharia a medicao, e trocado por um duble explicito.

# ── 1. O primeiro 429 abre a pausa ─────────────────────────────────────────────
tr.urllib.request.urlopen = responder_429
zerar()
check("comeca sem pausa", tr.em_pausa() == 0)
check("429 devolve None (a frase segue pendente)", tr.traduzir("oi", "pt") is None)
check("entra em pausa depois do 429", tr.em_pausa() > tr.RECUO_INICIAL - 1,
      round(tr.em_pausa(), 1))
check("o recuo dobra para a proxima vez", tr._ritmo["recuo"] == 2 * tr.RECUO_INICIAL,
      tr._ritmo["recuo"])

# ── 2. O ponto do bug: durante a pausa nao se toca no GOOGLE ───────────────────
# O plano B PODE ser chamado — e o motivo de existir. O que nao pode e insistir
# no endpoint que acabou de dizer "devagar", que era o que sustentava o bloqueio.
chamadas = {"n": 0}


def contar(*a, **k):
    chamadas["n"] += 1
    raise urllib.error.HTTPError("u", 429, "x", None, None)


tr.urllib.request.urlopen = contar
plano_b_chamado = {"n": 0}
original_plano_b = tr.traduzir_plano_b
tr.traduzir_plano_b = lambda *a, **k: (plano_b_chamado.__setitem__("n", plano_b_chamado["n"] + 1), None)[1]
for _ in range(30):
    tr.traduzir("oi", "pt")
check("em pausa nenhuma chamada ao Google e feita", chamadas["n"] == 0, chamadas["n"])
check("mas o plano B e tentado", plano_b_chamado["n"] == 30, plano_b_chamado["n"])
tr.traduzir_plano_b = original_plano_b

# ── 3. O recuo tem teto — nao vira espera eterna ───────────────────────────────
tr.urllib.request.urlopen = responder_429
zerar(recuo=tr.RECUO_MAXIMO)
tr.traduzir("oi", "pt")
check("o recuo nao passa do teto", tr._ritmo["recuo"] == tr.RECUO_MAXIMO, tr._ritmo["recuo"])
check("e a pausa nunca passa do teto", tr.em_pausa() <= tr.RECUO_MAXIMO + 1,
      round(tr.em_pausa(), 1))

# ── 4. Traducao normal continua funcionando, e zera o recuo ────────────────────
tr.urllib.request.urlopen = lambda *a, **k: RespostaFalsa(
    b'[[["ola","hi",null,null,10]],null,"en"]')
zerar(recuo=80.0)
check("traducao normal funciona", tr.traduzir("hi", "pt") == "ola")
check("sucesso zera o recuo", tr._ritmo["recuo"] == tr.RECUO_INICIAL, tr._ritmo["recuo"])

# Frase longa volta quebrada em pedacos; juntar e o que da a frase inteira.
tr.urllib.request.urlopen = lambda *a, **k: RespostaFalsa(
    b'[[["bom ","good ",null,null,0],["dia","morning",null,null,0]],null,"en"]')
zerar()
check("junta os pedacos de uma frase longa", tr.traduzir("good morning", "pt") == "bom dia")

# ── 5. Intervalo minimo entre chamadas, para nao criar rajada ──────────────────
tr.urllib.request.urlopen = lambda *a, **k: RespostaFalsa(
    b'[[["ola","hi",null,null,10]],null,"en"]')
zerar()
inicio = time.time()
for _ in range(3):
    tr.traduzir("hi", "pt")
gasto = time.time() - inicio
check("tres chamadas respeitam o intervalo minimo",
      gasto >= 2 * tr.INTERVALO_MIN_CHAMADA * 0.9, round(gasto, 2))
check("o intervalo e menor que o poll, para nao atrasar a traducao",
      tr.INTERVALO_MIN_CHAMADA < 1.0, tr.INTERVALO_MIN_CHAMADA)

# ── 6. Outros erros nao podem parar tudo ───────────────────────────────────────
zerar()
tr.urllib.request.urlopen = lambda *a, **k: (_ for _ in ()).throw(
    urllib.error.HTTPError("u", 500, "x", None, None))
tr.traduzir("oi", "pt")
check("erro 500 nao abre pausa", tr.em_pausa() == 0)

zerar()
tr.urllib.request.urlopen = lambda *a, **k: (_ for _ in ()).throw(OSError("rede caiu"))
check("queda de rede devolve None sem explodir", tr.traduzir("oi", "pt") is None)
check("queda de rede nao abre pausa", tr.em_pausa() == 0)

zerar()
tr.urllib.request.urlopen = lambda *a, **k: RespostaFalsa(b"nao e json")
check("resposta invalida devolve None sem explodir", tr.traduzir("oi", "pt") is None)

tr.urllib.request.urlopen = original_urlopen

print("\nTODOS OS TESTES PASSARAM" if falhas == 0 else "\n%d TESTE(S) FALHARAM" % falhas)
sys.exit(0 if falhas == 0 else 1)
