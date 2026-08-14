/**
 * PudimTranslate — pudimtr_patchApplyN.js
 *
 * Envolve uma função existente num Proxy para interceptar a chamada, permitindo rodar
 * código antes/depois do original sem reescrever o arquivo do jogo.
 *
 * O PudimMod e o AutoCiv têm funções equivalentes. Esta é própria de propósito: o
 * PudimTranslate funciona sozinho, sem depender de nenhum dos dois, e com os três
 * ativos cada um mexe só no seu global — sem disputa de namespace.
 *
 * O prefixo "!!!" no nome do arquivo garante o carregamento antes dos demais: o 0AD
 * carrega cada <script directory="..."/> em ordem alfabética, e "!" vem antes de tudo.
 *
 * Uso:
 *   pudimtr_patchApplyN("nomeDaFuncaoGlobal", (target, that, args) => { ... });
 *   pudimtr_patchApplyN(objeto, "metodo", (target, that, args) => { ... });
 *
 * O patch recebe (target, that, args) e é responsável por chamar target.apply(that, args)
 * se quiser preservar o comportamento original.
 */
global.pudimtr_patchApplyN = function()
{
	if (arguments.length < 2)
	{
		const erro = new Error("PudimTranslate: argumentos insuficientes para o patch: " + arguments[0]);
		warn(erro.message);
		warn(erro.stack);
		return;
	}

	let prefixo, metodo, patch;
	if (arguments.length == 2)
	{
		prefixo = global;
		metodo = arguments[0];
		patch = arguments[1];
	}
	else
	{
		prefixo = arguments[0];
		metodo = arguments[1];
		patch = arguments[2];
	}

	if (!(metodo in prefixo))
	{
		const erro = new Error("PudimTranslate: função não definida: " + metodo);
		warn(erro.message);
		warn(erro.stack);
		return;
	}

	prefixo[metodo] = new Proxy(prefixo[metodo], { "apply": patch });
};
