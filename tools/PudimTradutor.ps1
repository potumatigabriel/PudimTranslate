<#
.SYNOPSIS
    PudimTranslate — tradutor de chat do 0 A.D.

.DESCRIPTION
    Por que este programa existe
    ----------------------------
    O JS da GUI do 0 A.D. nao tem HTTP. Nao existe fetch, XHR nem nada
    equivalente: as unicas funcoes de rede expostas ao script sao a lobby
    (XMPP, em C++) e o mod.io (URL fixa). Ou seja, o mod nao consegue chamar o
    Google Tradutor sozinho.

    O que da pra fazer pelo script e ler e gravar arquivo (Engine.WriteJSONFile
    e Engine.ReadJSONFile sao APIs publicas, as mesmas que o jogo usa para
    salvar campanha e configuracao de partida). Entao a ponte e por arquivo: o
    mod escreve o que quer traduzir, este programa traduz e devolve.

        mod  --escreve-->  pudim_tr_req.json  --le-->  este programa  --> Google
        mod  <----le----   pudim_tr_res.json  <-escreve-----'

    Roda no Windows PowerShell 5.1, o que ja vem no Windows. Nao precisa
    instalar nada.

.PARAMETER Dir
    Pasta de dados do 0 A.D. (a que contem mods\ e saves\), se a busca falhar.

.PARAMETER To
    Idioma de destino quando o pedido nao disser qual. Normalmente quem manda e
    o jogo, que sabe em que idioma esta instalado.

.PARAMETER From
    Idioma de origem. O padrao "auto" deixa o Google identificar sozinho o que
    foi escrito, que e o comportamento desejado quase sempre.

.PARAMETER SemAtalho
    Nao criar o atalho na area de trabalho.

.EXAMPLE
    PudimTradutor.bat
    Abre o tradutor. Deixe a janela aberta enquanto joga.

.EXAMPLE
    powershell -File PudimTradutor.ps1 -Dir "D:\Documentos\My Games\0ad"
#>

[CmdletBinding()]
param(
    [string] $Dir,
    [string] $To = "pt",
    [string] $From = "auto",
    [switch] $SemAtalho
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\pudimtr_comum.ps1"

# De quanto em quanto tempo olhamos o arquivo de pedido.
$intervalo = 0.3
# O jogo considera o tradutor desligado se o sinal de vida tiver mais de 15s,
# entao regravamos a resposta a cada 5.
$intervaloSinal = 5
# Cache em disco: quanto mais, menos ida a rede em partidas seguidas.
$cacheMaximo = 4000


function Limit-PudimCache
{
    param([hashtable] $Cache)
    if ($Cache.Count -le $cacheMaximo) { return $Cache }
    $chaves = @($Cache.Keys)[-$cacheMaximo..-1]
    $novo = @{}
    foreach ($chave in $chaves) { $novo[$chave] = $Cache[$chave] }
    return $novo
}


# ─── Preparacao ───────────────────────────────────────────────────────────────

# Acentuacao na janela do console. Sem isto, "traducao" sai com caractere solto.
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false } catch { }

# O Google exige TLS 1.2; o PowerShell 5.1 nem sempre o escolhe sozinho.
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }

$userData = Get-PudimUserData -Preferida $Dir
$pasta = Get-PudimPastaPonte -UserData $userData

$caminhoPedido = Join-Path $pasta $script:ArqPedido
$caminhoResposta = Join-Path $pasta $script:ArqResposta
$caminhoCache = Join-Path $pasta $script:ArqCache

$cache = ConvertTo-PudimTabela -Objeto (Read-PudimJson -Caminho $caminhoCache)
$respostas = ConvertTo-PudimTabela -Objeto (Read-PudimJson -Caminho $caminhoResposta).done

# O cache de disco alimenta a resposta: reiniciar o tradutor no meio de uma
# partida nao pode fazer o jogo perder o que ja tinha sido traduzido.
foreach ($chave in $cache.Keys) {
    if (-not $respostas.ContainsKey($chave)) { $respostas[$chave] = $cache[$chave] }
}

Write-Host "PudimTranslate - tradutor de chat"
Write-Host "  pasta do jogo : $userData"
Write-Host "  ponte         : $pasta"
Write-Host "  idioma destino: $To (o jogo pode pedir outro)"
Write-Host "  cache         : $($cache.Count) frase(s) ja conhecidas"

