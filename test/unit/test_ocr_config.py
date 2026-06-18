import pytest
from unittest.mock import MagicMock
from core.config import Settings
from processors.ocr_engine import OCREngine
from processors.pdf_parser import PDFData


def test_ocr_engine_disabled():
    # Arrange
    settings = Settings(enable_ocr=False)
    ocr_engine = OCREngine(settings)

    mock_pdf_data = MagicMock(spec=PDFData)
    mock_pdf_data.image_blocks = []
    mock_pdf_data.page_count = 1
    mock_pdf_data.text_blocks = []

    # Act
    ocr_data = ocr_engine.process(mock_pdf_data)

    # Assert
    assert len(ocr_data.results) == 0
    assert len(ocr_data.pages_processed) == 0


def test_ocr_engine_enabled_by_default():
    settings = Settings()
    assert settings.enable_ocr is True
