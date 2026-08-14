# PudimTranslate — funcoes compartilhadas pelo tradutor e pelo lancador.
#
# Escrito para o Windows PowerShell 5.1, o que vem de fabrica no Windows 10 e 11.
# Nada aqui exige instalar coisa alguma: sem Python, sem .NET SDK, sem pacote
# externo. Por isso tambem nao ha ternario, "?." nem outras coisas que so
# existem no PowerShell 7.
#
# Este arquivo nao faz nada sozinho — e carregado com dot-source pelos outros:
#     . "$PSScriptRoot\pudimtr_comum.ps1"

# ─── Protocolo da ponte ───────────────────────────────────────────────────────
# Os arquivos ficam em <userdata>\saves\campaigns\. A pasta nao foi escolhida
# por gosto: o ReadJSONFile/WriteJSONFile da GUI do jogo so aceita uma lista
# fechada de caminhos — "gui/", "simulation/", "maps/", "campaigns/",
# "saves/campaigns/", "config/matchsettings.json" e
# "config/matchsettings.mp.json". Qualquer outro lugar responde "Restricted
# access to ...". Dessa lista, "saves/campaigns/" e a unica pasta do usuario em
# que da para gravar.
#
# Isso nao atrapalha as campanhas: o jogo lista so "*.0adcampaign" ali, e os
# nossos arquivos sao ".json".

$script:SubPasta  = "saves\campaigns"
$script:ArqPedido = "pudim_tr_req.json"
$script:ArqResposta = "pudim_tr_res.json"
$script:ArqCache  = "pudim_tr_cache.json"

# Tamanho fixo do arquivo de resposta, em bytes. Ver Write-PudimResposta.
$script:TamanhoResposta = 65536

$script:UrlGtx = "https://translate.googleapis.com/translate_a/single"
$script:NomeAtalho = "0 A.D. Translator.lnk"

# UTF-8 sem BOM. O jogo le os arquivos como UTF-8 puro; um BOM na frente
# quebraria o JSON.parse dele.
$script:Utf8 = New-Object System.Text.UTF8Encoding $false


# ─── Onde o Windows guarda as pastas do usuario ───────────────────────────────

function Get-PudimPastaShell
{
    <#
    .SYNOPSIS
        Pasta especial do usuario (Personal, Desktop...), lida do registro.
    .DESCRIPTION
        Precisa vir do registro, e nao de um palpite pelo nome: quando o
        OneDrive assume Documentos ou Area de Trabalho, o caminho vira algo como
        D:\OneDrive\Documentos e o C:\Users\<nome>\Documents costuma continuar
        existindo, vazio ou com restos de instalacao antiga. Adivinhar acerta a
        pasta errada.
    #>
    param([Parameter(Mandatory = $true)][string] $Nome)

    try {
        $chave = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
        $valor = (Get-ItemProperty -Path $chave -Name $Nome -ErrorAction Stop).$Nome
        if ($valor) { return [Environment]::ExpandEnvironmentVariables($valor) }
    } catch { }
    return $null
}


function Get-PudimUserData
{
    <#
    .SYNOPSIS
        Pasta de dados do 0 A.D. (a que contem mods\ e saves\).
    #>
    param([string] $Preferida)

    if ($Preferida) {
        if (Test-Path -LiteralPath $Preferida -PathType Container) {
            return (Resolve-Path -LiteralPath $Preferida).Path
        }
        throw "A pasta informada em -Dir nao existe: $Preferida"
    }

    $candidatos = New-Object System.Collections.Generic.List[string]

    $documentos = Get-PudimPastaShell -Nome "Personal"
    if ($documentos) { $candidatos.Add((Join-Path $documentos "My Games\0ad")) }

    foreach ($base in @($env:USERPROFILE, $env:OneDrive, $env:OneDriveConsumer, $env:OneDriveCommercial)) {
        if (-not $base) { continue }
        $candidatos.Add((Join-Path $base "Documents\My Games\0ad"))
        $candidatos.Add((Join-Path $base "Documentos\My Games\0ad"))
        $candidatos.Add((Join-Path $base "My Games\0ad"))
    }
    if ($env:APPDATA) { $candidatos.Add((Join-Path $env:APPDATA "0ad")) }

    foreach ($caminho in $candidatos) {
        # A pasta 'mods' e a assinatura: 'saves' pode nem existir ainda.
        if (Test-Path -LiteralPath (Join-Path $caminho "mods") -PathType Container) {
            return $caminho
        }
    }

    throw @"
Nao encontrei a pasta de dados do 0 A.D.
Rode de novo apontando o caminho, por exemplo:
  -Dir "D:\OneDrive\Documentos\My Games\0ad"
"@
}


