from PIL import Image
import sys

def resize_proportionately(input_path, output_base):
    img = Image.open(input_path)
    
    # Save the original as logo.png
    main_path = output_base + ".png"
    img.save(main_path)
    print(f"Saved {main_path}")
    
    # Resize to 256x256 (proportionately)
    img_256 = img.copy()
    img_256.thumbnail((256, 256), Image.Resampling.LANCZOS)
    # If the user wants it to be exactly a square, maybe crop? Or thumbnail keeps proportions.
    path_256 = output_base + "_256.png"
    img_256.save(path_256)
    print(f"Saved {path_256}")
    
    # Resize to 32x32 for favicon
    img_favicon = img.copy()
    img_favicon.thumbnail((32, 32), Image.Resampling.LANCZOS)
    path_favicon = output_base + "_favicon.png"
    img_favicon.save(path_favicon)
    print(f"Saved {path_favicon}")

if __name__ == "__main__":
    resize_proportionately(sys.argv[1], sys.argv[2])
