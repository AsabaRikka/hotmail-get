$ws = New-Object -ComObject WScript.Shell
$desktop = [System.Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop "LovartFetcher.lnk"
$s = $ws.CreateShortcut($shortcutPath)
$s.TargetPath = "wscript.exe"
$s.Arguments = """D:\App\hotmail-get\run_lovart.vbs"""
$s.WorkingDirectory = "D:\App\hotmail-get"
$s.IconLocation = "python.exe,0"
$s.Save()
