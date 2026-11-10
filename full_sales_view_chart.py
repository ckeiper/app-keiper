"""Daily sales chart and aligned strip of observed Full stock."""
from datetime import date
from html import escape
from math import ceil

LABELS = dict(available='Com estoque Full', empty='Sem estoque Full',
              unknown='Desconhecido', mixed='Consultas divergentes')

STYLE = """<style>
.full-sales-chart{margin:18px 0;padding:16px;background:#0c1b2e;border:1px solid #34516e;border-radius:12px}
.full-sales-chart figcaption{color:#eaf2ff;font-size:16px;font-weight:700}
.full-sales-chart .full-chart-scroll{padding:4px 12px 8px;scroll-padding-inline:12px}
.full-chart-layout{display:grid;grid-template-columns:auto minmax(0,1fr);margin-top:16px}
.full-chart-axis{position:relative;height:208px;min-width:3ch;margin:4px 0 0;padding-right:4px;
  font:11px system-ui;color:#bdcce1;text-align:right;font-variant-numeric:tabular-nums}
.full-chart-tick{position:absolute;right:4px;transform:translateY(-50%)}
.full-chart-columns{position:relative;display:grid;min-width:calc(var(--days) * var(--slot));
  grid-template-columns:repeat(var(--days),minmax(var(--slot),1fr))}
.full-chart-gridline{position:absolute;left:0;right:0;border-top:1px solid #2b425c;pointer-events:none}
.full-sales-chart .full-chart-day{position:relative;display:grid;grid-template-rows:208px 22px 30px;
  justify-items:center;align-items:center;min-width:0;margin:0;padding:0;border:0;border-radius:4px;
  background:transparent;color:#c7d7ec;font:11px system-ui;box-shadow:none;cursor:pointer;touch-action:pan-x pan-y}
.full-sales-chart .full-chart-day:is(:hover,:focus-visible,[aria-pressed=true]){background:#1e3652}
.full-sales-chart .full-chart-day:focus-visible{outline:2px solid #a7dcff;outline-offset:-2px;z-index:1}
.full-chart-sale{align-self:end;width:76%;max-width:48px;height:var(--bar);background:#60a5fa;border-radius:3px 3px 0 0}
.full-chart-sale[data-sales=zero]{height:2px;border-radius:2px}
.full-chart-sale[data-sales=missing]{height:3px;background:none;border-top:2px dashed #94a3b8}
.full-chart-stock{display:inline-block;width:14px;height:8px;box-sizing:border-box;border:1px solid;border-radius:2px}
.full-chart-stock[data-state=available]{background:#39b98b;border-color:#39b98b}
.full-chart-stock[data-state=empty]{background:transparent;border:2px solid #fb8d93}
.full-chart-stock[data-state=unknown]{background:transparent;border:1px dashed #a5b4c8}
.full-chart-stock[data-state=mixed]{border-color:#f1c572;background:repeating-linear-gradient(135deg,#f1c572 0 2px,transparent 2px 4px)}
.full-chart-date{position:absolute;bottom:8px;white-space:nowrap;font-variant-numeric:tabular-nums}
.full-chart-key{display:flex;align-items:center;flex-wrap:wrap;gap:6px 14px;color:#c7d7ec;font-size:12px;margin-top:12px}
.full-chart-key span{display:inline-flex;align-items:center;gap:6px}
.full-chart-readout{min-height:3.5em;margin-top:10px;padding:8px 12px;background:#142942;border-radius:6px;
  color:#dcecff;font-size:12px;line-height:1.5}
.full-chart-readout strong,.full-chart-readout small{display:block}
html[data-theme=light] .full-sales-chart{background:#f8fbff;color:#172d47;border-color:#c5d5e6}
html[data-theme=light] .full-sales-chart figcaption{color:#172d47}
html[data-theme=light] .full-chart-gridline{border-color:#d4dfec}
@layer keiper-appearance {
  html[data-theme=light] body .full-sales-chart .full-chart-day{background:transparent!important;color:#172d47!important}
  html[data-theme=light] body .full-sales-chart .full-chart-day:is(:hover,:focus-visible,[aria-pressed=true]){
    background:#e3efff!important;outline-color:#225fbe}
}
html[data-theme=light] .full-chart-sale{background:#2769c0}
html[data-theme=light] .full-chart-sale[data-sales=missing]{border-color:#52657c}
html[data-theme=light] .full-chart-stock[data-state=available]{background:#087447;border-color:#087447}
html[data-theme=light] .full-chart-stock[data-state=empty]{border-color:#b22539}
html[data-theme=light] .full-chart-stock[data-state=unknown]{border-color:#52657c}
html[data-theme=light] .full-chart-stock[data-state=mixed]{border-color:#8b6010;
  background:repeating-linear-gradient(135deg,#8b6010 0 2px,transparent 2px 4px)}
html[data-theme=light] .full-chart-readout{background:#eaf1fa}
@media(max-width:700px){.full-sales-chart{padding:12px}}
</style>"""

