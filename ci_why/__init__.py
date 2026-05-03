#!/usr/bin/env python3
"""
ci-why — find and explain CI failures in plain English.

Usage:
    python ci_why.py build.log
    cat build.log | python ci_why.py -
    python ci_why.py build.log --no-ai      # pattern-only, no API call
    python ci_why.py build.log --raw        # show extracted lines only

Requires: ANTHROPIC_API_KEY in env (only for AI explanation).
"""

from __future__ import annotations

import os
import re
import sys
import json
import textwrap
from pathlib import Path
from typing import NamedTuple

import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich import box
from rich.table import Table

app = typer.Typer(help="Find and explain CI build failures.")
console = Console()

# ── Failure signal patterns ─────────────────────────────────────────────────
# Ordered by specificity — first match wins for severity labelling.

PATTERNS: list[tuple[str, str, re.Pattern]] = [
    # (label, severity, pattern)
    ("Test failure",    "critical", re.compile(
        r"(FAIL|FAILED|AssertionError|assert\s+\w|✗|✕|● .+ ›)", re.I
    )),
    ("Error",           "critical", re.compile(
        r"(^\s*Error[: ]|Traceback \(most recent|exception:|panic:|fatal error)", re.I | re.M
    )),
    ("Exit code",       "critical", re.compile(
        r"(exit(ed)? (with )?code [^0]|Process (completed|exited) with exit code [^0])", re.I
    )),
    ("Missing module",  "high",    re.compile(
        r"(ModuleNotFoundError|cannot find module|no module named|command not found)", re.I
    )),
    ("Build error",     "high",    re.compile(
        r"(Build failed|compilation (failed|error)|SyntaxError|TypeError:|NameError:)", re.I
    )),
    ("Dependency",      "high",    re.compile(
        r"(npm ERR!|yarn error|pip.*error|Could not resolve|ERESOLVE|peer dep)", re.I
    )),
    ("Network/timeout", "medium",  re.compile(
        r"(Connection refused|timed? ?out|ECONNREFUSED|getaddrinfo ENOTFOUND)", re.I
    )),
    ("Lint/type check", "medium",  re.compile(
        r"(eslint|tslint|mypy|ruff|flake8).*(error|warning)|TS\d{4}:", re.I
    )),
    ("Warning→error",   "medium",  re.compile(
        r"(Treating warnings as errors|--werror|-Werror)", re.I
    )),
    ("Permission",      "medium",  re.compile(
        r"(Permission denied|EACCES|access denied)", re.I
    )),
]

NOISE_RE = re.compile(
    r"^(\s*$"                           # blank lines
    r"|.*\[debug\].*"                   # debug noise
    r"|.*downloading.*\d+%.*"           # download progress
    r"|.*\[OPT\].*"                     # optimizer spam
    r"|.*copying.*\.\.\."               # file copy progress
    r"|.*already (up.to.date|installed)" # no-op installs
    r"|##\[group\]|##\[endgroup\]"      # GHA fold markers
    r"|^time=.*level=debug"             # Go debug logs
    r")",
    re.I,
)

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2}
SEVERITY_COLOR = {"critical": "red", "high": "yellow", "medium": "blue"}


# ── Data structures ─────────────────────────────────────────────────────────

class Hit(NamedTuple):
    lineno: int
    label: str
    severity: str
    text: str


# ── Core extraction ─────────────────────────────────────────────────────────

def extract_failures(lines: list[str], context: int = 2) -> list[Hit]:
    """Return matched lines with surrounding context, deduped."""
    hits: list[Hit] = []
    seen_linenos: set[int] = set()

    for i, line in enumerate(lines):
        if NOISE_RE.match(line):
            continue
        for label, severity, pat in PATTERNS:
            if pat.search(line):
                # Grab context window
                start = max(0, i - context)
                end = min(len(lines), i + context + 1)
                for j in range(start, end):
                    if j not in seen_linenos:
                        seen_linenos.add(j)
                        sev = severity if j == i else "context"
                        hits.append(Hit(j + 1, label if j == i else "context", sev, lines[j].rstrip()))
                break  # first matching pattern wins

    # Sort by line number
    hits.sort(key=lambda h: h.lineno)
    return hits


def summarise_hits(hits: list[Hit]) -> str:
    """Compact text version of hits for passing to the LLM."""
    lines = []
    for h in hits:
        if h.severity == "context":
            lines.append(f"  {h.lineno:>5}: {h.text}")
        else:
            lines.append(f"[{h.severity.upper()}] line {h.lineno} ({h.label}): {h.text}")
    return "\n".join(lines)


