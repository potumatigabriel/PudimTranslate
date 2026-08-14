/**
 * PudimTranslate — textos do mod em inglês e português.
 *
 * Fica em gui/common/ porque as três telas onde o mod atua declaram
 * <script directory="gui/common/"/>: sessão, lobby e configuração da partida.
 * Assim existe um dicionário só, e não um por tela.
 *
 * A detecção de idioma aqui é direta — Engine.GetCurrentLocale devolve o locale
 * do jogo e GetLocaleLanguage o reduz a "pt". Não precisa da sondagem por
 * palavras traduzidas que o PudimMod faz: aquele código nasceu antes de esta
 * API estar em uso no mod.
 */

var g_PudimTrLocale = null;

/**
 * "pt" quando o 0 A.D. está em português, "en" em qualquer outro caso.
 *
 * Note que isto é o idioma dos textos DO MOD (tooltips, avisos), não o idioma
 * para o qual o chat é traduzido — esse é o locale completo do jogo e sai de
 * pudim_TrIdiomaDestino, em pudimtr_bridge.js.
 */
function pudimtr_Lang()
{
	if (g_PudimTrLocale)
		return g_PudimTrLocale;

	try {
		const idioma = Engine.GetLocaleLanguage(Engine.GetCurrentLocale());
		if (idioma)
			g_PudimTrLocale = idioma.toLowerCase().indexOf("pt") === 0 ? "pt" : "en";
	} catch (e) {
		// Sem cache do negativo: se a consulta falhar agora, a próxima chamada
		// tenta de novo em vez de travar em inglês para sempre.
	}

	return g_PudimTrLocale || "en";
}

/**
 * Cada entrada é [inglês, português].
 */
const PUDIMTR_STRINGS = {
	// Tooltips da fala clicável, na sessão
	"click":      ["Click to translate this message.", "Clique para traduzir esta fala."],
	"original":   ["Original:", "Original:"],
	"back":       ["Click to see the original text.", "Clique para ver o texto original."],
	"sent":       ["Request sent to the translator.", "Pedido enviado ao tradutor."],
	"offline":    ["The translator is not running.", "O tradutor não está rodando."],
	"offlineHow": ["Run tools/PudimTradutor.bat in the mod folder, then click again.",
	               "Execute tools/PudimTradutor.bat na pasta do mod e clique de novo."],

	// Avisos curtos, mostrados dentro da própria linha do chat
	"working":     ["translating…", "traduzindo…"],
	"offlineShort":["translator off — run tools/PudimTradutor.bat",
	                "tradutor desligado — rode tools/PudimTradutor.bat"]
};

/**
 * Texto no idioma ativo. Devolve a própria chave se ela não existir no
 * dicionário, para o problema ficar visível em vez de virar string vazia.
 */
function pudimtr_T(chave)
{
	const entrada = PUDIMTR_STRINGS[chave];
	if (!entrada)
		return chave;

	return pudimtr_Lang() === "pt" ? entrada[1] : entrada[0];
}
