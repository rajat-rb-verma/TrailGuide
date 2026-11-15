"""Generate the local demo catalog's product illustrations with Pillow."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from .catalog import seed_products

PALETTE = {"black": "#394149", "navy": "#304a73", "olive": "#748052",
           "orange": "#d57547", "grey": "#889294"}


def illustrate(item):
    color = PALETTE[item["color"]]
    name = item["name"].lower()
    family = item["category"]
    model_index = (item["id"] - 1) // 5
    line = model_index % 4
    accent = ("#e3b96d", "#e9e4d4", "#b9c794", "#eea379")[line]
    outline = "#23362d"
    image = Image.new("RGB", (480, 320), ("#e9eddf", "#e7eae8", "#e5ebdd", "#f0e6d9", "#e6e8e4")[(item["id"] - 1) % 5])
    draw = ImageDraw.Draw(image)
    # Model-specific background and pattern make neighboring product cards easier to distinguish.
    pattern = ("#fbf7e4", "#dae8ed", "#f3e0cb", "#e5e2f1")[line]
    draw.ellipse((145, 20, 335, 210), fill=pattern)
    radius = 97 + (model_index % 3) * 8
    draw.arc((240 - radius, 15, 240 + radius, 220), 190, 345, fill=accent, width=4)
    shade = Image.new("RGBA", image.size)
    ImageDraw.Draw(shade).ellipse((110, 246, 370, 275), fill=(28, 48, 40, 55))
    image.paste(shade, (0, 0), shade.filter(ImageFilter.GaussianBlur(10)))
    draw = ImageDraw.Draw(image)

    def box(coords, radius=12, fill=color):
        draw.rounded_rectangle(coords, radius, fill=fill, outline=outline, width=3)

    if family == "hiking footwear":
        high = 83 if "boots" in name else 125
        points = [(109, 232), (119, 176), (152, high), (225, high + 4), (241, 154),
                  (289, 190), (356, 201), (377, 225), (371, 244), (118, 244)]
        draw.polygon(points, fill=color, outline=outline, width=4)
        box((107, 230, 378, 254), 9, outline)
        draw.line((156, 209, 207, 180, 255, 207, 329, 219), fill=accent, width=9)
        for x in range(222, 279, 13):
            draw.line((x - 16, 163 + (x - 222) // 2, x + 7, 159 + (x - 222) // 2), fill="#f0eee0", width=4)
    elif family == "trekking poles":
        for x, y in ((172, 49), (233, 65)):
            draw.line((x, y + 28, x + 71, y + 193), fill=outline, width=13)
            draw.line((x + 38, y + 112, x + 71, y + 193), fill=accent, width=7)
            box((x - 8, y, x + 16, y + 57), 8)
            draw.arc((x - 37, y - 9, x + 17, y + 44), 65, 275, fill=outline, width=5)
            draw.line((x + 52, y + 175, x + 83, y + 164), fill=outline, width=5)
    elif family == "backpacks" or "hydration pack" in name:
        top = 71 - line * 5
        box((217, top - 16, 266, top + 17), 12, outline)
        box((155, top, 325, 253), 35)
        box((169, 164, 311, 237), 19, accent)
        draw.line((181, 180, 299, 180), fill=outline, width=4)
        draw.line((176, 120, 308, 120), fill=outline, width=5)
        box((220, 134, 259, 153), 6, "#f2eee0")
    elif family == "hydration":
        width = (102, 86, 76, 92)[line]
        left = 240 - width // 2
        box((left, 100, left + width, 255), 26)
        box((left + 12, 75, left + width - 12, 110), 8, outline)
        box((left + 7, 163, left + width - 7, 197), 8, accent)
    elif "tent" in name:
        draw.polygon([(91, 242), (203, 84), (352, 110), (404, 243)], fill=color, outline=outline, width=4)
        draw.polygon([(94, 242), (203, 84), (294, 242)], fill=accent, outline=outline, width=4)
        draw.polygon([(155, 241), (204, 157), (248, 241)], fill=outline)
    elif "sleeping bag" in name or "mat" in name or "roller" in name:
        box((126, 133, 347, 233), 45 if "mat" not in name else 19)
        draw.ellipse((285, 134, 354, 231), fill=accent, outline=outline, width=3)
        for x in (160, 197, 234, 271):
            draw.arc((x, 134, x + 43, 232), 80, 280, fill=outline, width=4)
    elif "headlamp" in name or "lantern" in name:
        draw.arc((153, 65, 325, 220), 170, 365, fill=outline, width=12)
        box((156, 132, 324, 237), 28)
        box((180, 153, 301, 208), 19, accent)
        draw.ellipse((214, 165, 263, 197), fill="#fff6cb", outline=outline, width=3)
    elif "bands" in name:
        for i in range(3):
            draw.ellipse((122 + i * 28, 90 + i * 18, 297 + i * 28, 214 + i * 18),
                         outline=(outline, accent, color)[i], width=15)
    else:
        box((149, 202, 332, 247), 18, outline)
        box((187, 122, 293, 231), 37)
        draw.line((240, 169, 320, 139), fill=outline, width=10)
        box((298, 125, 351, 150), 7, accent)
    draw.rectangle((0, 271, 480, 320), fill="#f9f8f0")
    draw.text((16, 276), item["name"], fill=outline, font_size=17)
    draw.text((16, 300), f'{item["color"].upper()}  ·  {item["brand"]}  ·  {item["sku"]}', fill=outline, font_size=12)
    return image


def main():
    folder = Path(__file__).resolve().parents[1] / "static" / "products"
    folder.mkdir(parents=True, exist_ok=True)
    for item in seed_products():
        illustrate(item).save(folder / f"{item['id']:03d}.png", optimize=True)


if __name__ == "__main__":
    main()
