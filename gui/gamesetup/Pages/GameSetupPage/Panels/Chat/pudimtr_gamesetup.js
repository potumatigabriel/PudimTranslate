/**
 * PudimTranslate — liga a tradução do chat na tela de configuração da partida.
 *
 * É o chat onde se combina o jogo antes de começar, e na prática é onde mais
 * se conversa em multiplayer.
 *
 * Todo o comportamento está em gui/common/pudimtr_list.js, compartilhado com
 * a lobby: as duas telas desenham o chat como `type="list"` e têm uma classe
 * ChatMessagesPanel de formato quase igual — a diferença é só a assinatura de
 * addText (aqui recebe só o texto; na lobby, carimbo e texto). O gancho não
 * olha os argumentos, pega o item recém-inserido na lista, então serve nas
 * duas sem adaptação.
 *
 * Este arquivo precisa morar nesta pasta. gamesetup.xml não declara
 * <script directory="gui/gamesetup/Pages/..."/> — quem declara é
 * GameSetupPage.xml:16, e é o que garante que ChatMessagesPanel já exista
 * quando chegarmos aqui.
 */

pudimtr_patchApplyN(ChatMessagesPanel.prototype, "addText", function(alvo, esse, argumentos)
{
	const resultado = alvo.apply(esse, argumentos);

	try {
		pudim_TrListaAoAdicionar(esse.chatText);
	} catch (e) {
		warn("PudimTranslate: falha ao preparar a tradução do chat da configuração: " + e);
	}

	return resultado;
});

pudimtr_patchApplyN(ChatMessagesPanel.prototype, "clearChatMessages", function(alvo, esse, argumentos)
{
	pudim_TrListaLimpar();
	return alvo.apply(esse, argumentos);
});
