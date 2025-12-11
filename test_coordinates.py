#!/usr/bin/env python3
"""
Script para diagnosticar problemas de coordenadas en PDFs con imágenes
"""

import fitz
from pathlib import Path
import sys

def test_coordinates(pdf_path):
    """Analiza las coordenadas de un PDF"""
    print(f"\n{'='*60}")
    print(f"Analizando: {pdf_path}")
    print(f"{'='*60}\n")

    doc = fitz.open(pdf_path)
    page = doc[0]

    # Información de la página
    print(f"MediaBox: {page.mediabox}")
    print(f"CropBox: {page.cropbox}")
    print(f"Rect: {page.rect}")
    print(f"Rotation: {page.rotation} grados")
    print(f"Dimensiones (width x height): {page.rect.width} x {page.rect.height} puntos")

    # Verificar si hay imágenes
    images = page.get_images(full=True)
    print(f"\nNúmero de imágenes: {len(images)}")

    if images:
        for i, img in enumerate(images):
            xref = img[0]
            try:
                img_rect = page.get_image_bbox(xref)
                print(f"\nImagen {i+1}:")
                print(f"  BBox: {img_rect}")
                print(f"  Dimensiones: {img_rect.width} x {img_rect.height}")
                print(f"  Posición: ({img_rect.x0}, {img_rect.y0})")

                # Obtener información de la imagen
                img_dict = doc.extract_image(xref)
                if img_dict:
                    print(f"  Resolución: {img_dict.get('width')} x {img_dict.get('height')} píxeles")
                    print(f"  DPI aproximado X: {img_dict.get('width') / img_rect.width * 72:.1f}")
                    print(f"  DPI aproximado Y: {img_dict.get('height') / img_rect.height * 72:.1f}")
            except Exception as e:
                print(f"  Error obteniendo info: {e}")

    # Probar dibujar un rectángulo en una posición conocida
    print(f"\n{'='*60}")
    print("Test de rectángulo")
    print(f"{'='*60}\n")

    # Rectángulo de prueba en el centro
    center_x = page.rect.width / 2
    center_y = page.rect.height / 2
    test_rect = fitz.Rect(
        center_x - 50,  # x0
        center_y - 25,  # y0
        center_x + 50,  # x1
        center_y + 25   # y1
    )

    print(f"Rectángulo de prueba (centro de página):")
    print(f"  Coordenadas: {test_rect}")
    print(f"  Centro calculado: ({center_x}, {center_y})")

    # Dibujar el rectángulo
    shape = page.new_shape()
    shape.draw_rect(test_rect)
    shape.finish(fill=(0.8, 0.8, 0.8), color=(0.8, 0.8, 0.8), width=0)
    shape.commit()

    # Guardar PDF con el rectángulo
    output_path = Path(pdf_path).parent / f"{Path(pdf_path).stem}_coordinate_test.pdf"
    doc.save(str(output_path))
    doc.close()

    print(f"\nPDF de prueba guardado en: {output_path}")
    print(f"\nVerifica que el rectángulo gris aparezca en el CENTRO de la página")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python test_coordinates.py <ruta_pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not Path(pdf_path).exists():
        print(f"Error: No se encuentra el archivo {pdf_path}")
        sys.exit(1)

    test_coordinates(pdf_path)
