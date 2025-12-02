#!/usr/bin/env python3
"""
Script de diagnóstico para ver TODAS las detecciones de PII
"""

import sys
from pathlib import Path

# Agregar backend al path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from core.config import Settings
from processors.pdf_parser import PDFParser
from processors.ocr_engine import OCREngine
from detectors.pii_detector import PIIDetector
from loguru import logger

# Configurar logging simple
logger.remove()
logger.add(sys.stdout, format="<level>{message}</level>", level="DEBUG")

def main():
    if len(sys.argv) < 2:
        print("Uso: python test_detection.py <archivo.pdf>")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])

    if not pdf_path.exists():
        print(f"Error: No se encuentra el archivo {pdf_path}")
        sys.exit(1)

    print(f"\n{'='*80}")
    print(f"DIAGNÓSTICO DE DETECCIÓN PII: {pdf_path.name}")
    print(f"{'='*80}\n")

    # Configurar
    settings = Settings()

    # Procesar
    pdf_parser = PDFParser()
    ocr_engine = OCREngine(settings)
    pii_detector = PIIDetector(settings, pdf_path=pdf_path)

    print("📄 Parseando PDF...")
    pdf_data = pdf_parser.parse(pdf_path)
    print(f"   ✓ {pdf_data.page_count} páginas, {len(pdf_data.text_blocks)} bloques de texto\n")

    print("🔍 Aplicando OCR...")
    ocr_data = ocr_engine.process(pdf_data)
    print(f"   ✓ {len(ocr_data.pages_processed)} páginas procesadas con OCR\n")

    print("🎯 Detectando PII...")
    matches = pii_detector.detect(pdf_data, ocr_data)

    print(f"\n{'='*80}")
    print(f"RESULTADOS: {len(matches)} ELEMENTOS DETECTADOS")
    print(f"{'='*80}\n")

    # Agrupar por tipo
    by_type = {}
    for match in matches:
        match_type = match.type.upper()
        if match_type not in by_type:
            by_type[match_type] = []
        by_type[match_type].append(match)

    # Mostrar resumen
    print("📊 RESUMEN POR TIPO:\n")
    for match_type, items in sorted(by_type.items()):
        print(f"   {match_type:20} : {len(items):3} elemento(s)")

    # Mostrar detalles
    print(f"\n{'='*80}")
    print("DETALLES DE CADA DETECCIÓN:")
    print(f"{'='*80}\n")

    for i, match in enumerate(matches, 1):
        print(f"{i:3}. [{match.type:20}] Página {match.page_num} | Confianza: {match.confidence:.2f} | Fuente: {match.source}")
        print(f"     Texto: '{match.text}'")
        print(f"     BBox:  {match.bbox}")
        print()

if __name__ == "__main__":
    main()
