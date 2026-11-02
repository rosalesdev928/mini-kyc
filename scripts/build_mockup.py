"""Build docs/mockup.html: static UI mockup of the screens, styled with the real frontend CSS.

Usage:  python scripts/build_mockup.py
"""

import base64
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "frontend" / "src" / "styles.css").read_text(encoding="utf-8")
# The dark theme lives on :root[data-theme="dark"]; re-scope the same tokens to a frame so one page can show both themes.
_DARK = re.search(r':root\[data-theme="dark"\]\s*\{(.*?)\n\}', CSS, re.S)
DARK_TOKENS = ".frame-dark {" + (_DARK.group(1) if _DARK else "") + "\n}"
SAMPLE = base64.b64encode((ROOT / "samples" / "sample_id_sharp.png").read_bytes()).decode()

LOGO = (
    '<svg class="brand-logo" viewBox="0 0 32 32" aria-hidden="true"><path d="M16 2.2 27.5 6.6v8.7c0 7.2-4.9 12.6-11.5 14.5C9.4 27.9 4.5 22.5 4.5 15.3V6.6z" fill="#0b3a5b"/>'
    '<path d="M16 2.2 27.5 6.6v8.7c0 7.2-4.9 12.6-11.5 14.5z" fill="#0b84c6"/>'
    '<path d="M10.2 16.2l4.1 4.1 7.6-8.6" fill="none" stroke="#fff" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/>'
    '<circle cx="25.4" cy="6.4" r="3.1" fill="#f5a300"/></svg>'
)


def topbar(admin=False, dark=False):
    return f"""
<header class="topbar">
  <div class="brand">{LOGO}<span class="brand-text"><span class="brand-name">Mini KYC</span><span class="brand-tagline">Digital onboarding</span></span></div>
  <div class="topbar-actions"><span class="theme-toggle">{"☀" if dark else "☾"}</span><span class="lang-toggle">ES</span><span class="operator">{"← Back to onboarding" if admin else "Admin panel"}</span></div>
</header>"""


PRIVACY = """<div class="privacy"><p><strong>Demo environment.</strong> Please do not upload real identity documents: use a sample or mock ID. Records are anonymized automatically after a retention period.</p><button>Got it</button></div>"""


def stepper(active):
    states = {"idle": ["active", "todo", "todo"], "loading": ["done", "active", "todo"], "success": ["done", "done", "done"]}[active]
    marks = {"done": "✓", "active": None, "todo": None}
    labels = ["Upload", "Reading", "Result"]
    items = "".join(
        f'<li class="step step-{st}{" step-working" if st == "active" and active == "loading" else ""}"><span class="step-dot">{marks[st] or i + 1}</span><span>{lb}</span></li>'
        for i, (st, lb) in enumerate(zip(states, labels))
    )
    return f'<ol class="stepper">{items}</ol>'


def upload_card(*, email="maria.fernandez@example.com", filled=True, loading=False, error=None):
    drop = (
        '<span class="drop-icon">↑</span><strong class="file-name">sample_id_sharp.png</strong><span class="muted">Change file</span>'
        if filled
        else '<span class="drop-icon">↑</span><span>Drag your document here or click to choose</span><span class="muted small">JPG or PNG · max. 5 MB</span>'
    )
    alert = f'<p class="alert">{error}</p>' if error else ""
    button = (
        '<span class="button"><span class="spinner"></span>Processing…</span>'
        if loading
        else '<span class="button">Process document</span>'
    )
    return f"""
<section class="card"><h2 class="card-title">Verify your identity</h2>
  <span class="field-label">Email address</span><div class="input">{email}</div>
  <span class="field-label">Identity document</span>
  <div class="dropzone{' has-file' if filled else ''}">{drop}</div>
  {alert}{button}
</section>"""


