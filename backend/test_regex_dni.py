#!/usr/bin/env python3
"""Test rápido de los patrones regex de DNI/NIE"""
import re

# Patrón mejorado de DNI
dni_pattern = re.compile(r'((?:DNI|NIF)(?:\s*:)?\s*(?:n[úu]m\.?|n\.?[oº]\.?)?\s*)(\d{8}[A-Za-z])\b', re.IGNORECASE)

# Textos de prueba
test_cases = [
    "DNI 12345678A",
    "DNI: 12345678A",
    "DNI núm. 13920075S",
    "DNI nº 12345678B",
    "DNI n.º 12345678C",
    "DNI num. 12345678D",
    "NIF: 98765432Z",
    "con DNI núm. 13920075S, con domicilio",
]

print("=" * 80)
print("PRUEBA DE PATRÓN REGEX DE DNI/NIF MEJORADO")
print("=" * 80)
print(f"\nPatrón: {dni_pattern.pattern}\n")

for text in test_cases:
    matches = dni_pattern.finditer(text)
    print(f"Texto: '{text}'")
    match_found = False
    for match in matches:
        match_found = True
        full_match = match.group(0)
        label = match.group(1)
        number = match.group(2)
        print(f"  ✓ Match completo: '{full_match}'")
        print(f"    - Etiqueta: '{label}'")
        print(f"    - Número: '{number}'")
    if not match_found:
        print(f"  ✗ NO detectado")
    print()
