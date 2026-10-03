Add-Type -AssemblyName System.Speech
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$audio = Join-Path $root 'audio'
New-Item -ItemType Directory -Force -Path $audio | Out-Null
$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice.Rate = -1
$texts = Get-Content (Join-Path $root 'narration.txt') -Raw -Encoding UTF8
$sections = $texts -split "`r?`n`r?`n"
for($i=0; $i -lt $sections.Count; $i++) {
  $path = Join-Path $audio ("voice_{0:D2}.wav" -f ($i+1))
  $voice.SetOutputToWaveFile($path)
  $voice.Speak($sections[$i])
  $voice.SetOutputToNull()
}
$voice.Dispose()