if (-not $SemAtalho) {
    $atalho = Set-PudimAtalho -PastaScripts $PSScriptRoot
    if ($atalho) {
        Write-Host ""
        Write-Host "  Atalho pronto na sua area de trabalho: $(Split-Path $atalho -Leaf)"
        Write-Host "  Use ele para jogar: abre o tradutor e o 0 A.D. juntos, na ordem certa."
    }
}

Write-Host ""
Write-Host "  Deixe esta janela aberta enquanto joga. Ctrl+C para sair."
Write-Host "  Se o 0 A.D. ja estiver aberto, feche e abra de novo - o jogo so"
Write-Host "  enxerga a ponte se ela existir quando ele inicia."
Write-Host ""

# Deixa uma resposta valida no lugar ja na largada: o mod precisa que o arquivo
# exista ANTES de o jogo iniciar, senao o VFS nunca o enxerga nesta sessao.
Write-PudimResposta -Caminho $caminhoResposta -Respostas $respostas -Vivo (Get-PudimAgora)

$ultimaModificacao = [DateTime]::MinValue
$ultimoSinal = Get-Date
$ultimoDestino = $null


# ─── Laco principal ───────────────────────────────────────────────────────────

try {
    while ($true) {
        $agora = Get-Date

        # Sinal de vida: e assim que o mod sabe que o tradutor esta ligado e
        # mostra a fala como clicavel em vez de avisar que esta desligado.
        if (($agora - $ultimoSinal).TotalSeconds -ge $intervaloSinal) {
            Write-PudimResposta -Caminho $caminhoResposta -Respostas $respostas `
                                -Vivo (Get-PudimAgora)
            $ultimoSinal = $agora
        }

        if (-not (Test-Path -LiteralPath $caminhoPedido -PathType Leaf)) {
            Start-Sleep -Seconds $intervalo
            continue
        }

        $modificacao = (Get-Item -LiteralPath $caminhoPedido).LastWriteTimeUtc
        if ($modificacao -eq $ultimaModificacao) {
            Start-Sleep -Seconds $intervalo
            continue
        }
        $ultimaModificacao = $modificacao

        $pedido = Read-PudimJson -Caminho $caminhoPedido
        if ($null -eq $pedido -or $null -eq $pedido.items) {
            Start-Sleep -Seconds $intervalo
            continue
        }

        # O idioma vem no pedido, escolhido pelo jogo — quem sabe em que idioma
        # o 0 A.D. esta rodando e ele, nao este programa. O -To so vale quando o
        # pedido nao diz nada.
        $destino = ConvertTo-PudimIdioma -Codigo $pedido.to
        if (-not $destino) { $destino = $To }

        $novidade = $false
        foreach ($item in @($pedido.items)) {
            $chave = [string] $item.id
            $texto = Clear-PudimTexto -Texto ([string] $item.text)
            if (-not $chave -or -not $texto -or $respostas.ContainsKey($chave)) { continue }

            # O idioma so e anunciado quando ha traducao de verdade para fazer.
            # Anunciar a cada pedido lido confundia: um pedido parado de uma
            # sessao anterior fazia o programa dizer um idioma que ninguem tinha
            # pedido agora.
            if ($destino -ne $ultimoDestino) {
                Write-Host "  traduzindo para: $destino"
                $ultimoDestino = $destino
            }

            Write-Host "  > $texto"
            $traduzido = Invoke-PudimTraducao -Texto $texto -Destino $destino -Origem $From
            if ($null -eq $traduzido) { continue }

            Write-Host "  < $traduzido"
            $respostas[$chave] = $traduzido
            $cache[$chave] = $traduzido
            $novidade = $true
        }

        if ($novidade) {
            $cache = Limit-PudimCache -Cache $cache
            Write-PudimBytesAtomico -Caminho $caminhoCache `
                -Bytes $script:Utf8.GetBytes(($cache | ConvertTo-Json -Compress -Depth 4))
            Write-PudimResposta -Caminho $caminhoResposta -Respostas $respostas `
                                -Vivo (Get-PudimAgora)
            $ultimoSinal = Get-Date
        }

        Start-Sleep -Seconds $intervalo
    }
}
finally {
    # Ctrl+C ou fechamento da janela: o cache do disco vale para a proxima vez.
    try {
        Write-PudimBytesAtomico -Caminho $caminhoCache `
            -Bytes $script:Utf8.GetBytes(((Limit-PudimCache -Cache $cache) | ConvertTo-Json -Compress -Depth 4))
    } catch { }
}
