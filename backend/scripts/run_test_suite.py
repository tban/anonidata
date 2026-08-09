import sys
import json
import datetime
from pathlib import Path

backend_path = Path("/Users/tban/Documents/Desarrollos/anonidata/backend")
sys.path.insert(0, str(backend_path))

from core.config import Settings
from core.processor import PDFProcessor
from processors.ocr_engine import OCREngine
import fitz

def get_pdf_metadata(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        return doc.metadata
    except Exception as e:
        return str(e)

def main():
    test_files = {
        "v1": {
            "path": Path("/Users/tban/Library/CloudStorage/GoogleDrive-tbanrguez@gmail.com/Mi unidad/PUBLICAPPS/ANONIDATA/TEST/plantilla_prueba_datos_personales_v1.pdf"),
            "expected_total": 56
        },
        "v2": {
            "path": Path("/Users/tban/Library/CloudStorage/GoogleDrive-tbanrguez@gmail.com/Mi unidad/PUBLICAPPS/ANONIDATA/TEST/plantilla_prueba_datos_personales_v2.pdf"),
            "expected_total": 94
        },
        "v3": {
            "path": Path("/Users/tban/Library/CloudStorage/GoogleDrive-tbanrguez@gmail.com/Mi unidad/PUBLICAPPS/ANONIDATA/TEST/plantilla_prueba_datos_personales_v3.pdf"),
            "expected_total": 134
        }
    }
    
    expected_grand_total = 284
    
    history_file = Path("/Users/tban/Documents/Desarrollos/anonidata/.agents/test_history.json")
    
    with open("/Users/tban/Documents/Desarrollos/anonidata/package.json", "r") as f:
        pkg = json.load(f)
        current_version = pkg.get("version", "unknown")
        
    settings = Settings()
    processor = PDFProcessor(settings)
    ocr_engine = OCREngine(settings)
    
    total_detections_all = 0
    results_by_template = {}
    
    for template_key, data in test_files.items():
        pdf_path = data["path"]
        if not pdf_path.exists():
            print(f"Error: {pdf_path} not found")
            sys.exit(1)
            
        print(f"Processing {pdf_path.name}...")
        
        # Simulate user accepting OCR conversion for v2
        if template_key == "v2":
            print(f"Generating searchable PDF for {pdf_path.name}...")
            pdf_path_to_process = Path(ocr_engine.create_searchable_pdf(str(pdf_path)))
        else:
            pdf_path_to_process = pdf_path
            
        result = processor.process_file(str(pdf_path_to_process))
        
        if result["status"] == "error":
            print(f"Error processing {pdf_path_to_process.name}: {result.get('error')}")
            sys.exit(1)
            
        breakdown = result["stats"]
        total = sum(breakdown.values())
        total_detections_all += total
        
        # Verify metadata of the generated anonymized file
        anon_path = pdf_path_to_process.parent / f"{pdf_path_to_process.stem}_anonimizado.pdf"
        metadata = get_pdf_metadata(anon_path)
        
        results_by_template[template_key] = {
            "file": pdf_path_to_process.name,
            "total_detections": total,
            "expected_total": data["expected_total"],
            "accuracy_percent": round((total / data["expected_total"]) * 100, 2) if data["expected_total"] > 0 else 0,
            "breakdown": breakdown,
            "metadata": metadata
        }
    
    overall_accuracy = round((total_detections_all / expected_grand_total) * 100, 2)
    
    history_entry = {
        "date": datetime.datetime.now().isoformat(),
        "version": current_version,
        "overall_accuracy_percent": overall_accuracy,
        "total_detections": total_detections_all,
        "expected_grand_total": expected_grand_total,
        "templates": results_by_template
    }
    
    if history_file.exists():
        with open(history_file, "r") as f:
            history = json.load(f)
    else:
        history = {"history": []}
        
    prev_entry = history["history"][-1] if history["history"] else None
    
    history["history"].append(history_entry)
    
    with open(history_file, "w") as f:
        json.dump(history, f, indent=4)
        
    print(f"---TEST_RESULTS---")
    print(json.dumps({
        "current": history_entry,
        "previous": prev_entry
    }))

if __name__ == "__main__":
    main()
