
import fitz
import sys
import os

def create_and_test_rotated_pdf():
    print("Creating rotated PDF test...")
    doc = fitz.open()
    page = doc.new_page() # Default A4 (595 x 842)
    
    # 1. Add some text content (so we have a 'bbox' to find)
    # Text in unrotated system at (50, 50)
    page.insert_text((50, 50), "Original Text (50,50)", fontsize=20)
    
    # 2. Set Rotation to 90 (Clockwise)
    # Visual Top is now Original Left
    # Visual Right is now Original Top
    page.set_rotation(90)
    
    # 3. Save as 'test_rotated.pdf'
    doc.save("test_rotated.pdf")
    doc.close()
    
    print("Saved test_rotated.pdf")
    
    # 4. Open and analyze
    doc = fitz.open("test_rotated.pdf")
    page = doc[0]
    
    print(f"Page Rotation: {page.rotation}")
    print(f"Page Rect: {page.rect}") # Should be (0,0, 842, 595)
    
    # 5. Extract text
    # expected: bbox in Unrotated coordinates? Or Rotated?
    # PyMuPDF get_text("blocks") usually returns coordinates relative to UNROTATED page.
    text_blocks = page.get_text("blocks")
    if text_blocks:
        b = text_blocks[0]
        # b[:4] bbox
        print(f"Text bbox (from get_text): {b[:4]}")
        # If it returns (50, 50, x, y) roughly, it's UNROTATED coordinates.
        
        # 6. Draw Rect using those coordinates
        shape = page.new_shape()
        shape.draw_rect(b[:4])
        shape.finish(color=(1, 0, 0), width=2) # RED
        
        # 7. Add Header at "Visual Top Right"
        # Visual Top Right of Rotated Page is (842, 0) approx
        # Let's try to calculate it based on page.rect
        tr_x = page.rect.width - 150
        tr_y = 50
        
        print(f"Attempting to draw Header at Visual ({tr_x}, {tr_y})")
        # Try 1: Direct coordinates
        page.insert_text((tr_x, tr_y), "Header (Direct)", color=(0, 0, 1), fontsize=20)
        
        # Try 2: Transformed?
        # If Direct doesn't work (appears rotated or wrong place), we'll see it.
        
        shape.commit()
    
    output_name = "test_rotated_debug.pdf"
    doc.save(output_name)
    print(f"Saved {output_name}")

if __name__ == "__main__":
    create_and_test_rotated_pdf()
