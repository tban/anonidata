#!/usr/bin/env python3
"""
Script de prueba para diagnosticar ubicación de rectángulos en PDFs con rotación
"""

import fitz
import sys
from pathlib import Path

def test_ubicacion(pdf_path):
    """Dibuja rectángulos en las 4 esquinas y centro para diagnosticar coordenadas"""
    print(f"\n{'='*70}")
    print(f"Test de ubicación de coordenadas")
    print(f"{'='*70}\n")

    doc = fitz.open(pdf_path)
    page = doc[0]

    # Información de la página
    print(f"MediaBox: {page.mediabox}")
    print(f"Rect: {page.rect}")
    print(f"Rotation: {page.rotation} grados")
    print(f"Dimensiones: {page.rect.width} x {page.rect.height} puntos")
    print()

    # Obtener dimensiones
    width = page.rect.width
    height = page.rect.height

    # Definir tamaño de los rectángulos de prueba
    rect_size = 50

    # Definir posiciones de prueba en coordenadas del PDF ORIGINAL (sin rotar)
    # Estas son las coordenadas que debería enviar el frontend después de la transformación
    test_positions = {
        "Esquina Superior Izquierda": [10, 10, 10 + rect_size, 10 + rect_size],
        "Esquina Superior Derecha": [width - rect_size - 10, 10, width - 10, 10 + rect_size],
        "Esquina Inferior Izquierda": [10, height - rect_size - 10, 10 + rect_size, height - 10],
        "Esquina Inferior Derecha": [width - rect_size - 10, height - rect_size - 10, width - 10, height - 10],
        "Centro": [width/2 - rect_size/2, height/2 - rect_size/2, width/2 + rect_size/2, height/2 + rect_size/2]
    }

    # Colores para cada posición
    colors = {
        "Esquina Superior Izquierda": (1, 0, 0),      # Rojo
        "Esquina Superior Derecha": (0, 1, 0),        # Verde
        "Esquina Inferior Izquierda": (0, 0, 1),      # Azul
        "Esquina Inferior Derecha": (1, 1, 0),        # Amarillo
        "Centro": (1, 0, 1)                           # Magenta
    }

    print("Dibujando rectángulos de prueba en coordenadas del PDF original...")
    print("(Estas son las coordenadas que debería enviar el frontend)\n")

    for label, bbox in test_positions.items():
        color = colors[label]
        rect = fitz.Rect(bbox)

        # Usar page.new_shape() para overlay no destructivo
        shape = page.new_shape()
        shape.draw_rect(rect)
        shape.finish(fill=color, color=color, width=0)
        shape.commit()

        print(f"{label}:")
        print(f"  BBox: {bbox}")
        print(f"  Color: {color}")
        print()

    # Guardar resultado
    output_path = Path(pdf_path).parent / f"{Path(pdf_path).stem}_ubicacion_test.pdf"
    doc.save(str(output_path))
    doc.close()

    print(f"{'='*70}")
    print(f"PDF guardado: {output_path}")
    print(f"{'='*70}\n")
    print("VERIFICA QUE LOS RECTÁNGULOS APAREZCAN EN:")
    print("  - ROJO:     Esquina superior izquierda del documento VISUAL")
    print("  - VERDE:    Esquina superior derecha del documento VISUAL")
    print("  - AZUL:     Esquina inferior izquierda del documento VISUAL")
    print("  - AMARILLO: Esquina inferior derecha del documento VISUAL")
    print("  - MAGENTA:  Centro del documento VISUAL")
    print()
    print("Si los rectángulos NO aparecen en estas posiciones visuales,")
    print("significa que hay un problema con las coordenadas del PDF original.")
    print()
    print("NOTA IMPORTANTE:")
    print("Si el PDF tiene rotación, PDF.js muestra el documento rotado,")
    print("pero las coordenadas del PDF original se refieren al documento SIN rotar.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python test_ubicacion.py <ruta_pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not Path(pdf_path).exists():
        print(f"Error: No se encuentra el archivo {pdf_path}")
        sys.exit(1)

    test_ubicacion(pdf_path)
