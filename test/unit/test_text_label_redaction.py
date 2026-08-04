import pytest
from core.config import Settings
from processors.anonymizer import Anonymizer
from detectors.pii_detector import PIIMatch
import fitz

def test_settings_supports_text_label():
    settings = Settings(redaction_strategy="text_label")
    assert settings.redaction_strategy == "text_label"

def test_anonymizer_text_label_execution(tmp_path):
    # Crear un PDF simple de una página para probar la anonimización
    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Hola Juan, tu telefono es 666777888")
    doc.save(str(pdf_path))
    doc.close()

    # Configurar anonymizer con la nueva estrategia
    settings = Settings(redaction_strategy="text_label")
    anonymizer = Anonymizer(settings)

    # Crear una coincidencia de prueba
    matches = [
        PIIMatch(
            text="Juan",
            type="NAME",
            bbox=(50, 40, 100, 60),  # bbox aproximada
            confidence=1.0,
            page_num=0,
            source="test"
        )
    ]

    # Ejecutar anonimización
    output_path = anonymizer.apply_final_redactions(pdf_path, matches)

    # Verificar que el archivo final existe y se puede abrir
    assert output_path.exists()
    
    # Abrir el PDF final y comprobar el texto
    final_doc = fitz.open(output_path)
    assert final_doc.page_count == 1
    text = final_doc[0].get_text()
    
    # El texto original "Juan" debería haber sido eliminado o reemplazado
    assert "Juan" not in text
    final_doc.close()
