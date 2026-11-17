"""A live board for multi-agent labs: one card per agent, and the messages between them.

    from meridian.lab import board
    board.cards([{"name": "Network", "role": "investigates", "status": "working", "activity": "Reading logs"}, ...])
    board.feed([{"time": "10:21", "from": "orchestrator", "to": "network", "text": "...", "kind": "message"}, ...])

Status: idle, working, waiting, done, error, unused.
"""

from __future__ import annotations

import json
from html import escape
from typing import Any

import streamlit as st

STYLE = """
<style>
.mb-row{display:flex;gap:10px;flex-wrap:wrap;margin:4px 0 12px}
.mb-card{flex:1 1 150px;min-width:150px;border:1px solid #e5e7eb;border-radius:10px;padding:10px 12px;background:#fff;transition:all .2s}
.mb-card .n{font-weight:600;font-size:15px;color:#111827}
.mb-card .r{font-size:12px;color:#6b7280;margin-bottom:8px}
.mb-card .s{font-size:12px;font-weight:600;display:flex;align-items:center;gap:6px}
.mb-card .a{font-size:12px;color:#374151;margin-top:6px;line-height:1.35;max-height:5.4em;overflow:hidden;white-space:pre-wrap}
.mb-dot{width:8px;height:8px;border-radius:50%;display:inline-block;background:#9ca3af}
.mb-working{border-color:#3b82f6;box-shadow:0 0 0 3px #dbeafe}.mb-working .s{color:#1d4ed8}.mb-working .mb-dot{background:#3b82f6;animation:mbp 1s infinite}
.mb-waiting{border-color:#f59e0b;box-shadow:0 0 0 3px #fef3c7}.mb-waiting .s{color:#b45309}.mb-waiting .mb-dot{background:#f59e0b;animation:mbp 1s infinite}
.mb-done .s{color:#047857}.mb-done .mb-dot{background:#10b981}
.mb-error{border-color:#ef4444}.mb-error .s{color:#b91c1c}.mb-error .mb-dot{background:#ef4444}
.mb-idle .s{color:#6b7280}
.mb-unused{opacity:.4}
@keyframes mbp{50%{opacity:.25}}
.mb-feed{border:1px solid #e5e7eb;border-radius:10px;padding:6px 12px;max-height:340px;overflow-y:auto;background:#fff}
.mb-msg{display:flex;gap:10px;padding:6px 0;border-bottom:1px solid #f3f4f6;font-size:13px;line-height:1.4}
.mb-msg:last-child{border-bottom:none}
.mb-t{color:#9ca3af;min-width:40px}
.mb-w{min-width:190px;color:#374151;font-weight:600}
.mb-x{color:#374151;white-space:pre-wrap}
.mb-k{font-size:11px;font-weight:600;border-radius:4px;padding:0 5px;margin-right:4px}
.mb-action{background:#ede9fe;color:#5b21b6}.mb-approval{background:#fef3c7;color:#92400e}
.mb-approved{background:#d1fae5;color:#065f46}.mb-rejected{background:#fee2e2;color:#991b1b}
.mb-tool{background:#f3f4f6;color:#6b7280}
.mb-checkpoint{background:#dbeafe;color:#1e40af}.mb-note{background:#e0e7ff;color:#3730a3}
.mb-crash{background:#ef4444;color:#fff}.mb-msg.mb-row-crash .mb-x{color:#b91c1c;font-weight:600}
.mb-msg.mb-row-tool{font-size:12px;padding:3px 0}.mb-row-tool .mb-w,.mb-row-tool .mb-x{color:#9ca3af;font-weight:400}
</style>
"""

LABELS = {"idle": "Waiting", "working": "Working", "waiting": "Needs approval", "done": "Done", "error": "Error", "unused": "Not used"}
TAGS = {"tool": "TOOL", "action": "ACTION", "approval": "APPROVAL?", "approved": "APPROVED", "rejected": "REJECTED",
        "checkpoint": "CHECKPOINT", "note": "YOUR CODE", "crash": "CRASH"}


def cards(items: list[dict[str, Any]]) -> None:
    html = []
    for item in items:
        status = item.get("status", "idle")
        html.append(
            f'<div class="mb-card mb-{status}"><div class="n">{escape(item["name"])}</div><div class="r">{escape(item.get("role", ""))}</div>'
            f'<div class="s"><span class="mb-dot"></span>{LABELS.get(status, status)}</div>'
            f'<div class="a">{escape(item.get("activity", ""))}</div></div>'
        )
    st.html(STYLE + f'<div class="mb-row">{"".join(html)}</div>')


