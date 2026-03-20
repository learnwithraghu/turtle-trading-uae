"""
HTML report renderer.

Generates output/report.html from scan results using Jinja2.
Dark-theme design with:
  - Commission strip
  - Stats row
  - Top-7 pick cards (each with full GTT box)
  - Full sortable results table
  - Daily workflow instructions
"""

from __future__ import annotations

import webbrowser
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, BaseLoader

# ── Inline Jinja2 template ────────────────────────────────────────────────────
_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>UAE Turtle Trader — {{ generated_at }}</title>
<style>
  :root {
    --bg:      #0f1117;
    --surface: #1a1d27;
    --card:    #22263a;
    --border:  #2e3347;
    --accent:  #4f8ef7;
    --green:   #22c55e;
    --red:     #ef4444;
    --yellow:  #f59e0b;
    --text:    #e2e8f0;
    --muted:   #64748b;
    --dfm:     #3b82f6;
    --adx:     #8b5cf6;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; font-size: 14px; }
  a { color: var(--accent); text-decoration: none; }

  /* ── Layout ── */
  .container { max-width: 1400px; margin: 0 auto; padding: 24px 16px; }
  header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
  header h1 { font-size: 1.6rem; font-weight: 700; letter-spacing: -0.5px; }
  .ts { color: var(--muted); font-size: 0.8rem; }

  /* ── Commission strip ── */
  .comm-strip { background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
    padding: 12px 20px; margin-bottom: 20px; display: flex; gap: 32px; flex-wrap: wrap; }
  .comm-item { display: flex; flex-direction: column; gap: 2px; }
  .comm-label { font-size: 0.7rem; color: var(--muted); text-transform: uppercase; letter-spacing: .5px; }
  .comm-value { font-size: 1rem; font-weight: 600; }

  /* ── Stats row ── */
  .stats { display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; }
  .stat-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
    padding: 14px 20px; flex: 1; min-width: 120px; }
  .stat-num  { font-size: 1.8rem; font-weight: 700; }
  .stat-lbl  { font-size: 0.72rem; color: var(--muted); margin-top: 2px; }

  /* ── Pick cards ── */
  .section-title { font-size: 1rem; font-weight: 600; margin-bottom: 14px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; }
  .picks-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 16px; margin-bottom: 40px; }

  .pick-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 18px; position: relative; }
  .pick-card.breakout { border-color: var(--green); box-shadow: 0 0 0 1px var(--green)20; }
  .pick-card.near     { border-color: var(--yellow); box-shadow: 0 0 0 1px var(--yellow)20; }

  .card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
  .ticker-name { font-size: 1.1rem; font-weight: 700; }
  .badges      { display: flex; gap: 6px; }
  .badge       { font-size: 0.65rem; font-weight: 700; padding: 3px 7px; border-radius: 4px; text-transform: uppercase; }
  .badge-dfm   { background: var(--dfm)33; color: var(--dfm); }
  .badge-adx   { background: var(--adx)33; color: var(--adx); }
  .badge-bo    { background: var(--green)22; color: var(--green); }
  .badge-near  { background: var(--yellow)22; color: var(--yellow); }

  .price-row   { display: flex; align-items: baseline; gap: 8px; margin-bottom: 12px; }
  .price-main  { font-size: 1.4rem; font-weight: 700; }
  .price-chg   { font-size: 0.85rem; }
  .pos { color: var(--green); } .neg { color: var(--red); }

  /* ── GTT box ── */
  .gtt-box { background: var(--surface); border-radius: 8px; padding: 12px; margin-bottom: 12px; }
  .gtt-title { font-size: 0.7rem; text-transform: uppercase; letter-spacing: .8px; color: var(--muted); margin-bottom: 8px; }
  .gtt-grid  { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 16px; }
  .gtt-item  { display: flex; flex-direction: column; gap: 1px; }
  .gtt-lbl   { font-size: 0.68rem; color: var(--muted); }
  .gtt-val   { font-size: 0.92rem; font-weight: 600; }
  .gtt-val.trigger { color: var(--accent); }
  .gtt-val.target  { color: var(--green); }
  .gtt-val.stop    { color: var(--red);   }
  .gtt-val.pnl     { color: var(--green); }
  .gtt-val.rr      { color: var(--yellow); }

  /* ── Distance bar ── */
  .dist-bar-wrap { margin-top: 4px; }
  .dist-label    { font-size: 0.68rem; color: var(--muted); margin-bottom: 4px; display: flex; justify-content: space-between; }
  .dist-bar      { height: 5px; background: var(--border); border-radius: 3px; overflow: hidden; }
  .dist-fill     { height: 100%; border-radius: 3px; transition: width .3s; }
  .fill-green    { background: var(--green); }
  .fill-yellow   { background: var(--yellow); }
  .fill-muted    { background: var(--muted); }

  /* ── Full results table ── */
  .table-wrap { overflow-x: auto; margin-bottom: 40px; }
  table { width: 100%; border-collapse: collapse; }
  thead th { background: var(--surface); color: var(--muted); font-size: 0.72rem; text-transform: uppercase;
    letter-spacing: .5px; padding: 10px 12px; text-align: right; cursor: pointer; white-space: nowrap; }
  thead th:first-child { text-align: left; }
  thead th:hover { color: var(--text); }
  tbody tr { border-bottom: 1px solid var(--border); }
  tbody tr:hover { background: var(--surface); }
  tbody td { padding: 9px 12px; text-align: right; font-size: 0.82rem; }
  tbody td:first-child { text-align: left; font-weight: 600; }
  .signal-bo   { color: var(--green); font-weight: 700; }
  .signal-near { color: var(--yellow); font-weight: 700; }
  .signal-none { color: var(--muted); }

  /* ── Workflow ── */
  .workflow { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 20px; }
  .workflow h3 { margin-bottom: 12px; font-size: 0.9rem; color: var(--accent); }
  .workflow ol { padding-left: 20px; line-height: 1.9; color: var(--muted); font-size: 0.84rem; }
  .workflow ol li strong { color: var(--text); }
