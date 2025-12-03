#!/usr/bin/env python3
"""
Script de test para verificar la detección de PII en documentos reales
NO usa hardcodeo - valida la lógica de detección genérica
"""

import sys
from pathlib import Path
from typing import Dict, List, Set

backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from core.config import Settings
from processors.pdf_parser import PDFParser
from processors.ocr_engine import OCREngine
from detectors.pii_detector import PIIDetector
from processors.anonymizer import Anonymizer
from detectors.models import PIIMatch
from loguru import logger

# Configurar logging
logger.remove()
logger.add(sys.stdout, format="<level>{level}: {message}</level>", level="INFO")


class PIITestValidator:
    """Validador de detección de PII sin hardcodeo"""

    def __init__(self):
        self.settings = Settings()
        self.pdf_parser = PDFParser()
        self.ocr_engine = OCREngine(self.settings)
        self.anonymizer = Anonymizer(self.settings)

    def analyze_document(self, pdf_path: Path) -> Dict:
        """
        Analiza un documento y retorna las detecciones agrupadas

        Returns:
            Dict con estadísticas y detecciones por tipo
        """
        print(f"\n{'='*80}")
        print(f"ANALIZANDO: {pdf_path.name}")
        print(f"{'='*80}\n")

        # Procesar PDF
        pdf_data = self.pdf_parser.parse(pdf_path)
        ocr_data = self.ocr_engine.process(pdf_data)

        # Detectar PII
        pii_detector = PIIDetector(self.settings, pdf_path=pdf_path)
        matches = pii_detector.detect(pdf_data, ocr_data)

        # Agrupar por tipo
        by_type = {}
        for match in matches:
            pii_type = match.type
            if pii_type not in by_type:
                by_type[pii_type] = []
            by_type[pii_type].append(match)

        # Identificar nombres únicos (sin duplicados)
        unique_names = self._extract_unique_names(by_type)

        return {
            'total': len(matches),
            'by_type': by_type,
            'unique_names': unique_names,
            'stats': self._calculate_stats(by_type, unique_names)
        }

    def _extract_unique_names(self, by_type: Dict) -> Set[str]:
        """Extrae nombres únicos de todas las detecciones de tipo nombre"""
        unique_names = set()

        # Buscar en todas las categorías que puedan contener nombres
        name_categories = ['PERSON', 'NOMBRES_CON_PREFIJO', 'NOMBRES_CON_FIRMA']

        for category in name_categories:
            if category in by_type:
                for match in by_type[category]:
                    # Normalizar el nombre (minúsculas para comparación)
                    unique_names.add(match.text.strip().lower())

        return unique_names

    def _calculate_stats(self, by_type: Dict, unique_names: Set) -> Dict:
        """Calcula estadísticas de detección"""
        stats = {
            'dni_count': 0,
            'name_detections': 0,  # Total de detecciones de nombres
            'unique_names': len(unique_names),  # Nombres únicos
            'address_count': 0,
            'phone_count': 0,
            'email_count': 0,
        }

        # Contar DNI/NIE
        if 'DNI' in by_type:
            stats['dni_count'] += len(by_type['DNI'])
        if 'NIE' in by_type:
            stats['dni_count'] += len(by_type['NIE'])

        # Contar nombres (todas las detecciones)
        name_categories = ['PERSON', 'NOMBRES_CON_PREFIJO', 'NOMBRES_CON_FIRMA']
        for category in name_categories:
            if category in by_type:
                stats['name_detections'] += len(by_type[category])

        # Contar direcciones
        if 'ADDRESS' in by_type:
            stats['address_count'] = len(by_type['ADDRESS'])

        # Contar teléfonos
        if 'PHONE' in by_type:
            stats['phone_count'] = len(by_type['PHONE'])

        # Contar emails
        if 'EMAIL' in by_type:
            stats['email_count'] = len(by_type['EMAIL'])

        return stats

    def validate_document(self, pdf_path: Path, expected: Dict) -> bool:
        """
        Valida que un documento cumpla con las expectativas de detección

        Args:
            pdf_path: Ruta al PDF
            expected: Diccionario con valores esperados:
                - name_occurrences: número de veces que aparece el nombre
                - dni: boolean
                - address: boolean
                - phone: boolean (opcional)
                - email: boolean (opcional)

        Returns:
            True si pasa todas las validaciones
        """
        result = self.analyze_document(pdf_path)
        stats = result['stats']

        print(f"\n📊 RESULTADOS DE DETECCIÓN:")
        print(f"   Total de detecciones: {result['total']}")
        print(f"   DNI/NIE: {stats['dni_count']}")
        print(f"   Nombres (detecciones totales): {stats['name_detections']}")
        print(f"   Nombres únicos: {stats['unique_names']}")
        print(f"   Direcciones: {stats['address_count']}")
        print(f"   Teléfonos: {stats['phone_count']}")
        print(f"   Emails: {stats['email_count']}")

        print(f"\n🔍 DETALLE POR TIPO:")
        for pii_type, matches in sorted(result['by_type'].items()):
            print(f"\n   {pii_type}: {len(matches)} detecciones")
            for i, match in enumerate(matches, 1):
                print(f"      [{i}] '{match.text}' (página {match.page_num})")

        # Validaciones
        passed = True
        errors = []

        # Validar nombres
        if expected.get('name_occurrences'):
            if stats['name_detections'] < expected['name_occurrences']:
                errors.append(
                    f"❌ NOMBRES: Se esperaban {expected['name_occurrences']} detecciones, "
                    f"se encontraron {stats['name_detections']}"
                )
                passed = False
            else:
                print(f"\n✅ NOMBRES: {stats['name_detections']} detecciones "
                      f"(esperado: al menos {expected['name_occurrences']})")

        # Validar DNI
        if expected.get('dni'):
            if stats['dni_count'] == 0:
                errors.append("❌ DNI: No se detectó ningún DNI/NIE")
                passed = False
            else:
                print(f"✅ DNI: {stats['dni_count']} detectado(s)")

        # Validar dirección
        if expected.get('address'):
            if stats['address_count'] == 0:
                errors.append("❌ DIRECCIÓN: No se detectó ninguna dirección")
                passed = False
            else:
                print(f"✅ DIRECCIÓN: {stats['address_count']} detectada(s)")

        # Validar teléfono
        if expected.get('phone'):
            if stats['phone_count'] == 0:
                errors.append("❌ TELÉFONO: No se detectó ningún teléfono")
                passed = False
            else:
                print(f"✅ TELÉFONO: {stats['phone_count']} detectado(s)")

        # Validar email
        if expected.get('email'):
            if stats['email_count'] == 0:
                errors.append("❌ EMAIL: No se detectó ningún email")
                passed = False
            else:
                print(f"✅ EMAIL: {stats['email_count']} detectado(s)")

        # Mostrar errores si los hay
        if errors:
            print(f"\n⚠️  ERRORES ENCONTRADOS:")
            for error in errors:
                print(f"   {error}")

        # Generar PDF anonimizado para verificación visual
        if result['total'] > 0:
            print(f"\n🖋️  GENERANDO PDF ANONIMIZADO...")
            output_path = self._anonymize_document(pdf_path, result)
            if output_path:
                print(f"   ✅ PDF anonimizado guardado en: {output_path.name}")
            else:
                print(f"   ❌ Error generando PDF anonimizado")

        return passed

    def _anonymize_document(self, pdf_path: Path, detection_result: Dict) -> Path:
        """
        Genera el PDF anonimizado en la misma carpeta

        Args:
            pdf_path: Ruta al PDF original
            detection_result: Resultado de analyze_document con las detecciones

        Returns:
            Ruta al PDF anonimizado o None si hay error
        """
        try:
            # Re-parsear el PDF (necesario para el anonymizer)
            pdf_data = self.pdf_parser.parse(pdf_path)

            # Obtener todas las detecciones
            all_matches = []
            for pii_type, matches in detection_result['by_type'].items():
                all_matches.extend(matches)

            # Generar nombre de salida en la misma carpeta
            output_path = pdf_path.parent / f"{pdf_path.stem}_anonimizado{pdf_path.suffix}"

            # Si ya existe, eliminar
            if output_path.exists():
                output_path.unlink()

            # Anonimizar usando el FileManager para generar path correcto
            from utils.file_manager import FileManager
            file_manager = FileManager(self.settings)

            # Temporalmente configurar output_dir a la carpeta de test
            original_output_dir = getattr(self.settings, 'output_dir', None)
            self.settings.output_dir = pdf_path.parent

            # Anonimizar
            import fitz
            doc = fitz.open(pdf_path)

            try:
                # Agrupar matches por página
                matches_by_page = {}
                for match in all_matches:
                    page_num = match.page_num
                    if page_num not in matches_by_page:
                        matches_by_page[page_num] = []
                    matches_by_page[page_num].append(match)

                # Procesar cada página
                for page_num, matches in matches_by_page.items():
                    if page_num < doc.page_count:
                        page = doc[page_num]
                        self.anonymizer._anonymize_page(page, matches)

                # Guardar
                doc.save(
                    str(output_path),
                    garbage=4,
                    deflate=True,
                    clean=True,
                )

                return output_path

            finally:
                doc.close()
                # Restaurar output_dir
                if original_output_dir:
                    self.settings.output_dir = original_output_dir

        except Exception as e:
            logger.error(f"Error generando PDF anonimizado: {e}")
            import traceback
            traceback.print_exc()
            return None