# ── AI explanation ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = textwrap.dedent("""\
    You are a CI debugging assistant. You will receive the key failure lines
    extracted from a CI log. Your job is to:
    1. State in ONE sentence what actually went wrong (the root cause).
    2. List up to 3 concrete, actionable fix steps — each on its own line,
       prefixed with a number and a space.
    3. If you can identify the specific file, line number, or command to run,
       include it.
    Be direct. No preamble. No "it seems like". No markdown headers.
""")


def explain_with_ai(extracted: str) -> str | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return None

    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 400,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": extracted}],
    }

    try:
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"].strip()
    except httpx.HTTPStatusError as e:
        console.print(f"[yellow]AI unavailable (HTTP {e.response.status_code}) — showing pattern analysis only.[/yellow]")
        return None
    except Exception as e:
        console.print(f"[yellow]AI unavailable ({e}) — showing pattern analysis only.[/yellow]")
        return None


# ── Rendering ───────────────────────────────────────────────────────────────

def render_hits_table(hits: list[Hit]) -> None:
    t = Table(box=box.SIMPLE_HEAD, show_header=True, highlight=True)
    t.add_column("Line", style="dim", justify="right", width=6)
    t.add_column("Severity", width=10)
    t.add_column("Label", width=16)
    t.add_column("Content")

    for h in hits:
        color = SEVERITY_COLOR.get(h.severity, "white")
        t.add_row(
            str(h.lineno),
            f"[{color}]{h.severity}[/{color}]",
            h.label,
            h.text[:120],
        )
    console.print(t)


# ── CLI ─────────────────────────────────────────────────────────────────────

@app.command()
def main(
    source: str = typer.Argument(
        ..., help="CI log file path, or '-' to read from stdin."
    ),
    no_ai: bool = typer.Option(
        False, "--no-ai", help="Skip AI explanation; show pattern matches only."
    ),
    raw: bool = typer.Option(
        False, "--raw", help="Print extracted failure lines as plain text and exit."
    ),
    context: int = typer.Option(
        2, "--context", "-c",
        help="Lines of context around each failure (default 2).",
        min=0, max=10,
    ),
    max_lines: int = typer.Option(
        50_000, "--max-lines",
        help="Truncate log to this many lines before scanning (default 50 000).",
        min=100,
    ),
) -> None:
    """Diagnose CI failures: extract signal lines and explain them in plain English."""

    # ── Load ──
    if source == "-":
        raw_text = sys.stdin.read()
    else:
        p = Path(source)
        if not p.exists():
            console.print(f"[red]Error:[/red] File not found: {source}")
            raise typer.Exit(1)
        raw_text = p.read_text(encoding="utf-8", errors="replace")

    lines = raw_text.splitlines()
    total_lines = len(lines)
    if total_lines > max_lines:
        console.print(f"[dim]Log has {total_lines} lines; scanning last {max_lines}.[/dim]")
        lines = lines[-max_lines:]

    # ── Extract ──
    with console.status("Scanning for failures…"):
        hits = extract_failures(lines, context=context)

    if not hits:
        console.print(
            Panel(
                "[green]No failure signals found.[/green]\n"
                "The log may show a success, or the failure pattern isn't recognised.\n"
                "Try [bold]--context 5[/bold] or check the raw log.",
                title="ci-why",
                border_style="green",
            )
        )
        return

    if raw:
        for h in hits:
            print(f"{h.lineno}: {h.text}")
        return

    # ── Display ──
    signal_hits = [h for h in hits if h.severity != "context"]
    console.print(Rule(f"[bold]ci-why[/bold] — {len(signal_hits)} signal(s) in {total_lines} lines"))
    render_hits_table(hits)

    summary = summarise_hits(hits)

    if not no_ai:
        with console.status("Asking AI for root cause…"):
            explanation = explain_with_ai(summary)

        if explanation:
            console.print(
                Panel(
                    explanation,
                    title="[bold cyan]Root cause & fixes[/bold cyan]",
                    border_style="cyan",
                    padding=(1, 2),
                )
            )
        else:
            console.print(
                "[dim]Set ANTHROPIC_API_KEY for AI-powered root cause analysis.[/dim]"
            )
    else:
        console.print("[dim]AI explanation skipped (--no-ai).[/dim]")


if __name__ == "__main__":
    app()
