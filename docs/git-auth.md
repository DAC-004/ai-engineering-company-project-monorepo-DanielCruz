# Git authentication for DAC-004 projects

Use this guide when `git push` fails with **403 Permission denied** to `DAC-004/*` repositories because Git is using the wrong GitHub account (for example `danielcruz-glitch` instead of an account with org access).

This setup is **global**: once configured, it applies to every current and future clone under `https://github.com/DAC-004/`.

## Prerequisites

1. A GitHub **personal access token (PAT)** from an account that can write to the `DAC-004` organization.
   - GitHub → **Settings → Developer settings → Personal access tokens**
   - Scope: at least **`repo`**
2. [GitHub CLI](https://cli.github.com/) (`gh`) installed.
3. Git for Windows (includes the shell helpers used by the credential helper).

## One-time setup

### 1. Store the PAT permanently (Windows)

**Settings → System → About → Advanced system settings → Environment Variables**

Add a **User** variable:

| Name | Value |
| --- | --- |
| `DAC004_GITHUB_PAT` | your `ghp_...` token |

Restart Cursor (or open a new terminal) so the variable is loaded.

### 2. Remove stale GitHub credentials (if push still fails)

**Control Panel → Credential Manager → Windows Credentials**

Delete entries for `git:https://github.com` or `github.com`, or run:

```powershell
cmdkey /delete:LegacyGeneric:target=git:https://github.com
```

### 3. Run the setup script

From any project in this monorepo (repo root):

**Windows (PowerShell):**

```powershell
.\.cursor\setup-git-auth.ps1
```

**macOS / Linux / Git Bash / Codespaces:**

```bash
./.cursor/setup-git-auth.sh
```

Both scripts:

- Use `DAC004_GITHUB_PAT` (or `GITHUB_PAT` if already set).
- Log in `gh` with the token.
- Configure Git to authenticate all `https://github.com/DAC-004/` URLs with that token.

## Verify

```powershell
gh auth status
gh api user --jq .login
git push origin main
```

You should see the correct GitHub username and pushes to `DAC-004/*` should succeed.

## New projects

Clone with the normal HTTPS URL:

```bash
git clone https://github.com/DAC-004/your-repo.git
```

No per-repo auth setup is required as long as step 3 was run once on the machine.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `error: wrong number of arguments` when running the PowerShell script | Fixed in `.cursor/setup-git-auth.ps1` — rerun the script after pulling the latest version. The old script used `credential.helper ''`, which Git for Windows rejects. |
| `DAC004_GITHUB_PAT is unavailable` | Set the env var and restart the terminal. |
| `gh auth login failed` | Install or update GitHub CLI. |
| Still 403 on push | Clear Windows Credential Manager entries and run the setup script again. |
| Token expired | Create a new PAT, update `DAC004_GITHUB_PAT`, rerun the setup script. |

## Security notes

- Do not commit PATs to the repository.
- Prefer `DAC004_GITHUB_PAT` over hard-coding tokens in scripts.
- Revoke old tokens in GitHub when rotating credentials.
