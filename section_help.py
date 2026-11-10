"""Compact, keyboard-accessible disclosure for section methodology."""
from html import escape

STYLE = """<style>
.section-help{position:relative;min-height:36px;margin:0 0 6px}
.section-help>.section-help-title{margin:0;padding:5px 46px 5px 0}
.section-help>details>summary{position:absolute;right:0;top:0;display:grid;place-items:center;
  list-style:none;box-sizing:border-box;width:36px;height:36px;margin:0;padding:0;border-radius:50%;
  border:1px solid #597896;background:#192f47;color:#eaf2ff;cursor:pointer;font:700 16px system-ui}
.section-help>details>summary::-webkit-details-marker{display:none}
.section-help>details>summary:focus-visible{outline:2px solid #80c6ff;outline-offset:3px}
.section-help>details[open]>summary{background:#294d73}
.section-help-copy{margin:8px 0 12px;padding:10px 14px;border-left:2px solid #597896;
  font-size:.88rem;line-height:1.55;overflow-wrap:anywhere}
.section-help-copy p{margin:0 0 6px}
.section-help-copy p:last-child{margin-bottom:0}
@layer keiper-appearance {
  html[data-theme=light] body .section-help>details>summary{background:#edf4fc!important;color:#244b76!important;border-color:#9bb4ce}
  html[data-theme=light] body .section-help>details[open]>summary{background:#dceafd!important}
}
</style>"""


def section_help(title, label, body, *, subheading=False):
    """Render a heading and an explanation supplied as trusted HTML."""
    heading = 'h3' if subheading else 'h2'
    return (f"<header class='section-help'><{heading} class='section-help-title'>{escape(title)}</{heading}>"
            f"<details><summary aria-label='{escape(label)}' title='{escape(label)}'>?</summary>"
            f"<div class='section-help-copy'>{body}</div></details></header>")
