/**
 * PudimTranslate — tradução do chat na sessão de jogo.
 *
 * Como a fala vira botão
 * ----------------------
 * Não foi preciso inventar nada: o ChatOverlay do jogo já trata cada linha do
 * chat como botão. Em gui/session/chat/ChatOverlay.js:55 ele faz
 *
 *     this.chatLines[i].ghost = !chatMessage || !chatMessage.callback;
 *
 * ou seja, basta a mensagem trazer um `callback` para a linha virar clicável e
 * ganhar tooltip. E a linha é dimensionada na largura exata do texto
 * (ChatOverlay.js:42-46), então tornar a fala clicável não cobre o mapa nem
 * rouba clique de unidade — só a área da própria frase responde.
 *
 * Então o "botão traduzir por fala" é a fala em si: clicou, traduziu; clicou de
 * novo, volta ao inglês. Nada de botãozinho extra poluindo a tela.
 *
 * A tradução em si vem da ponte em gui/common/pudimtr_bridge.js, que conversa
 * com tools/pudim_tradutor.py — o JS da GUI do 0 A.D. não tem HTTP.
 *
 * Este arquivo mora em gui/session/chat/ porque session.xml declara
 * <script directory="gui/session/chat/"/>: assim ele carrega depois das classes
 * do chat, que é quando dá para mexer nos protótipos delas.
 */

// ─── Cores ────────────────────────────────────────────────────────────────────

/** Tom esverdeado para a linha traduzida se distinguir do inglês original. */
const PUDIM_TR_COR = "150 230 150";
/** Cinza do aviso de "traduzindo…" e afins. */
const PUDIM_TR_COR_AVISO = "170 170 170";

// ─── Estado ───────────────────────────────────────────────────────────────────

/**
 * Mensagens do overlay que decoramos, para saber quais redesenhar quando a
 * tradução chega. Guardamos o próprio objeto que o ChatOverlay mantém em
 * this.chatMessages — mexer nele e mandar redesenhar basta.
 */
var g_PudimTrLinhas = [];

// ─── Texto da linha ───────────────────────────────────────────────────────────

function pudim_TrPintar(texto, cor)
{
	return "[color=\"" + cor + "\"]" + texto + "[/color]";
}

/**
 * Reescreve a linha conforme o estado dela.
 *
 * Fica sempre em uma linha só. O overlay posiciona as falas por
 * `top = i * altura` (ChatOverlay.js:43), então uma fala de duas linhas
 * empurraria as outras para cima da vizinha. Por isso a tradução substitui o
 * original em vez de aparecer embaixo — e o original fica no tooltip.
 */
function pudim_TrRedesenharLinha(linha)
{
	if (linha.pudimEstado == "traduzido")
	{
		linha.text = linha.pudimPrefixo + pudim_TrPintar(linha.pudimTraducao, PUDIM_TR_COR);
		linha.tooltip = pudimtr_T("original") + " " + linha.pudimTextoLimpo + "\n" +
			pudimtr_T("back");
	}
	else if (linha.pudimEstado == "esperando")
	{
		linha.text = linha.pudimOriginal + " " +
			pudim_TrPintar("(" + pudimtr_T("working") + ")", PUDIM_TR_COR_AVISO);
		linha.tooltip = pudimtr_T("sent");
	}
	else if (linha.pudimEstado == "semTradutor")
	{
		linha.text = linha.pudimOriginal;
		linha.tooltip = pudimtr_T("offline") + "\n" + pudimtr_T("offlineHow");
	}
	else
	{
		linha.text = linha.pudimOriginal;
		linha.tooltip = pudimtr_T("click");
	}
}

// ─── Clique na fala ───────────────────────────────────────────────────────────

