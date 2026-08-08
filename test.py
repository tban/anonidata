import os
import sys
import json

sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from core.config import Settings
from core.processor import PDFProcessor

def test_file():
    test_path = "/Users/tban/Library/CloudStorage/Box-Box/ACCESO PUBLICO/plantilla_prueba_datos_personales_v2.pdf"
    
    if not os.path.exists(test_path):
        print(f"File not found: {test_path}")
        return
        
    print(f"Testing {test_path}...")
    settings = Settings()
    processor = PDFProcessor(settings=settings)
    
    # process_file returns (anonymized_pdf_path, matches, has_large_images)
    try:
        result = processor.process_file(test_path)
        stats = result.get("stats", {})
        print(f"\n--- TEST RESULTS ---")
        print(f"Total Detections: {sum(stats.values())}")
        
        for type_name, count in stats.items():
            print(f"- {type_name}: {count}")
            
    except Exception as e:
        print(f"Error processing file: {e}")

if __name__ == "__main__":
    test_file()
