# -*- coding: utf-8 -*-
"""
Dicionario de bolso: o tradutor que nunca fica mudo.

Ideia do jogador, em 25/08:

  "talvez o plano B seja ter um pequeno dicionario de palavras de ingles, portugues e
   espanhol... com as palavras mais usadas em jogos online, usando as girias e
   abreviacoes mais comuns e palavras comuns e jargoes... e o cache que salva, seja de
   palavras e nao de frases.. pq ai traduz o que conseguir"

Ele resolve duas coisas diferentes, e vale separar porque so uma e obvia.

A obvia: nao depende de nada. Sem rede, sem cota, sem 429, sem servico de terceiro
continuar existindo. Quando as tres portas do Google estao em recuo e a MyMemory tambem
nao responde, e ele que evita o silencio.

A menos obvia: em GIRIA DE JOGO ele acerta MAIS que o Google. "gg" nao sao duas letras,
e "bom jogo"; "afk", "rax", "eco", "pop", "brb" — o Google devolve lixo nesses. Por isso
ele e consultado ANTES das APIs para frases curtas, e nao so no fim da fila.

E dai vem o cuidado que este teste protege mais de perto: o dicionario nao conjuga, nao
concorda genero e nao reordena. Numa frase com gramatica de verdade ele PERDE feio para o
Google, e como as palavras de ligacao estao nele, uma frase longa pode alcancar 100% de
cobertura e roubar a traducao de quem faria melhor. O limite de palavras do atalho e o
freio disso, e esta cravado aqui.

Rodar:  python tools/test_dicionario.py
"""
import io
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import pudim_tradutor as tr

falhas = 0


def check(nome, cond, extra=None):
    global falhas
    if cond:
        print("  ok   " + nome)
        return
    falhas += 1
    print("  FAIL " + nome + ("  ->  " + str(extra) if extra is not None else ""))


print("dicionario de bolso")

# ── 1. O arquivo existe e tem forma ────────────────────────────────────────────
caminho = os.path.join(AQUI, tr.DICIONARIO_ARQUIVO)
check("o arquivo do dicionario existe", os.path.isfile(caminho), caminho)
dados = json.load(io.open(caminho, encoding="utf-8"))
conceitos = dados.get("conceitos", [])
check("tem conceitos suficientes para um chat de jogo", len(conceitos) >= 200, len(conceitos))

sem_idioma = [i for i, c in enumerate(conceitos)
              if not (c.get("en") and c.get("pt") and c.get("es"))]
check("todo conceito tem os tres idiomas", not sem_idioma, sem_idioma[:5])

vazias = [c for c in conceitos
          if any(not f or not f.strip() for k in ("en", "pt", "es") for f in c.get(k, []))]
check("nenhuma forma vazia", not vazias, len(vazias))

# O arquivo e escrito sem acento de proposito: a normalizacao tira acento, entao uma forma
# acentuada no arquivo seria buscada de um jeito e escrita de outro. So a SAIDA pode ter
# acento — e ela nao tem, porque o chat do jogo e lido em fonte de bitmap e acento as vezes
# some. Manter tudo sem acento evita a pergunta.
acentuadas = [f for c in conceitos for k in ("en", "pt", "es") for f in c[k]
              if any(ord(ch) > 127 for ch in f)]
check("nenhuma forma tem caractere fora do ASCII", not acentuadas, acentuadas[:5])

# ── 2. Carregamento e tabelas ──────────────────────────────────────────────────
d = tr.carregar_dicionario()
check("carrega os conceitos", len(d["conceitos"]) == len(conceitos))
for idioma in ("en", "pt", "es"):
    check("monta a tabela de " + idioma, len(d["formas"][idioma]) > 200,
          len(d["formas"][idioma]))
check("a tabela indexa forma normalizada, sem pontuacao",
      tr._dic_normalizar("Attack!") == "attack", tr._dic_normalizar("Attack!"))
check("e a normalizacao tira acento", tr._dic_normalizar("está") == "esta")
check("carregar duas vezes nao recarrega o arquivo", tr.carregar_dicionario() is d)

# ── 3. As girias, que sao a razao de ele vir ANTES do Google ───────────────────
# Nestes o Google erra: ele traduz "gg" como as duas letras e "afk" ao pe da letra.
girias = [
    ("gg", "pt", "bom jogo"),
    ("gg wp", "pt", "bom jogo bem jogado"),
    ("ty gl hf", "pt", "obrigado boa sorte divirta-se"),
    ("attack blue now", "pt", "ataque azul agora"),
    ("i need wood please", "pt", "preciso madeira por favor"),
    ("bom jogo", "en", "good game"),
]
for frase, destino, esperado in girias:
    saida = tr.traduzir_offline_completo(frase, destino)
    check('"%s" -> "%s"' % (frase, esperado), saida == esperado, saida)

