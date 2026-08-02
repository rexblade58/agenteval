"""AgentEval arena - shareable SVG badges.

Generates self-contained shields-style SVG badges (no external services,
no network-loaded assets) so repositories can show verification evidence
in their READMEs:

    agenteval verify --badge agenteval-verified.svg
    agenteval arena --repo . --task "..." --agents codex --badge winner.svg
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .results import ArenaResult

GREEN = "#4c1"
RED = "#e05d44"
GRAY = "#555"
BLUE = "#3b82f6"


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _render_badge(label: str, value: str, color: str, width: int = 140) -> str:
    """Render a shields-style badge with two segments."""
    label_width = 18 + len(label) * 7
    value_width = max(28, width - label_width)
    total = label_width + value_width

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="20" role="img" aria-label="{_escape(label)}: {_escape(value)}">
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r"><rect width="{total}" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_width}" height="20" fill="{GRAY}"/>
    <rect x="{label_width}" width="{value_width}" height="20" fill="{color}"/>
    <rect width="{total}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="{label_width // 2}" y="14" fill="#010101" fill-opacity=".3">{_escape(label)}</text>
    <text x="{label_width // 2}" y="13">{_escape(label)}</text>
    <text x="{label_width + value_width // 2}" y="14" fill="#010101" fill-opacity=".3">{_escape(value)}</text>
    <text x="{label_width + value_width // 2}" y="13">{_escape(value)}</text>
  </g>
</svg>"""


def verified_badge(passed: bool, detail: str = "") -> str:
    """Badge for a verification run: AgentEval Verified (green) or Failed (red)."""
    if passed:
        value = "Verified"
        if detail:
            value += f" {detail}"
        return _render_badge("AgentEval", value, GREEN)
    return _render_badge("AgentEval", "Failed", RED)


def winner_badge(result: ArenaResult) -> str:
    """Badge for an arena run: winner + score."""
    winner = result.winner
    if winner is None:
        return _render_badge("AgentEval Arena", "no winner", GRAY)
    return _render_badge(
        "AgentEval Arena",
        f"Winner: {winner.agent} {winner.score.total}",
        GREEN if winner.score.total >= 60 else BLUE,
    )


def write_badge(svg: str, path: Path) -> None:
    """Write an SVG badge to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding="utf-8")


def markdown_snippet(path: str) -> str:
    """Markdown snippet to embed a badge in a README."""
    return f"[![AgentEval]({path})](#)"


__all__ = ["verified_badge", "winner_badge", "write_badge", "markdown_snippet"]
