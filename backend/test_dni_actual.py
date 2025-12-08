#!/usr/bin/env python3
"""Test del regex DNI con el texto real del PDF"""
import re

# El texto real del PDF
text = "D. ELIAS LOPEZ DE LA PEDRAJA , con DNI núm.   13920075S , con domicilio a "

print("=" * 80)
print("TEST DE REGEX DNI CON TEXTO REAL DEL PDF")
print("=" * 80)
print(f"\nTexto: '{text}'")

# El patrón mejorado
pattern = re.compile(r'((?:DNI|NIF)(?:\s*:)?\s*(?:n[úu]m\.?|n\.?[oº]\.?)?\s*)(\d{8}[A-Za-z])\b', re.IGNORECASE)

print(f"\nPatrón: {pattern.pattern}")

# Buscar coincidencias
matches = pattern.finditer(text)

print("\nCoincidencias encontradas:")
found = False
for match in matches:
    found = True
    print(f"  - Match completo: '{match.group(0)}'")
    print(f"    Prefijo: '{match.group(1)}'")
    print(f"    DNI: '{match.group(2)}'")
    print(f"    Posición: {match.start()}-{match.end()}")

if not found:
    print("  ❌ NO SE ENCONTRÓ NINGUNA COINCIDENCIA")

    # Intentar identificar el problema
    print("\n" + "=" * 80)
    print("ANÁLISIS DEL PROBLEMA")
    print("=" * 80)

    # Buscar el texto "DNI" para ver qué hay alrededor
    dni_pos = text.find("DNI")
    if dni_pos >= 0:
        print(f"\nEncontré 'DNI' en posición {dni_pos}")
        context = text[dni_pos:dni_pos+30]
        print(f"Contexto: '{context}'")

        # Mostrar los caracteres uno por uno
        print("\nCaracteres individuales:")
        for i, char in enumerate(context):
            print(f"  [{i}] '{char}' (ord={ord(char)})")

        # Probar regex más simple
        print("\nProbando regex más simple:")
        simple_pattern = re.compile(r'DNI.*?(\d{8}[A-Za-z])', re.IGNORECASE)
        simple_match = simple_pattern.search(text)
        if simple_match:
            print(f"  ✓ Match simple: '{simple_match.group(0)}'")
            print(f"    DNI: '{simple_match.group(1)}'")
        else:
            print("  ❌ Ni siquiera el regex simple funcionó")
else:
    print("  ✓ Regex funcionó correctamente!")
