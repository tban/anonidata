#!/usr/bin/env python3
"""
Script para probar transformaciones de coordenadas en PyMuPDF
"""

import fitz
from pathlib import Path

def test_transformations(pdf_path):
    """Prueba diferentes formas de aplicar coordenadas"""
    print(f"\n{'='*60}")
    print(f"Probando transformaciones de coordenadas")
    print(f"{'='*60}\n")

    doc = fitz.open(pdf_path)
    page = doc[0]

    # Información de la página
    print(f"Dimensiones de página: {page.rect.width} x {page.rect.height}")
    print(f"Rotation: {page.rotation} grados")
    print(f"Transformation matrix: {page.transformation_matrix}")
    print(f"MediaBox: {page.mediabox}")
    print()

    # Definir un rectángulo en coordenadas "top-left" (como envía el frontend)
    # Esquina superior izquierda: 100 puntos desde arriba, 100 desde la izquierda
    test_coords = [100, 100, 200, 150]  # [x0, y0, x1, y1]

    print(f"Coordenadas de prueba (top-left): {test_coords}")
    print(f"  x0={test_coords[0]}, y0={test_coords[1]}")
    print(f"  x1={test_coords[2]}, y1={test_coords[3]}")
    print()

    # MÉTODO 1: Usar directamente las coordenadas (asumiendo top-left)
    print("MÉTODO 1: Coordenadas directas (top-left)")
    rect1 = fitz.Rect(test_coords)
    shape1 = page.new_shape()
    shape1.draw_rect(rect1)
    shape1.finish(fill=(1, 0, 0), color=(1, 0, 0), width=0)  # Rojo
    shape1.commit()
    print(f"  Rectángulo rojo dibujado en: {rect1}")
    print()

    # MÉTODO 2: Invertir eje Y (convertir de top-left a bottom-left)
    print("MÉTODO 2: Invertir eje Y (top-left -> bottom-left)")
    page_height = page.rect.height
    y0_inverted = page_height - test_coords[3]  # Invertir y0
    y1_inverted = page_height - test_coords[1]  # Invertir y1
    rect2 = fitz.Rect(test_coords[0], y0_inverted, test_coords[2], y1_inverted)
    shape2 = page.new_shape()
    shape2.draw_rect(rect2)
    shape2.finish(fill=(0, 1, 0), color=(0, 1, 0), width=0)  # Verde
    shape2.commit()
    print(f"  y0_original={test_coords[1]} -> y0_inverted={y0_inverted}")
    print(f"  y1_original={test_coords[3]} -> y1_inverted={y1_inverted}")
    print(f"  Rectángulo verde dibujado en: {rect2}")
    print()

    # MÉTODO 3: Usar la matriz de transformación inversa
    print("MÉTODO 3: Aplicar transformación inversa")
    inv_matrix = ~page.transformation_matrix  # Matriz inversa
    print(f"  Matriz inversa: {inv_matrix}")

    # Transformar las esquinas
    p0 = fitz.Point(test_coords[0], test_coords[1]) * inv_matrix
    p1 = fitz.Point(test_coords[2], test_coords[3]) * inv_matrix
    rect3 = fitz.Rect(p0, p1)
    shape3 = page.new_shape()
    shape3.draw_rect(rect3)
    shape3.finish(fill=(0, 0, 1), color=(0, 0, 1), width=0)  # Azul
    shape3.commit()
    print(f"  Punto 0 transformado: {p0}")
    print(f"  Punto 1 transformado: {p1}")
    print(f"  Rectángulo azul dibujado en: {rect3}")
    print()

    # Guardar resultado
    output_path = Path(pdf_path).parent / f"{Path(pdf_path).stem}_transformation_test.pdf"
    doc.save(str(output_path))
    doc.close()

    print(f"{'='*60}")
    print(f"PDF guardado: {output_path}")
    print(f"{'='*60}\n")
    print("Verifica qué rectángulo aparece en la posición correcta:")
    print("  - ROJO: Coordenadas directas (top-left)")
    print("  - VERDE: Eje Y invertido (bottom-left)")
    print("  - AZUL: Transformación inversa aplicada")
    print("\nEl rectángulo que esté en la esquina superior izquierda")
    print("(100 puntos desde arriba y desde la izquierda) es el método correcto.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python test_transformation.py <ruta_pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not Path(pdf_path).exists():
        print(f"Error: No se encuentra el archivo {pdf_path}")
        sys.exit(1)

    test_transformations(pdf_path)
