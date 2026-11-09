# Creates the AI Editor folder for Scams on Record: D:\AI Editor\Scams on Record.
# Safe to run again: it only creates what's missing and never deletes or moves anything.
# Run: open PowerShell, paste this whole file, press Enter.

$accounts = @(
  @{ Drive = "D:"; Name = "Scams on Record" }
)

$readme = @"
What goes where
===============
raw         Your recordings, straight from the phone, the mic or a screen recording.
            Claude never changes or deletes anything in raw.
references  Reels you like, downloaded to study the style (pacing, hook, captions).
            For private study only: never reuse their footage, music or captions,
            and never use them as a source for facts.
done        Finished drafts from Claude: name-draft-v1.mp4, then v2, v3 after your notes.
            Review them here. Post only after the fact-check passes (RULES.md).
work        Claude's working files (transcripts, cut lists, frames). Safe to delete.

To edit: open the Claude desktop app, start a Local session in this folder,
and ask Claude to edit the newest recording in raw.
"@

foreach ($a in $accounts) {
  if (-not (Test-Path ($a.Drive + "\"))) {
    Write-Host "Skipped $($a.Name): drive $($a.Drive) isn't connected." -ForegroundColor Yellow
    continue
  }
  $root = Join-Path ($a.Drive + "\AI Editor") $a.Name
  foreach ($f in "raw", "references", "done", "work") {
    New-Item -ItemType Directory -Force -Path (Join-Path $root $f) | Out-Null
  }
  $txt = Join-Path $root "README.txt"
  if (-not (Test-Path $txt)) { Set-Content -Path $txt -Value $readme -Encoding UTF8 }
  Write-Host "Ready: $root" -ForegroundColor Green
}
