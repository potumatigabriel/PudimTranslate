# Atribuição e licença dos arquivos `wikdict-*.json.gz`

**Estes arquivos NÃO seguem a licença do resto do PudimTranslate.** O mod é GPL-3.0-or-later;
estes seis arquivos de dados são **CC BY-SA 3.0 Unported**, e continuam sendo ao serem
redistribuídos. Estão numa pasta separada, com este aviso, justamente para a fronteira ficar
óbvia para quem abrir o repositório.

## De onde vieram

    Wiktionary  →  DBnary  →  WikDict  →  estes arquivos

- **Wiktionary** — o conteúdo original, escrito pelos colaboradores do projeto.
  https://www.wiktionary.org/
  Licenciado sob CC BY-SA 4.0 e GFDL (Termos de Uso da Wikimedia, §7).
  https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use

- **DBnary** — extrai o Wiktionary para RDF. CC BY-SA 3.0.
  http://kaiko.getalp.org/about-dbnary/

- **WikDict** — transforma o DBnary em dicionários bilíngues. Os TEI que ele gera carimbam
  CC BY-SA 3.0 Unported.
  https://www.wikdict.com/
  Arquivos de origem: https://download.wikdict.com/dictionaries/sqlite/2/ (snapshot 2026-06-23)

## O que foi modificado

Os dados **foram modificados**, e a licença exige dizer o quê:

1. A origem é o SQLite do WikDict, tabela `simple_translation`, colunas `written_rep` e
   `trans_list`.
2. Foram mantidos **apenas os pares de palavra única → palavra única**. Entradas com mais de
   uma palavra em qualquer lado foram descartadas.
3. De cada entrada foi mantida **somente a primeira tradução** da lista, descartando as demais.
   Isso perde nuance de propósito: o uso aqui é troca palavra por palavra num tradutor de chat
   que só entra em ação quando as APIs falham, e não haveria como escolher entre alternativas
   sem contexto.
4. As chaves foram passadas para minúscula.
5. Convertido de SQLite para JSON e comprimido com gzip.

Nada foi acrescentado, corrigido ou reescrito — o conteúdo restante é o do WikDict.

## O que isto obriga quem redistribuir

Manter este arquivo junto dos dados, manter os créditos acima, continuar indicando que houve
modificação, e manter os arquivos `wikdict-*.json.gz` sob CC BY-SA (3.0 ou posterior). Texto da
licença: https://creativecommons.org/licenses/by-sa/3.0/

## O que NÃO está coberto por isto

`tools/pudimtr_dicionario.json` — o dicionário de gíria de jogo — é obra original do autor do
mod e segue a licença do mod (GPL-3.0-or-later). Ele existe separado por um motivo prático além
do jurídico: **não há fonte livre de gíria de jogo com tradução.** `gg`, `wp`, `afk`, `glhf` têm
verbete no Wiktionary mas sem tabela de tradução útil, e as listas de abreviação de internet que
existem no GitHub ou são minúsculas, ou estão abandonadas desde 2018, ou não declaram licença.
Essa parte é escrita à mão porque não há de onde copiar.
