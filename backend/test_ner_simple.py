#!/usr/bin/env python3
"""Test simple de NER con spaCy"""
import spacy

# Cargar modelo
nlp = spacy.load("es_core_news_sm")

# Texto de prueba del PDF de alegaciones
texto_alegaciones = """
D. ELIAS LOPEZ DE LA PEDRAJA, con DNI núm. 13920075S, con domicilio a
efectos de notificaciones en [DIRECCIÓN COMPLETA], teléfono [TELÉFONO] y
correo electrónico [EMAIL],
EXPONE:
"""

texto_firma = """
Fdo.: D. Elias López de la Pedraja
"""

print("=" * 80)
print("PRUEBA 1: Texto de encabezado")
print("=" * 80)
print(f"Texto: {texto_alegaciones}")
print()

doc = nlp(texto_alegaciones)
print(f"Entidades detectadas por spaCy:")
for ent in doc.ents:
    print(f"  - '{ent.text}' [{ent.label_}] en posición {ent.start_char}-{ent.end_char}")

print("\n" + "=" * 80)
print("PRUEBA 2: Texto de firma")
print("=" * 80)
print(f"Texto: {texto_firma}")
print()

doc2 = nlp(texto_firma)
print(f"Entidades detectadas por spaCy:")
for ent in doc2.ents:
    print(f"  - '{ent.text}' [{ent.label_}] en posición {ent.start_char}-{ent.end_char}")

# Prueba con texto variado
print("\n" + "=" * 80)
print("PRUEBA 3: Variaciones del nombre")
print("=" * 80)

variaciones = [
    "ELIAS LOPEZ DE LA PEDRAJA",
    "Elias López de la Pedraja",
    "D. Elias López de la Pedraja",
    "Elias Lopez",
    "Sr. Juan García Pérez",
    "DNI 13920075S",
]

for var in variaciones:
    doc = nlp(var)
    print(f"\nTexto: '{var}'")
    if doc.ents:
        for ent in doc.ents:
            print(f"  ✓ Detectado: '{ent.text}' [{ent.label_}]")
    else:
        print(f"  ✗ NO detectado")
