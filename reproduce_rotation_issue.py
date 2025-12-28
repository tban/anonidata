
import fitz
import sys
import os

def debug_pdf_rotation(input_path):
    print(f"Opening {input_path}")
    doc = fitz.open(input_path)
    page = doc[0]
    
    print(f"Page Rotation: {page.rotation}")
    print(f"Page Rect: {page.rect}")
    print(f"Page MediaBox: {page.mediabox}")
    
    # 1. Extract text and see its bbox
    text_blocks = page.get_text("blocks")
    if text_blocks:
        b = text_blocks[0]
        print(f"First text block bbox (from get_text): {b[:4]}")
        print(f"First text content: {b[4][:20]}...")
        
        # Draw a GREEN rect around what get_text thinks is the bbox
        # This will show us if draw_rect uses the same coordinate system as get_text
        shape = page.new_shape()
        shape.draw_rect(b[:4])
        shape.finish(color=(0, 1, 0), width=2) # GREEN
        shape.commit()
    
    # 2. Draw a RED rect at (10, 10, 100, 100)
    # This roughly Top-Left of the Coordinate System used by draw_rect
    shape = page.new_shape()
    shape.draw_rect(fitz.Rect(10, 10, 100, 100))
    shape.finish(color=(1, 0, 0), fill=(1, 0, 0)) # RED
    shape.commit()

    # Output
    out_name = input_path.replace(".pdf", "_repro_coords.pdf")
    doc.save(out_name)
    print(f"Saved debug PDF to {out_name}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        debug_pdf_rotation(sys.argv[1])
    else:
        # scan for a pdf if none provided
        pdf_files = [f for f in os.listdir('.') if f.endswith('.pdf') and not 'anonymized' in f and not 'debug' in f]
        if pdf_files:
            debug_pdf_rotation(pdf_files[0])
        else:
            print("No PDF found to test")
