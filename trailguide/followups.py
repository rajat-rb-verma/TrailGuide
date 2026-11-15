"""Answer product questions with fields from the catalog."""
import re

from .model import plan_product_question

FIELDS = {
    "price": ("Price", r"price|cost|cheapest|expensive|how much|afford"),
    "weight": ("Weight", r"weigh|weight|lightest|heaviest|heavier|lighter|heavy|grams|easy to carry"),
    "material": ("Materials", r"material|made (?:of|from|with)|fabric|latex|construction|steel|plastic|nylon|aluminium"),
    "warranty": ("Warranty", r"warranty|guarantee|covered|how long .* protected"),
    "delivery": ("Delivery", r"deliver|ship|arrive|arrival|reach|fastest|(?:get|ship) (?:it )?here"),
    "stock": ("Stock", r"stock|in hand|available|inventory|left"),
    "sizes": ("UK sizes", r"size|sizing|fit my feet"),
    "color": ("Color", r"colou?r|shade|navy|olive|orange|grey|black"),
    "brand": ("Brand", r"brand|manufacturer|who makes"),
    "specification": ("Specs", r"spec|capacity|thick|long|wide|lumen|battery|runtime|how many|how bright|how cold|how warm|hold|pack down|fit inside|resistance|dimensions|feature|waterproof|fold|cold|insulat"),
    "use_case": ("Best for", r"suitable|good for|best for|purpose|use case|beginner|recommend|appropriate"),
    "review": ("Sample review", r"review|feedback|what .* say"),
    "returns": ("Returns", r"return|refund|exchange|doesn.t fit|does not fit|wrong size|send it back"),
}


def field_value(item, field):
    if field == "price":
        return f"₹{item['price']:,}"
    if field == "weight":
        return f"{item['weight_g']:,} g"
    if field == "delivery":
        return f"{item['delivery_days']} days estimated · {', '.join(item['regions'])} regions"
    if field == "stock":
        return f"{item['stock']} in stock" if item["stock"] else "Out of stock"
    if field == "sizes":
        return ", ".join(map(str, item["sizes"])) or "One size"
    return item.get(field, "Unlisted")


def answer(query, products, focus, updates):
    if not products:
        return None
    named = [item for item in products if item["name"].lower() in query]
    ordinals = re.findall(r"(?:\b(first|second|third|1st|2nd|3rd|option\s+[123])|(?<!\w)(#[123]))\b", query)
    references = [word or number for word, number in ordinals]
    targets = named
    if references and not named:
        mapping = {"first": 0, "second": 1, "third": 2}
        positions = [mapping[ref] if ref in mapping else int(re.search(r"[123]", ref)[0]) - 1 for ref in references]
        targets = [products[index] for index in dict.fromkeys(positions) if index < len(products)]
        if not targets:
            return []
    selected = next((item for item in products if item["id"] == focus), None)
    is_question = bool(re.search(r"\?|^(?:what|which|who|when|where|why|does|do|is|are|can|how|compare|tell me|show .* details)\b", query))
    if not is_question and not focus:
        return None
    if updates.get("category") and all(item["category"] != updates["category"] for item in products):
        return None
    if re.match(r"^(?:actually|instead|change|switch|make it|try|find|show me)\b", query) and (
        set(updates) & {"category", "color", "size", "max_price", "features", "drop_features", "deadline"}
    ):
        return None
    if updates.get("max_price") is not None and not targets and not selected:
        return None
    fields = [key for key, (_, pattern) in FIELDS.items() if re.search(pattern, query)]
    if fields == ["color"] and updates.get("color") and not targets and not selected:
        return None
    if fields == ["sizes"] and updates.get("size") and not targets and not selected:
        return None
    if fields == ["specification"] and updates.get("features") and not targets and not selected and not re.search(r"\b(?:these|those|of them|any of|the options)\b", query):
        return None
    if selected and not targets and not re.search(r"\b(?:which|compare|all|them)\b", query):
        targets = [selected]
    if "why" in query and targets:
        return [{"name": item["name"], "facts": {"Fit": item.get("reason", "Shown in the recent results."),
                 **({"Trade-offs": "; ".join(item["tradeoffs"])} if item.get("tradeoffs") else {})}} for item in targets]
    if not fields:
        if re.search(r"compare|differences|details|tell me", query):
            fields = ["price", "weight", "material", "specification", "warranty"]
        else:
            scoped = targets or products
            plan = plan_product_question(query, scoped, FIELDS)
            if plan and plan[1]:
                indices, fields = plan
                targets = [scoped[index] for index in indices] or scoped
            elif selected or targets:
                return []
            else:
                return None
    targets = targets or products
    if "heaviest" in query or "heavier" in query:
        targets = sorted(targets, key=lambda item: item["weight_g"], reverse=True)
    if "lightest" in query or "lighter" in query:
        targets = sorted(targets, key=lambda item: item["weight_g"])
    if "cheapest" in query:
        targets = sorted(targets, key=lambda item: item["price"])
    if "fastest" in query:
        targets = sorted(targets, key=lambda item: item["delivery_days"])
    return [{"name": item["name"], "facts": {FIELDS[key][0]: field_value(item, key) for key in fields}} for item in targets]
