import os
import sys
import subprocess
import smtplib
from pathlib import Path
from email.message import EmailMessage
from html import escape

import markdown


def git_output(*args):
    return subprocess.check_output(
        ["git", *args], text=True
    ).strip()


def latest_markdown():
    # File Markdown attualmente tracciati da Git.
    result = subprocess.check_output([
        "git", "ls-files", "-z",
        "--", "*.md", "*.markdown"
    ])
    files = [
        p.decode("utf-8")
        for p in result.split(b"\0")
        if p
    ]

    if not files:
        raise RuntimeError("Nessun file Markdown trovato.")

    candidates = []

    for filename in files:
        path = Path(filename)

        if not path.is_file():
            continue

        # Timestamp dell'ultimo commit che ha modificato il file.
        timestamp = int(git_output(
            "log", "-1", "--format=%ct", "--", filename
        ) or "0")

        candidates.append((timestamp, filename))

    if not candidates:
        raise RuntimeError("Nessun file Markdown disponibile.")

    # In caso di parità, il nome del file rende la scelta stabile.
    _, filename = max(candidates)
    return Path(filename)


def markdown_to_html(source):
    # Arithmatex prepara le formule per MathJax.
    body = markdown.markdown(
        source,
        extensions=[
            "extra",
            "tables",
            "fenced_code",
            "toc",
            "pymdownx.arithmatex",
        ],
        extension_configs={
            "pymdownx.arithmatex": {
                "generic": True,
            }
        },
        output_format="html5",
    )

    return f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width">
<title>Documento Markdown</title>

<style>
body {{
    font-family: Arial, Helvetica, sans-serif;
    line-height: 1.65;
    color: #24292f;
    max-width: 850px;
    margin: 0 auto;
    padding: 24px;
}}
h1, h2, h3 {{
    line-height: 1.3;
    margin-top: 1.5em;
}}
pre {{
    background: #f6f8fa;
    padding: 14px;
    border-radius: 6px;
    overflow-wrap: anywhere;
    white-space: pre-wrap;
}}
code {{
    font-family: Consolas, monospace;
}}
blockquote {{
    border-left: 4px solid #d0d7de;
    padding-left: 16px;
    color: #57606a;
}}
table {{
    border-collapse: collapse;
    width: 100%;
}}
th, td {{
    border: 1px solid #d0d7de;
    padding: 8px;
    text-align: left;
}}
th {{
    background: #f6f8fa;
}}
img {{
    max-width: 100%;
    height: auto;
}}
</style>

<script>
window.MathJax = {{
  tex: {{
    inlineMath: [['\\\\(', '\\\\)'], ['$', '$']],
    displayMath: [
      ['\\\\[', '\\\\]'],
      ['$$', '$$']
    ]
  },
  options: {{
    skipHtmlTags: [
      'script', 'noscript', 'style',
      'textarea', 'pre', 'code'
    ]
  }}
}};
</script>
<script defer
  src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js">
</script>
</head>
<body>
{body}
<hr>
<p style="color:#6e7781;font-size:12px">
Email generata automaticamente da GitHub Actions.
</p>
</body>
</html>"""


def main():
    source_file = latest_markdown()
    source = source_file.read_text(encoding="utf-8")

    html = markdown_to_html(source)

    # Costruisce una versione testuale alternativa dell'email.
    plain_text = (
        f"File: {source_file}\n\n"
        f"{source}\n\n"
        "Nota: le formule sono disponibili nel sorgente LaTeX."
    )

    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "465"))
    username = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    sender = os.environ["EMAIL_FROM"]
    recipient = os.environ["EMAIL_TO"]

    message = EmailMessage()
    message["Subject"] = f"Markdown aggiornato: {source_file.name}"
    message["From"] = sender
    message["To"] = recipient

    message.set_content(plain_text)
    message.add_alternative(html, subtype="html")

    # Porta 465: SMTP su TLS implicito.
    with smtplib.SMTP_SSL(host, port, timeout=30) as server:
        server.login(username, password)
        server.send_message(message)

    print(f"Email inviata: {source_file}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        sys.exit(1)
