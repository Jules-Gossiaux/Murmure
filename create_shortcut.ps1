param(
    [string]$ShortcutPath = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $projectRoot "dist\Murmure\Murmure.exe"
if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
    throw "Murmure.exe est introuvable. Lancez build.bat avant de créer le raccourci."
}

if ([string]::IsNullOrWhiteSpace($ShortcutPath)) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $ShortcutPath = Join-Path $desktop "Murmure.lnk"
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($ShortcutPath)
$shortcut.TargetPath = $target
$shortcut.WorkingDirectory = Split-Path -Parent $target
$shortcut.IconLocation = "$target,0"
$shortcut.Description = "Murmure · Dictée locale"
$shortcut.Save()
Write-Output "Raccourci créé : $ShortcutPath"
