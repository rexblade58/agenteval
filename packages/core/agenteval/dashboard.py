"""AgentEval - local web dashboard.

Serves evaluation reports from a reports/ directory over HTTP so you can
visualize accuracy, cost, and latency trends across providers and time.

Zero dependencies: built entirely on Python's standard library.
"""

from __future__ import annotations

import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


def load_reports(reports_dir: Path) -> list[dict[str, Any]]:
    """Load all valid *.json reports from a directory, newest first."""
    reports: list[dict[str, Any]] = []
    if not reports_dir.is_dir():
        return reports

    for path in sorted(reports_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if "provider" not in data or "accuracy" not in data:
            continue
        data["_file"] = path.name
        reports.append(data)

    reports.sort(key=lambda r: r.get("generated_at", ""), reverse=True)
    return reports


def _fmt_pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "-"


def _fmt_usd(value: Any) -> str:
    try:
        return f"${float(value):.6f}"
    except (TypeError, ValueError):
        return "-"


def _fmt_ms(value: Any) -> str:
    try:
        return f"{float(value):.0f} ms"
    except (TypeError, ValueError):
        return "-"


def _fmt_time(value: Any) -> str:
    if not value:
        return "-"
    try:
        return value[:19].replace("T", " ")
    except TypeError:
        return str(value)


def _provider_summary(reports: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Average accuracy/latency/cost per provider."""
    agg: dict[str, dict[str, list[float]]] = {}
    for r in reports:
        name = r.get("provider", "unknown")
        entry = agg.setdefault(name, {"accuracy": [], "latency": [], "cost": []})
        try:
            entry["accuracy"].append(float(r["accuracy"]))
        except (KeyError, TypeError, ValueError):
            pass
        try:
            entry["latency"].append(float(r["avg_latency_ms"]))
        except (KeyError, TypeError, ValueError):
            pass
        try:
            entry["cost"].append(float(r["total_cost_usd"]))
        except (KeyError, TypeError, ValueError):
            pass

    summary: dict[str, dict[str, float]] = {}
    for name, buckets in agg.items():
        summary[name] = {
            "accuracy": (sum(buckets["accuracy"]) / len(buckets["accuracy"])) if buckets["accuracy"] else 0.0,
            "latency": (sum(buckets["latency"]) / len(buckets["latency"])) if buckets["latency"] else 0.0,
            "cost": (sum(buckets["cost"]) / len(buckets["cost"])) if buckets["cost"] else 0.0,
        }
    return summary


def _trend_rows(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Accuracy trend over time, oldest first."""
    rows = [r for r in reports if r.get("generated_at")]
    rows.sort(key=lambda r: r["generated_at"])
    return rows


def render_html(reports: list[dict[str, Any]]) -> str:
    """Render the dashboard as a self-contained HTML page."""
    summary = _provider_summary(reports)
    trend = _trend_rows(reports)
    max_accuracy = max((v["accuracy"] for v in summary.values()), default=0.0)

    provider_bars = "".join(
        f"""
        <div class="bar-row">
          <span class="bar-label">{name}</span>
          <div class="bar-track"><div class="bar-fill" style="width:{v['accuracy'] / max_accuracy * 100 if max_accuracy else 0:.1f}%"></div></div>
          <span class="bar-value">{_fmt_pct(v['accuracy'])}</span>
          <span class="bar-meta">{_fmt_ms(v['latency'])} &middot; {_fmt_usd(v['cost'])} avg</span>
        </div>"""
        for name, v in sorted(summary.items(), key=lambda kv: kv[1]["accuracy"], reverse=True)
    ) or '<p class="muted">No reports yet.</p>'

    trend_spark = ""
    if len(trend) >= 2:
        width, height = 320, 60
        pad = 4
        vals = [float(r["accuracy"]) for r in trend]
        lo, hi = min(vals), max(vals)
        span = (hi - lo) or 1.0
        points = [
            (pad + i * (width - 2 * pad) / (len(vals) - 1),
             height - pad - (v - lo) / span * (height - 2 * pad))
            for i, v in enumerate(vals)
        ]
        coords = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        trend_spark = (
            f'<svg viewBox="0 0 {width} {height}" class="spark" aria-label="accuracy trend">'
            f'<polyline points="{coords}" fill="none" stroke="#4f46e5" stroke-width="2"/></svg>'
        )

    rows = "".join(
        f"""
        <tr>
          <td><a href="/reports/{r['_file']}">{r['_file']}</a></td>
          <td>{r.get('provider', '-')}</td>
          <td>{r.get('model', '-')}</td>
          <td>{r.get('suite', '-')}</td>
          <td>{_fmt_time(r.get('generated_at'))}</td>
          <td class="num">{_fmt_pct(r.get('accuracy'))}</td>
          <td class="num">{r.get('passed', '-')}/{r.get('total_tasks', '-')}</td>
          <td class="num">{_fmt_ms(r.get('avg_latency_ms'))}</td>
          <td class="num">{_fmt_usd(r.get('total_cost_usd'))}</td>
        </tr>"""
        for r in reports
    ) or '<tr><td colspan="9" class="muted">No reports found. Run <code>agenteval run --output reports/&lt;name&gt;.json</code> first.</td></tr>'

    latest = reports[0] if reports else {}

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AgentEval Dashboard</title>
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: system-ui, -apple-system, sans-serif; margin: 0; background: #f8fafc; color: #0f172a; }}
  header {{ padding: 24px 32px; background: #0f172a; color: #f8fafc; }}
  header h1 {{ margin: 0; font-size: 1.4rem; }}
  header p {{ margin: 4px 0 0; color: #94a3b8; font-size: 0.9rem; }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 24px 32px 48px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 24px; }}
  .card {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px 16px; }}
  .card .label {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; }}
  .card .value {{ font-size: 1.5rem; font-weight: 650; margin-top: 4px; }}
  .card .sub {{ font-size: 0.8rem; color: #94a3b8; }}
  h2 {{ font-size: 1rem; margin: 24px 0 12px; color: #334155; }}
  .panel {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px; }}
  .bar-row {{ display: grid; grid-template-columns: 110px 1fr 80px 180px; gap: 12px; align-items: center; margin-bottom: 10px; }}
  .bar-label {{ font-size: 0.85rem; color: #334155; overflow: hidden; text-overflow: ellipsis; }}
  .bar-track {{ background: #eef2f7; border-radius: 6px; height: 12px; overflow: hidden; }}
  .bar-fill {{ height: 100%; background: #4f46e5; border-radius: 6px; }}
  .bar-value {{ font-size: 0.85rem; font-weight: 600; }}
  .bar-meta {{ font-size: 0.8rem; color: #94a3b8; }}
  .spark {{ display: block; margin: 8px auto; max-width: 100%; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; }}
  th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid #eef2f7; font-size: 0.85rem; }}
  th {{ background: #f1f5f9; color: #475569; font-weight: 600; }}
  tr:last-child td {{ border-bottom: none; }}
  td.num {{ font-variant-numeric: tabular-nums; }}
  a {{ color: #4f46e5; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .muted {{ color: #94a3b8; }}
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  @media (max-width: 800px) {{ .grid-2 {{ grid-template-columns: 1fr; }} .bar-row {{ grid-template-columns: 90px 1fr 70px; }} .bar-meta {{ display: none; }} }}
</style>
</head>
<body>
<header>
  <h1>AgentEval Dashboard</h1>
  <p>{len(reports)} report(s) &middot; local only &middot; schema v{1}</p>
</header>
<main>
  <div class="cards">
    <div class="card"><div class="label">Reports</div><div class="value">{len(reports)}</div><div class="sub">JSON files</div></div>
    <div class="card"><div class="label">Providers</div><div class="value">{len(summary)}</div><div class="sub">compared</div></div>
    <div class="card"><div class="label">Latest accuracy</div><div class="value">{_fmt_pct(latest.get('accuracy'))}</div><div class="sub">{latest.get('provider', '-')} &middot; {latest.get('model', '-')}</div></div>
    <div class="card"><div class="label">Latest cost</div><div class="value">{_fmt_usd(latest.get('total_cost_usd'))}</div><div class="sub">{_fmt_ms(latest.get('avg_latency_ms'))} avg</div></div>
  </div>

  <div class="grid-2">
    <section>
      <h2>Accuracy by provider (avg)</h2>
      <div class="panel">{provider_bars}</div>
    </section>
    <section>
      <h2>Accuracy over time</h2>
      <div class="panel">{trend_spark or '<p class="muted">Need at least 2 reports with timestamps.</p>'}</div>
    </section>
  </div>

  <h2>All reports</h2>
  <table>
    <thead>
      <tr><th>File</th><th>Provider</th><th>Model</th><th>Suite</th><th>Generated</th><th>Accuracy</th><th>Passed</th><th>Latency</th><th>Cost</th></tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</main>
</body>
</html>"""


def make_handler(reports_dir: Path) -> type[BaseHTTPRequestHandler]:
    """Create an HTTP handler bound to a reports directory."""

    class DashboardHandler(BaseHTTPRequestHandler):
        def _send(self, status: int, content: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            reports = load_reports(reports_dir)

            if path in ("/", "/index.html"):
                self._send(200, render_html(reports).encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/api/reports":
                self._send(200, json.dumps(reports).encode("utf-8"), "application/json")
            elif path.startswith("/reports/"):
                name = path.removeprefix("/reports/")
                target = (reports_dir / name).resolve()
                if reports_dir.resolve() not in target.parents or not target.is_file():
                    self._send(404, b'{"error":"not found"}', "application/json")
                    return
                try:
                    content = target.read_bytes()
                except OSError:
                    self._send(500, b'{"error":"read failed"}', "application/json")
                    return
                self._send(200, content, "application/json")
            else:
                self._send(404, b'{"error":"not found"}', "application/json")

        def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
            print(f"[dashboard] {self.address_string()} - {fmt % args}")

    return DashboardHandler


def serve(reports_dir: Path, host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start the dashboard server (blocking)."""
    if not reports_dir.is_dir():
        print(f"warning: {reports_dir} does not exist - create it or run "
              f"`agenteval run --output {reports_dir / 'report.json'}` first.")
    handler = make_handler(reports_dir)
    httpd = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{port}"
    print(f"AgentEval dashboard: {url}")
    print(f"Serving reports from: {reports_dir.resolve()}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        httpd.server_close()


__all__ = ["load_reports", "render_html", "make_handler", "serve"]
