#!/usr/bin/env python3
"""Extraer y mostrar el texto del PDF para entender su estructura"""
import fitz  # PyMuPDF
import sys

def show_pdf_text(pdf_path: str):
    """Mostrar el texto extraído del PDF"""
    print(f"\n{'=' * 80}")
    print(f"TEXTO EXTRAÍDO DE: {pdf_path}")
    print(f"{'=' * 80}\n")

    doc = fitz.open(pdf_path)

    for page_num in range(min(2, len(doc))):  # Solo primeras 2 páginas
        page = doc[page_num]
        print(f"\n--- PÁGINA {page_num + 1} ---\n")

        # Método 1: Texto completo
        text = page.get_text()
        print("TEXTO COMPLETO (get_text()):")
        print(text[:2000])  # Primeros 2000 caracteres
        print("\n" + "-" * 80 + "\n")

        # Método 2: Bloques de texto
        blocks = page.get_text("dict")["blocks"]
        print(f"BLOQUES DE TEXTO ({len(blocks)} bloques):")

        text_blocks = [b for b in blocks if "lines" in b]
        for i, block in enumerate(text_blocks[:10]):  # Primeros 10 bloques
            for line in block["lines"]:
                line_text = " ".join([span["text"] for span in line["spans"]])
                print(f"  Bloque {i}: '{line_text}'")

    doc.close()

if __name__ == "__main__":
    # Test con el PDF problemático
    show_pdf_text("test/pdfs/ALEGACIONES_NO_SOLICITO_PLAZA.pdf")
