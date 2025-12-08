#!/usr/bin/env python3
"""Test de detección de PII en los PDFs problemáticos"""
import sys
from pathlib import Path

# Agregar el directorio backend al path
sys.path.insert(0, str(Path(__file__).parent))

from detectors.pii_detector import PIIDetector
from core.config import Settings
from core.pdf_processor import extract_text_with_structure
import fitz  # PyMuPDF

def test_pdf(pdf_path: str, description: str):
    """Probar detección en un PDF"""
    print("\n" + "=" * 80)
    print(f"PROBANDO: {description}")
    print(f"Archivo: {pdf_path}")
    print("=" * 80)

    # Verificar que existe el archivo
    if not Path(pdf_path).exists():
        print(f"❌ ERROR: Archivo no encontrado: {pdf_path}")
        return

    # Configurar detector con todas las opciones activadas
    settings = Settings(
        detect_names=True,
        detect_dni_nie=True,
        detect_phones=True,
        detect_emails=True,
        detect_addresses=True,
        detect_iban=True,
        use_ner=True
    )

    detector = PIIDetector(settings)

    # Abrir PDF y extraer texto estructurado
    doc = fitz.open(pdf_path)

    print(f"\n📄 PDF tiene {len(doc)} página(s)")

    all_matches = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        print(f"\n--- PÁGINA {page_num + 1} ---")

        # Extraer bloques de texto
        blocks = page.get_text("dict")["blocks"]

        # Procesar cada bloque de texto
        for block in blocks:
            if "lines" not in block:
                continue

            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"]
                    if not text.strip():
                        continue

                    # Crear objeto simulado de bloque de texto
                    class TextBlock:
                        def __init__(self, text, page_num):
                            self.text = text
                            self.page_num = page_num
                            self.bbox = span["bbox"]

                    text_block = TextBlock(text, page_num)

                    # Detectar PII
                    matches = detector.detect(text_block)

                    if matches:
                        print(f"\n  📝 Texto: '{text}'")
                        for match in matches:
                            print(f"     🔍 Detectado [{match['type']}]: '{match['text']}'")
                            print(f"        Posición: {match['start']}-{match['end']}")
                            if 'confidence' in match:
                                print(f"        Confianza: {match['confidence']:.2f}")
                        all_matches.extend(matches)

    doc.close()

    # Resumen
    print(f"\n" + "=" * 80)
    print(f"RESUMEN: {len(all_matches)} detecciones en total")

    # Agrupar por tipo
    by_type = {}
    for match in all_matches:
        tipo = match['type']
        if tipo not in by_type:
            by_type[tipo] = []
        by_type[tipo].append(match['text'])

    for tipo, textos in sorted(by_type.items()):
        print(f"  - {tipo}: {len(textos)} detecciones")
        for texto in set(textos):  # Usar set para evitar duplicados
            print(f"      • '{texto}'")

    print("=" * 80)

def main():
    """Ejecutar tests en los PDFs problemáticos"""

    print("\n" + "🔬" * 40)
    print("TEST DE DETECCIÓN DE PII - VERIFICACIÓN DE CORRECCIONES")
    print("🔬" * 40)

    # Definir PDFs a probar
    tests = [
        {
            "path": "test/pdfs/ALEGACIONES_NO_SOLICITO_PLAZA.pdf",
            "description": "Alegaciones (debe detectar: ELIAS LOPEZ DE LA PEDRAJA, DNI núm. 13920075S, firma)"
        },
        {
            "path": "test/pdfs/Resumen orientativo.pdf",
            "description": "Resumen orientativo (debe detectar nombres de personas)"
        }
    ]

    for test in tests:
        try:
            test_pdf(test["path"], test["description"])
        except Exception as e:
            print(f"\n❌ ERROR procesando {test['path']}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "✅" * 40)
    print("TEST COMPLETADO")
    print("✅" * 40 + "\n")

if __name__ == "__main__":
    main()
