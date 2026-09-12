$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$root = $PSScriptRoot
$settingsPath = Join-Path $root 'host-settings.json'
if (!(Test-Path -LiteralPath $settingsPath -PathType Leaf)) {
    [void][Windows.Forms.MessageBox]::Show('Start your own Enhanced host with Play-Enhanced.cmd first. To use DM on the shared Internet realms, ask their host to grant you control, then press G in game.','MSR Dungeon Master')
    exit 0
}
$settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
$form = New-Object Windows.Forms.Form
$form.Text = 'MSR Dungeon Master - Host controls'
$form.ClientSize = New-Object Drawing.Size(720,510)
$form.StartPosition = 'CenterScreen'
$form.Font = New-Object Drawing.Font('Segoe UI',10)
$realm = New-Object Windows.Forms.ComboBox
$realm.SetBounds(16,16,440,30)
$realm.DropDownStyle = 'DropDownList'
foreach ($server in $settings.servers) { [void]$realm.Items.Add($server.hostname) }
$realm.SelectedIndex = 0
$form.Controls.Add($realm)
$output = New-Object Windows.Forms.TextBox
$output.SetBounds(16,108,688,290)
$output.Multiline = $true
$output.ReadOnly = $true
$output.ScrollBars = 'Both'
$output.Font = New-Object Drawing.Font('Consolas',9)
$form.Controls.Add($output)
$slot = New-Object Windows.Forms.NumericUpDown
$slot.SetBounds(110,65,60,28)
$slot.Minimum = 0
$slot.Maximum = 31
$form.Controls.Add($slot)
$label = New-Object Windows.Forms.Label
$label.Text = 'Player slot:'
$label.SetBounds(16,68,94,24)
$form.Controls.Add($label)
function Send-Command([string]$command) {
    $server = $settings.servers[$realm.SelectedIndex]
    $form.UseWaitCursor = $true
    try {
        $result = & (Join-Path $root 'runtime\python.exe') (Join-Path $root 'FN\game_query.py') rcon --port $server.port --server-id $server.id --command $command 2>&1
        $output.Text = ($result | Out-String)
        if ($LASTEXITCODE -ne 0 -or !$output.Text.Trim()) { $output.AppendText("`r`nStart the realm host first. The server did not answer.") }
    } finally { $form.UseWaitCursor = $false }
}
function Add-Button([string]$text,[int]$x,[int]$y,[int]$width,[scriptblock]$action) {
    $button = New-Object Windows.Forms.Button
    $button.Text = $text
    $button.SetBounds($x,$y,$width,30)
    $button.Add_Click($action)
    $form.Controls.Add($button)
}
Add-Button 'Refresh players' 472 16 232 { Send-Command 'status' }
Add-Button 'Grant Dungeon Master' 184 62 244 { Send-Command ('ms_dm_grant ' + [int]$slot.Value) }
Add-Button 'Revoke all grants' 440 62 264 { Send-Command 'ms_dm_revoke' }
Add-Button 'Event status' 16 412 160 { Send-Command 'ms_event status' }
Add-Button 'Random events ON' 184 412 164 { Send-Command 'ms_event on' }
Add-Button 'Random events OFF' 356 412 172 { Send-Command 'ms_event off' }
Add-Button 'Clear encounter' 536 412 168 { Send-Command 'ms_event clear' }
$hint = New-Object Windows.Forms.Label
$hint.Text = 'Refresh, find your # player slot, then grant it. In game: G > Dungeon Master. Grants end on disconnect or map change.'
$hint.SetBounds(16,456,688,46)
$form.Controls.Add($hint)
$form.Add_Shown({ Send-Command 'status' })
[void]$form.ShowDialog()

