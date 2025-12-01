"""
Configuración global de la aplicación
"""

from pydantic import BaseModel, Field
from typing import Literal


class Settings(BaseModel):
    """Configuración del procesador"""

    # General
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    auto_clean_temp: bool = True
    max_file_size: int = Field(default=52428800, description="50MB en bytes")

    # OCR
    ocr_language: str = "spa"  # Español
    ocr_dpi: int = 300
    use_gpu: bool = False

    # Detección PII
    detect_dni: bool = True
    detect_nie: bool = True
    detect_names: bool = True
    detect_addresses: bool = True
    detect_phones: bool = True
    detect_emails: bool = True
    detect_iban: bool = True
    detect_signatures: bool = True
    detect_qr_codes: bool = True

    # Anonimización
    redaction_color: tuple[float, float, float] = (0.35, 0.35, 0.35)  # Gris oscuro
    pixelation_level: int = 16
    redaction_strategy: Literal["black_box", "pixelate", "blur"] = "black_box"

    # Performance
    max_workers: int = 4
    batch_size: int = 10

    class Config:
        extra = "allow"  # Permitir campos adicionales