def feed(messages: list[dict[str, str]], names: dict[str, str] | None = None, limit: int = 400) -> None:
    names = names or {}
    rows = []
    for message in messages:
        kind = message.get("kind", "message")
        tag = f'<span class="mb-k mb-{kind}">{TAGS[kind]}</span>' if kind in TAGS else ""
        who = f'{escape(names.get(message["from"], message["from"]))} → {escape(names.get(message["to"], message["to"]))}'
        text = message["text"] if len(message["text"]) <= limit else message["text"][:limit] + "…"
        rows.append(f'<div class="mb-msg mb-row-{kind}"><span class="mb-t">{escape(message["time"][-5:])}</span><span class="mb-w">{who}</span>'
                    f'<span class="mb-x">{tag}{escape(text)}</span></div>')
    st.html(STYLE + f'<div class="mb-feed">{"".join(rows) or "<div class=mb-msg>No messages yet.</div>"}</div>')


def as_text(messages: list[dict[str, str]], names: dict[str, str] | None = None) -> str:
    """The messages as plain text, one per line, to paste anywhere."""
    names = names or {}
    lines = []
    for message in messages:
        tag = f"[{TAGS[message.get('kind', '')]}] " if message.get("kind") in TAGS else ""
        who = f"{names.get(message['from'], message['from'])} → {names.get(message['to'], message['to'])}"
        lines.append(f"{message['time'][-5:]}  {who}: {tag}{message['text']}")
    return "\n".join(lines)


def copy_button(text: str, label: str = "Copy log") -> None:
    """A small button that copies `text` to the clipboard."""
    # The log holds model output: escape '</' so nothing in it can close the <script> tag.
    data = json.dumps(text).replace("</", "<\\/")
    st.iframe(f"""
<button id="b" style="float:right;font:13px 'Source Sans Pro',sans-serif;color:#374151;background:#fff;border:1px solid #d1d5db;
border-radius:8px;padding:5px 12px;cursor:pointer">&#x2398; {label}</button>
<script>
const text = {data};
const button = document.getElementById("b");
button.onclick = async () => {{
  try {{ await navigator.clipboard.writeText(text); }}
  catch (e) {{
    const area = document.createElement("textarea"); area.value = text; document.body.appendChild(area);
    area.select(); document.execCommand("copy"); area.remove();
  }}
  button.innerHTML = "&#x2713; Copied"; setTimeout(() => button.innerHTML = "&#x2398; {label}", 1500);
}};
</script>""", height=38)


WATERFALL = """
<style>
.wf{border:1px solid #e5e7eb;border-radius:10px;background:#fff;padding:8px 12px;max-height:520px;overflow-y:auto;font-size:12px}
.wf-row{display:flex;align-items:center;gap:10px;padding:2px 0;border-bottom:1px solid #f9fafb}
.wf-l{flex:0 0 38%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#374151}
.wf-t{flex:1;position:relative;height:14px;background:#f9fafb;border-radius:3px}
.wf-b{position:absolute;top:2px;height:10px;border-radius:3px;min-width:2px}
.wf-incident{background:#9ca3af}.wf-invoke_agent{background:#3b82f6}.wf-chat{background:#a78bfa}.wf-execute_tool{background:#d1d5db}
.wf-error .wf-b{background:#ef4444}.wf-error .wf-l{color:#b91c1c;font-weight:600}
.wf-agent .wf-l{font-weight:600;color:#111827}
.wf-legend{display:flex;gap:14px;font-size:12px;color:#6b7280;margin:2px 0 6px}
.wf-legend span:before{content:"";display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}
.wf-legend .a:before{background:#3b82f6}.wf-legend .c:before{background:#a78bfa}.wf-legend .t:before{background:#d1d5db}
</style>
"""


def waterfall(rows: list[dict[str, Any]]) -> None:
    """Spans as a waterfall. rows: label, depth, start, end, kind, detail (tooltip), error."""
    total = max((r["end"] for r in rows), default=1) or 1
    html = ['<div class="wf-legend"><span class="a">agent</span><span class="c">model call</span><span class="t">tool call</span></div><div class="wf">']
    for r in rows:
        left, width = 100 * r["start"] / total, max(100 * (r["end"] - r["start"]) / total, 0.3)
        css = f"wf-row{' wf-error' if r.get('error') else ''}{' wf-agent' if r['kind'] == 'invoke_agent' else ''}"
        html.append(f'<div class="{css}" title="{escape(r.get("detail", ""))}"><div class="wf-l" style="padding-left:{14 * r["depth"]}px">'
                    f'{escape(r["label"])}</div><div class="wf-t"><div class="wf-b wf-{escape(r["kind"])}" '
                    f'style="left:{left:.2f}%;width:{width:.2f}%"></div></div></div>')
    html.append("</div>")
    st.html(WATERFALL + "".join(html))
