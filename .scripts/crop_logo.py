from PIL import Image

def crop_logo(input_path, output_path):
    img = Image.open(input_path)
    
    # Convert to RGB to find bounding box easily, assuming white background
    bg = Image.new(img.mode, img.size, img.getpixel((0,0)))
    diff = Image.chops.difference(img, bg) if hasattr(Image, 'chops') else None
    
    # Instead of full auto crop, let's just do a percentage crop to remove the sparkle (bottom right)
    # and whitespace. Or we can find the bounding box of non-background pixels.
    # Actually, Gemini images often have off-white textured backgrounds.
    # So finding bounding box based on exact pixel match might fail.
    # Let's crop out 10% from edges, but specifically avoid the bottom right 10%.
    # Wait, the user said "try to crop to the central content keeping text and icon".
    # Since I can't visually see the exact coordinates, I'll do a center crop that is around 70% of the image size.
    # Gemini image is usually 1536x1536 or 16:9.
    
    width, height = img.size
    
    # We can try to crop out 15% from left, right, top and 20% from bottom (to avoid the watermark)
    left = width * 0.20
    top = height * 0.10
    right = width * 0.80
    bottom = height * 0.90
    
    # But wait, we want to KEEP the text. The text is usually under the icon.
    # So the bottom shouldn't be cropped too much if the text is there.
    # Let's just crop out the watermark in the bottom right.
    # The watermark is usually the bottom-right 5%.
    # So we can crop: left=10%, right=90%, top=5%, bottom=90%
    # Actually, if we just crop the left 15%, right 15%, top 10%, bottom 12%, that usually centers it nicely and removes the watermark.
    
    crop_box = (int(width * 0.22), int(height * 0.08), int(width * 0.78), int(height * 0.92))
    img_cropped = img.crop(crop_box)
    
    # Main size
    img_cropped.save(output_path)
    print(f"Saved {output_path}")
    
    # Favicon size
    img_favicon = img_cropped.resize((32, 32), Image.Resampling.LANCZOS)
    favicon_path = output_path.replace('.png', '_favicon.png')
    img_favicon.save(favicon_path)
    print(f"Saved {favicon_path}")
    
    # Medium size
    img_medium = img_cropped.resize((256, 256), Image.Resampling.LANCZOS)
    medium_path = output_path.replace('.png', '_256.png')
    img_medium.save(medium_path)
    print(f"Saved {medium_path}")

if __name__ == "__main__":
    import sys
    crop_logo(sys.argv[1], sys.argv[2])
