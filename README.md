<div align="center">

<h1>ci-why</h1>

<p>Your CI failed. 400 lines of logs. This tells you why in seconds.</p>

[![PyPI version](https://img.shields.io/pypi/v/ci-why?color=f85149&labelColor=0d1117&logo=pypi&logoColor=white)](https://pypi.org/project/ci-why)
[![Python](https://img.shields.io/pypi/pyversions/ci-why?color=f85149&labelColor=0d1117&logo=python&logoColor=white)](https://pypi.org/project/ci-why)
[![License: MIT](https://img.shields.io/badge/license-MIT-f85149?labelColor=0d1117)](LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/ci-why?color=f85149&labelColor=0d1117)](https://pypi.org/project/ci-why)

<img src="https://raw.githubusercontent.com/gitwingo/ci-why/main/docs/images/screenshot.png" alt="ci-why terminal screenshot" width="820">

</div>

---

CI logs are noisy. A failed GitHub Actions run gives you hundreds of lines of downloading, copying, grouping, and progress output — and somewhere buried in it is the 3 lines that actually matter.

`ci-why` strips the noise, extracts the signal lines with context, and optionally asks Claude to explain the root cause and give you concrete fix steps.

No CI platform lock-in. Works on any log you can pipe or point at a file.

---

## Install

```bash
pip install ci-why
```

Or with pipx (recommended for CLI tools — keeps it isolated):

```bash
pipx install ci-why
```

---

## Usage

```bash
# From a log file
ci-why build.log

# Pipe directly from GitHub CLI
gh run view --log | ci-why -

# Pattern analysis only — no API call
ci-why build.log --no-ai

# Just the raw extracted failure lines (great for piping)
ci-why build.log --raw

# More context lines around each failure
ci-why build.log --context 5

# Scan only the last N lines (for huge logs)
ci-why build.log --max-lines 10000
```

---

## AI explanation

Set your Anthropic API key to get plain-English root cause analysis and fix steps:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
ci-why build.log
```

Without the key, `ci-why` still works — it shows the extracted failure lines using pattern matching only. The AI explanation is additive, not required.

---

## What it recognises

`ci-why` detects failure signals across Python, Node, Go, Rust, and generic CI output:

| Signal | Examples |
|---|---|
| Test failures | `FAIL`, `AssertionError`, Jest `●`, pytest `FAILED` |
| Errors & tracebacks | `Traceback (most recent call last)`, `panic:`, `fatal error` |
| Exit codes | `Process completed with exit code 1` |
| Missing modules | `ModuleNotFoundError`, `Cannot find module` |
| Build errors | `Build failed`, `SyntaxError`, `compilation error` |
| Dependency errors | `npm ERR!`, `yarn error`, `pip error`, `ERESOLVE` |
| Network / timeout | `Connection refused`, `ECONNREFUSED`, `timed out` |
| Lint / type errors | ESLint, mypy, ruff, TypeScript `TS2345:` |
| Permission errors | `Permission denied`, `EACCES` |

Noise filtered out: download progress, `[debug]` lines, file copy progress, GHA group markers, already-installed notices.

---

## All options

```
Arguments:
  SOURCE        CI log file path, or '-' to read from stdin.

Options:
  --no-ai       Skip AI explanation; show pattern matches only.
  --raw         Print extracted failure lines as plain text and exit.
  -c, --context Lines of context around each failure (default: 2, max: 10).
  --max-lines   Truncate log to this many lines before scanning (default: 50000).
  --help        Show this message and exit.
```

---

## Examples

**GitHub Actions log via CLI:**
```bash
gh run view 1234567890 --log | ci-why -
```

**GitLab CI — download job log and analyse:**
```bash
curl -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "https://gitlab.com/api/v4/projects/123/jobs/456/trace" | ci-why -
```

**Save just the failure lines to a file:**
```bash
ci-why build.log --raw > failures.txt
```

**Use in a script — exit code reflects whether failures were found:**
```bash
ci-why build.log --no-ai --raw || echo "Failures detected"
```

---

## Where to install / publish this tool

| Platform | Command | Notes |
|---|---|---|
| **PyPI** | `pip install ci-why` | Primary distribution |
| **pipx** | `pipx install ci-why` | Best for CLI tools — isolated environment |
| **Homebrew** (tap) | `brew install gitwingo/tap/ci-why` | macOS/Linux users who avoid pip |
| **GitHub Releases** | Single `.py` file download | Zero-install option |
| **npm wrapper** | `npm install -g ci-why` | Reaches frontend/Node developers |

> **Recommended publishing order:** PyPI → pipx (works automatically) → Homebrew tap after traction → npm wrapper if Node developer adoption is strong.

---

## Development

```bash
git clone https://github.com/gitwingo/ci-why
cd ci-why
pip install -e .
```

---
## Support

If sniff-schema has been useful to you, consider supporting its development:

<a href="https://ko-fi.com/gitwingo">
  <img src="https://ko-fi.com/img/githubbutton_sm.svg" alt="Buy Me a Ko-Fi" />
</a>


## Connect

- GitHub: [@gitwingo](https://github.com/gitwingo)
- Reddit: [u/gitwingo](https://reddit.com/user/gitwingo)
- X / Twitter: [@gitwingo](https://x.com/gitwingo)

---

<div align="center">
  <sub>Made with 💖 by <a href="https://github.com/gitwingo">Gitwingo</a></sub>
</div>

---
## License

MIT © [gitwingo](https://github.com/gitwingo)