function pudim_TrClicar(linha)
{
	// Segundo clique numa fala já traduzida devolve o inglês, e o terceiro
	// traz a tradução de volta — sem custar novo pedido, o texto está em mãos.
	if (linha.pudimEstado == "traduzido")
		linha.pudimEstado = "original";
	else if (linha.pudimTraducao)
		linha.pudimEstado = "traduzido";
	else
	{
		const pronta = pudim_TrPedir(linha.pudimTextoLimpo);
		if (pronta)
		{
			linha.pudimTraducao = pronta;
			linha.pudimEstado = "traduzido";
		}
		else
			linha.pudimEstado = pudim_TrEstaVivo() ? "esperando" : "semTradutor";
	}

	pudim_TrRedesenharLinha(linha);
	g_Chat.ChatOverlay.displayChatMessages();
}

// ─── Decoração das mensagens novas ────────────────────────────────────────────

function pudim_TrDecorar(chatMessage)
{
	const texto = chatMessage.text;
	// Só o que foi dito é traduzido; o nome fica intocado, com a cor do jogador.
	// A separação mora em gui/common/pudimtr_bridge.js, junto com a da lobby.
	const partes = pudim_TrPartes(texto);

	const linha = {
		"pudimPrefixo": partes.prefixo,
		"pudimOriginal": texto,
		"pudimTextoLimpo": partes.dito,
		"pudimTraducao": null,
		"pudimEstado": "original"
	};

	if (!linha.pudimTextoLimpo)
		return;

	// O objeto da linha e o do overlay são o mesmo: escrever em linha.text
	// muda o que o jogo desenha, e o callback é o que faz a linha virar botão.
	Object.assign(chatMessage, linha);
	chatMessage.callback = () => pudim_TrClicar(chatMessage);

	// Se a frase já passou pelo tradutor antes (alguém repetiu, ou é uma
	// partida nova com o cache do tradutor cheio), mostramos na hora.
	const pronta = pudim_TrObter(chatMessage.pudimTextoLimpo);
	if (pronta)
	{
		chatMessage.pudimTraducao = pronta;
		if (pudim_TrTraduzirTudoLigado())
			chatMessage.pudimEstado = "traduzido";
	}
	else if (pudim_TrTraduzirTudoLigado() && pudim_TrEstaVivo())
	{
		pudim_TrPedir(chatMessage.pudimTextoLimpo);
		chatMessage.pudimEstado = "esperando";
	}

	pudim_TrRedesenharLinha(chatMessage);
	g_PudimTrLinhas.push(chatMessage);

	// A lista não pode crescer para sempre numa partida longa. O overlay mostra
	// 20 linhas; guardar 60 cobre com folga o que ainda pode ser redesenhado.
	if (g_PudimTrLinhas.length > 60)
		g_PudimTrLinhas.splice(0, g_PudimTrLinhas.length - 60);
}

/**
 * Modo "traduzir tudo": em vez de clicar fala por fala, toda mensagem que
 * chega já vem traduzida. Guardado na config do usuário, então sobrevive entre
 * partidas.
 */
function pudim_TrTraduzirTudoLigado()
{
	try {
		return Engine.ConfigDB_GetValue("user", "pudimtranslate.auto") == "true";
	} catch (e) {
		return false;
	}
}

function pudim_TrAlternarTraduzirTudo()
{
	const novo = !pudim_TrTraduzirTudoLigado();
	Engine.ConfigDB_CreateAndSaveValue("user", "pudimtranslate.auto", String(novo));

	// Aplica o modo novo ao que já está na tela, em vez de valer só para a
	// próxima fala — senão parece que o botão não fez nada.
	for (const linha of g_PudimTrLinhas)
	{
		if (novo)
		{
			if (linha.pudimTraducao)
				linha.pudimEstado = "traduzido";
			else if (linha.pudimEstado == "original")
			{
				pudim_TrPedir(linha.pudimTextoLimpo);
				linha.pudimEstado = pudim_TrEstaVivo() ? "esperando" : "semTradutor";
			}
		}
		else if (linha.pudimEstado == "traduzido")
			linha.pudimEstado = "original";

		pudim_TrRedesenharLinha(linha);
	}

	g_Chat.ChatOverlay.displayChatMessages();
	return novo;
}

