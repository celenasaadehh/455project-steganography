"""Send e-mail through SMTP.

Settings come from environment variables or from data/mail.env (see mail.env.example):
  SMTP_USER  the account that sends (e.g. you@gmail.com)
  SMTP_PASS  its password; for Gmail this must be an App Password, not the normal one
  SMTP_HOST  default smtp.gmail.com for Gmail addresses
  SMTP_PORT  587 (STARTTLS, default) or 465 (SSL)
  MAIL_FROM  sender address shown to the recipient, defaults to SMTP_USER
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent / "data" / "mail.env"
KEYS = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "MAIL_FROM")


class MailError(Exception):
    """Message is safe to show to the user."""


def config() -> dict:
    cfg = {k: os.environ.get(k, "") for k in KEYS}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k in KEYS and not cfg[k]:
                cfg[k] = v
    if not cfg["SMTP_HOST"] and cfg["SMTP_USER"].lower().endswith(("@gmail.com", "@googlemail.com")):
        cfg["SMTP_HOST"] = "smtp.gmail.com"
    cfg["SMTP_PORT"] = int(cfg["SMTP_PORT"] or 587)
    cfg["MAIL_FROM"] = cfg["MAIL_FROM"] or cfg["SMTP_USER"]
    return cfg


def configured() -> bool:
    c = config()
    return bool(c["SMTP_HOST"] and c["SMTP_USER"] and c["SMTP_PASS"])


def send(to: str, subject: str, text: str) -> None:
    c = config()
    if not configured():
        raise MailError("E-mail is not set up on this server.")
    msg = EmailMessage()
    msg["From"] = f"Stego Mail <{c['MAIL_FROM']}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    ctx = ssl.create_default_context()
    try:
        if c["SMTP_PORT"] == 465:
            with smtplib.SMTP_SSL(c["SMTP_HOST"], 465, timeout=20, context=ctx) as s:
                s.login(c["SMTP_USER"], c["SMTP_PASS"])
                s.send_message(msg)
        else:
            with smtplib.SMTP(c["SMTP_HOST"], c["SMTP_PORT"], timeout=20) as s:
                s.ehlo()
                s.starttls(context=ctx)
                s.login(c["SMTP_USER"], c["SMTP_PASS"])
                s.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        raise MailError("The mail server rejected the sender's username or password. For Gmail, use an App Password.") from None
    except (smtplib.SMTPException, OSError) as exc:
        raise MailError(f"Could not send the e-mail: {exc}") from None
