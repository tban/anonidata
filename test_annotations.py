#!/usr/bin/env python3
"""
Script de prueba para verificar que las anotaciones funcionan correctamente
en PDFs con imágenes escaneadas
"""

import fitz  # PyMuPDF
from pathlib import Path

# Ruta al PDF de prueba
input_pdf = Path("test/pdfs/testpdfimagen.pdf")
output_pdf = Path("test/pdfs/testpdfimagen_con_anotaciones.pdf")

print(f"Abriendo PDF: {input_pdf}")
doc = fitz.open(input_pdf)

# Obtener primera página
page = doc[0]
print(f"Dimensiones de página: {page.rect.width} x {page.rect.height}")

# Verificar si tiene imágenes
images = page.get_images(full=True)
print(f"Número de imágenes en la página: {len(images)}")

if images:
    for i, img in enumerate(images):
        xref = img[0]
        try:
            img_rect = page.get_image_bbox(xref)
            print(f"  Imagen {i}: {img_rect}")
        except:
            print(f"  Imagen {i}: No se pudo obtener bbox")

# Añadir varias anotaciones de prueba en diferentes posiciones
print("\nAñadiendo anotaciones de cuadrado...")

# Color gris claro (igual al usado en la app)
color = (0.8, 0.8, 0.8)

# MÉTODO 1: Usar shape (dibujo directo sobre la página)
print("  Método: Usando page.new_shape() para dibujar rectángulos")

# Anotación 1: Esquina superior izquierda
rect1 = fitz.Rect(50, 50, 200, 100)
shape = page.new_shape()
shape.draw_rect(rect1)
shape.finish(fill=color, color=color, width=0)
shape.commit()
print(f"  Rectángulo 1 dibujado en {rect1}")

# Anotación 2: Centro de la página
center_x = page.rect.width / 2
center_y = page.rect.height / 2
rect2 = fitz.Rect(center_x - 75, center_y - 40, center_x + 75, center_y + 40)
shape = page.new_shape()
shape.draw_rect(rect2)
shape.finish(fill=color, color=color, width=0)
shape.commit()
print(f"  Rectángulo 2 dibujado en {rect2}")

# Anotación 3: Esquina inferior derecha
rect3 = fitz.Rect(page.rect.width - 200, page.rect.height - 100, page.rect.width - 50, page.rect.height - 50)
shape = page.new_shape()
shape.draw_rect(rect3)
shape.finish(fill=color, color=color, width=0)
shape.commit()
print(f"  Rectángulo 3 dibujado en {rect3}")

# Guardar PDF con anotaciones
print(f"\nGuardando PDF con anotaciones: {output_pdf}")
doc.save(
    str(output_pdf),
    garbage=4,
    deflate=True,
    clean=True
)
doc.close()

print("\n✓ PDF guardado exitosamente")
print(f"\nResultado: {output_pdf}")
print("\nVerifica manualmente que:")
print("  1. La imagen original se vea completa")
print("  2. Los 3 rectángulos grises estén sobre la imagen")
print("  3. Los rectángulos NO tapen completamente la imagen (solo las áreas específicas)")