def review_note_card():
    steps = stepper("success")
    flags = '<ul class="flags"><li class="flag">Low reading confidence</li><li class="flag">This photo was already used with another email</li></ul>'
    body = f"""
<div class="result-grid"><img class="preview" src="data:image/png;base64,{SAMPLE}" alt="Uploaded document">
<dl class="fields">
<div><dt>Full name</dt><dd>Maria Fernandez Torres</dd></div>
<div><dt>Document type</dt><dd>DNI</dd></div>
<div><dt>Document no.</dt><dd>12345678</dd></div>
<div><dt>OCR confidence</dt><dd><span class="meter"><span class="meter-track"><span class="meter-fill meter-fill-low" style="width:71%"></span></span><span>71.0%</span></span></dd></div>
<div><dt>Registered</dt><dd>11/2/2026, 10:44:31 AM</dd></div></dl></div>
<p class="note">An operator will review this record manually. Your data was saved.</p>{flags}"""
    head = '<div class="card-heading"><h2 class="card-title">Extracted data</h2><span class="badge badge-warn">Needs review</span></div>'
    return f'<section class="card result-card">{steps}{head}{body}</section>'


def admin_overview_card():
    def card(value, label, extra=""):
        return f'<div class="stat-card{extra}"><span class="stat-value">{value}</span><span class="stat-label">{label}</span></div>'

    cards = "".join(
        [
            card(48, "Total records"),
            card(31, "Verified"),
            card(5, "Needs review", " stat-attention"),
            card(7, "Approved"),
            card(3, "Rejected"),
            card(2, "Erased"),
            card("91.4%", "Avg. confidence"),
        ]
    )
    counts = [("VERIFIED", "Verified", 31), ("APPROVED", "Approved", 7), ("NEEDS_REVIEW", "Needs review", 5), ("REJECTED", "Rejected", 3), ("ERASED", "Erased", 2)]
    seg = "".join(f'<span class="seg-{k}" style="width:{n / 48 * 100:.1f}%"></span>' for k, _, n in counts)
    legend = "".join(f'<li><span class="swatch swatch-{k}"></span>{lb}<span class="count">{n}</span></li>' for k, lb, n in counts)
    days = [("Tue 27", 4), ("Wed 28", 7), ("Thu 29", 3), ("Fri 30", 9), ("Sat 31", 2), ("Sun 1", 6), ("Mon 2", 17)]
    bars = "".join(
        f'<li class="bar"><span class="bar-value">{n}</span><span class="bar-fill" style="height:{n / 17 * 100:.0f}%"></span><span class="bar-label">{d}</span></li>'
        for d, n in days
    )
    return f"""
<section>
<div class="admin-head"><h2 class="card-title">Admin panel</h2>
<div class="admin-tools"><span>Your name</span><div class="input reviewer-input">Ana</div><span class="button button-secondary button-compact">Sign out</span></div></div>
<div class="tabs"><span class="tab" aria-selected="true">Overview</span><span class="tab">Records</span></div>
<div class="stat-cards">{cards}</div>
<div class="panels">
<section class="card"><h3 class="card-title">Records by status</h3><div class="distribution">{seg}</div><ul class="legend">{legend}</ul></section>
<section class="card"><h3 class="card-title">Registrations, last 7 days</h3><ul class="bars">{bars}</ul></section>
</div></section>"""


