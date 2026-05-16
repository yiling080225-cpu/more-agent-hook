$ws = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$link = $ws.CreateShortcut("$desktop\Agent联邦客户端.lnk")
$link.TargetPath = 'pythonw.exe'
$link.Arguments = 'fedcli_gui.py'
$link.WorkingDirectory = 'd:\multimodal_agent_federation_mvp'
$link.IconLocation = 'pythonw.exe,0'
$link.Description = 'Agent 联邦平台 GUI 客户端'
$link.Save()
Write-Host "Shortcut created: $desktop\Agent联邦客户端.lnk"
