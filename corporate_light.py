"""Corporate light styles for the shared shell and store overview."""

STYLE = """<style>
@layer keiper-appearance {
html[data-theme=light] {
  --kp-ink:#0b2343;
  --kp-subtle:#465b76;
  --kp-bg:#f3f6fb;
  --kp-line:#d7e1ef;
  --kp-accent:#005ed4;
  --kp-navy:#092442;
  --kp-paper:#fff;
}
html[data-theme=light] body {
  background:var(--kp-bg)!important;
  color:var(--kp-ink)!important;
}
html[data-theme=light] body :where(.card,.stat,.kh-store,.kh-menu,.mgmt-chart) {
  background:var(--kp-paper)!important;
  border-color:var(--kp-line)!important;
  box-shadow:0 2px 8px #102c5008!important;
}
html[data-theme=light] body :where(.btn-acoes,.btn) {
  background:var(--kp-accent)!important;
  border-color:var(--kp-accent)!important;
}
html[data-theme=light] body :where(.btn-acoes,.btn).cinza,
html[data-theme=light] body .top .sair {
  background:var(--kp-paper)!important;
  color:var(--kp-ink)!important;
  border-color:var(--kp-line)!important;
}
html[data-theme=light] body .ks-sidebar {
  background:var(--kp-navy) linear-gradient(160deg,#061d36,var(--kp-navy))!important;
  color:#f3f7ff!important;
  border-color:#233e5e!important;
}
html[data-theme=light] body .ks-sidebar :where(a,summary,.ks-label,.ks-store-name) {color:inherit!important}
html[data-theme=light] body .ks-sidebar :where(a:hover,summary:hover,.ks-nav-group[open]>summary) {
  background:#173d65!important;
}
html[data-theme=light] body .ks-sidebar a[aria-current=page] {
  background:#245284!important;
  box-shadow:none!important;
}
html[data-theme=light] body .ks-sidebar a.ks-danger {color:#ffc4ce!important}
html[data-theme=light] body .ks-sidebar :where(.ks-foot,.ks-nav-children) {border-color:#2b4868!important}
html[data-theme=light] body .ks-toggle {
  background:transparent!important;
  color:inherit!important;
  border-color:transparent!important;
  font-weight:700!important;
  font-size:15px!important;
}
html[data-theme=light] body .ks-toggle > span:first-child {display:none!important}
html[data-theme=light] body .ks-brand-logo {
  display:block!important;
  width:36px!important;
  height:36px!important;
  flex:none!important;
  object-fit:contain!important;
  border-radius:7px!important;
}
html[data-theme=light] body .ks-store-sidebar .ks-store-name {display:none!important}
html[data-theme=light] body .ks-sidebar :where(a,summary) {font-size:14px!important}
html[data-theme=light] body .ks-store-sidebar nav {margin-top:20px!important}
html[data-theme=light] body .ks-sidebar :where(.ks-nav-children a,.ks-foot a) {font-size:12px!important}
html[data-theme=light] body:has(.ks-store-sidebar) > .top {
  min-height:60px!important;
  padding:8px clamp(14px,2vw,32px)!important;
  border-bottom:1px solid var(--kp-line)!important;
  justify-content:flex-start!important;
  flex-wrap:nowrap!important;
}
html[data-theme=light] body:has(.ks-store-sidebar) > .top > div:first-child {display:none!important}
html[data-theme=light] body .top .top-store {
  order:0!important;
  flex-basis:auto!important;
  min-width:0!important;
  max-width:70%!important;
  color:var(--kp-ink)!important;
  box-shadow:none!important;
  border-radius:10px!important;
}
html[data-theme=light] body .top .sair {margin-left:auto!important;order:1!important}
html[data-theme=light] body:has(.mgmt-dashboard) > .wrap {
  max-width:1680px!important;
  margin:14px auto!important;
  padding:0 clamp(12px,1.7vw,30px)!important;
}
html[data-theme=light] body .mgmt-dashboard {font-family:Inter,'Segoe UI',system-ui,sans-serif!important}
html[data-theme=light] body .mgmt-header {
  background:linear-gradient(115deg,#f6f8fc,#eaf1fc)!important;
  border:0!important;
  box-shadow:none!important;
  padding:12px 14px 4px!important;
  margin:0!important;
}
html[data-theme=light] body .mgmt-header h2 {
  font-size:clamp(27px,3vw,38px)!important;
  line-height:1.15!important;
  margin:4px 0!important;
}
html[data-theme=light] body .mgmt-eyebrow {font-size:11px!important;letter-spacing:2px!important}
html[data-theme=light] body .mgmt-header .btn-acoes:first-child {
  background:var(--kp-paper)!important;
  border-color:#b7cbe5!important;
  color:var(--kp-accent)!important;
}
html[data-theme=light] body .mgmt-header .btn-acoes.cinza {
  background:var(--kp-accent)!important;
  border-color:var(--kp-accent)!important;
  color:#fff!important;
}
html[data-theme=light] body .mgmt-dashboard .btn-acoes {font-size:13px!important}
html[data-theme=light] body .mgmt-period {
  background:transparent!important;
  border:0!important;
  box-shadow:none!important;
  margin:0!important;
  padding:8px 14px!important;
}
html[data-theme=light] body .mgmt-period :where(label,a,summary,select,input) {font-size:13px!important}
html[data-theme=light] body .mgmt-period-dates {align-self:end!important;padding-bottom:8px!important}
html[data-theme=light] body .mgmt-period-dates summary > .mgmt-date-label,
html[data-theme=light] body .mgmt-period-dates[open] .mgmt-date-range {display:none!important}
html[data-theme=light] body .mgmt-period-dates:not([open]) .mgmt-date-range {display:inline!important}
html[data-theme=light] body .mgmt-period-dates[open] summary > .mgmt-date-label {display:inline!important}
html[data-theme=light] body .mgmt-date-range .mgmt-date-label {
  position:absolute!important;
  width:1px!important;
  height:1px!important;
  clip-path:inset(50%)!important;
  overflow:hidden!important;
}
html[data-theme=light] body .mgmt-period + .muted {margin:4px 14px 8px!important}
html[data-theme=light] body .mgmt-tabs {
  gap:6px!important;
  margin:10px 0 18px!important;
  border-color:var(--kp-line)!important;
}
html[data-theme=light] body .mgmt-tabs a {
  color:var(--kp-ink)!important;
  padding:12px clamp(8px,1.5vw,23px)!important;
  font-size:14px!important;
}
html[data-theme=light] body .mgmt-tabs a[aria-selected=true] {
  color:var(--kp-accent)!important;
  border-color:var(--kp-accent)!important;
}
html[data-theme=light] body .mgmt-sales-metrics {
  background:transparent!important;
  box-shadow:none!important;
}
html[data-theme=light] body .mgmt-sales-metrics .mgmt-kpis {margin-bottom:12px!important;gap:12px!important}
html[data-theme=light] body .mgmt-sales-metrics .stat {
  --metric-color:#008163;
  --metric-bg:#def4ec;
  padding:16px clamp(12px,1.35vw,24px) 12px!important;
  background:var(--kp-paper)!important;
  color:var(--kp-ink)!important;
}
html[data-theme=light] body .mgmt-sales-metrics .mgmt-tone-teal {--metric-color:#6246da;--metric-bg:#ede8ff}
html[data-theme=light] body .mgmt-sales-metrics .mgmt-tone-amber {--metric-color:#005ed4;--metric-bg:#e4efff}
html[data-theme=light] body .mgmt-sales-metrics .mgmt-metric-icon {
  position:static!important;
  float:left!important;
  width:40px!important;
  height:40px!important;
  margin:0 12px 4px 0!important;
  color:var(--metric-color)!important;
  background:var(--metric-bg)!important;
}
html[data-theme=light] body .mgmt-sales-metrics .mgmt-metric-icon svg {width:22px!important;height:22px!important}
html[data-theme=light] body .mgmt-sales-metrics :where(.lab,.num,small) {margin-left:52px!important;max-width:none!important}
html[data-theme=light] body .mgmt-sales-metrics .lab {font-size:13px!important;line-height:1.35!important}
html[data-theme=light] body .mgmt-sales-metrics .num {font-size:clamp(22px,2vw,33px)!important;margin-top:4px!important;margin-bottom:4px!important}
html[data-theme=light] body .mgmt-sales-metrics small {font-size:12px!important;color:var(--kp-subtle)!important}
html[data-theme=light] body .mgmt-sparkline {
  display:block!important;
  width:100%!important;
  height:32px!important;
  margin-top:9px!important;
  color:var(--metric-color)!important;
  fill:currentColor!important;
}
html[data-theme=light] body .mgmt-sparkline .mgmt-spark-stroke {
  stroke:currentColor!important;
  stroke-width:1.7!important;
  vector-effect:non-scaling-stroke!important;
  fill:none!important;
}
html[data-theme=light] body .mgmt-sparkline .mgmt-spark-area {fill:currentColor;fill-opacity:.08}
html[data-theme=light] body .mgmt-chart .mgmt-chart-date {display:inline!important}
html[data-theme=light] body #mgmt-panel-overview > .muted {font-size:13px!important;margin:10px 6px!important}
html[data-theme=light] body .mgmt-chart-switch {margin:12px 6px 0!important}
html[data-theme=light] body .mgmt-chart-switch button {
  background:var(--kp-paper)!important;
  border-color:#b7cbe5!important;
  color:var(--kp-ink)!important;
  font-size:13px!important;
  font-weight:650!important;
}
html[data-theme=light] body .mgmt-chart-switch button[aria-pressed=true] {
  background:var(--kp-accent)!important;
  border-color:var(--kp-accent)!important;
  color:#fff!important;
}
html[data-theme=light] body .mgmt-chart {padding:16px clamp(14px,1.8vw,32px)!important}
html[data-theme=light] body .mgmt-chart-header h2 {font-size:clamp(19px,1.7vw,27px)!important}
html[data-theme=light] body .mgmt-chart :where(.muted,.mgmt-chart-y,.mgmt-chart-x,.mgmt-chart-legend) {font-size:12px!important}
html[data-theme=light] body .mgmt-chart svg line {stroke:#dce5f1!important}
html[data-theme=light] body .mgmt-chart-legend span:first-child:before {background:#1455ed!important}
html[data-theme=light] body .mgmt-chart-legend span+span:before {background:#008763!important}
html[data-theme=light] body .mgmt-current {color:#1455ed!important}
html[data-theme=light] body .mgmt-previous {color:#008763!important}
html[data-theme=light] body .mgmt-chart :where(.mgmt-current,.mgmt-previous) path {stroke:currentColor!important}
html[data-theme=light] body .mgmt-chart :where(.mgmt-current,.mgmt-previous) circle {fill:currentColor!important}
html[data-theme=light] body .mgmt-chart .mgmt-light-tick {display:initial!important}
html[data-theme=light] body .mgmt-chart .mgmt-chart-area {
  display:initial!important;
  fill:currentColor!important;
  fill-opacity:.09!important;
  stroke:none!important;
  pointer-events:none!important;
}
@media (min-width:641px) {
  html[data-theme=light] body:has(.ks-sidebar):not(.ks-collapsed) {--ks-width:248px!important}
  html[data-theme=light] body:has(.ks-store-sidebar) > .top {padding-left:72px!important}
}
@media (max-width:1160px) {
  html[data-theme=light] body .mgmt-sales-metrics .mgmt-kpis {grid-template-columns:repeat(2,minmax(0,1fr))!important}
}
@media (max-width:640px) {
  html[data-theme=light] body .mgmt-chart .mgmt-chart-date {display:none!important}
  html[data-theme=light] body .mgmt-sales-metrics .mgmt-metric-icon {
    float:none!important;
    width:30px!important;
    height:30px!important;
    margin:0 0 5px!important;
  }
  html[data-theme=light] body .mgmt-sales-metrics :where(.lab,.num,small) {margin-left:0!important}
  html[data-theme=light] body:has(.ks-store-sidebar) > .top {padding-left:58px!important}
}
html[data-theme=light] body > .ks-mobile-toggle {
  display:block!important;
  position:absolute!important;
  top:8px!important;
  inset-inline-start:8px!important;
  z-index:31!important;
  width:44px!important;
  height:44px!important;
  margin:0!important;
  padding:0!important;
  overflow:hidden!important;
  white-space:nowrap!important;
  font-size:0!important;
  background:transparent!important;
  border-color:transparent!important;
  color:var(--kp-ink)!important;
}
html[data-theme=light] body > .ks-mobile-toggle::before {content:'☰'!important;font-size:19px!important}
@media (min-width:641px) {
  html[data-theme=light] body > .ks-mobile-toggle {inset-inline-start:calc(var(--ks-width) + 14px)!important}
}
}
</style>"""
