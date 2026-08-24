/**
 * PudimTranslate — ponte de tradução do chat (lado do jogo).
 *
 * Por que uma ponte por arquivo
 * -----------------------------
 * O JS da GUI do 0 A.D. não tem HTTP. Não existe fetch nem XHR: as únicas
 * funções de rede expostas ao script são a lobby (XMPP, em C++) e o mod.io
 * (URL fixa). Chamar o Google Tradutor direto daqui é impossível sem patch
 * em C++.
 *
 * O que dá pra fazer é ler e gravar arquivo — Engine.WriteJSONFile e
 * Engine.ReadJSONFile são APIs públicas, as mesmas que o jogo usa para salvar
 * campanha e configuração de partida. Então:
 *
 *     este arquivo  --escreve-->  saves/campaigns/pudim_tr_req.json
 *     tools/pudim_tradutor.py     lê, traduz no Google, escreve o _res
 *     este arquivo  <----lê-----  saves/campaigns/pudim_tr_res.json
 *
 * A pasta não foi escolhida por gosto. O ReadJSONFile/WriteJSONFile da GUI só
 * aceita uma lista fechada de caminhos — "gui/", "simulation/", "maps/",
 * "campaigns/", "saves/campaigns/", "config/matchsettings.json" e
 * "config/matchsettings.mp.json". Qualquer outro lugar responde
 * "Restricted access to ...". Dessa lista, "saves/campaigns/" é a única pasta
 * do usuário que dá para gravar, então é onde a ponte mora. Não atrapalha as
 * campanhas: o jogo lista só "*.0adcampaign" ali (gui/campaigns/load_modal/
 * LoadModal.js:66), e os nossos são ".json".
 *
 * Fica em gui/common/ de propósito: tanto session.xml quanto lobby.xml
 * declaram <script directory="gui/common/"/>, então a ponte carrega sozinha
 * nas duas telas, sem duplicar código.
 *
 * Sem o tradutor rodando nada quebra — pudim_TrEstaVivo() devolve false e a
 * interface avisa que ele está desligado.
 */

// ─── Protocolo ────────────────────────────────────────────────────────────────

const PUDIM_TR_REQ = "saves/campaigns/pudim_tr_req.json";
const PUDIM_TR_RES = "saves/campaigns/pudim_tr_res.json";

/**
 * De quanto em quanto tempo olhamos o arquivo de resposta, em ms.
 * 500 dá sensação de imediato sem custar nada perceptível: é um ReadJSONFile
 * de um arquivo pequeno, e só roda enquanto há frase pendente ou a cada 3s
 * para atualizar o sinal de vida.
 */
const PUDIM_TR_INTERVALO = 500;
const PUDIM_TR_INTERVALO_OCIOSO = 3000;

/**
 * Quanto esperar depois de uma leitura que falhou, antes de tentar de novo.
 * 2s é curto o bastante para a tradução não parecer travada e longo o bastante
 * para não repetir o erro do motor várias vezes por segundo.
 */
const PUDIM_TR_RECUO_FALHA = 2000;
var g_PudimTrLeituraBloqueadaAte = 0;

/**
 * O tradutor regrava res.json a cada 5s como sinal de vida. Se o carimbo está
 * mais velho que isto, consideramos que ele foi fechado.
 */
const PUDIM_TR_TOLERANCIA_VIDA = 15;

var g_PudimTr = {
	/** id -> texto traduzido, já confirmado pelo tradutor. */
	"cache": {},
	/** id -> texto original, pedido e ainda sem resposta. */
	"pendentes": {},
	/** Carimbo de tempo (segundos) do último sinal de vida lido. */
	"vivoEm": 0,
	/** Evita agendar dois laços de polling ao mesmo tempo. */
	"rodando": false,
	/** Quando o arquivo de resposta foi lido pela última vez (ms). */
	"ultimoTique": 0,
	/** Evita pendurar o laço no onTick mais de uma vez. */
	"presoNoTique": false,
	/** Handlers avisados sempre que chega tradução nova. */
	"ouvintes": []
};

