from fastapi_mail import FastMail, MessageSchema

from ..models.email import email_config


async def send_verification_email(email: str, verification_link: str):
    message = MessageSchema(
        subject="Your Verification Link",
        recipients=[email],
        body=f"Your verification Link is {verification_link}.",
        subtype="plain",
    )

    fm = FastMail(email_config)
    await fm.send_message(message)
