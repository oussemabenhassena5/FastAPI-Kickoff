import os

from dotenv import load_dotenv
from fastapi_mail import ConnectionConfig
from pydantic import BaseModel, EmailStr, Field

# Load environment variables
load_dotenv()


class EmailConfig(BaseModel):
    """
    Pydantic model for email configuration settings.
    """

    MAIL_USERNAME: EmailStr = Field(
        ..., description="SMTP server username (email address)."
    )
    MAIL_PASSWORD: str = Field(..., description="SMTP server password.")
    MAIL_FROM: EmailStr = Field(..., description="Sender email address.")
    MAIL_PORT: int = Field(..., ge=1, le=65535, description="SMTP server port.")
    MAIL_SERVER: str = Field(..., description="SMTP server hostname or IP.")
    MAIL_STARTTLS: bool = Field(
        default=False, description="Use STARTTLS for SMTP connection."
    )
    MAIL_SSL_TLS: bool = Field(
        default=False, description="Use SSL/TLS for SMTP connection."
    )
    USE_CREDENTIALS: bool = Field(
        default=True, description="Use credentials for authentication."
    )
    VALIDATE_CERTS: bool = Field(
        default=True, description="Validate server SSL certificates."
    )

    @classmethod
    def from_env(cls) -> "EmailConfig":
        """
        Creates an EmailConfig instance from environment variables.
        """
        return cls(
            MAIL_USERNAME=os.getenv("SMTP_USERNAME"),
            MAIL_PASSWORD=os.getenv("SMTP_PASSWORD"),
            MAIL_FROM=os.getenv("SMTP_USERNAME"),
            MAIL_PORT=int(os.getenv("SMTP_PORT", 587)),
            MAIL_SERVER=os.getenv("SMTP_HOST"),
            MAIL_STARTTLS=os.getenv("SMTP_STARTTLS", "false").lower()
            in ("true", "1", "yes"),
            MAIL_SSL_TLS=os.getenv("SMTP_SSL_TLS", "false").lower()
            in ("true", "1", "yes"),
            USE_CREDENTIALS=os.getenv("USE_CREDENTIALS", "true").lower()
            in ("true", "1", "yes"),
            VALIDATE_CERTS=os.getenv("VALIDATE_CERTS", "true").lower()
            in ("true", "1", "yes"),
        )


# Initialize email configuration
email_config_instance = EmailConfig.from_env()

# Use the configuration for FastAPI Mail
email_config = ConnectionConfig(
    MAIL_USERNAME=email_config_instance.MAIL_USERNAME,
    MAIL_PASSWORD=email_config_instance.MAIL_PASSWORD,
    MAIL_FROM=email_config_instance.MAIL_FROM,
    MAIL_PORT=email_config_instance.MAIL_PORT,
    MAIL_SERVER=email_config_instance.MAIL_SERVER,
    MAIL_STARTTLS=email_config_instance.MAIL_STARTTLS,
    MAIL_SSL_TLS=email_config_instance.MAIL_SSL_TLS,
    USE_CREDENTIALS=email_config_instance.USE_CREDENTIALS,
    VALIDATE_CERTS=email_config_instance.VALIDATE_CERTS,
)
