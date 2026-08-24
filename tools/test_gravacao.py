# -*- coding: utf-8 -*-
"""
Testa a gravacao da resposta do tradutor.

Relato de 19/08, no lobby, em vermelho por cima da tela:

    CVFSFile: file saves/campaigns/pudim_tr_res.json couldn't be opened
    (vfs_load: -110300)
    Failed to load file 'saves/campaigns/pudim_tr_res.json': CVFSFile_LoadFailed

O arquivo estava no disco, com 64 KB. A causa e o os.replace: ele e atomico e
evita leitura pela metade, mas TROCA A ENTRADA DE DIRETORIO, e o VFS do 0 A.D.
guarda a entrada de quando indexou a pasta. Depois do replace ela aponta para um
arquivo que nao existe mais, e o motor imprime o erro dele — que nenhum
try/catch do JS consegue silenciar, porque quem escreve e o C++.

Como a resposta tem sempre o mesmo tamanho, da para reescrever por cima.

Rodar:  python tools/test_gravacao.py
"""
import os
import sys
import json
import tempfile

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


print("gravacao da resposta")

pasta = tempfile.mkdtemp(prefix="pudimtr_")
alvo = os.path.join(pasta, "pudim_tr_res.json")

# ── 1. Primeira gravacao cria o arquivo ────────────────────────────────────────
tr.gravar_resposta(alvo, {"a": "ola"}, 1000)
check("cria o arquivo na primeira gravacao", os.path.exists(alvo))
check("tamanho e sempre TAMANHO_RESPOSTA", os.path.getsize(alvo) == tr.TAMANHO_RESPOSTA,
      os.path.getsize(alvo))
with open(alvo, "r", encoding="utf-8") as f:
    conteudo = f.read()
check("o conteudo e JSON valido apesar do preenchimento", json.loads(conteudo)["done"]["a"] == "ola")

# ── 2. O ponto do bug: a identidade do arquivo nao pode mudar ──────────────────
# E exatamente isto que o VFS do 0 A.D. guarda. os.replace cria um arquivo NOVO e
# troca a entrada de diretorio: o identificador muda e a entrada que o VFS
# indexou passa a apontar para nada. Reescrever por cima mantem o identificador.
# No Windows o st_ino do Python 3 devolve o file index do NTFS, que serve.
antes = os.stat(alvo)
tr.gravar_resposta(alvo, {"a": "ola", "b": "mundo"}, 2000)
depois = os.stat(alvo)
check("o identificador do arquivo NAO muda entre gravacoes",
      (antes.st_ino, antes.st_dev) == (depois.st_ino, depois.st_dev),
      str(antes.st_ino) + " -> " + str(depois.st_ino))
with open(alvo, "r", encoding="utf-8") as f:
    check("e o conteudo novo esta la", json.loads(f.read())["done"].get("b") == "mundo")

# Prova de que o teste acima nao passa por acidente: com os.replace o
# identificador MUDA, que era o comportamento antigo.
alvo2 = os.path.join(pasta, "controle.json")
tr.gravar_bytes_atomico(alvo2, b"x" * 100)
ino1 = os.stat(alvo2).st_ino
tr.gravar_bytes_atomico(alvo2, b"y" * 100)
ino2 = os.stat(alvo2).st_ino
check("(controle) os.replace realmente troca o identificador", ino1 != ino2,
      str(ino1) + " vs " + str(ino2))
os.remove(alvo2)

# ── 3. Nenhum arquivo temporario sobra ao lado ─────────────────────────────────
restos = [n for n in os.listdir(pasta) if n.endswith(".tmp")]
check("nao deixa .tmp para tras", restos == [], restos)
check("so existe um arquivo na pasta", len(os.listdir(pasta)) == 1, os.listdir(pasta))

# ── 4. Tamanho errado no disco volta pelo caminho do replace ───────────────────
with open(alvo, "wb") as f:
    f.write(b"{}")            # arquivo truncado por qualquer motivo
tr.gravar_resposta(alvo, {"c": "recupera"}, 3000)
check("arquivo com tamanho errado e recriado inteiro",
      os.path.getsize(alvo) == tr.TAMANHO_RESPOSTA, os.path.getsize(alvo))
with open(alvo, "r", encoding="utf-8") as f:
    check("e volta a ter conteudo valido", json.loads(f.read())["done"]["c"] == "recupera")

# ── 5. Arquivo inexistente nao levanta excecao ─────────────────────────────────
novo = os.path.join(pasta, "sub", "outro.json")
os.makedirs(os.path.dirname(novo))
try:
    tr.gravar_resposta(novo, {"d": "1"}, 4000)
    check("cria arquivo novo em pasta vazia sem erro", os.path.getsize(novo) == tr.TAMANHO_RESPOSTA)
except Exception as e:
    check("cria arquivo novo em pasta vazia sem erro", False, e)

# ── 6. Resposta grande e podada para caber, sem estourar o tamanho ─────────────
gigante = {str(i): "x" * 200 for i in range(2000)}
tr.gravar_resposta(alvo, gigante, 5000)
check("resposta grande e podada, nunca estoura o tamanho",
      os.path.getsize(alvo) == tr.TAMANHO_RESPOSTA, os.path.getsize(alvo))
with open(alvo, "r", encoding="utf-8") as f:
    dados = json.loads(f.read())
check("e o que sobrou continua sendo JSON valido", isinstance(dados.get("done"), dict))
check("o sinal de vida sobrevive a poda", dados.get("vivo") == 5000)

# ── 7. Acento sobrevive ao ida e volta ─────────────────────────────────────────
tr.gravar_resposta(alvo, {"e": "coração à noite"}, 6000)
with open(alvo, "r", encoding="utf-8") as f:
    check("acentuacao preservada", json.loads(f.read())["done"]["e"] == "coração à noite")

for nome in os.listdir(pasta):
    caminho = os.path.join(pasta, nome)
    if os.path.isfile(caminho):
        os.remove(caminho)

print("\nTODOS OS TESTES PASSARAM" if falhas == 0 else "\n%d TESTE(S) FALHARAM" % falhas)
sys.exit(0 if falhas == 0 else 1)
