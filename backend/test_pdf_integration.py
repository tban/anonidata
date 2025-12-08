#!/usr/bin/env python3
"""Test de integración completo - procesar PDFs problemáticos"""
import sys
from pathlib import Path

# Agregar el directorio backend al path
sys.path.insert(0, str(Path(__file__).parent))

from core.config import Settings
from core.processor import PDFProcessor
import json

def test_pdf_file(pdf_path: str, expected_detections: dict):
    """Probar procesamiento de un PDF"""
    print("\n" + "=" * 80)
    print(f"PROBANDO: {Path(pdf_path).name}")
    print("=" * 80)

    # Verificar que existe el archivo
    if not Path(pdf_path).exists():
        print(f"❌ ERROR: Archivo no encontrado: {pdf_path}")
        return False

    # Configurar procesador con todas las opciones activadas
    settings = Settings(
        detect_names=True,
        detect_dni_nie=True,
        detect_phones=True,
        detect_emails=True,
        detect_addresses=True,
        detect_iban=True,
        use_ner=True,
        output_dir=Path("test/output"),
        auto_clean_temp=False
    )

    # Asegurar que existe el directorio de salida
    settings.output_dir.mkdir(parents=True, exist_ok=True)

    processor = PDFProcessor(settings)

    print(f"\n📄 Procesando: {pdf_path}")

    try:
        # Procesar el PDF
        result = processor.process_file(pdf_path)

        # Mostrar resultado
        print(f"\n✓ Estado: {result['status']}")

        if result['status'] == 'error':
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
            return False

        # Mostrar estadísticas
        stats = result.get('stats', {})
        print(f"\n📊 ESTADÍSTICAS DE DETECCIÓN:")
        print(f"  - DNI/NIE: {stats.get('dniCount', 0)}")
        print(f"  - Nombres: {stats.get('nameCount', 0)}")
        print(f"  - Direcciones: {stats.get('addressCount', 0)}")
        print(f"  - Teléfonos: {stats.get('phoneCount', 0)}")
        print(f"  - Emails: {stats.get('emailCount', 0)}")
        print(f"  - Firmas: {stats.get('signatureCount', 0)}")
        print(f"  - QR Codes: {stats.get('qrCount', 0)}")

        # Mostrar warnings si los hay
        if 'warnings' in result:
            print(f"\n⚠️  ADVERTENCIAS:")
            for warning in result['warnings']:
                print(f"  - {warning}")

        # Verificar detecciones esperadas
        print(f"\n🔍 VERIFICACIÓN DE DETECCIONES ESPERADAS:")
        all_passed = True

        for key, expected_count in expected_detections.items():
            actual_count = stats.get(key, 0)
            if actual_count >= expected_count:
                print(f"  ✓ {key}: {actual_count} >= {expected_count} (esperado)")
            else:
                print(f"  ✗ {key}: {actual_count} < {expected_count} (esperado)")
                all_passed = False

        # Mostrar archivo de salida
        print(f"\n📁 Archivo de salida: {result.get('outputFile', 'N/A')}")
        print(f"⏱️  Tiempo de procesamiento: {result.get('processingTime', 0):.2f}s")

        return all_passed

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Ejecutar tests de integración"""

    print("\n" + "🔬" * 40)
    print("TEST DE INTEGRACIÓN - VERIFICACIÓN DE CORRECCIONES DE PII")
    print("🔬" * 40)

    # Definir tests
    tests = [
        {
            "path": "test/pdfs/ALEGACIONES_NO_SOLICITO_PLAZA.pdf",
            "expected": {
                "dniCount": 1,  # DNI núm. 13920075S
                "nameCount": 2,  # ELIAS LOPEZ DE LA PEDRAJA (en texto y en firma)
                "addressCount": 1,  # Calle Principal 123
                "phoneCount": 1,  # 666123456
                "emailCount": 1,  # email@example.com
            }
        },
        {
            "path": "test/pdfs/Resumen orientativo.pdf",
            "expected": {
                "nameCount": 1,  # Al menos 1 nombre detectado
            }
        }
    ]

    results = []
    for test in tests:
        passed = test_pdf_file(test["path"], test["expected"])
        results.append({
            "file": test["path"],
            "passed": passed
        })

    # Resumen final
    print("\n" + "=" * 80)
    print("RESUMEN FINAL")
    print("=" * 80)

    all_passed = True
    for result in results:
        status = "✅ PASÓ" if result["passed"] else "❌ FALLÓ"
        print(f"{status}: {Path(result['file']).name}")
        if not result["passed"]:
            all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print("✅ TODOS LOS TESTS PASARON")
    else:
        print("❌ ALGUNOS TESTS FALLARON - REVISAR DETECCIONES")
    print("=" * 80 + "\n")

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
