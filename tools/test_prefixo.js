/**
 * Testa a separacao entre quem falou e o que foi falado.
 *
 * Do log de 24/08: a ponte mandou ao tradutor a linha inteira
 *
 *     (Aliado) <Pudim (1584)> going
 *
 * incluindo o rotulo do canal e o apelido. Isso desperdica uma ida a rede, polui a
 * traducao com nome de jogador virando substantivo, e faz a mesma frase dita por duas
 * pessoas contar como duas traducoes diferentes.
 *
 * O apelido ja era removido; faltava o rotulo de canal que vem na frente dele em fala de
 * aliado e privada.
 *
 * Rodar:  node tools/test_prefixo.js
 */
"use strict";
const fs = require("fs");
const path = require("path");

const SRC = fs.readFileSync(
	path.join(__dirname, "..", "gui", "common", "pudimtr_bridge.js"), "utf8");

let fails = 0;
function check(name, cond, extra) {
	if (cond) { console.log("  ok   " + name); return; }
	fails++;
	console.log("  FAIL " + name + (extra !== undefined ? "  →  " + extra : ""));
}

// Extrai as tres expressoes do arquivo real, para o teste medir o que vai para o jogo.
function extrair(nome) {
	const m = SRC.match(new RegExp("const " + nome + " =\\s*(/[\\s\\S]*?/);"));
	if (!m) { console.error("FALHA: nao achei " + nome); process.exit(1); }
	return eval(m[1]);
}
const CARIMBO = extrair("PUDIM_TR_CARIMBO");
const CANAL = extrair("PUDIM_TR_CANAL");
const APELIDO = extrair("PUDIM_TR_APELIDO");

/** Replica de pudim_TrPartes, na mesma ordem do codigo. */
function partes(texto) {
	let resto = texto, prefixo = "";
	for (const re of [CARIMBO, CANAL, APELIDO]) {
		const m = re.exec(resto);
		if (m) { prefixo += m[0]; resto = resto.substr(m[0].length); }
	}
	return { prefixo, dito: resto.trim(), temApelido: APELIDO.test(texto) || prefixo.includes("<") || prefixo.includes(":") };
}

console.log("separacao de prefixo e fala");

// ── Os casos reais que apareceram no log ──────────────────────────────────────────────
const casos = [
	["(Aliado) <Pudim (1584)> going", "going"],
	["(Privado) <kyng (399)> hello there", "hello there"],
	["(Aliado) <Anolddude (1435)> we fight 3 wake up", "we fight 3 wake up"],
	["<Fulano> oi", "oi"],
	["Alice: oi", "oi"],
	["\\[09:38] (Aliado) <Bob> atacar agora", "atacar agora"],
	["\\[09:38] <Bob> atacar agora", "atacar agora"],
];
for (const [entrada, esperado] of casos)
	check(JSON.stringify(entrada.slice(0, 40)) + " -> fala limpa",
		partes(entrada).dito === esperado, JSON.stringify(partes(entrada).dito));

// ── O rotulo de canal nao pode comer fala de verdade ──────────────────────────────────
// Uma frase que COMECA com parenteses e fala, nao rotulo. O limite de 20 caracteres
// dentro dos parenteses e o que separa "(Aliado)" de "(isso aqui e uma frase inteira)".
check("frase que comeca com parenteses longo nao e confundida com canal",
	partes("(essa frase toda esta entre parenteses) oi").dito.startsWith("(essa"),
	JSON.stringify(partes("(essa frase toda esta entre parenteses) oi").dito));
check("mas um rotulo curto e removido", partes("(Time) <Bob> vamos").dito === "vamos");

// ── O prefixo e preservado inteiro, para ser reimpresso ───────────────────────────────
const p = partes("(Aliado) <Pudim (1584)> going");
check("o prefixo guarda canal e apelido juntos",
	p.prefixo === "(Aliado) <Pudim (1584)> ", JSON.stringify(p.prefixo));
check("prefixo + fala reconstroem a linha original",
	p.prefixo + p.dito === "(Aliado) <Pudim (1584)> going");

// ── Aviso do sistema continua sem apelido, logo sem traducao ──────────────────────────
check("aviso do sistema nao tem apelido", !partes("== Fulano entrou.").temApelido);

console.log(fails === 0 ? "\nTODOS OS TESTES PASSARAM" : "\n" + fails + " TESTE(S) FALHARAM");
process.exit(fails === 0 ? 0 : 1);