// ─── Chegada das traduções ────────────────────────────────────────────────────

function pudim_TrAtualizarLinhas()
{
	let mudou = false;

	for (const linha of g_PudimTrLinhas)
	{
		if (linha.pudimTraducao)
			continue;

		const pronta = pudim_TrObter(linha.pudimTextoLimpo);
		if (!pronta)
			continue;

		linha.pudimTraducao = pronta;
		if (linha.pudimEstado == "esperando")
			linha.pudimEstado = "traduzido";

		pudim_TrRedesenharLinha(linha);
		mudou = true;
	}

	if (mudou)
	{
		g_Chat.ChatOverlay.displayChatMessages();

		// A janela de histórico, se estiver aberta, também precisa refletir.
		if (g_Chat.ChatWindow.isOpen() && g_Chat.ChatWindow.isExtended())
			g_Chat.ChatHistory.displayChatHistory();
	}
}

// ─── Histórico do chat ────────────────────────────────────────────────────────

/**
 * No histórico não dá para clicar fala por fala: ele é um único objeto de texto
 * (chatHistoryText), com todas as mensagens emendadas por "\n". Como ali sobra
 * espaço vertical, a tradução entra numa linha abaixo do original em vez de
 * substituí-lo — dá para conferir os dois lados.
 */
function pudim_TrEnfeitarHistorico(texto)
{
	if (!texto)
		return texto;

	return texto.split("\n").map(linha => {
		const dito = pudim_TrPartes(linha).dito;
		if (!dito)
			return linha;

		const pronta = pudim_TrObter(dito);
		if (!pronta || pronta == dito)
			return linha;

		return linha + "\n    " + pudim_TrPintar("↳ " + pronta, PUDIM_TR_COR);
	}).join("\n");
}

// ─── Ligação com o jogo ───────────────────────────────────────────────────────

pudimtr_patchApplyN("init", function(target, that, args)
{
	const resultado = target.apply(that, args);

	try {
		// O laço se pendura no onTick do painel do chat, o mesmo objeto que
		// existe nas três telas. Aqui os setTimeout da GUI funcionam (session.js
		// chama updateTimers), mas os dois caminhos convivem sem custo — passam
		// pelo mesmo freio de tempo.
		let painel = null;
		try {
			painel = Engine.GetGUIObjectByName("chatPanel");
		} catch (e) {}

		pudim_TrIniciar(painel);

		// Decoramos a mensagem antes de o overlay guardá-la: o objeto que
		// chega aqui é o mesmo que ele vai desenhar, então o callback já entra
		// valendo no primeiro desenho.
		pudimtr_patchApplyN(ChatOverlay.prototype, "onChatMessage", function(alvo, esse, argumentos)
		{
			const [msg, chatMessage] = argumentos;

			// Só fala de jogador. Notificação de jogo ("Fulano foi derrotado")
			// já vem traduzida pelo próprio 0 A.D. — mandar para o Google seria
			// pagar uma volta na rede para piorar o texto.
			if (msg && msg.type == "message" && chatMessage && chatMessage.text)
				try {
					pudim_TrDecorar(chatMessage);
				} catch (e) {
					warn("PudimTranslate: falha ao preparar a tradução da fala: " + e);
				}

			return alvo.apply(esse, argumentos);
		});

		pudimtr_patchApplyN(ChatHistory.prototype, "displayChatHistory", function(alvo, esse, argumentos)
		{
			const resultadoHistorico = alvo.apply(esse, argumentos);
			try {
				esse.chatHistoryText.caption = pudim_TrEnfeitarHistorico(esse.chatHistoryText.caption);
			} catch (e) {
				warn("PudimTranslate: falha ao traduzir o histórico do chat: " + e);
			}
			return resultadoHistorico;
		});

		pudim_TrAoTraduzir(pudim_TrAtualizarLinhas);
	} catch (e) {
		warn("PudimTranslate: tradução do chat não pôde ser ligada: " + e);
	}

	return resultado;
});
