import logging
from email.message import EmailMessage

import aiosmtplib
import httpx
from core import settings

log = logging.getLogger(__name__)


class MailService:
    async def send_confirmation_code_through_email(
        self, to_email: str, code: str
    ) -> None:
        subject = "Код подтверждения регистрации"
        text = f"Ваш код подтверждения: {code}\n\nОн действует 5 минут."

        if settings.mail.provider == "mailtrap_api":
            await self._send_via_mailtrap_api(to_email, subject, text)
        else:
            await self._send_via_smtp(to_email, subject, text)

    async def _send_via_smtp(self, to_email: str, subject: str, text: str) -> None:
        message = EmailMessage()
        message["From"] = settings.mail.from_email
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(text)

        await aiosmtplib.send(
            message,
            hostname=settings.mail.host,
            port=settings.mail.port,
            username=settings.mail.username,
            password=settings.mail.password,
            start_tls=settings.mail.start_tls,
            timeout=10,
        )
        log.info("Confirmation email sent to %s via SMTP", to_email)

    async def _send_via_mailtrap_api(
        self, to_email: str, subject: str, text: str
    ) -> None:
        if not settings.mail.api_token:
            raise RuntimeError("Mailtrap API token is not configured")

        payload = {
            "from": {"email": settings.mail.from_email, "name": "Torty"},
            "to": [{"email": to_email}],
            "subject": subject,
            "text": text,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                settings.mail.api_url,
                headers={"Authorization": f"Bearer {settings.mail.api_token}"},
                json=payload,
            )
            response.raise_for_status()
        log.info("Confirmation email sent to %s via Mailtrap API", to_email)


mail_service = MailService()
