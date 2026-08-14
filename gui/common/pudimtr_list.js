/**
 * PudimTranslate — tradução de chat desenhado como lista.
 *
 * Duas telas do 0 A.D. mostram o chat como `type="list"`, um item por fala:
 *
 *   - a lobby multiplayer  (gui/lobby/LobbyPage/Chat/ChatPanel.xml)
 *   - a configuração da partida (gui/gamesetup/Pages/GameSetupPage/Panels/Chat/ChatPanel.xml)
 *
 * As duas têm até uma classe `ChatMessagesPanel` com o mesmo formato — mudando
 * só a assinatura de addText. Como o comportamento que queremos é idêntico, ele
 * mora aqui e cada tela só amarra o gancho, em três linhas.
 *
 * Numa lista não há botão por linha, mas há seleção — então o gesto acaba sendo
 * o mesmo da partida: clicar na fala traduz, clicar de novo devolve o inglês.
 * (Na sessão é diferente: lá cada fala já é um botão de verdade. Veja
 * gui/session/chat/pudimtr_session.js.)
 *
 * A tradução em si vem da ponte em gui/common/pudimtr_bridge.js.
 */

const PUDIM_TR_LISTA_COR = "150 230 150";
const PUDIM_TR_LISTA_COR_AVISO = "170 170 170";

var g_PudimTrLista = {
	/** Texto original de cada item, na mesma ordem da lista. */
	"originais": [],
	/** Índices que estão mostrando a tradução. */
	"traduzidos": {},
	/** Índices com recado na frente: {indice: "esperando"|"semTradutor"}. */
	"avisos": {},
	/** O objeto da lista, guardado quando o painel aparece. */
	"lista": null,
	/** Evita que a reescrita da lista dispare o handler de seleção de novo. */
	"redesenhando": false,
	"ligado": false
};

/**
 * Reescreve a lista inteira a partir dos originais e do que já foi traduzido.
 *
 * Reescrever tudo em vez de trocar um item só é de propósito: a lista da GUI do
 * 0 A.D. não expõe alteração de item individual, e um chat de lobby é pequeno o
 * bastante para isso não pesar.
 */
function pudim_TrListaRedesenhar()
{
	if (!g_PudimTrLista.lista)
		return;

	// Quem estava esperando e já tem tradução em mãos deixa de esperar.
	for (const indice in g_PudimTrLista.avisos)
		if (g_PudimTrLista.avisos[indice] == "esperando" &&
		    pudim_TrObter(pudim_TrPartes(g_PudimTrLista.originais[indice]).dito))
			delete g_PudimTrLista.avisos[indice];

	const itens = g_PudimTrLista.originais.map((original, indice) => {
		const aviso = g_PudimTrLista.avisos[indice];
		if (aviso)
			return original + " [color=\"" + PUDIM_TR_LISTA_COR_AVISO + "\"](" +
				pudimtr_T(aviso == "esperando" ? "working" : "offlineShort") +
				")[/color]";

		if (!g_PudimTrLista.traduzidos[indice])
			return original;

		const partes = pudim_TrPartes(original);
		const pronta = pudim_TrObter(partes.dito);
		if (!pronta)
			return original;

		return partes.prefixo + "[color=\"" + PUDIM_TR_LISTA_COR + "\"]" + pronta + "[/color]";
	});

	g_PudimTrLista.redesenhando = true;
	g_PudimTrLista.lista.list = itens;
	// Deselecionar ao fim é o que permite clicar duas vezes na mesma fala para
	// ir e voltar: uma lista só dispara onSelectionChange quando a seleção
	// muda, e reclicar a linha já selecionada não mudaria nada.
	g_PudimTrLista.lista.selected = -1;
	g_PudimTrLista.redesenhando = false;
}

function pudim_TrListaClicar()
{
	if (g_PudimTrLista.redesenhando || !g_PudimTrLista.lista)
		return;

	const indice = g_PudimTrLista.lista.selected;
	if (indice < 0 || indice >= g_PudimTrLista.originais.length)
		return;

	// Clicar de novo numa fala já traduzida — ou num aviso — devolve o inglês.
	if (g_PudimTrLista.traduzidos[indice] || g_PudimTrLista.avisos[indice])
	{
		delete g_PudimTrLista.traduzidos[indice];
		delete g_PudimTrLista.avisos[indice];
		pudim_TrListaRedesenhar();
		return;
	}

	const partes = pudim_TrPartes(g_PudimTrLista.originais[indice]);

	// Linha sem apelido é aviso do sistema ("== Fulano entrou."), que o jogo já
	// entrega no idioma do jogador. Clicar nela não faz nada.
	if (!partes.dito || !partes.temApelido)
		return;

	if (pudim_TrPedir(partes.dito))
		g_PudimTrLista.traduzidos[indice] = true;
	else if (pudim_TrEstaVivo())
	{
		// A resposta chega pelo ouvinte registrado em pudim_TrListaLigar, que
		// redesenha a lista sozinho.
		g_PudimTrLista.traduzidos[indice] = true;
		g_PudimTrLista.avisos[indice] = "esperando";
	}
	else
		g_PudimTrLista.avisos[indice] = "semTradutor";

	pudim_TrListaRedesenhar();
}

function pudim_TrListaLigar(lista)
{
	if (g_PudimTrLista.ligado)
		return;

	g_PudimTrLista.ligado = true;
	g_PudimTrLista.lista = lista;

	// O laço se pendura no onTick do painel do chat. Na lobby isso é o que faz
	// a resposta do tradutor chegar: lá os setTimeout da GUI não avançam.
	let painel = null;
	try {
		painel = Engine.GetGUIObjectByName("chatPanel");
	} catch (e) {}

	pudim_TrIniciar(painel);
	pudim_TrAoTraduzir(pudim_TrListaRedesenhar);

	// A lista não tinha handler de seleção; se um dia passar a ter, encadeamos
	// em vez de atropelar.
	const anterior = lista.onSelectionChange;
	lista.onSelectionChange = () => {
		if (anterior)
			anterior();
		pudim_TrListaClicar();
	};
}

/**
 * Gancho para as duas telas: chame depois do addText original.
 *
 * @param lista - o objeto GUI da lista de mensagens (chatText).
 */
function pudim_TrListaAoAdicionar(lista)
{
	pudim_TrListaLigar(lista);

	// Só o item recém-adicionado é guardado, nunca a lista inteira: os itens
	// anteriores podem já ter sido reescritos por nós com a tradução no lugar do
	// inglês, e copiá-los de volta perderia o original para sempre. O último
	// item é sempre o texto cru que acabou de chegar — inclusive com carimbo de
	// hora, quando ligado, para o índice bater.
	const itens = lista.list;
	if (itens.length > g_PudimTrLista.originais.length)
		g_PudimTrLista.originais.push(itens[itens.length - 1]);
}

function pudim_TrListaLimpar()
{
	g_PudimTrLista.originais = [];
	g_PudimTrLista.traduzidos = {};
	g_PudimTrLista.avisos = {};
}
