/**
 * PudimTranslate — liga a tradução do chat na lobby multiplayer.
 *
 * Todo o comportamento está em gui/common/pudimtr_list.js, compartilhado com
 * a tela de configuração da partida — as duas desenham o chat como lista e a
 * interação é a mesma. Aqui fica só o gancho.
 *
 * Este arquivo precisa morar nesta pasta: lobby.xml não declara
 * <script directory="gui/lobby/LobbyPage/Chat/"/> — quem declara é
 * ChatPanel.xml, e é o que garante que ChatMessagesPanel já exista quando
 * chegarmos aqui.
 */

pudimtr_patchApplyN(ChatMessagesPanel.prototype, "addText", function(alvo, esse, argumentos)
{
	const resultado = alvo.apply(esse, argumentos);

	try {
		// A primeira mensagem é o gancho: aqui o painel já existe e o objeto da
		// lista está pronto. Não há um "init" da lobby para patchear.
		pudim_TrListaAoAdicionar(esse.chatText);
	} catch (e) {
		warn("PudimTranslate: falha ao preparar a tradução do chat da lobby: " + e);
	}

	return resultado;
});

pudimtr_patchApplyN(ChatMessagesPanel.prototype, "clearChatMessages", function(alvo, esse, argumentos)
{
	pudim_TrListaLimpar();
	return alvo.apply(esse, argumentos);
});
