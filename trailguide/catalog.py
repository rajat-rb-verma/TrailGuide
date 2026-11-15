"""Seed catalog for the fictional INR store."""
from itertools import product

from .specs import SPECS

COLORS = ("black", "navy", "olive", "orange", "grey")
LINES = {
    "hiking footwear": [
        ("Waterproof hiking boots", 4200, ("waterproof", "ankle support")),
        ("Lightweight trail shoes", 2900, ("lightweight", "breathable", "beginner")),
        ("Grip hiking boots", 3600, ("extra grip", "ankle support")),
        ("Cushioned walking shoes", 2500, ("cushioned", "lightweight")),
    ],
    "trekking poles": [
        ("Carbon trekking poles", 4199, ("carbon", "lightweight")),
        ("Folding carbon poles", 3299, ("carbon", "foldable")),
        ("Aluminum trekking poles", 1799, ("aluminum", "beginner", "adjustable")),
        ("Shock-absorbing walking poles", 2599, ("aluminum", "shock absorbing", "adjustable")),
    ],
    "backpacks": [
        ("Lightweight 18 L daypack", 1499, ("lightweight", "18 l")),
        ("Waterproof 25 L daypack", 2699, ("waterproof", "25 l")),
        ("Ventilated 30 L trail pack", 3299, ("breathable", "30 l")),
        ("40 L camping backpack", 4499, ("40 l", "extra padding")),
    ],
    "camping gear": [
        ("Rechargeable headlamp", 999, ("rechargeable", "lightweight")),
        ("Compact camping lantern", 1399, ("rechargeable", "beginner")),
        ("Two-person waterproof tent", 4399, ("waterproof", "two person")),
        ("Insulated sleeping bag", 2399, ("insulated", "beginner")),
    ],
    "hydration": [
        ("Insulated 750 ml bottle", 1099, ("insulated", "750 ml")),
        ("Lightweight 1 L bottle", 649, ("lightweight", "1 l")),
        ("Leakproof 500 ml bottle", 549, ("leakproof", "500 ml")),
        ("2 L hydration pack", 2199, ("2 l", "lightweight")),
    ],
    "home fitness": [
        ("Beginner resistance band set", 849, ("beginner", "low impact")),
        ("Cushioned exercise mat", 1199, ("cushioned", "low impact")),
        ("Textured foam roller", 949, ("textured", "recovery")),
        ("Compact pedal exerciser", 3699, ("low impact", "compact")),
    ],
}


EXTRA_LINES = {
    "hiking footwear": [
        ("Rain Ridge mid boots", 3475, ("waterproof", "ankle support", "extra grip")),
        ("Brookstep waterproof trail shoes", 3175, ("waterproof", "lightweight", "cushioned")),
    ],
    "trekking poles": [
        ("Trailbrace aluminum poles", 2090, ("aluminum", "adjustable", "shock absorbing")),
        ("Skyfold carbon poles", 3690, ("carbon", "foldable", "lightweight")),
    ],
    "backpacks": [
        ("Rainline 22 L daypack", 2340, ("waterproof", "22 l", "lightweight")),
        ("Canyon 35 L overnight pack", 3990, ("35 l", "extra padding")),
    ],
    "camping gear": [
        ("Solo shelter tent", 3390, ("waterproof", "one person", "lightweight")),
        ("Trailbeam clip lantern", 1170, ("rechargeable", "compact")),
    ],
    "hydration": [
        ("Thermo Trail 1 L bottle", 1390, ("insulated", "1 l", "leakproof")),
        ("Mist 600 ml squeeze bottle", 520, ("lightweight", "600 ml", "leakproof")),
    ],
    "home fitness": [
        ("Softstep folding exercise mat", 1580, ("cushioned", "low impact", "foldable")),
        ("Flex Loop fabric band set", 990, ("beginner", "low impact", "latex free")),
    ],
}


def seed_products():
    index = 0
    for category, lines in (*LINES.items(), *EXTRA_LINES.items()):
        for (name, price, features), (shade, color) in product(lines, enumerate(COLORS)):
            index += 1
            sizes = [size for size in range(6, 12) if (size + shade) % 5]
            brand, weight, material, warranty, specification, use_case = SPECS[name]
            yield {
                "id": index, "category": category, "name": name, "color": color,
                "price": price + shade * 100, "features": features,
                "sizes": sizes if category == "hiking footwear" else [],
                "stock": 0 if shade == 4 else 3 + index % 11,
                "sku": f"TG-{index:03d}", "brand": brand, "weight_g": weight,
                "material": material, "warranty": warranty, "specification": specification,
                "use_case": use_case, "returns": "30 days for unused items",
                "image": f"/static/products/{index:03d}.png",
                "regions": ["north", "west", "south", "east"] if shade < 3 else ["north", "west"],
                "delivery_days": 2 + shade,
                "review": f"Liked the {features[0]} design on my first use.",
            }