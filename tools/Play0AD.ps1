<#
.SYNOPSIS
    PudimTranslate — abre o 0 A.D. com o tradutor de chat ligado.

.DESCRIPTION
    O mod nao consegue ligar o tradutor sozinho: o JS da GUI do 0 A.D. nao
    executa programa nenhum — nao ha API para isso, e nem deveria haver. Entao a
    forma de "ligar junto com o jogo" e inverter a ordem: em vez de o jogo abrir
    o tradutor, este lancador abre os dois.

        liga o tradutor -> abre o 0 A.D. -> espera voce fechar -> encerra o tradutor

    A ordem importa de verdade: o 0 A.D. indexa as pastas de dados uma vez, ao
    iniciar, e nunca percebe arquivo que apareca depois. Se a ponte nao existir
    naquele instante, a sessao inteira fica sem traducao. Por isso o lancador
    espera o arquivo de resposta aparecer antes de abrir o jogo.

    Roda no Windows PowerShell 5.1, o que ja vem no Windows.

.PARAMETER Jogo
    Caminho do pyrogenesis.exe, se a busca automatica falhar. Fica guardado.

.PARAMETER To
    Forca o idioma de destino. Normalmente o jogo decide, pelo idioma em que
    esta instalado.

.PARAMETER ArgumentosDoJogo
    Repassados ao 0 A.D. tal como vieram.

.EXAMPLE
    Play0AD.bat

.EXAMPLE
    powershell -File Play0AD.ps1 -Jogo "C:\Games\0ad\binaries\system\pyrogenesis.exe"
#>

[CmdletBinding()]
param(
    [string] $Jogo,
    [string] $To,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $ArgumentosDoJogo
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\pudimtr_comum.ps1"

try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false } catch { }

$caminhoJogo = Get-PudimJogo -Preferido $Jogo -PastaScripts $PSScriptRoot

if (-not $caminhoJogo) {
    Write-Host "Nao encontrei o 0 A.D. neste computador."
    Write-Host ""
    Write-Host "Rode uma vez com o caminho certo, e ele fica guardado:"
    Write-Host '  powershell -File Play0AD.ps1 -Jogo "C:\caminho\para\pyrogenesis.exe"'
    Write-Host ""
    Read-Host "Enter para sair"
    exit 1
}

Write-Host "PudimTranslate"
Write-Host "  jogo    : $caminhoJogo"
Write-Host ""

# O tradutor em janela propria, para o log de traducao ficar visivel — e util
# para conferir que esta funcionando.
#
# As aspas em volta do caminho sao obrigatorias, nao enfeite: o -ArgumentList do
# Start-Process junta os elementos com espaco e NAO poe aspas em quem tem espaco
# dentro. Sem elas, um caminho como "...\My Games\..." chega cortado no "My" e o
# PowerShell responde que o arquivo nao tem extensao .ps1 — o tradutor morria na
# largada, numa janela que fechava sozinha, e o jogo abria sem traducao sem
# ninguem ver o erro.
$scriptTradutor = Join-Path $PSScriptRoot "PudimTradutor.ps1"
$argsTradutor = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$scriptTradutor`"")
if ($To) { $argsTradutor += @("-To", "`"$To`"") }

$tradutor = $null
try {
    $tradutor = Start-Process -FilePath "powershell.exe" -ArgumentList $argsTradutor -PassThru
} catch {
    Write-Host "[aviso] nao consegui ligar o tradutor: $($_.Exception.Message)"
    Write-Host "        O jogo abre assim mesmo, so nao traduz."
    $tradutor = $null
}

# Se o tradutor caiu logo de cara, e melhor dizer agora do que deixar o jogador
# descobrir no meio da partida que nada traduz.
if ($tradutor) {
    Start-Sleep -Milliseconds 700
    if ($tradutor.HasExited) {
        Write-Host "[aviso] o tradutor fechou sozinho logo apos abrir."
        Write-Host "        Rode PudimTradutor.bat direto para ver a mensagem de erro."
        $tradutor = $null
    }
}

# Espera a ponte existir antes de abrir o jogo. No caso normal isso leva alguns
# centesimos; o limite de 5s evita travar se algo der errado no tradutor.
if ($tradutor) {
    $userData = $null
    try { $userData = Get-PudimUserData } catch { }
    if ($userData) {
        $resposta = Join-Path (Join-Path $userData $script:SubPasta) $script:ArqResposta
        for ($i = 0; $i -lt 50; $i++) {
            if (Test-Path -LiteralPath $resposta -PathType Leaf) { break }
            Start-Sleep -Milliseconds 100
        }
    }
}

Write-Host "Abrindo o 0 A.D. Esta janela se fecha sozinha quando voce sair do jogo."

try {
    $parametros = @{
        FilePath         = $caminhoJogo
        WorkingDirectory = (Split-Path $caminhoJogo -Parent)
        Wait             = $true
    }
    if ($ArgumentosDoJogo -and $ArgumentosDoJogo.Count -gt 0) {
        $parametros["ArgumentList"] = $ArgumentosDoJogo
    }
    Start-Process @parametros
} catch {
    Write-Host "[erro] nao consegui abrir o jogo: $($_.Exception.Message)"
    Read-Host "Enter para sair"
}

# O tradutor nao tem razao de existir sem o jogo aberto.
if ($tradutor -and -not $tradutor.HasExited) {
    Write-Host "Jogo fechado. Encerrando o tradutor."
    try { Stop-Process -Id $tradutor.Id -Force -ErrorAction Stop } catch { }
}
