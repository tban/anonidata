
import fitz
import sys

def test_matrix_logic():
    print("Testing Matrix Logic...")
    doc = fitz.open("test_rotated.pdf")
    page = doc[0]
    
    # 1. Page Info
    # Rotation: 90
    # Rect (Visual): (0,0, 842, 595)
    # MediaBox (UserSpace): (0,0, 595, 842) usually
    
    print(f"Rotation: {page.rotation}")
    print(f"Visual Rect: {page.rect}")
    
    # 2. Define a Visual Box (e.g. at Visual Top-Left (10,10))
    # If we want to draw at Visual (10,10), we need UserSpace coords.
    visual_point = fitz.Point(10, 10)
    
    # 3. Create Derotation Matrix
    # page.rotation_matrix maps UserSpace -> Visual ?
    # Let's check docs: "The transformation matrix... from user space to device space"
    # Actually rotation is User -> Display.
    # So we want Inverse: Display -> User.
    
    # fitz.Matrix(alpha) rotates by alpha degrees.
    # If we rotate by -90, does it cancel?
    
    # Try derotation
    mat = page.derotation_matrix
    print(f"Derotation Matrix: {mat}")
    
    userspace_point = visual_point * mat
    print(f"Visual (10,10) -> UserSpace {userspace_point}")
    
    # 4. Draw using UserSpace Point
    shape = page.new_shape()
    shape.draw_circle(userspace_point, 5) # Blue circle at Visual 10,10
    shape.finish(color=(0,0,1), fill=(0,0,1))
    
    # 5. Test Header Position: Visual Top-Right
    # Visual Top-Right is (W_vis, 0)
    vis_tr = fitz.Point(page.rect.width - 50, 50)
    us_tr = vis_tr * mat
    print(f"Visual TR {vis_tr} -> UserSpace {us_tr}")
    
    page.insert_text(us_tr, "Header Matrix", color=(0,0,1), fontsize=20, rotate=-90) 
    # Try rotate=-90 (270) to make it horizontal?
    
    shape.commit()
    
    out = "test_matrix.pdf"
    doc.save(out)
    print(f"Saved {out}")

if __name__ == "__main__":
    test_matrix_logic()