# ── 4. O freio: frase longa NAO pode ser roubada do Google ─────────────────────
# Este e o caso que motivou DIC_MAX_ATALHO. Sao 7 palavras e TODAS estao no dicionario,
# porque as de ligacao (my, are, they) estao la. Sem o limite, a cobertura daria 100% e o
# atalho devolveria "ajuda eles e ataque meu base" no lugar de uma traducao de verdade.
longa = "help me they are attacking my base"
parcial, n, total = tr.traduzir_pelo_dicionario(longa, "pt")
check("a frase longa REALMENTE tem cobertura total (o risco e real)",
      n == total and total == 7, "%d/%d" % (n, total))
check("mas o atalho recusa, porque gramatica pesa mais que giria",
      tr.traduzir_offline_completo(longa, "pt") is None)
check("o limite do atalho e pequeno o bastante para isso",
      tr.DIC_MAX_ATALHO <= 5, tr.DIC_MAX_ATALHO)
check("e grande o bastante para as girias curtas passarem",
      tr.DIC_MAX_ATALHO >= 4, tr.DIC_MAX_ATALHO)

# ── 5. Cobertura parcial: "traduz o que conseguir" ─────────────────────────────
parcial, n, total = tr.traduzir_pelo_dicionario("zxqw nonsense here", "pt")
check("palavra desconhecida fica como veio", "zxqw" in parcial, parcial)
check("mas o que da para traduzir e traduzido", n >= 1 and "aqui" in parcial, parcial)
check("e o total conta todas as palavras", total == 3, total)

check("frase inteiramente desconhecida devolve zero traduzidas",
      tr.traduzir_pelo_dicionario("zxqw plkm vbnm", "pt")[1] == 0)

# ── 6. Detalhes que aparecem no chat de verdade ────────────────────────────────
check("pontuacao no fim volta colada",
      tr.traduzir_pelo_dicionario("attack!", "pt")[0] == "ataque!",
      tr.traduzir_pelo_dicionario("attack!", "pt")[0])
check("maiuscula na entrada nao atrapalha",
      tr.traduzir_offline_completo("GG WP", "pt") == "bom jogo bem jogado")
check("forma composta ganha da simples (good game, nao good + game)",
      tr.traduzir_offline_completo("good game", "pt") == "bom jogo",
      tr.traduzir_offline_completo("good game", "pt"))
check("texto vazio nao explode", tr.traduzir_pelo_dicionario("", "pt")[2] == 0)
check("idioma de destino desconhecido devolve o texto intacto",
      tr.traduzir_pelo_dicionario("gg", "zz")[0] == "gg")
check("traduzir para o proprio idioma nao inventa nada",
      tr.traduzir_pelo_dicionario("bom jogo", "pt")[1] == 0)

# O idioma de origem NAO vem no pedido do jogo, entao ele testa os tres e fica com o que
# reconhece mais. Numa frase de chat isso decide certo praticamente sempre.
check("descobre a origem sozinho: espanhol -> portugues",
      "madeira" in tr.traduzir_pelo_dicionario("necesito madera", "pt")[0],
      tr.traduzir_pelo_dicionario("necesito madera", "pt")[0])
check("descobre a origem sozinho: portugues -> espanhol",
      tr.traduzir_offline_completo("boa sorte", "es") == "buena suerte",
      tr.traduzir_offline_completo("boa sorte", "es"))

# ── 7. Onde ele entra na fila ──────────────────────────────────────────────────
FONTE = io.open(os.path.join(AQUI, "pudim_tradutor.py"), encoding="utf-8").read()
i_atalho = FONTE.index("pronto = traduzir_offline_completo")
i_google = FONTE.index("for cliente in GTX_CLIENTES:")
i_planob = FONTE.index("alternativa = traduzir_plano_b")
i_planoc = FONTE.index("parcial, n, total = traduzir_pelo_dicionario")
check("o atalho vem ANTES do Google", i_atalho < i_google)
check("o Google vem antes do plano B", i_google < i_planob)
check("e o dicionario parcial e o ULTIMO recurso", i_planob < i_planoc)
check("o plano C exige ao menos uma palavra reconhecida",
      "if n > 0:" in FONTE[i_planoc:i_planoc + 400])
check("o plano C diz quantas palavras saiu traduzindo",
      "%d de %d palavras" in FONTE[i_planoc:i_planoc + 400])

print("\nTODOS OS TESTES PASSARAM" if falhas == 0 else "\n%d TESTE(S) FALHARAM" % falhas)
sys.exit(0 if falhas == 0 else 1)
