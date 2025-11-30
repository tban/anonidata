"""
Configuración de logging con sanitización de PII
"""

import re
import sys
from pathlib import Path
from loguru import logger


def sanitize_message(message: str) -> str:
    """
    Elimina cualquier PII de los mensajes de log

    Args:
        message: Mensaje original

    Returns:
        Mensaje sanitizado
    """
    # Redactar DNI/NIE
    message = re.sub(r'\b[0-9]{8}[A-Z]\b', '[DNI_REDACTED]', message)
    message = re.sub(r'\b[XYZ][0-9]{7}[A-Z]\b', '[NIE_REDACTED]', message)

    # Redactar emails
    message = re.sub(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        '[EMAIL_REDACTED]',
        message
    )

    # Redactar teléfonos
    message = re.sub(r'\b\+?[0-9]{9,15}\b', '[PHONE_REDACTED]', message)

    # Redactar IBAN
    message = re.sub(r'\bES[0-9]{2}\s?[0-9]{20}\b', '[IBAN_REDACTED]', message)

    return message


class SanitizingFilter:
    """Filtro para sanitizar logs"""

    def __call__(self, record):
        record["message"] = sanitize_message(record["message"])
        return True


def setup_logging():
    """Configurar sistema de logging"""

    # Remover handlers por defecto
    logger.remove()

    # Console handler (para desarrollo)
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="DEBUG",
        filter=SanitizingFilter(),
    )

    # File handler
    logs_dir = Path(__file__).parent.parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)

    logger.add(
        logs_dir / "anonidata_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="INFO",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        filter=SanitizingFilter(),
    )

    logger.info("Sistema de logging configurado")
