"""Build docs/mockup.html: static UI mockup of the screens, styled with the real frontend CSS.

Usage:  python scripts/build_mockup.py
"""

import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "frontend" / "src" / "styles.css").read_text(encoding="utf-8")
SAMPLE = base64.b64encode((ROOT / "samples" / "sample_id_sharp.png").read_bytes()).decode()

TOPBAR = """
<header class="topbar">
  <div class="brand"><span class="brand-mark"></span><span class="brand-name">Digital Onboarding · KYC</span></div>
  <div class="topbar-actions"><span class="lang-toggle">ES</span><span class="operator">Operator</span></div>
</header>"""


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
    flags = '<ul class="flags"><li class="flag">Low reading confidence</li><li class="flag">This photo was already used with another email</li></ul>'
    body = f"""
<div class="result-grid"><img class="preview" src="data:image/png;base64,{SAMPLE}" alt="Uploaded document">
<dl class="fields">
<div><dt>Full name</dt><dd>Maria Fernandez Torres</dd></div>
<div><dt>Document type</dt><dd>DNI</dd></div>
<div><dt>Document no.</dt><dd>12345678</dd></div>
<div><dt>OCR confidence</dt><dd>71.0%</dd></div>
<div><dt>Registered</dt><dd>11/2/2026, 10:44:31 AM</dd></div></dl></div>
<p class="note">An operator will review this record manually. Your data was saved.</p>{flags}"""
    head = '<div class="card-heading"><h2 class="card-title">Extracted data</h2><span class="badge badge-warn">Needs review</span></div>'
    return f'<section class="card result-card">{head}{body}</section>'


def operator_card():
    item = """
<li class="review-item">
  <div class="review-item-head"><strong>#12 · Maria Fernandez Torres</strong><span class="muted small">11/2/2026, 10:44:31 AM</span></div>
  <dl class="review-fields">
    <div><dt>Email address</dt><dd>maria.fernandez@example.com</dd></div>
    <div><dt>Document type</dt><dd>DNI · 12345678</dd></div>
    <div><dt>OCR confidence</dt><dd>71.0%</dd></div>
  </dl>
  <ul class="flags"><li class="flag">Low reading confidence</li><li class="flag">This photo was already used with another email</li></ul>
  <div class="input">Comment (optional)</div>
  <div class="review-buttons"><span class="button button-approve">Approve</span><span class="button button-reject">Reject</span></div>
</li>"""
    return f"""
<section class="card review-card"><div class="card-heading review-heading"><h2 class="card-title">Manual review</h2>
<div class="review-actions"><span class="button button-secondary">Refresh</span><span class="button button-secondary">Sign out</span></div></div>
<span class="field-label">Your name</span><div class="input reviewer-input">Ana</div>
<ul class="review-list">{item}</ul></section>"""


def result_card(kind):
    head = '<div class="card-heading"><h2 class="card-title">Extracted data</h2>{badge}</div>'
    if kind == "idle":
        body = '<div class="placeholder"><p class="placeholder-title">No document processed yet</p><p class="muted">Enter your email and upload a photo of your ID to see the extracted data here.</p></div>'
        return f'<section class="card result-card">{head.format(badge="")}{body}</section>'
    if kind == "loading":
        body = '<div class="placeholder"><span class="spinner spinner-large"></span><p>Reading your document. This usually takes a few seconds…</p></div>'
        return f'<section class="card result-card">{head.format(badge="")}{body}</section>'
    if kind == "error":
        return result_card("idle")
    body = f"""
<div class="result-grid"><img class="preview" src="data:image/png;base64,{SAMPLE}" alt="Uploaded document">
<dl class="fields">
<div><dt>Full name</dt><dd>Maria Fernandez Torres</dd></div>
<div><dt>Document type</dt><dd>DNI</dd></div>
<div><dt>Document no.</dt><dd>12345678</dd></div>
<div><dt>OCR confidence</dt><dd>98.0%</dd></div>
<div><dt>Registered</dt><dd>11/2/2026, 10:42:07 AM</dd></div></dl></div>
<p class="note">AI / OCR: automatic extraction of fields from the document image.</p>"""
    return f'<section class="card result-card">{head.format(badge=chr(60) + "span class=" + chr(34) + "badge badge-ok" + chr(34) + ">Verified</span>")}{body}</section>'


def screen(number, title, upload, result, single=False):
    layout = '<main class="layout layout-single">' + result + "</main>" if single else f'<main class="layout">{upload}{result}</main>'
    return f"""
<section class="mock">
  <h1>{number}. {title}</h1>
  <div class="frame">{TOPBAR}{layout}</div>
</section>"""


SCREENS = [
    screen(1, "Initial state", upload_card(email="", filled=False), result_card("idle")),
    screen(2, "Processing (loading state)", upload_card(loading=True), result_card("loading")),
    screen(3, "Result: verified", upload_card(), result_card("success")),
    screen(
        4,
        "Error: blurry image",
        upload_card(error="The photo is too blurry to read. Retake it in good light and keep the camera steady."),
        result_card("error"),
    ),
    screen(5, "Result: flagged for manual review", upload_card(), review_note_card()),
    screen(6, "Operator: manual review of flagged records", "", operator_card(), single=True),
]

HTML = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mini KYC - UI mockup</title>
<style>{CSS}
body {{ background: #e9edf2; }}
.mock {{ max-width: 1180px; margin: 0 auto; padding: 1.5rem 1rem 0; }}
.mock h1 {{ font-size: 1rem; color: var(--navy); margin: 0 0 .6rem; }}
.frame {{ background: var(--bg); border: 1px solid var(--border); border-radius: 14px; overflow: hidden; box-shadow: 0 6px 24px rgba(11,58,91,.12); }}
.intro {{ max-width: 1180px; margin: 0 auto; padding: 1.5rem 1rem 0; color: var(--muted); }}
</style></head><body>
<p class="intro">Mockup of the system screens (deliverable 3). Built from the same CSS as the real frontend, so it matches the implementation. The responsive layout collapses to one column below 900&nbsp;px.</p>
{''.join(SCREENS)}
<div style="height:2rem"></div></body></html>"""

(ROOT / "docs").mkdir(exist_ok=True)
(ROOT / "docs" / "mockup.html").write_text(HTML, encoding="utf-8")
print("Wrote docs/mockup.html")