// ─── Identificação das frases ─────────────────────────────────────────────────

/**
 * Tags de cor e de ícone que o chat do 0 A.D. embute no texto.
 * Traduzir com elas dentro suja o resultado, então saem antes de enviar — e
 * também antes de gerar o id, para que a mesma frase dita por dois jogadores
 * de cores diferentes conte como uma tradução só.
 */
const PUDIM_TR_TAGS = /\[\/?(?:color|font|icon|imgleft|imgright)[^\]]*\]/g;

function pudim_TrLimpar(texto)
{
	return String(texto || "").replace(PUDIM_TR_TAGS, "").trim();
}

// ─── Separar quem falou do que foi falado ─────────────────────────────────────

/**
 * Carimbo de hora que o jogo põe na frente da fala quando "chat.timestamp" está
 * ligado. Precisa sair antes de qualquer outra coisa — foi justamente ele que
 * quebrou a primeira versão disto, que tentava casar nome e dois-pontos de uma
 * vez só e engolia o "[09:" achando que era o apelido.
 *
 * A barra invertida opcional não é enfeite: na GUI do 0 A.D. o colchete abre
 * tag, então colchete literal é escrito escapado. O texto que chega aqui é
 * "\[09:38] ", não "[09:38] " — ChatHistory.js monta o prefixo com
 * translate("\\[%(time)s]"). Sem aceitar a barra, o carimbo escapava do filtro
 * e ia parar no tradutor junto com a fala.
 */
const PUDIM_TR_CARIMBO = /^\\?\[\d{1,2}:\d{2}(?::\d{2})?\]\s*/;

/**
 * O apelido de quem falou, nos dois formatos que o jogo usa:
 *
 *   "[font=\"…\"]<[color=\"…\"]kyng (399)[/color]>[/font] oi"  lobby e configuração
 *   "[color=\"255 0 0\"]Alice[/color]: oi"                     sessão
 *
 * Repare que na primeira forma as tags de cor ficam DENTRO dos sinais de menor
 * e maior, e a de negrito por fora — é o que ClientChat.js monta: o apelido já
 * vem colorido, o "<%(username)s>" o envolve, e só então vem o setStringTags do
 * negrito.
 *
 * Por isso os quantificadores contam TAGS INTEIRAS como uma unidade, não
 * caracteres. Contando caractere, as tags de cor sozinhas comiam quase trinta
 * do orçamento e sobrava espaço para uns onze de nome: apelido curto como
 * "kyng (399)" era reconhecido e "jagsusindia (ultra sexy)" não, e a fala
 * simplesmente não respondia ao clique. O limite continua existindo, generoso,
 * só para uma fala que por acaso tenha "<" e ">" no meio não ser confundida
 * com um apelido gigante.
 */
const PUDIM_TR_APELIDO =
	/^((?:\[[^\]]*\])*\s*<(?:\[[^\]]*\]|[^>\[\]]){1,80}>\s*(?:\[[^\]]*\])*\s*|(?:\[[^\]]*\]|[^:\[\]]){1,60}:\s*)/;

/**
 * Separa a fala em três partes:
 *
 *   prefixo — carimbo de hora + apelido, preservado exatamente como veio,
 *             para ser reimpresso na frente da tradução com a cor/negrito
 *             originais.
 *   temApelido — se alguém realmente falou. Linha sem apelido é aviso do
 *             sistema ("== Fulano entrou."), que o próprio 0 A.D. já entrega
 *             traduzido: mandar ao Google seria pagar uma ida à rede para
 *             piorar o texto. O carimbo de hora sozinho não conta como
 *             apelido, senão todo aviso passaria no teste.
 *   dito    — o que foi falado, já sem tags. É só isto que vai ao tradutor:
 *             mandar o apelido junto dá resultado ridículo — nome de jogador
 *             virando substantivo — e faria a mesma frase dita por duas
 *             pessoas contar como duas traduções diferentes.
 */
