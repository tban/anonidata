#!/usr/bin/env python3
"""
Test POC del flujo de revisión de anonimización
Prueba el enfoque de dos etapas: pre-anonimizado -> revisión -> final
"""
import sys
from pathlib import Path

# Agregar el directorio backend al path
sys.path.insert(0, str(Path(__file__).parent))

from core.config import Settings
from processors.anonymizer import Anonymizer
from processors.pdf_parser import PDFParser
from processors.ocr_engine import OCREngine
from detectors.pii_detector import PIIDetector
import fitz

def test_review_workflow(pdf_path: str):
    """Probar el flujo completo de revisión"""
    print("\n" + "=" * 80)
    print("TEST POC - FLUJO DE REVISIÓN DE ANONIMIZACIÓN")
    print("=" * 80)

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        print(f"❌ ERROR: Archivo no encontrado: {pdf_path}")
        return False

    print(f"\n📄 Procesando: {pdf_path.name}")

    # Configurar
    settings = Settings(
        detect_names=True,
        detect_dni=True,
        detect_nie=True,
        detect_phones=True,
        detect_emails=True,
        detect_addresses=True,
    )

    # PASO 1: Detectar PII usando el procesador completo
    print("\n" + "-" * 80)
    print("PASO 1: Detección de PII")
    print("-" * 80)

    pdf_parser = PDFParser()
    ocr_engine = OCREngine(settings)
    pii_detector = PIIDetector(settings, pdf_path=pdf_path)
    anonymizer = Anonymizer(settings)

    # Parsear PDF
    pdf_data = pdf_parser.parse(pdf_path)
    print(f"✓ PDF parseado: {pdf_data.page_count} páginas")

    # Procesar con OCR
    ocr_data = ocr_engine.process(pdf_data)
    print(f"✓ OCR procesado")

    # Detectar PII
    all_matches = pii_detector.detect(pdf_data, ocr_data)
    pdf_parser.close(pdf_data)

    print(f"✓ Detectados {len(all_matches)} elementos de PII")

    # Mostrar estadísticas por tipo
    by_type = {}
    for match in all_matches:
        tipo = match.type
        if tipo not in by_type:
            by_type[tipo] = 0
        by_type[tipo] += 1

    print("\n📊 Estadísticas de detección:")
    for tipo, count in sorted(by_type.items()):
        print(f"  - {tipo}: {count}")

    if len(all_matches) == 0:
        print("\n⚠️  No se detectaron PII para probar el flujo")
        return False

    # PASO 2: Crear PDF pre-anonimizado
    print("\n" + "-" * 80)
    print("PASO 2: Crear PDF pre-anonimizado (con texto debajo de rectángulos grises)")
    print("-" * 80)

    pre_anon_path, detections_path = anonymizer.create_pre_anonymized(
        pdf_path,
        all_matches
    )

    print(f"✓ PDF pre-anonimizado creado: {pre_anon_path.name}")
    print(f"✓ Detecciones guardadas en: {detections_path.name}")

    # Verificar que el PDF tiene las anotaciones
    doc_pre = fitz.open(pre_anon_path)
    has_annotations = False
    for page in doc_pre:
        if len(list(page.annots())) > 0:
            has_annotations = True
            break
    doc_pre.close()

    if has_annotations:
        print("✓ El PDF pre-anonimizado tiene anotaciones (rectángulos grises)")
    else:
        print("❌ El PDF pre-anonimizado NO tiene anotaciones")
        return False

    # PASO 3: Cargar detecciones desde JSON
    print("\n" + "-" * 80)
    print("PASO 3: Cargar detecciones desde JSON")
    print("-" * 80)

    loaded_matches = anonymizer.load_detections(detections_path)
    print(f"✓ Cargadas {len(loaded_matches)} detecciones desde JSON")

    if len(loaded_matches) != len(all_matches):
        print(f"❌ ERROR: Número de detecciones no coincide")
        print(f"   Original: {len(all_matches)}, Cargadas: {len(loaded_matches)}")
        return False

    # Verificar que los datos son correctos
    for i, (original, loaded) in enumerate(zip(all_matches, loaded_matches)):
        if original.type != loaded.type or original.text != loaded.text:
            print(f"❌ ERROR: Detección {i} no coincide")
            print(f"   Original: {original.type} - '{original.text}'")
            print(f"   Cargada:  {loaded.type} - '{loaded.text}'")
            return False

    print("✓ Todas las detecciones cargadas correctamente")

    # PASO 4: Simular revisión y aprobar solo algunas detecciones
    print("\n" + "-" * 80)
    print("PASO 4: Simular revisión del usuario")
    print("-" * 80)

    # Simular que el usuario aprueba el 70% de las detecciones
    # En producción, esto vendría de la interfaz de usuario
    num_approved = int(len(loaded_matches) * 0.7)
    approved_matches = loaded_matches[:num_approved]

    print(f"📝 Usuario revisó {len(loaded_matches)} detecciones")
    print(f"✓ Usuario aprobó {len(approved_matches)} detecciones")
    print(f"✗ Usuario rechazó {len(loaded_matches) - len(approved_matches)} detecciones")

    # PASO 5: Aplicar redacciones finales solo a detecciones aprobadas
    print("\n" + "-" * 80)
    print("PASO 5: Aplicar redacciones finales (solo detecciones aprobadas)")
    print("-" * 80)

    final_path = anonymizer.apply_final_redactions(
        pdf_path,
        approved_matches
    )

    print(f"✓ PDF final anonimizado creado: {final_path.name}")

    # Verificar que el PDF final existe y es válido
    if not final_path.exists():
        print("❌ ERROR: El PDF final no se creó")
        return False

    doc_final = fitz.open(final_path)
    print(f"✓ PDF final tiene {doc_final.page_count} páginas")
    doc_final.close()

    # RESUMEN
    print("\n" + "=" * 80)
    print("RESUMEN DEL TEST POC")
    print("=" * 80)
    print(f"✅ Archivo original:        {pdf_path.name}")
    print(f"✅ PDF pre-anonimizado:     {pre_anon_path.name}")
    print(f"✅ Detecciones JSON:        {detections_path.name}")
    print(f"✅ PDF final anonimizado:   {final_path.name}")
    print(f"")
    print(f"📊 Estadísticas:")
    print(f"   - Detecciones totales:   {len(all_matches)}")
    print(f"   - Detecciones aprobadas: {len(approved_matches)}")
    print(f"   - Detecciones rechazadas: {len(loaded_matches) - len(approved_matches)}")
    print("")
    print("✅ TEST POC COMPLETADO EXITOSAMENTE")
    print("=" * 80 + "\n")

    return True

if __name__ == "__main__":
    # Verificar si hay un PDF de prueba
    import glob

    # Buscar PDFs de prueba
    test_pdfs = list(Path("test/pdfs").glob("*.pdf")) if Path("test/pdfs").exists() else []

    if not test_pdfs:
        print("\n⚠️  No se encontraron PDFs de prueba en test/pdfs/")
        print("   Por favor, coloca un PDF de prueba y ejecuta de nuevo:")
        print("   python backend/test_review_workflow.py <ruta_al_pdf>")
        sys.exit(1)

    # Usar el primer PDF encontrado
    test_pdf = test_pdfs[0]

    # Permitir especificar PDF por línea de comandos
    if len(sys.argv) > 1:
        test_pdf = Path(sys.argv[1])

    success = test_review_workflow(str(test_pdf))
    sys.exit(0 if success else 1)
