#!/usr/bin/env python3
"""
Test para verificar cómo PyMuPDF maneja coordenadas con páginas rotadas
"""

import fitz
import sys
from pathlib import Path

def test_rotation_coords(pdf_path):
    """Prueba cómo PyMuPDF interpreta coordenadas en páginas rotadas"""
    print(f"\n{'='*70}")
    print(f"Test de coordenadas con rotación en PyMuPDF")
    print(f"{'='*70}\n")

    doc = fitz.open(pdf_path)
    page = doc[0]

    # Información de la página
    print(f"page.rotation: {page.rotation}°")
    print(f"page.rect: {page.rect}")
    print(f"page.mediabox: {page.mediabox}")
    print()

    # Si la página tiene rotación 90°, las dimensiones se intercambian
    # MediaBox es SIEMPRE el PDF original (sin rotar)
    # Rect es el viewport DESPUÉS de rotar

    # Para este test, vamos a dibujar un rectángulo en la esquina superior izquierda
    # usando DIFERENTES sistemas de coordenadas

    mediabox_width = page.mediabox.width
    mediabox_height = page.mediabox.height
    rect_width = page.rect.width
    rect_height = page.rect.height

    print(f"MediaBox (PDF original): {mediabox_width} x {mediabox_height}")
    print(f"Rect (viewport rotado): {rect_width} x {rect_height}")
    print()

    # Definir un rectángulo de prueba: esquina superior izquierda
    test_size = 100

    # Test 1: Coordenadas en sistema del MediaBox (PDF original sin rotar)
    bbox_mediabox = [10, 10, 10 + test_size, 10 + test_size]

    # Test 2: Coordenadas en sistema del Rect (viewport rotado)
    bbox_rect = [10, 10, 10 + test_size, 10 + test_size]

    print("Test 1: Usando coordenadas del MediaBox (PDF original)")
    print(f"  BBox: {bbox_mediabox}")
    rect1 = fitz.Rect(bbox_mediabox)
    shape1 = page.new_shape()
    shape1.draw_rect(rect1)
    shape1.finish(fill=(1, 0, 0), color=(1, 0, 0), width=0)  # Rojo
    shape1.commit()
    print("  Color: ROJO")
    print()

    print("Test 2: Usando coordenadas del Rect (viewport rotado)")
    print(f"  BBox: {bbox_rect}")
    print("  (En este caso es igual porque estamos en la esquina)")
    print()

    # Si hay rotación, probar transformación inversa
    if page.rotation == 90:
        # PDF.js envía coordenadas transformadas del canvas rotado al PDF original
        # PyMuPDF espera coordenadas del Rect (viewport rotado)
        # Entonces necesitamos la transformación INVERSA: PDF original → viewport rotado

        # Transformación 90° CW (PyMuPDF aplica): PDF original → Viewport rotado
        # Si PDF original tiene dimensiones (W, H) y coordenada (x, y)
        # Viewport rotado tiene dimensiones (H, W) y coordenada (y, W - x)

        # Pero nosotros recibimos coordenadas en sistema PDF original
        # y necesitamos convertir a sistema viewport rotado

        # Espera... esto es confuso. Déjame dibujar otro rectángulo para verificar

        # Rectángulo de prueba en coordenadas del viewport rotado (verde)
        # Esquina superior derecha del viewport rotado
        bbox_test = [rect_width - test_size - 10, 10, rect_width - 10, 10 + test_size]
        print(f"Test 3: Esquina superior derecha del viewport rotado")
        print(f"  BBox: {bbox_test}")
        rect3 = fitz.Rect(bbox_test)
        shape3 = page.new_shape()
        shape3.draw_rect(rect3)
        shape3.finish(fill=(0, 1, 0), color=(0, 1, 0), width=0)  # Verde
        shape3.commit()
        print("  Color: VERDE")
        print()

    # Guardar resultado
    output_path = Path(pdf_path).parent / f"{Path(pdf_path).stem}_rotation_backend_test.pdf"
    doc.save(str(output_path))
    doc.close()

    print(f"{'='*70}")
    print(f"PDF guardado: {output_path}")
    print(f"{'='*70}\n")
    print("INTERPRETACIÓN:")
    print("- ROJO: Coordenadas directas en esquina superior izquierda")
    print("- VERDE: Esquina superior derecha del viewport rotado")
    print()
    print("Si el ROJO aparece en la esquina superior izquierda VISUAL:")
    print("  → PyMuPDF usa sistema de coordenadas del VIEWPORT ROTADO")
    print()
    print("Si el ROJO aparece en otra posición:")
    print("  → PyMuPDF usa sistema de coordenadas del PDF ORIGINAL")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python test_rotation_backend.py <ruta_pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not Path(pdf_path).exists():
        print(f"Error: No se encuentra el archivo {pdf_path}")
        sys.exit(1)

    test_rotation_coords(pdf_path)