def admin_records_card(detail=False):
    rows_data = [
        (48, "11/2/2026, 10:44", "maria.fernandez@example.com", "Maria Fernandez Torres", "DNI •••••678", "71.0%", "badge-warn", "Needs review"),
        (47, "11/2/2026, 10:42", "carlos.ruiz@example.com", "Carlos Ruiz Soto", "DNI •••••221", "98.0%", "badge-ok", "Verified"),
        (46, "11/1/2026, 18:03", "lucia.perez@example.com", "Lucia Perez Rios", "CE ••••904", "93.5%", "badge-ok", "Approved"),
        (45, "11/1/2026, 09:15", "erased-45@anonymized.invalid", "[erased]", "ERASED-45", "88.0%", "badge-muted", "Erased"),
    ]
    rows = "".join(
        f'<tr class="table-row"><td>{i}</td><td>{d}</td><td class="cell-wrap">{e}</td><td class="cell-wrap">{n}</td><td>{doc}</td><td>{c}</td><td><span class="badge {b}">{st}</span></td><td><span class="link-button">View</span></td></tr>'
        for i, d, e, n, doc, c, b, st in rows_data
    )
    table = f"""
<section class="card"><h3 class="card-title">Records</h3>
<div class="filters">
<div><span class="field-label">Status</span><div class="input">All</div></div>
<div class="filters-wide"><span class="field-label">Search</span><div class="input">Email or name</div></div>
<div><span class="field-label">From</span><div class="input">2026-10-27</div></div>
<div><span class="field-label">To</span><div class="input">2026-11-02</div></div>
<div class="filter-buttons"><span class="button button-compact">Search</span><span class="button button-secondary button-compact">Clear</span><span class="button button-secondary button-compact">Export CSV</span></div>
</div>
<div class="table-wrap"><table class="table"><thead><tr><th>ID</th><th>Date</th><th>Email</th><th>Name</th><th>Document</th><th>Confidence</th><th>Status</th><th></th></tr></thead><tbody>{rows}</tbody></table></div>
<div class="pager"><span class="muted small">1–4 of 48</span><div class="pager-buttons"><span class="button button-secondary button-compact">Previous</span><span class="button button-secondary button-compact">Next</span></div></div>
</section>"""
    if not detail:
        return table
    modal = """
<div class="modal-backdrop" style="position:absolute"><div class="modal">
<div class="modal-head"><h2>Record #48</h2><span class="modal-close">×</span></div>
<p><span class="badge badge-warn">Needs review</span></p>
<dl class="detail-grid">
<div><dt>Full name</dt><dd>Maria Fernandez Torres</dd></div><div><dt>Email address</dt><dd>maria.fernandez@example.com</dd></div>
<div><dt>Document type</dt><dd>DNI · 12345678</dd></div>
<div><dt>OCR confidence</dt><dd><span class="meter"><span class="meter-track"><span class="meter-fill meter-fill-low" style="width:71%"></span></span><span>71.0%</span></span></dd></div>
</dl>
<ul class="flags"><li class="flag">Low reading confidence</li><li class="flag">This photo was already used with another email</li></ul>
<h3 class="section-title">History of this record</h3>
<ol class="timeline">
<li><strong>Registered</strong><span class="when">11/2/2026, 10:44:31 AM</span></li>
<li><strong>Flagged for review</strong><span class="muted"> · Low reading confidence</span><span class="when">11/2/2026, 10:44:31 AM</span></li>
<li><strong>Flagged for review</strong><span class="muted"> · This photo was already used with another email</span><span class="when">11/2/2026, 10:44:31 AM</span></li>
</ol>
<div class="action-box"><h3>Manual decision</h3><div class="input">Comment (optional)</div>
<div class="action-buttons"><span class="button button-approve button-compact">Approve</span><span class="button button-reject button-compact">Reject</span></div></div>
<div class="action-box action-box-danger"><h3>Erase personal data</h3><p>Replaces the name, document number and file name with placeholders and breaks the link to the email. The audit trail is kept. This cannot be undone.</p>
<div class="input">Reason (optional)</div><label class="check-row"><input type="checkbox"> I understand this cannot be undone</label>
<div class="action-buttons"><span class="button button-danger button-compact">Erase personal data</span></div></div>
</div></div>"""
    return f'<div style="position:relative;min-height:980px">{table}{modal}</div>'