function pudim_TrPartes(texto)
{
	const original = String(texto || "");
	let resto = original;
	let prefixo = "";

	const carimbo = PUDIM_TR_CARIMBO.exec(resto);
	if (carimbo)
	{
		prefixo += carimbo[0];
		resto = resto.substr(carimbo[0].length);
	}

	const apelido = PUDIM_TR_APELIDO.exec(resto);
	if (apelido)
	{
		prefixo += apelido[0];
		resto = resto.substr(apelido[0].length);
	}

	return {
		"prefixo": prefixo,
		"temApelido": !!apelido,
		"dito": pudim_TrLimpar(resto)
	};
}

// ─── Idioma de destino ────────────────────────────────────────────────────────

var g_PudimTrIdioma = null;

/**
 * Idioma para o qual traduzir: o mesmo em que o 0 A.D. está rodando.
 *
 * Assim quem joga em espanhol recebe espanhol sem configurar nada. A origem não
 * precisa ser dita — o Google identifica sozinho o idioma de quem escreveu.
 */
function pudim_TrIdiomaDestino()
{
	if (g_PudimTrIdioma)
		return g_PudimTrIdioma;

	try {
		// GetLocaleLanguage reduz "pt_BR" a "pt", que é o código que o tradutor
		// espera. Idiomas que precisam da região (zh_CN vs zh_TW) são exceção,
		// mas o Google aceita "zh" e escolhe o simplificado.
		const idioma = Engine.GetLocaleLanguage(Engine.GetCurrentLocale());
		if (idioma)
			g_PudimTrIdioma = idioma;
	} catch (e) {
		warn("PudimTranslate: não consegui descobrir o idioma do jogo: " + e);
	}

	return g_PudimTrIdioma || "pt";
}

/**
 * Id curto e estável para uma frase (hash FNV-1a de 32 bits, em base 36).
 *
 * Serve de chave nos dois lados da ponte. Usar o texto inteiro como chave
 * funcionaria, mas encheria o JSON de repetição — e frase de chat pode ter
 * até 1024 caracteres.
 *
 * O idioma de destino entra no hash: se o jogador trocar o idioma do jogo, os
 * ids mudam junto e o cache antigo não devolve texto na língua errada.
 */
function pudim_TrId(texto)
{
	const limpo = pudim_TrIdiomaDestino() + "|" + pudim_TrLimpar(texto);
	let hash = 0x811c9dc5;
	for (let i = 0; i < limpo.length; ++i)
	{
		hash ^= limpo.charCodeAt(i);
		hash = (hash * 0x01000193) >>> 0;
	}
	return hash.toString(36) + "_" + limpo.length.toString(36);
}

// ─── Consulta ─────────────────────────────────────────────────────────────────

/**
 * @returns true se o programa auxiliar deu sinal de vida há pouco.
 */
function pudim_TrEstaVivo()
{
	return (Date.now() / 1000 - g_PudimTr.vivoEm) < PUDIM_TR_TOLERANCIA_VIDA;
}

/**
 * @returns a tradução da frase, ou null se ainda não temos.
 */
function pudim_TrObter(texto)
{
	return g_PudimTr.cache[pudim_TrId(texto)] || null;
}

/**
 * Enfileira uma frase para tradução.
 *
 * @returns a tradução, se já estiver em cache — nesse caso nada é pedido.
 *          Senão null, e a resposta chega depois pelos ouvintes.
 */
function pudim_TrPedir(texto)
{
	const limpo = pudim_TrLimpar(texto);
	if (!limpo)
		return null;

	const id = pudim_TrId(limpo);
	if (g_PudimTr.cache[id])
		return g_PudimTr.cache[id];

	if (!g_PudimTr.pendentes[id])
	{
		g_PudimTr.pendentes[id] = limpo;
		pudim_TrEnviarPedido();
	}

	return null;
}

/**
 * Registra quem deve ser avisado quando chegar tradução nova.
 * O handler recebe o array de ids que acabaram de chegar.
 */
