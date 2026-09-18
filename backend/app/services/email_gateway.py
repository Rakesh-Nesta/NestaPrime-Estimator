"""Amendment 8 continuation (Section 17): thin client for real email
sending via SMTP -- any real mailbox works (Google Workspace, Microsoft
365, a transactional relay account), no vendor-specific client needed.

Kept deliberately small, same shape as wa_gateway.py/telegram.py: one
call (send_email), no retry/queueing here -- a send that fails surfaces
as Message.status=FAILED immediately, same synchronous-request style as
the rest of this app; a PM/Sales can just try again from the Messages
panel.
"""

import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings


class EmailGatewayError(Exception):
    """An email could not be sent -- not configured, an SMTP connection/
    auth failure, or any other send error. The caller (app/api/
    messages.py) catches this and records Message.status=FAILED rather
    than letting it 500."""


def _require_configured() -> None:
    if not settings.smtp_host or not settings.smtp_username or not settings.smtp_password:
        raise EmailGatewayError("Email sending is not configured (SMTP_HOST/USERNAME/PASSWORD unset)")


def send_email(
    to: str,
    subject: str,
    body: str,
    attachment_bytes: bytes | None = None,
    attachment_filename: str | None = None,
) -> None:
    """Plain-text send only, matching WhatsApp/Telegram's own plain-text
    messages rather than HTML email (Section 17 Decision 3). Raises
    EmailGatewayError on any failure. Returns nothing on success -- SMTP
    gives no provider message id the way wa-gateway/Telegram's own APIs
    do, so Message.provider_message_id stays unset for email (matching
    DELIVERED already being left unused for every channel -- a
    successful send here means "accepted by the mail server for relay,"
    never "the recipient received it")."""
    _require_configured()
    from_address = settings.smtp_from_address or settings.smtp_username

    message = MIMEMultipart()
    message["From"] = from_address
    message["To"] = to
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    if attachment_bytes is not None and attachment_filename:
        part = MIMEApplication(attachment_bytes, Name=attachment_filename)
        part["Content-Disposition"] = f'attachment; filename="{attachment_filename}"'
        message.attach(part)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            if settings.smtp_use_tls:
                server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(from_address, [to], message.as_string())
    except (smtplib.SMTPException, OSError) as exc:
        raise EmailGatewayError(f"Email send failed: {exc}") from exc