def result_card(kind):
    head = '<div class="card-heading"><h2 class="card-title">Extracted data</h2>{badge}</div>'
    if kind == "idle":
        body = '<div class="placeholder"><p class="placeholder-title">No document processed yet</p><p class="muted">Enter your email and upload a photo of your ID to see the extracted data here.</p></div>'
        return f'<section class="card result-card">{stepper("idle")}{head.format(badge="")}{body}</section>'
    if kind == "loading":
        body = '<div class="placeholder"><span class="spinner spinner-large"></span><p>Reading your document. This usually takes a few seconds…</p></div>'
        return f'<section class="card result-card">{stepper("loading")}{head.format(badge="")}{body}</section>'
    if kind == "error":
        return result_card("idle")
    body = f"""
<div class="result-grid"><img class="preview" src="data:image/png;base64,{SAMPLE}" alt="Uploaded document">
<dl class="fields">
<div><dt>Full name</dt><dd>Maria Fernandez Torres</dd></div>
<div><dt>Document type</dt><dd>DNI</dd></div>
<div><dt>Document no.</dt><dd>12345678</dd></div>
<div><dt>OCR confidence</dt><dd><span class="meter"><span class="meter-track"><span class="meter-fill" style="width:98%"></span></span><span>98.0%</span></span></dd></div>
<div><dt>Registered</dt><dd>11/2/2026, 10:42:07 AM</dd></div></dl></div>
<p class="note">AI / OCR: automatic extraction of fields from the document image.</p>"""
    return f'<section class="card result-card">{stepper("success")}{head.format(badge=chr(60) + "span class=" + chr(34) + "badge badge-ok" + chr(34) + ">Verified</span>")}{body}</section>'


def screen(number, title, upload, result, *, wide=False, dark=False, admin=False):
    if wide:
        layout = '<main class="layout layout-wide">' + result + "</main>"
    else:
        layout = f'<main class="layout">{upload}{result}</main>'
    frame = "frame frame-dark" if dark else "frame"
    notice = "" if admin else PRIVACY
    return f"""
<section class="mock">
  <h1>{number}. {title}</h1>
  <div class="{frame}">{topbar(admin=admin, dark=dark)}{notice}{layout}</div>
</section>"""


SCREENS = [
    screen(1, "Initial state (logo, privacy notice, progress steps)", upload_card(email="", filled=False), result_card("idle")),
    screen(2, "Processing (loading state)", upload_card(loading=True), result_card("loading")),
    screen(3, "Result: verified", upload_card(), result_card("success")),
    screen(
        4,
        "Error: blurry image",
        upload_card(error="The photo is too blurry to read. Retake it in good light and keep the camera steady."),
        result_card("error"),
    ),
    screen(5, "Result: flagged for manual review", upload_card(), review_note_card()),
    screen(6, "Admin panel: overview and statistics", "", admin_overview_card(), wide=True, admin=True),
    screen(7, "Admin panel: records, filters, CSV export", "", admin_records_card(), wide=True, admin=True),
    screen(8, "Admin panel: record detail, manual decision and data erasure", "", admin_records_card(detail=True), wide=True, admin=True),
    screen(9, "Dark mode", upload_card(), result_card("success"), dark=True),
]

HTML = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mini KYC - UI mockup</title>
<style>{CSS}
{DARK_TOKENS}
body {{ background: #e9edf2; }}
.mock {{ max-width: 1180px; margin: 0 auto; padding: 1.5rem 1rem 0; }}
.mock h1 {{ font-size: 1rem; color: var(--navy); margin: 0 0 .6rem; }}
.frame {{ background: var(--bg); color: var(--text); line-height: 1.45; border: 1px solid var(--border); border-radius: 14px; overflow: hidden; box-shadow: 0 6px 24px rgba(11,58,91,.12); }}
.intro {{ max-width: 1180px; margin: 0 auto; padding: 1.5rem 1rem 0; color: var(--muted); }}
</style></head><body>
<p class="intro">Mockup of the system screens (deliverable 3). Built from the same CSS as the real frontend, so it matches the implementation. The responsive layout collapses to one column below 900&nbsp;px.</p>
{''.join(SCREENS)}
<div style="height:2rem"></div></body></html>"""

(ROOT / "docs").mkdir(exist_ok=True)
(ROOT / "docs" / "mockup.html").write_text(HTML, encoding="utf-8")
print("Wrote docs/mockup.html")