function pudim_TrAoTraduzir(handler)
{
	g_PudimTr.ouvintes.push(handler);
}

// ─── Escrita e leitura dos arquivos ───────────────────────────────────────────

/**
 * Grava req.json com tudo que está pendente.
 *
 * Manda a fila inteira, não só o item novo: se o tradutor foi aberto depois do
 * jogo, ou reiniciou no meio da partida, ele encontra tudo que ficou faltando
 * no primeiro arquivo que ler, sem precisar de reenvio.
 */
function pudim_TrEnviarPedido()
{
	const itens = Object.keys(g_PudimTr.pendentes).map(id => ({
		"id": id,
		"text": g_PudimTr.pendentes[id]
	}));

	try {
		Engine.WriteJSONFile(PUDIM_TR_REQ, {
			"items": itens,
			// O idioma vai no pedido, não na configuração do auxiliar: quem
			// sabe em que língua o jogo está é o jogo.
			"to": pudim_TrIdiomaDestino(),
			"t": Date.now()
		});
	} catch (e) {
		warn("PudimTranslate: falha ao gravar o pedido de tradução: " + e);
	}
}

/**
 * Lê res.json e move para o cache o que chegou.
 * @returns o array de ids novos (vazio se nada mudou).
 */
function pudim_TrLerResposta()
{
	// Recuo depois de uma falha de leitura. O erro que aparece na tela
	// ("CVFSFile: file ... couldn't be opened") é impresso pelo MOTOR, dentro do
	// ReadJSONFile — o try/catch abaixo pega a exceção em JS, mas a linha vermelha
	// já foi escrita. A única forma de não vê-la é não insistir: falhou, espera.
	// A causa raiz está no tradutor (ver gravar_bytes_no_lugar em
	// tools/pudim_tradutor.py); isto aqui é a segunda linha de defesa, para o caso
	// de estar rodando com uma versão antiga dele.
	const agoraLeitura = Date.now();
	if (g_PudimTrLeituraBloqueadaAte > agoraLeitura)
		return [];

	let dados = null;
	try {
		if (!Engine.FileExists(PUDIM_TR_RES))
			return [];
		dados = Engine.ReadJSONFile(PUDIM_TR_RES);
	} catch (e) {
		// Arquivo pego no meio de uma escrita, ou JSON quebrado. A próxima
		// leitura resolve — não vale poluir o log a cada 500ms.
		g_PudimTrLeituraBloqueadaAte = agoraLeitura + PUDIM_TR_RECUO_FALHA;
		return [];
	}
	if (!dados) {
		// ReadJSONFile devolve null quando o motor não conseguiu abrir o arquivo.
		g_PudimTrLeituraBloqueadaAte = agoraLeitura + PUDIM_TR_RECUO_FALHA;
		return [];
	}

	if (dados.vivo)
		g_PudimTr.vivoEm = dados.vivo;

	const traduzidas = dados.done;
	if (!traduzidas)
		return [];

	const novos = [];
	for (const id in traduzidas)
	{
		if (g_PudimTr.cache[id])
			continue;

		g_PudimTr.cache[id] = traduzidas[id];
		if (g_PudimTr.pendentes[id])
		{
			delete g_PudimTr.pendentes[id];
			novos.push(id);
		}
	}

	return novos;
}

// ─── Laço de verificação ──────────────────────────────────────────────────────

/**
 * Lê a resposta e avisa os interessados. Não agenda nada: quem chama decide o
 * ritmo.
 */
function pudim_TrTique()
{
	g_PudimTr.ultimoTique = Date.now();

	const novos = pudim_TrLerResposta();
	if (!novos.length)
		return;

	for (const ouvinte of g_PudimTr.ouvintes)
		try {
			ouvinte(novos);
		} catch (e) {
			warn("PudimTranslate: erro no ouvinte de tradução: " + e);
		}
}

