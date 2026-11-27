# Optional fixture authoring on Windows; the experiment reads the archived media.
$ErrorActionPreference = 'Stop'
$voice = New-Object -ComObject SAPI.SpVoice
$voice.Voice = $voice.GetVoices('Language=804').Item(0)
foreach ($line in Get-Content (Join-Path $PSScriptRoot 'media_sync_cases.jsonl') -Encoding utf8) {
    $case = $line | ConvertFrom-Json
    $stream = New-Object -ComObject SAPI.SpFileStream
    try {
        $stream.Open((Join-Path $PSScriptRoot $case.audio), 3)
        $voice.AudioOutputStream = $stream
        [void]$voice.Speak($case.utterance)
    } finally {
        $stream.Close()
    }
}
