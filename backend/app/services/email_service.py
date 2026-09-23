"""Backend-only email delivery service using standard SMTP.

Supports standard SMTP (e.g. Gmail App Password, university SMTP, etc.).
Provides test/mock isolation so real emails are never dispatched during automated test suites.
Never exposes or logs SMTP passwords.
"""

from __future__ import annotations

import logging
import os
import re
import smtplib
import sys
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Protocol

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class EmailConfig:
    smtp_host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", "").strip())
    smtp_port: int = field(
        default_factory=lambda: int(os.getenv("SMTP_PORT", "587").strip() or 587)
    )
    smtp_username: str = field(
        default_factory=lambda: os.getenv("SMTP_USERNAME", "").strip()
    )
    smtp_password: str = field(
        default_factory=lambda: os.getenv("SMTP_PASSWORD", "").strip()
    )
    smtp_from_email: str = field(
        default_factory=lambda: (
            os.getenv("SMTP_FROM_EMAIL", "").strip()
            or os.getenv("SMTP_USERNAME", "").strip()
            or "noreply@campus-lostandfound.edu"
        )
    )
    smtp_from_name: str = field(
        default_factory=lambda: os.getenv("SMTP_FROM_NAME", "Campus Lost & Found").strip()
    )
    smtp_use_tls: bool = field(
        default_factory=lambda: os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")
    )
    smtp_use_ssl: bool = field(
        default_factory=lambda: os.getenv("SMTP_USE_SSL", "false").lower() in ("true", "1", "yes")
    )
    timeout_seconds: int = 10

    @property
    def is_configured(self) -> bool:
        return bool(self.smtp_host)


@dataclass
class EmailDeliveryResult:
    status: str  # "SENT", "FAILED", "SKIPPED"
    recipient: str
    subject: str
    error: str | None = None


class EmailTransport(Protocol):
    def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> EmailDeliveryResult: ...


class SmtpEmailTransport:
    """Standard SMTP email transport with TLS/SSL and authentication support."""

    def __init__(self, config: EmailConfig | None = None) -> None:
        self.config = config or EmailConfig()

    def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> EmailDeliveryResult:
        if not to_email or "@" not in to_email:
            return EmailDeliveryResult(
                status="SKIPPED",
                recipient=to_email,
                subject=subject,
                error="Invalid or missing recipient email address.",
            )

        if not self.config.is_configured:
            logger.info(
                "SMTP not configured; skipping email delivery to %s for subject '%s'",
                to_email,
                subject,
            )
            return EmailDeliveryResult(
                status="SKIPPED",
                recipient=to_email,
                subject=subject,
                error="SMTP_HOST is not configured in backend environment.",
            )

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self.config.smtp_from_name} <{self.config.smtp_from_email}>"
        msg["To"] = to_email

        # Attach text and optional HTML alternative
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        if body_html:
            msg.attach(MIMEText(body_html, "html", "utf-8"))

        try:
            logger.info(
                "Connecting to SMTP server at %s:%d to send notification to %s",
                self.config.smtp_host,
                self.config.smtp_port,
                to_email,
            )
            if self.config.smtp_use_ssl:
                server = smtplib.SMTP_SSL(
                    self.config.smtp_host,
                    self.config.smtp_port,
                    timeout=self.config.timeout_seconds,
                )
            else:
                server = smtplib.SMTP(
                    self.config.smtp_host,
                    self.config.smtp_port,
                    timeout=self.config.timeout_seconds,
                )

            with server:
                if self.config.smtp_use_tls and not self.config.smtp_use_ssl:
                    server.starttls()

                if self.config.smtp_username and self.config.smtp_password:
                    server.login(self.config.smtp_username, self.config.smtp_password)

                server.sendmail(
                    self.config.smtp_from_email,
                    [to_email],
                    msg.as_string(),
                )

            logger.info("Successfully sent email notification to %s", to_email)
            return EmailDeliveryResult(
                status="SENT",
                recipient=to_email,
                subject=subject,
            )

        except Exception as exc:
            # Sanitize error to avoid leaking credentials
            err_msg = str(exc)
            if self.config.smtp_password and self.config.smtp_password in err_msg:
                err_msg = err_msg.replace(self.config.smtp_password, "[REDACTED]")
            logger.error(
                "SMTP email delivery to %s failed: %s",
                to_email,
                err_msg,
            )
            return EmailDeliveryResult(
                status="FAILED",
                recipient=to_email,
                subject=subject,
                error=err_msg,
            )


class MockEmailTransport:
    """In-memory mock transport for testing. Does not send real network requests."""

    def __init__(self) -> None:
        self.sent_emails: list[dict[str, Any]] = []
        self.simulate_failure: bool = False
        self.failure_error: str = "Simulated SMTP connection error"

    def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> EmailDeliveryResult:
        if not to_email or "@" not in to_email:
            return EmailDeliveryResult(
                status="SKIPPED",
                recipient=to_email,
                subject=subject,
                error="Invalid or missing recipient email address.",
            )

        if self.simulate_failure:
            return EmailDeliveryResult(
                status="FAILED",
                recipient=to_email,
                subject=subject,
                error=self.failure_error,
            )

        email_record = {
            "to": to_email,
            "subject": subject,
            "body_text": body_text,
            "body_html": body_html,
        }
        self.sent_emails.append(email_record)
        return EmailDeliveryResult(
            status="SENT",
            recipient=to_email,
            subject=subject,
        )

    def clear(self) -> None:
        self.sent_emails.clear()
        self.simulate_failure = False


# Active transport singleton
_active_transport: EmailTransport | None = None


def get_email_transport() -> EmailTransport:
    global _active_transport
    if _active_transport is not None:
        return _active_transport

    # Auto-detect test environment to prevent real emails during test runs
    if "pytest" in sys.modules or os.getenv("ENVIRONMENT") == "test":
        _active_transport = MockEmailTransport()
    else:
        _active_transport = SmtpEmailTransport()

    return _active_transport


def set_email_transport(transport: EmailTransport | None) -> None:
    global _active_transport
    _active_transport = transport