function Get-PudimPastaPonte
{
    param([Parameter(Mandatory = $true)][string] $UserData)

    $pasta = Join-Path $UserData $script:SubPasta
    if (-not (Test-Path -LiteralPath $pasta)) {
        New-Item -ItemType Directory -Force -Path $pasta | Out-Null
    }
    return $pasta
}


# ─── Onde o 0 A.D. esta instalado ─────────────────────────────────────────────

function Get-PudimCaminhosProvaveis
{
    $saidas = New-Object System.Collections.Generic.List[string]
    $exe = "binaries\system\pyrogenesis.exe"

    foreach ($base in @($env:LOCALAPPDATA, $env:ProgramFiles, ${env:ProgramFiles(x86)})) {
        if (-not $base) { continue }
        foreach ($pasta in @("0 A.D. Empires Ascendant", "0 A.D.", "0ad")) {
            $saidas.Add((Join-Path $base (Join-Path $pasta $exe)))
        }
    }

    # Steam, incluindo bibliotecas em outras unidades.
    foreach ($base in @(${env:ProgramFiles(x86)}, $env:ProgramFiles)) {
        if ($base) { $saidas.Add((Join-Path $base "Steam\steamapps\common\0 A.D\$exe")) }
    }
    foreach ($unidade in @("C", "D", "E", "F", "G")) {
        $saidas.Add("${unidade}:\SteamLibrary\steamapps\common\0 A.D\$exe")
    }

    return $saidas
}


function Get-PudimAlvoDeAtalho
{
    <# Para onde um .lnk aponta, ou "" se nao der para ler. #>
    param([Parameter(Mandatory = $true)][string] $Atalho)

    try {
        $ws = New-Object -ComObject WScript.Shell
        return $ws.CreateShortcut($Atalho).TargetPath
    } catch {
        return ""
    }
}


