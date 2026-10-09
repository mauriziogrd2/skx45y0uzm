
import os
import sys
import subprocess
import smtplib
from pathlib import Path
from email.message import EmailMessage

import markdown


def git_output(*args):
    """Esegue un comando Git e restituisce l'output."""
    return subprocess.check_output(
        ["git", *args],
        text=True
    ).strip()


def latest_markdown():
    """
    Trova il file Markdown tracciato da Git con il
    timestamp dell'ultimo commit più recente.
    """
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
        raise RuntimeError(
            "Nessun file Markdown trovato nel repository."
        )

    candidates = []

    for filename in files:
        path = Path(filename)

        if not path.is_file():
            continue

        timestamp = int(
            git_output(
                "log",
                "-1",
                "--format=%ct",
                "--",
                filename
            ) or "0"
        )

        candidates.append((timestamp, filename))

    if not candidates:
        raise RuntimeError(
            "Nessun file Markdown disponibile."
        )

    # Se più file hanno lo stesso timestamp, il nome
    # del file garantisce una scelta deterministica.
    _, filename = max(candidates)

    print(f"File Markdown selezionato: {filename}")

    return Path(filename)


def markdown_to_html(source):
    """Converte Markdown in HTML con supporto per LaTeX."""

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

    # Template HTML normale, NON una f-string:
    # le parentesi graffe JavaScript non causano SyntaxError.
    template = r"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width">
<title>Documento Markdown</title>

<style>
body {
    font-family: Arial, Helvetica, sans-serif;
    line-height: 1.65;
    color: #24292f;
    max-width: 850px;
    margin: 0 auto;
    padding: 24px;
    overflow-wrap: anywhere;
}

h1, h2, h3, h4 {
    line-height: 1.3;
    margin-top: 1.5em;
}

pre {
    background: #f6f8fa;
    padding: 14px;
    border-radius: 6px;
    overflow-x: auto;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
}

code {
    font-family: Consolas, Monaco, monospace;
}

blockquote {
    border-left: 4px solid #d0d7de;
    padding-left: 16px;
    color: #57606a;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin: 16px 0;
}

th, td {
    border: 1px solid #d0d7de;
    padding: 8px;
    text-align: left;
}

th {
    background: #f6f8fa;
}

img {
    max-width: 100%;
    height: auto;
}

a {
    color: #0969da;
}
</style>

<script>
window.MathJax = {
  tex: {
    inlineMath: [['\\(', '\\)'], ['$', '$']],
    displayMath: [['\\[', '\\]'], ['$$', '$$']]
  },
  options: {
    skipHtmlTags: [
      'script', 'noscript', 'style',
      'textarea', 'pre', 'code'
    ]
  }
};
</script>

<script defer
  src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js">
</script>

</head>
<body>

__MARKDOWN_BODY__

<hr>

<p style="color:#6e7781;font-size:12px">
Email generata automaticamente da GitHub Actions.
</p>

</body>
</html>
"""

    return template.replace("__MARKDOWN_BODY__", body)


def send_email(source_file, source, html):
    """Invia l'email HTML tramite SMTP."""

    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "465"))
    username = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    sender = os.environ["EMAIL_FROM"]
    recipient = os.environ["EMAIL_TO"]

    message = EmailMessage()

    message["Subject"] = (
        f"Markdown aggiornato: {source_file.name}"
    )
    message["From"] = sender
    message["To"] = recipient

    # Versione testuale alternativa per i client senza HTML.
    plain_text = (
        f"File Markdown: {source_file}\n\n"
        f"{source}\n\n"
        "Le formule matematiche sono riportate "
        "nella sintassi LaTeX originale."
    )

    message.set_content(plain_text)
    message.add_alternative(html, subtype="html")

    if port == 465:
        # TLS implicito, ad esempio Gmail sulla porta 465.
        with smtplib.SMTP_SSL(
            host,
            port,
            timeout=30
        ) as server:
            server.login(username, password)
            server.send_message(message)

    else:
        # STARTTLS, ad esempio Gmail sulla porta 587.
        with smtplib.SMTP(
            host,
            port,
            timeout=30
        ) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(username, password)
            server.send_message(message)

    print(f"Email inviata correttamente a {recipient}")


def main():
    source_file = latest_markdown()

    source = source_file.read_text(
        encoding="utf-8"
    )

    html = markdown_to_html(source)

    send_email(
        source_file=source_file,
        source=source,
        html=html,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"ERRORE: {type(exc).__name__}: {exc}",
            file=sys.stderr
        )
        sys.exit(1)
