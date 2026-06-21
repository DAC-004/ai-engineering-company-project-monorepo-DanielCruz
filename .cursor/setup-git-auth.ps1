#Requires -Version 5.1
$ErrorActionPreference = 'Stop'

if (-not $env:GITHUB_PAT -and $env:DAC004_GITHUB_PAT) {
  $env:GITHUB_PAT = $env:DAC004_GITHUB_PAT
}

if (-not $env:GITHUB_PAT) {
  Write-Error 'GITHUB_PAT is not set and DAC004_GITHUB_PAT is unavailable.'
  exit 1
}

$env:GIT_TERMINAL_PROMPT = '0'
$pat = $env:GITHUB_PAT

# PowerShell passes '' poorly to git on Windows; --unset-all clears helpers instead.
git config --global --unset-all credential.helper 2>$null
git config --global --add credential.helper ('!f() { echo username=x-access-token; echo password=' + $pat + '; }; f')

if ($env:GH_TOKEN) {
  Remove-Item Env:GH_TOKEN
}

$pat | gh auth login --hostname github.com --with-token
if ($LASTEXITCODE -ne 0) {
  Write-Error 'gh auth login failed. Install GitHub CLI: https://cli.github.com/'
  exit 1
}

gh auth setup-git
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}

# Remove stale rewrites (for example x-access-token:@ with an empty token).
git config --global --get-regexp '^url\..*github\.com/DAC-004/.*\.insteadOf$' 2>$null |
  ForEach-Object {
    $key = ($_ -split ' ', 2)[0]
    if ($key -match 'x-access-token:@') {
      git config --global --unset-all $key 2>$null
    }
  }

$rewriteKey = "url.https://x-access-token:$pat@github.com/DAC-004/.insteadOf"
git config --global $rewriteKey 'https://github.com/DAC-004/'

$login = gh api user --jq .login
Write-Host "Git auth configured for $login"
