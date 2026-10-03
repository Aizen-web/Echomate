from PIL import Image, ImageDraw
from pathlib import Path

def create_ecomate_icon():
    base_size = 256
    img = Image.new("RGBA", (base_size, base_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Background Rounded Hexagon / Shield
    # Midnight Cosmic gradient effect
    padding = 16
    r = 52
    
    # Outer glow / border
    draw.rounded_rectangle(
        [padding - 4, padding - 4, base_size - padding + 4, base_size - padding + 4],
        radius=r + 4,
        fill=(98, 116, 224, 90)
    )
    draw.rounded_rectangle(
        [padding - 2, padding - 2, base_size - padding + 2, base_size - padding + 2],
        radius=r + 2,
        fill=(124, 143, 255, 140)
    )
    # Background fill: deep obsidian/midnight blue
    draw.rounded_rectangle(
        [padding, padding, base_size - padding, base_size - padding],
        radius=r,
        fill=(10, 14, 34, 250),
        outline=(124, 143, 255, 200),
        width=3
    )

    # 2. Glowing inner aura
    draw.ellipse(
        [60, 60, base_size - 60, base_size - 60],
        fill=(76, 217, 138, 45)
    )

    # 3. Botanical Companion Leaf 1 (Left / Main Leaf)
    # Vibrant Emerald to Sakura gradient motif
    leaf_pts = [
        (128, 52),
        (190, 88),
        (205, 148),
        (175, 196),
        (128, 210),
        (85, 196),
        (55, 148),
        (68, 88),
    ]
    draw.polygon(leaf_pts, fill=(46, 196, 120, 245))

    # Inner leaf highlight
    inner_leaf = [
        (128, 68),
        (175, 100),
        (185, 145),
        (160, 185),
        (128, 195),
        (96, 185),
        (72, 145),
        (82, 100),
    ]
    draw.polygon(inner_leaf, fill=(76, 217, 138, 255))

    # Central Stem / Spine
    draw.line([(128, 70), (128, 215)], fill=(240, 255, 245, 230), width=5)
    # Leaf veins
    draw.line([(128, 110), (160, 95)], fill=(240, 255, 245, 190), width=4)
    draw.line([(128, 135), (96, 120)], fill=(240, 255, 245, 190), width=4)
    draw.line([(128, 160), (155, 148)], fill=(240, 255, 245, 190), width=4)
    draw.line([(128, 180), (105, 172)], fill=(240, 255, 245, 190), width=4)

    # 4. Sprout / Water Droplet Accent on top right
    drop_pts = [
        (178, 48),
        (194, 66),
        (192, 82),
        (178, 90),
        (164, 82),
        (162, 66),
    ]
    draw.polygon(drop_pts, fill=(124, 210, 255, 240))
    draw.ellipse([168, 60, 184, 76], fill=(220, 245, 255, 255))

    # Output paths
    calcifer_dir = Path(__file__).resolve().parent
    ico_path = calcifer_dir / "ecomate.ico"
    web_ico_path = calcifer_dir / "web" / "ecomate.ico"

    # Multi-resolution ICO
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(ico_path, format="ICO", sizes=sizes)
    img.save(web_ico_path, format="ICO", sizes=sizes)
    print(f"Generated {ico_path} and {web_ico_path} successfully with sizes: {sizes}")

if __name__ == "__main__":
    create_ecomate_icon()