def main():
    """Test principal"""
    test_dir = Path(__file__).parent / "test" / "pdfs"

    if not test_dir.exists():
        print(f"❌ Error: No se encuentra el directorio {test_dir}")
        sys.exit(1)

    validator = PIITestValidator()

    print("\n" + "="*80)
    print("TEST DE DETECCIÓN DE PII - SIN HARDCODEO")
    print("="*80)

    all_passed = True

    # Test 1: Solicitud_Comision_Servicios.pdf
    # Expectativa: 2 nombres, 1 DNI, 1 dirección
    pdf1 = test_dir / "Solicitud_Comision_Servicios.pdf"
    if pdf1.exists():
        passed1 = validator.validate_document(pdf1, {
            'name_occurrences': 2,  # Nombre aparece 2 veces
            'dni': True,
            'address': True,
        })
        all_passed = all_passed and passed1
    else:
        print(f"\n⚠️  No se encuentra: {pdf1.name}")
        all_passed = False

    # Test 2: Recurso de Alzada.pdf
    # Expectativa: 2 nombres, 1 DNI, 1 dirección, 1 teléfono, 1 email
    pdf2 = test_dir / "Recurso de Alzada.pdf"
    if pdf2.exists():
        passed2 = validator.validate_document(pdf2, {
            'name_occurrences': 2,  # Nombre aparece 2 veces
            'dni': True,
            'address': True,
            'phone': True,
            'email': True,
        })
        all_passed = all_passed and passed2
    else:
        print(f"\n⚠️  No se encuentra: {pdf2.name}")
        all_passed = False

    # Resultado final
    print(f"\n{'='*80}")
    if all_passed:
        print("✅ TODOS LOS TESTS PASARON")
    else:
        print("❌ ALGUNOS TESTS FALLARON")
    print(f"{'='*80}\n")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