INTERACTION = """<script>
(() => {
  const chart = document.currentScript.previousElementSibling;
  const days = Array.from(chart.querySelectorAll('.full-chart-day'));
  const readout = chart.querySelector('.full-chart-readout');
  const heading = readout.querySelector('strong');
  const detail = readout.querySelector('small');
  let selected;
  function show(day) {
    heading.textContent = day.dataset.summary;
    detail.textContent = day.dataset.reason;
  }
  function activate(day) {
    if (selected) {
      selected.tabIndex = -1;
      selected.setAttribute('aria-pressed', 'false');
    }
    selected = day;
    day.tabIndex = 0;
    day.setAttribute('aria-pressed', 'true');
    show(day);
  }
  days.forEach((day, index) => {
    day.tabIndex = -1;
    day.addEventListener('pointerenter', event => {
      if (event.pointerType === 'mouse') show(day);
    });
    day.addEventListener('focus', () => activate(day));
    day.addEventListener('click', () => activate(day));
    day.addEventListener('keydown', event => {
      const target = {
        ArrowLeft: index - 1, ArrowRight: index + 1,
        Home: 0, End: days.length - 1
      }[event.key];
      if (typeof target !== 'number') return;
      event.preventDefault();
      days[Math.min(days.length - 1, Math.max(0, target))].focus();
    });
  });
  chart.querySelector('.full-chart-columns').addEventListener('pointerleave', () => {
    if (selected) show(selected);
  });
  days[0].tabIndex = 0;
})();
</script>"""


def chart(days):
    if not days:
        return ''
    peak = max(d['units'] or 0 for d in days)
    tick = max(1, ceil(peak / 4))
    maximum = tick * max(1, ceil(peak / tick))
    ticks = range(0, maximum + 1, tick)
    slot = 36 if len(days) <= 7 else 24
    date_interval = 1 if len(days) <= 7 else 2
    out = [
        STYLE,
        "<figure class='full-sales-chart'>",
        "<figcaption>Unidades vendidas</figcaption>",
        f"<div class='full-chart-layout'><div class='full-chart-axis' "
        f"style='min-width:{max(3, len(str(maximum)))}ch' aria-hidden='true'>",
    ]
    for value in ticks:
        top = (1 - value / maximum) * 100
        out.append(f"<span class='full-chart-tick' style='top:{top:g}%'>{value}</span>")
    out.append("</div><div class='full-chart-scroll' tabindex='0' role='region' "
               "aria-label='Vendas e estoque Full por dia' aria-describedby='full-chart-help'>"
               f"<div class='full-chart-columns' style='--days:{len(days)};--slot:{slot}px'>")
    for value in ticks:
        top = (1 - value / maximum) * 208
        out.append(f"<span class='full-chart-gridline' aria-hidden='true' style='top:{top:g}px'></span>")
    for index, day in enumerate(days):
        units, state, observations = day['units'], day['state'], day['observations']
        stamp = date.fromisoformat(day['day'])
        sales = 'Vendas indisponíveis' if units is None else f'{units} ' + ('unidade vendida' if units == 1 else 'unidades vendidas')
        reads = f'{observations} ' + ('consulta' if observations == 1 else 'consultas')
        summary = f"{stamp:%d/%m/%Y} · {sales} · Full: {LABELS[state]} · {reads}"
        reason = (day.get('reason') or '') if units is None else ''
        if not observations:
            reason = ' '.join(filter(None, (reason, 'Sem consulta Full registrada neste dia.')))
        label = ' '.join(filter(None, (summary, reason)))
        bar = 'missing' if units is None else 'zero' if units == 0 else 'positive'
        height = (units or 0) / maximum * 100
        out.append(f"<button type='button' class='full-chart-day' aria-pressed='false' "
                   f"aria-label='{escape(label)}' data-summary='{escape(summary)}' data-reason='{escape(reason)}'>"
                   f"<span class='full-chart-sale' data-sales='{bar}' style='--bar:{height:.6f}%' aria-hidden='true'></span>"
                   f"<span class='full-chart-stock' data-state='{state}' aria-hidden='true'></span>")
        if index % date_interval == 0:
            out.append(f"<time class='full-chart-date' datetime='{day['day']}' aria-hidden='true'>{stamp:%d/%m}</time>")
        out.append('</button>')
    out.append("</div></div></div><div class='full-chart-key'><strong>Disponibilidade Full observada</strong>")
    for state, label in LABELS.items():
        out.append(f"<span><i class='full-chart-stock' data-state='{state}' aria-hidden='true'></i>{label}</span>")
    out.append("</div><div class='full-chart-readout'><strong>Detalhes por dia</strong><small></small></div>"
               "<p id='full-chart-help'>Passe o cursor, toque ou use as setas do teclado para consultar um dia. "
               "Traço azul: zero unidades. Traço cinza tracejado: vendas indisponíveis.</p></figure>")
    out.append(INTERACTION)
    return ''.join(out)