/**
 * Tique com freio: só faz alguma coisa se já passou tempo suficiente.
 *
 * Enquanto há frase esperando, olhamos rápido; parado, devagar. Serve para ser
 * chamada a cada quadro sem custo perceptível — é o que o onTick faz.
 */
function pudim_TrTiqueSeHora()
{
	const pendente = Object.keys(g_PudimTr.pendentes).length > 0;
	const intervalo = pendente ? PUDIM_TR_INTERVALO : PUDIM_TR_INTERVALO_OCIOSO;

	if (Date.now() - g_PudimTr.ultimoTique >= intervalo)
		pudim_TrTique();
}

/**
 * Faz o laço rodar pendurado no onTick de um objeto da GUI.
 *
 * Isto não é redundância com o setTimeout: na lobby o setTimeout simplesmente
 * não funciona. Os temporizadores da GUI (gui/common/timer.js) só avançam onde
 * alguém chama updateTimers(), e no 0 A.D. 0.28 isso acontece na sessão
 * (session.js:644) e na configuração da partida (SetupWindow.js:114) — na
 * lobby, só dentro da tela de Configurações da conta. Na lobby principal
 * nenhum setTimeout dispara, e era por isso que a resposta do tradutor nunca
 * chegava lá: o pedido era gravado, o tradutor respondia, e o jogo nunca
 * relia o arquivo.
 *
 * O handler anterior é preservado — o objeto pode já ter um.
 */
function pudim_TrLigarTique(objeto)
{
	if (!objeto || g_PudimTr.presoNoTique)
		return;

	g_PudimTr.presoNoTique = true;

	const anterior = objeto.onTick;
	objeto.onTick = () => {
		if (anterior)
			anterior();
		pudim_TrTiqueSeHora();
	};
}

/**
 * Laço por setTimeout, mantido onde ele funciona.
 *
 * Os dois caminhos convivem sem problema: ambos passam pelo mesmo freio de
 * tempo, então chamar duas vezes no mesmo intervalo não lê o arquivo duas
 * vezes.
 */
function pudim_TrLacoPorTemporizador()
{
	pudim_TrTiqueSeHora();

	const pendente = Object.keys(g_PudimTr.pendentes).length > 0;
	setTimeout(pudim_TrLacoPorTemporizador, pendente ? PUDIM_TR_INTERVALO : PUDIM_TR_INTERVALO_OCIOSO);
}

/**
 * Prepara a ponte. Pode ser chamada mais de uma vez sem efeito colateral.
 *
 * @param objetoDoTique - objeto da GUI em cujo onTick o laço se pendura.
 *        As três telas têm um "chatPanel", então é sempre ele.
 */
function pudim_TrIniciar(objetoDoTique)
{
	pudim_TrLigarTique(objetoDoTique);

	if (g_PudimTr.rodando)
		return;

	g_PudimTr.rodando = true;

	// Cria só o arquivo de PEDIDO, e só se faltar. O de resposta é criado pelo
	// tradutor ao ligar, e é de propósito que não o criemos aqui.
	//
	// O VFS do jogo guarda o tamanho do arquivo de quando indexou a pasta.
	// Criar aqui um arquivo de resposta pequeno faria o jogo guardar esse
	// tamanho e, quando o tradutor gravasse a versão cheia, a leitura pararia no
	// tamanho antigo — JSON cortado no meio, "unterminated string". Por isso o
	// arquivo de resposta tem tamanho fixo, e quem o define é sempre o tradutor.
	//
	// O pedido não sofre disso: só o jogo escreve nele, e escrever não passa
	// pelo tamanho guardado.
	try {
		if (!Engine.FileExists(PUDIM_TR_REQ))
			Engine.WriteJSONFile(PUDIM_TR_REQ, { "items": [], "t": Date.now() });
	} catch (e) {
		warn("PudimTranslate: não consegui preparar a ponte de tradução: " + e);
	}

	// Leitura imediata, para já saber se o tradutor está ligado antes mesmo do
	// primeiro clique, e só então o laço.
	pudim_TrTique();
	pudim_TrLacoPorTemporizador();
}