</style>
</head>
<body>
<div class="container">

  <!-- Header -->
  <header>
    <h1>🐢 UAE Turtle Trader</h1>
    <span class="ts">Generated {{ generated_at }} · System {{ turtle_system }}-day</span>
  </header>

  <!-- Commission strip -->
  <div class="comm-strip">
    <div class="comm-item">
      <span class="comm-label">Trade Size</span>
      <span class="comm-value">AED {{ "{:,.0f}".format(trade_size_aed) }}</span>
    </div>
    <div class="comm-item">
      <span class="comm-label">Net P&amp;L Target</span>
      <span class="comm-value" style="color:var(--green)">AED {{ profit_target_aed }}</span>
    </div>
    <div class="comm-item">
      <span class="comm-label">DFM Round-trip</span>
      <span class="comm-value">≈ AED {{ dfm_rt_cost }}</span>
    </div>
    <div class="comm-item">
      <span class="comm-label">ADX Round-trip</span>
      <span class="comm-value">≈ AED {{ adx_rt_cost }}</span>
    </div>
    <div class="comm-item">
      <span class="comm-label">DFM Gross Needed</span>
      <span class="comm-value">AED {{ dfm_gross_needed }}</span>
    </div>
    <div class="comm-item">
      <span class="comm-label">ADX Gross Needed</span>
      <span class="comm-value">AED {{ adx_gross_needed }}</span>
    </div>
  </div>

  <!-- Stats row -->
  <div class="stats">
    <div class="stat-card">
      <div class="stat-num">{{ stats.scanned }}</div>
      <div class="stat-lbl">Stocks Scanned</div>
    </div>
    <div class="stat-card">
      <div class="stat-num" style="color:var(--green)">{{ stats.breakouts }}</div>
      <div class="stat-lbl">Breakouts</div>
    </div>
    <div class="stat-card">
      <div class="stat-num" style="color:var(--yellow)">{{ stats.near }}</div>
      <div class="stat-lbl">Near Breakout</div>
    </div>
    <div class="stat-card">
      <div class="stat-num" style="color:var(--accent)">{{ stats.curated }}</div>
      <div class="stat-lbl">Curated Picks</div>
    </div>
    <div class="stat-card">
      <div class="stat-num" style="color:var(--muted)">{{ stats.failed }}</div>
      <div class="stat-lbl">Failed / Skipped</div>
    </div>
  </div>

  <!-- Top picks -->
  <div class="section-title">Top {{ picks|length }} GTT-Ready Picks</div>
  <div class="picks-grid">
    {% for p in picks %}
    {% set exch = p.exchange %}
    {% set sig  = p.signal %}
    <div class="pick-card {{ 'breakout' if sig == 'BREAKOUT' else 'near' if sig == 'NEAR' else '' }}">
      <div class="card-header">
        <div>
          <div class="ticker-name">{{ p.ticker }}</div>
          {% if p.name %}<div style="font-size:.75rem;color:var(--muted);margin-top:2px">{{ p.name }}</div>{% endif %}
        </div>
        <div class="badges">
          <span class="badge {{ 'badge-dfm' if exch == 'DFM' else 'badge-adx' }}">{{ exch }}</span>
          {% if sig == 'BREAKOUT' %}<span class="badge badge-bo">🚀 BREAKOUT</span>
          {% elif sig == 'NEAR'   %}<span class="badge badge-near">⚡ NEAR</span>{% endif %}
        </div>
      </div>

      <div class="price-row">
        <span class="price-main">{{ "%.4f"|format(p.last_close) }}</span>
        <span class="price-chg {{ 'pos' if p.pct_to_high <= 0 else '' }}">
          {{ "%.2f"|format(p.pct_to_high) }}% to high
        </span>
      </div>

      <div class="gtt-box">
        <div class="gtt-title">GTT Order Parameters</div>
        <div class="gtt-grid">
          <div class="gtt-item">
            <span class="gtt-lbl">Trigger</span>
            <span class="gtt-val trigger">{{ "%.4f"|format(p.gtt_trigger) }}</span>
          </div>
          <div class="gtt-item">
            <span class="gtt-lbl">Qty (shares)</span>
            <span class="gtt-val">{{ p.shares }}</span>
          </div>
          <div class="gtt-item">
            <span class="gtt-lbl">Target</span>
            <span class="gtt-val target">{{ "%.4f"|format(p.target_price) }}</span>
          </div>
          <div class="gtt-item">
            <span class="gtt-lbl">Stop Loss</span>
            <span class="gtt-val stop">{{ "%.4f"|format(p.stop_loss) }}</span>
          </div>
          <div class="gtt-item">
            <span class="gtt-lbl">Net P&amp;L</span>
            <span class="gtt-val pnl">≈ AED {{ "%.0f"|format(p.net_pnl) }}</span>
          </div>
          <div class="gtt-item">
            <span class="gtt-lbl">R/R Ratio</span>
            <span class="gtt-val rr">{{ "%.2f"|format(p.rr) }}×</span>
          </div>
        </div>
      </div>

      <!-- Distance-to-high bar -->
      <div class="dist-bar-wrap">
        <div class="dist-label">
          <span>{{ p.period_low|round(4) }} ({{ turtle_system }}-day low)</span>
          <span>{{ p.period_high|round(4) }} (high)</span>
        </div>
        {% set range_sz = p.period_high - p.period_low %}
        {% set fill_pct = ((p.last_close - p.period_low) / range_sz * 100) if range_sz > 0 else 100 %}
        <div class="dist-bar">
          <div class="dist-fill {{ 'fill-green' if sig == 'BREAKOUT' else 'fill-yellow' if sig == 'NEAR' else 'fill-muted' }}"
               style="width: {{ [fill_pct, 100]|min }}%"></div>
        </div>
      </div>
    </div>
    {% endfor %}
  </div>

  <!-- Full results table -->
  <div class="section-title">All Scanned Stocks ({{ results|length }})</div>
  <div class="table-wrap">
    <table id="resultsTable">
      <thead>
        <tr>
          <th onclick="sortTable(0)">Ticker ↕</th>
          <th onclick="sortTable(1)">Exch ↕</th>
          <th onclick="sortTable(2)">Close ↕</th>
          <th onclick="sortTable(3)">Signal ↕</th>
          <th onclick="sortTable(4)">% to High ↕</th>
          <th onclick="sortTable(5)">Trigger ↕</th>
          <th onclick="sortTable(6)">Target ↕</th>
          <th onclick="sortTable(7)">Stop ↕</th>
          <th onclick="sortTable(8)">Shares ↕</th>
          <th onclick="sortTable(9)">Net P&amp;L ↕</th>
          <th onclick="sortTable(10)">R/R ↕</th>
          <th onclick="sortTable(11)">ATR ↕</th>
        </tr>
      </thead>
      <tbody>
        {% for r in results %}
        <tr>
          <td>{{ r.ticker }}</td>
          <td>{{ r.exchange }}</td>
          <td>{{ "%.4f"|format(r.last_close) }}</td>
          <td class="{{ 'signal-bo' if r.signal == 'BREAKOUT' else 'signal-near' if r.signal == 'NEAR' else 'signal-none' }}">
            {{ r.signal }}
          </td>
          <td>{{ "%.2f"|format(r.pct_to_high) }}%</td>
          <td>{{ "%.4f"|format(r.gtt_trigger) }}</td>
          <td>{{ "%.4f"|format(r.target_price) }}</td>
          <td>{{ "%.4f"|format(r.stop_loss) }}</td>
          <td>{{ r.shares }}</td>
          <td>{{ "%.0f"|format(r.net_pnl) }}</td>
          <td>{{ "%.2f"|format(r.rr) }}×</td>
          <td>{{ "%.4f"|format(r.atr) }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  <!-- Daily workflow -->
  <div class="workflow">
    <h3>📋 Daily Workflow (Sun–Thu, after 3 PM UAE)</h3>
    <ol>
      <li><strong>Run the scanner:</strong> <code>python scan.py</code> — this report opens automatically.</li>
      <li><strong>Review Top 7 picks</strong> above — prioritise 🚀 BREAKOUT signals.</li>
      <li><strong>Log in to ENBD Securities</strong> and place GTT orders using the Trigger, Target, and Stop Loss shown on each card.</li>
      <li><strong>Qty:</strong> use the <em>Shares</em> value from the GTT box (pre-calculated for AED {{ "{:,.0f}".format(trade_size_aed) }} trade size).</li>
      <li><strong>Next morning:</strong> check if any GTT orders were triggered. Move stop up to entry cost if trade is in profit by 1× ATR.</li>
    </ol>
  </div>

</div>

<script>
// Simple table sort
let sortDir = {};
function sortTable(col) {
  const tbl = document.getElementById("resultsTable");
  const rows = Array.from(tbl.tBodies[0].rows);
  sortDir[col] = !sortDir[col];
  rows.sort((a, b) => {
    let av = a.cells[col].innerText.replace(/[%×,]/g, "").trim();
    let bv = b.cells[col].innerText.replace(/[%×,]/g, "").trim();
    const an = parseFloat(av), bn = parseFloat(bv);
    if (!isNaN(an) && !isNaN(bn)) return sortDir[col] ? an - bn : bn - an;
    return sortDir[col] ? av.localeCompare(bv) : bv.localeCompare(av);
  });
  rows.forEach(r => tbl.tBodies[0].appendChild(r));
}
</script>
</body>
</html>
"""


def render_report(
    results: list[dict],
    picks:   list[dict],
    config:  object,
) -> Path:
    """
    Render the HTML report and write it to ``config.report_path``.

    Returns the path to the written file.
    """
    from turtle.commission import (
        calc_round_trip_commission,
        DFM_FLAT_FEE, ADX_TOTAL_RATE, DFM_TOTAL_RATE,
    )

    trade = config.trade_size_aed
    dfm_rt  = round(calc_round_trip_commission(trade, "DFM"), 2)
    adx_rt  = round(calc_round_trip_commission(trade, "ADX"), 2)
    target  = config.profit_target_aed

    stats = {
        "scanned":   len(results),
        "breakouts": sum(1 for r in results if r.get("signal") == "BREAKOUT"),
        "near":      sum(1 for r in results if r.get("signal") == "NEAR"),
        "curated":   len(picks),
        "failed":    sum(1 for r in results if r.get("signal") == "ERROR"),
    }

    env  = Environment(loader=BaseLoader())
    tmpl = env.from_string(_TEMPLATE)
    html = tmpl.render(
        generated_at     = datetime.now().strftime("%Y-%m-%d %H:%M"),
        turtle_system    = config.turtle_system,
        trade_size_aed   = trade,
        profit_target_aed= target,
        dfm_rt_cost      = dfm_rt,
        adx_rt_cost      = adx_rt,
        dfm_gross_needed = round(target + dfm_rt, 2),
        adx_gross_needed = round(target + adx_rt, 2),
        stats            = stats,
        picks            = picks,
        results          = results,
    )

    out_path = Path(config.report_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def open_report(path: Path) -> None:
    webbrowser.open(path.resolve().as_uri())
