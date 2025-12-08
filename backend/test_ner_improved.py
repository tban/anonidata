#!/usr/bin/env python3
"""Test de la detección NER mejorada con entidades MISC/ORG"""
import spacy

# Cargar modelo
nlp = spacy.load("es_core_news_sm")

# Texto de prueba del PDF de alegaciones
texto_completo = """
D. ELIAS LOPEZ DE LA PEDRAJA, con DNI núm. 13920075S, con domicilio a
efectos de notificaciones en Calle Principal 123, teléfono 666123456 y
correo electrónico email@example.com, EXPONE:
"""

texto_firma = "Fdo.: D. Elias López de la Pedraja"

print("=" * 80)
print("PRUEBA DE DETECCIÓN NER MEJORADA")
print("=" * 80)

# Analizar texto
doc = nlp(texto_completo)
print(f"\nTexto: {texto_completo}\n")
print("Entidades detectadas por spaCy:")
for ent in doc.ents:
    print(f"  - '{ent.text}' [{ent.label_}] en posición {ent.start_char}-{ent.end_char}")

# Simular la lógica del código mejorado
print("\n" + "=" * 80)
print("LÓGICA MEJORADA DE FILTRADO")
print("=" * 80)

org_keywords = ['servicio', 'ministerio', 'dirección', 'consejería', 'departamento',
               'hospital', 'ayuntamiento', 'junta', 'gobierno', 'cabildo']

for ent in doc.ents:
    is_potential_name = False

    if ent.label_ == "PER":
        is_potential_name = True
        print(f"\n✓ '{ent.text}' detectado como PER")

    elif ent.label_ in ["MISC", "ORG"]:
        words = ent.text.split()
        has_org_keyword = any(kw in ent.text.lower() for kw in org_keywords)

        if not has_org_keyword and len(words) >= 2:
            capitalized_words = [w for w in words if w and (w[0].isupper() or w.isupper())]
            if len(capitalized_words) >= 2:
                is_potential_name = True
                print(f"\n✓ '{ent.text}' [{ent.label_}] clasificado como NOMBRE potencial")
                print(f"  - Palabras capitalizadas: {capitalized_words}")
            else:
                print(f"\n✗ '{ent.text}' [{ent.label_}] NO clasificado (solo {len(capitalized_words)} palabra(s) capitalizada(s))")
        elif has_org_keyword:
            print(f"\n✗ '{ent.text}' [{ent.label_}] filtrado (contiene palabra de organización)")
        else:
            print(f"\n✗ '{ent.text}' [{ent.label_}] filtrado (solo {len(words)} palabra(s))")

print("\n" + "=" * 80)
print("PRUEBA CON FIRMA")
print("=" * 80)
print(f"\nTexto: {texto_firma}\n")

doc2 = nlp(texto_firma)
print("Entidades detectadas:")
for ent in doc2.ents:
    print(f"  - '{ent.text}' [{ent.label_}]")