function Get-PudimJogoPeloMenuIniciar
{
    <#
    .DESCRIPTION
        Le o alvo do atalho do 0 A.D. no menu Iniciar. E a fonte mais confiavel
        quando a instalacao nao esta em nenhum lugar obvio: o proprio instalador
        criou o atalho apontando para o lugar certo.
    #>
    $pastas = @(
        (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"),
        (Join-Path $env:ProgramData "Microsoft\Windows\Start Menu\Programs")
    )

    foreach ($pasta in $pastas) {
        if (-not (Test-Path -LiteralPath $pasta)) { continue }
        $atalhos = Get-ChildItem -LiteralPath $pasta -Filter *.lnk -Recurse -ErrorAction SilentlyContinue |
                   Where-Object { $_.Name -match "0.?A" }
        foreach ($atalho in $atalhos) {
            $alvo = Get-PudimAlvoDeAtalho -Atalho $atalho.FullName
            if ($alvo -and $alvo.ToLower().EndsWith("pyrogenesis.exe") -and (Test-Path -LiteralPath $alvo)) {
                return $alvo
            }
        }
    }
    return $null
}


function Get-PudimJogo
{
    <#
    .SYNOPSIS
        Caminho do pyrogenesis.exe, ou $null se nao achar.
    .DESCRIPTION
        O caminho encontrado e guardado ao lado dos scripts, para a busca
        acontecer uma vez so. Esse arquivo e especifico de cada maquina e fica
        fora do repositorio — cada pessoa que instalar descobre o seu.
    #>
    param([string] $Preferido, [string] $PastaScripts)

    if ($Preferido) {
        if (Test-Path -LiteralPath $Preferido -PathType Leaf) { return $Preferido }
        throw "Nao existe: $Preferido"
    }

    $memoria = Join-Path $PastaScripts "caminho_do_jogo.txt"
    if (Test-Path -LiteralPath $memoria) {
        try {
            $guardado = ([IO.File]::ReadAllText($memoria, $script:Utf8)).Trim()
            if ($guardado -and (Test-Path -LiteralPath $guardado -PathType Leaf)) { return $guardado }
        } catch { }
    }

    foreach ($caminho in (Get-PudimCaminhosProvaveis)) {
        if (Test-Path -LiteralPath $caminho -PathType Leaf) {
            Save-PudimJogo -Caminho $caminho -PastaScripts $PastaScripts
            return $caminho
        }
    }

    $doMenu = Get-PudimJogoPeloMenuIniciar
    if ($doMenu) {
        Save-PudimJogo -Caminho $doMenu -PastaScripts $PastaScripts
        return $doMenu
    }

    return $null
}


function Save-PudimJogo
{
    param([string] $Caminho, [string] $PastaScripts)
    try {
        [IO.File]::WriteAllText((Join-Path $PastaScripts "caminho_do_jogo.txt"), $Caminho, $script:Utf8)
    } catch {
        # Nao achar onde guardar nao pode impedir o jogo de abrir; so significa
        # procurar de novo na proxima vez.
    }
}


# ─── Atalho na area de trabalho ───────────────────────────────────────────────

function Set-PudimAtalho
{
    <#
    .SYNOPSIS
        Garante o atalho na area de trabalho apontando para o lancador.
    .DESCRIPTION
        O alvo e o Play0AD.bat, e nao o tradutor sozinho: ele abre o tradutor,
        espera a ponte ficar pronta, abre o 0 A.D. e encerra o tradutor na
        saida. Um clique so, na ordem certa — que e o que importa, porque o jogo
        so enxerga a ponte se ela existir quando ele inicia.

        O icone vem do proprio 0 A.D., para o atalho ficar reconhecivel ao lado
        do atalho do jogo. Um .bat nao pode ter icone proprio: o Windows tira o
        icone de um .bat do TIPO de arquivo, entao so um atalho resolve — e e
        por isso que ele existe.

        Se o atalho ja existe apontando para outro lugar (versao anterior, ou a
        pasta do mod mudou), o alvo e corrigido em vez de ficar quebrado.
    .OUTPUTS
        O caminho do atalho, se criado ou corrigido. $null se ja estava certo.
    #>
    param([string] $PastaScripts)

    $area = Get-PudimPastaShell -Nome "Desktop"
    if (-not $area -or -not (Test-Path -LiteralPath $area)) { return $null }

    $alvo = Join-Path $PastaScripts "Play0AD.bat"
    if (-not (Test-Path -LiteralPath $alvo -PathType Leaf)) { return $null }

    $atalho = Join-Path $area $script:NomeAtalho
    if (Test-Path -LiteralPath $atalho) {
        $atual = Get-PudimAlvoDeAtalho -Atalho $atalho
        if ($atual -and ($atual.ToLower() -eq $alvo.ToLower())) { return $null }
    }

    try {
        $ws = New-Object -ComObject WScript.Shell
        $s = $ws.CreateShortcut($atalho)
        $s.TargetPath = $alvo
        $s.WorkingDirectory = $PastaScripts
        $s.Description = "Abre o 0 A.D. com o tradutor de chat do PudimTranslate"

        # O icone e um extra: sem o executavel, o atalho e criado do mesmo
        # jeito, apenas com o icone padrao.
        $jogo = Get-PudimJogo -PastaScripts $PastaScripts
        if ($jogo) { $s.IconLocation = "$jogo,0" }

        $s.Save()
        return $atalho
    } catch {
        # Nao conseguir criar um atalho de conveniencia nao pode derrubar nada.
        return $null
    }
}


# ─── Tempo ────────────────────────────────────────────────────────────────────

function Get-PudimAgora
{
    <#
    .SYNOPSIS
        Segundos desde a epoca, em UTC.
    .DESCRIPTION
        Nao use "Get-Date -UFormat %s" para isto. No Windows PowerShell 5.1 ele
        calcula a partir da hora LOCAL, entao devolve um valor deslocado do fuso
        — quatro horas a menos no Brasil. O jogo compara este carimbo com o
        Date.now() dele, que e UTC, e concluiria que o tradutor esta desligado
        mesmo com ele rodando na frente. Foi exatamente o que aconteceu no
        primeiro teste desta versao.
    #>
    return [int] [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
}


# ─── Leitura e escrita dos arquivos da ponte ──────────────────────────────────

function Read-PudimJson
{
    <# Le e converte um JSON, devolvendo $null em qualquer problema. #>
    param([string] $Caminho)

    try {
        if (-not (Test-Path -LiteralPath $Caminho -PathType Leaf)) { return $null }
        $texto = [IO.File]::ReadAllText($Caminho, $script:Utf8)
        if (-not $texto.Trim()) { return $null }
        return $texto | ConvertFrom-Json
    } catch {
        # Arquivo pego no meio de uma escrita, ou JSON quebrado. A proxima
        # leitura resolve.
        return $null
    }
}


function ConvertTo-PudimTabela
{
    <#
    .SYNOPSIS
        Transforma o objeto do ConvertFrom-Json numa hashtable comum.
    .DESCRIPTION
        O ConvertFrom-Json do PowerShell 5.1 devolve PSCustomObject, que nao da
        para indexar por chave nem para acrescentar item. Como as chaves aqui
        sao ids gerados pelo mod, precisamos de uma tabela de verdade.
    #>
    param($Objeto)

    $tabela = @{}
    if ($null -eq $Objeto) { return $tabela }
    foreach ($prop in $Objeto.PSObject.Properties) { $tabela[$prop.Name] = $prop.Value }
    return $tabela
}


function Write-PudimBytesAtomico
{
    <#
    .DESCRIPTION
        Grava num arquivo temporario e so entao move por cima do definitivo.
        Sem isso o jogo consegue ler o arquivo pela metade — ele fica lendo em
        laco, e a chance de pegar uma escrita no meio e real.
    #>
    param([string] $Caminho, [byte[]] $Bytes)

    $temporario = "$Caminho.tmp"
    [IO.File]::WriteAllBytes($temporario, $Bytes)
    Move-Item -LiteralPath $temporario -Destination $Caminho -Force
}


function Write-PudimResposta
{
    <#
    .SYNOPSIS
        Grava a resposta SEMPRE com o mesmo tamanho, completando com espacos.
    .DESCRIPTION
        Isto nao e capricho. O VFS do 0 A.D. guarda o tamanho do arquivo de
        quando indexou a pasta; quando o arquivo cresce, a leitura para no
        tamanho antigo e o jogo recebe o JSON cortado no meio —
        "JSON.parse: unterminated string". Com tamanho fixo, o valor guardado
        nunca fica errado. Espaco depois do JSON e valido: o JSON.parse ignora.

        Se as traducoes nao couberem, as mais antigas sao descartadas. O jogo
        guarda em memoria tudo o que ja recebeu, entao perder as antigas daqui
        nao apaga nada da tela.
    #>
    param([string] $Caminho, [hashtable] $Respostas, [int] $Vivo)

    $chaves = @($Respostas.Keys)
    $bytes = $null

    while ($true) {
        $parcial = @{}
        foreach ($chave in $chaves) { $parcial[$chave] = $Respostas[$chave] }
        $json = (@{ done = $parcial; vivo = $Vivo } | ConvertTo-Json -Compress -Depth 4)
        $bytes = $script:Utf8.GetBytes($json)

        if ($bytes.Length -le $script:TamanhoResposta -or $chaves.Count -eq 0) { break }

        # Descarta um quarto dos mais antigos por vez, para nao ficar tentando
        # um item de cada vez num arquivo grande.
        $descartar = [Math]::Max(1, [int]($chaves.Count / 4))
        $chaves = $chaves[$descartar..($chaves.Count - 1)]
    }

    if ($bytes.Length -gt $script:TamanhoResposta) {
        # So acontece se uma unica traducao for gigante; melhor mandar vazio do
        # que mandar cortado.
        $bytes = $script:Utf8.GetBytes((@{ done = @{}; vivo = $Vivo } | ConvertTo-Json -Compress))
    }

    $saida = New-Object byte[] $script:TamanhoResposta
    [Array]::Copy($bytes, $saida, $bytes.Length)
    for ($i = $bytes.Length; $i -lt $script:TamanhoResposta; $i++) { $saida[$i] = 0x20 }

    Write-PudimBytesAtomico -Caminho $Caminho -Bytes $saida
}


# ─── Traducao ─────────────────────────────────────────────────────────────────

# Tags de cor e de icone que o chat do 0 A.D. embute no texto. Mandar isso para
# o tradutor suja o resultado, entao saem antes.
$script:RegexTags = [regex] '\[/?(?:color|font|icon|imgleft|imgright)[^\]]*\]'

function Clear-PudimTexto
{
    param([string] $Texto)
    if (-not $Texto) { return "" }
    return $script:RegexTags.Replace($Texto, "").Trim()
}


function ConvertTo-PudimIdioma
{
    <#
    .DESCRIPTION
        O 0 A.D. escreve locale com underscore ("pt_BR") e o Google espera hifen
        ("pt-BR"). Ambos aceitam a forma curta ("pt"), que e o que o mod costuma
        mandar; a conversao garante que a forma longa tambem funcione.
    #>
    param([string] $Codigo)
    if (-not $Codigo) { return $null }
    return $Codigo.Trim().Replace("_", "-")
}


function Invoke-PudimTraducao
{
    <#
    .SYNOPSIS
        Traduz um texto, ou devolve $null se a chamada falhar.
    .DESCRIPTION
        Usa o endpoint translate_a/single com client=gtx — o mesmo que a pagina
        translate.google.com usa. Gratis, sem chave e sem cadastro. Nao e
        documentado pelo Google, entao pode mudar sem aviso; para o volume de um
        chat de partida funciona bem e nao esbarra em limite.

        A resposta e um array aninhado: o primeiro elemento e uma lista de
        pedacos, e o texto traduzido de cada pedaco esta no indice 0. Juntar os
        pedacos importa — frase longa volta quebrada em varios deles.
    #>
    param([string] $Texto, [string] $Destino, [string] $Origem = "auto")

    $url = "$($script:UrlGtx)?client=gtx&sl=$Origem&tl=$Destino&dt=t&q=" + [uri]::EscapeDataString($Texto)

    try {
        $resposta = Invoke-RestMethod -Uri $url -UseBasicParsing -TimeoutSec 10 -Headers @{
            "User-Agent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
    } catch {
        Write-Host "  ! falha ao traduzir: $($_.Exception.Message)"
        return $null
    }

    try {
        $partes = $resposta[0] | ForEach-Object { $_[0] }
        return (-join $partes)
    } catch {
        Write-Host "  ! resposta em formato inesperado"
        return $null
    }
}
