# PowerShell script to create EcoMate desktop shortcut
$WScriptShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path $DesktopPath "EcoMate.lnk"
$Shortcut = $WScriptShell.CreateShortcut($ShortcutPath)

# Set the target to the batch file
$Shortcut.TargetPath = Join-Path $PSScriptRoot "Launch EcoMate.bat"
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.IconLocation = Join-Path $PSScriptRoot "ecomate.ico"
$Shortcut.Description = "Launch EcoMate AI Assistant"
$Shortcut.Save()

Write-Host "Desktop shortcut created successfully at: $ShortcutPath" -ForegroundColor Green
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
