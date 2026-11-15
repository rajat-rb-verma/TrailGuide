"""Shopping agents. Each stage returns evidence for the demo trace."""
import json
import re
from datetime import date, timedelta

from .catalog import EXTRA_LINES, LINES
from .followups import answer

ALIASES = {
    "hiking footwear": r"boots?|shoes?|footwear|sneakers?",
    "trekking poles": r"poles?|walking sticks?",
    "backpacks": r"backpacks?|daypacks?|trail packs?",
    "camping gear": r"camping|tents?|lanterns?|headlamps?|sleeping bags?",
    "hydration": r"bottles?|hydration",
    "home fitness": r"fitness|recovery|exercise|workout|resistance bands?|foam rollers?|yoga|pedal exercisers?",
}
FEATURES = ("waterproof", "lightweight", "breathable", "ankle support", "beginner",
            "carbon", "aluminum", "adjustable", "foldable", "insulated", "low impact",
            "cushioned", "rechargeable", "leakproof", "compact", "recovery", "latex free", "extra grip")
SIZE_WORDS = dict(zip(
    ("six", "seven", "eight", "nine", "ten", "eleven", "twelve"), range(6, 13)
))
REGION_ALIASES = {
    "north": "north|delhi|chandigarh|jaipur|lucknow",
    "south": "south|bengaluru|bangalore|chennai|hyderabad|kochi",
    "east": "east|kolkata|bhubaneswar|patna",
    "west": "west|mumbai|pune|ahmedabad|goa",
}
COLORS = ("black", "navy", "olive", "orange", "grey", "red", "blue", "green",
          "white", "yellow", "pink", "purple", "brown", "beige", "teal", "silver")
WEIGHT_LIMIT = re.compile(
    r"(?P<operator>less than|under|below|up to|within|at most|no more than|maximum(?: of)?)"
    r"\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>kg|g|kilograms?|grams?)\b"
)
LIGHTNESS = re.compile(r"\blight[- ]?weight\b|\b(?:light(?:er|est)? to carry|lightest|(?:should be|must be|that is|is) light|as light as possible)\b|\blight (?:bag|backpack|pack|shoes?|boots?|poles?|tent|bottle|mat)\b")


def format_weight(grams):
    return f"{grams / 1000:g} kg" if grams >= 1000 else f"{grams:g} g"



def ingest(message):
    return re.sub(r"^(?:hey|hi|hello)[, !]+", "", " ".join(message.lower().split()))


def extract(query, pending):
    updates = {}
    for category, aliases in ALIASES.items():
        matching_line = next((line[0] for line in (*LINES[category], *EXTRA_LINES[category]) if line[0].lower() in query), None)
        if matching_line:
            updates["category"] = category
            if f"the {matching_line.lower()}" in query:
                updates["product_line"] = matching_line
            break
        if re.search(rf"\b(?:{aliases})\b", query):
            updates.setdefault("category", category)
    budget_pattern = r"(under|below|up to|within|budget(?: of| around| is|:)?|around|at most|no more than)\s*(?:₹|rs\.?|inr|rupees)?\s*([\d,]+)(?:\.(\d+))?\s*(k)?\b"
    for budget in re.finditer(budget_pattern, query):
        if re.match(r"\s*(?:days?|weeks?|hours?|kilograms?|kg|grams?|g|liters?|litres?|l|ml)\b", query[budget.end():]):
            continue
        amount = budget[2].replace(",", "") + ("." + budget[3] if budget[3] else "")
        if amount and len(amount) <= 10:
            updates["max_price"] = round(float(amount) * (1000 if budget[4] else 1))
            updates["strict_price"] = budget[1] in ("under", "below")
        break
    if pending == "budget" and "max_price" not in updates:
        amount = re.fullmatch(r"(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*)\s*(k)?[.!]?", query)
        if amount and len(amount[1]) <= 10:
            updates.update(max_price=int(amount[1].replace(",", "")) * (1000 if amount[2] else 1), strict_price=False)
    size_pattern = r"(\d{1,2}|six|seven|eight|nine|ten|eleven|twelve)"
    size = re.search(rf"\b(?:size\s*(?:uk\s*)?|uk\s*){size_pattern}\b", query)
    if size is None and pending == "size":
        size = re.fullmatch(size_pattern + r"[.!]?", query)
    if size:
        updates["size"] = int(size[1]) if size[1].isdigit() else SIZE_WORDS[size[1]]
    weight = WEIGHT_LIMIT.search(query)
    if weight:
        factor = 1000 if weight["unit"].startswith("k") else 1
        updates["max_weight_g"] = float(weight["value"]) * factor
        updates["strict_weight"] = weight["operator"] in {"less than", "under", "below"}
    if LIGHTNESS.search(query) or re.fullmatch(r"light(?:er)?[.!]?", query):
        updates["prefer_lighter"] = True

    color_words = "|".join((*COLORS, "gray"))
    explicit_color = re.search(r"\bcolou?r\s*(?:should be|must be|is|:)\s*([a-z]+)\b", query)
    mentioned_color = re.findall(rf"\b(?:{color_words})\b", query)
    if explicit_color or mentioned_color:
        color = explicit_color[1] if explicit_color else mentioned_color[-1]
        if color not in {"any", "either", "does", "do", "options"}:
            updates["color"] = "grey" if color == "gray" else color
    for region, aliases in REGION_ALIASES.items():
        if re.search(rf"\b(?:{aliases})\b", query):
            updates["region"] = region
            break
    if "tomorrow" in query:
        updates["deadline"] = (date.today() + timedelta(days=1)).isoformat()
    days = re.search(r"\b(?:in|within) (\d{1,3}) days?\b", query)
    if days:
        updates["deadline"] = (date.today() + timedelta(days=int(days[1]))).isoformat()
    for weekday, name in enumerate(("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")):
        if f"by {name}" in query:
            updates["deadline"] = (date.today() + timedelta(days=(weekday - date.today().weekday()) % 7)).isoformat()
    canonical = re.sub(r"\baluminium\b", "aluminum", query)
    features = [feature for feature in FEATURES if re.search(rf"\b{feature.replace(' ', '[- ]')}\b", canonical)]
    if re.search(r"\b(?:no need for|doesn.t need to be|does not need to be|don.t need)\b", query):
        updates["drop_features"] = features
        features = []
    capacity = re.search(r"\b(\d+(?:\.\d+)?)\s*(ml|l|litres?|liters?)\b", query)
    if capacity:
        features.append(f"{capacity[1]} {'ml' if capacity[2] == 'ml' else 'l'}")
    if updates.get("prefer_lighter") and "lightweight" in features:
        features.remove("lightweight")
    if features:
        updates["features"] = features
    for intent, pattern in {"gift": r"gift|birthday", "replacement": r"replace|replacement", "comparison": r"compare|versus"}.items():
        if re.search(rf"\b(?:{pattern})\b", query):
            updates["intent"] = intent
            break
    if re.search(r"bad knees|knee pain|sore knees|joint.?friendly|easy on (?:the |his |her )?knees", query):
        updates["preferences"] = ["shock absorbing", "cushioned", "low impact"]
    if re.search(r"\bhik(?:e|ing)\b|\btrail\b", query):
        updates["activity"] = "hiking"
    if re.search(r"\bdad\b|\bfather\b", query):
        updates["recipient"] = "dad"
    if re.search(r"\bfor myself\b|\bfor me\b", query):
        updates.setdefault("intent", "self-use")
    return updates


def remember(previous, updates, query):
    previous = previous.copy()
    updates = updates.copy()
    if re.match(r"(new search|start over|different topic|switch to)\b", query):
        previous = {}
    if updates.get("category", previous.get("category")) != previous.get("category"):
        for field in ("size", "size_skipped", "features", "color", "product_line", "max_weight_g", "strict_weight", "prefer_lighter"):
            previous.pop(field, None)
    requested = set(updates.pop("features", []))
    dropped = set(updates.pop("drop_features", []))
    if requested & {"carbon", "aluminum"} and len(requested & {"carbon", "aluminum"}) == 1:
        dropped |= {"carbon", "aluminum"} - requested
    if any(re.fullmatch(r"[\d.]+ (?:ml|l)", value) for value in requested):
        dropped |= {value for value in previous.get("features", []) if re.fullmatch(r"[\d.]+ (?:ml|l)", value)}
    if "size" in updates:
        previous.pop("size_skipped", None)
    if requested or dropped:
        previous["features"] = sorted((set(previous.get("features", [])) - dropped) | requested)
    return previous | updates


RESET_SEARCH = re.compile(r"^(?:new search|start over|different topic|switch to)\b")
DONE = re.compile(r"^(?:no(?:pe|,? thanks|,? show (?:the )?(?:matches|results))?|nothing(?: else| more)?|that(?:'s| is) (?:all|enough)|show (?:me )?(?:the )?(?:results|products|options)|skip)[.!?]*$")


def clarify(state, pending, query, updates):
    done = bool(DONE.fullmatch(query))
    if not state.get("category") and not state.get("activity"):
        return "category", "What are you shopping for? I can help with hiking footwear, trekking poles, backpacks, camping gear, hydration, and home fitness."
    if state.get("category") == "hiking footwear" and not state.get("size") and not state.get("size_skipped"):
        if done and pending == "size":
            state["size_skipped"] = True
        else:
            return "size", "What UK shoe size should I look for? Say “skip” if you’re browsing without a size."
    if done and query.rstrip(".!?") == "skip" and pending in {"size", "budget", "priority"}:
        return "specifics", "Anything more specific before I search? Add a requirement or say “no” to see the matches and comparison."
    if done:
        return None, None
    if pending == "budget" and "max_price" not in updates:
        return "budget", "What price should I stay within? Enter a rupee amount or say “skip.”"
    if pending == "specifics":
        if not updates:
            return "specifics", "What would you like to add? You can give me a budget, color, feature, or delivery deadline, or say “no” to see the comparison."
    elif pending not in {"size", "budget", "priority"}:
        if "max_price" not in state:
            return "budget", "What budget should I stay within? You can give me a price in rupees or say “skip.”"
        return "priority", "What matters most besides the requirements you shared? For example, you can add a color, feature, or delivery location, or say “skip.”"
    return "specifics", "Anything more specific before I search? Add a requirement or say “no” to see the matches and comparison."


def map_catalog(state):
    if "category" in state:
        return [state["category"]]
    return ["trekking poles", "backpacks", "hydration", "camping gear"]


def retrieve(db, categories, state):
    placeholders = ",".join("?" for _ in categories)
    rows = db.execute(f"SELECT details FROM products WHERE stock > 0 AND category IN ({placeholders})", categories)
    products = (json.loads(row[0]) for row in rows)
    return [item for item in products if not state.get("region") or state["region"] in item["regions"]]


def mismatches(item, state):
    issues = {}
    if state.get("product_line") and state["product_line"] != item["name"]:
        issues["model"] = f"Different model from {state['product_line']}"
    if "max_price" in state:
        cap = state["max_price"]
        if item["price"] > cap or item["price"] == cap and state.get("strict_price"):
            difference = item["price"] - cap
            issues["budget"] = f"₹{difference:,} above budget" if difference else f"At ₹{cap:,}, outside your under-₹{cap:,} limit"
    if "max_weight_g" in state:
        limit = state["max_weight_g"]
        actual = item["weight_g"]
        if actual > limit:
            issues["weight"] = f"Weighs {format_weight(actual)}, {format_weight(actual - limit)} over your limit"
        elif actual == limit and state.get("strict_weight"):
            issues["weight"] = f"Weighs {format_weight(actual)}, at your strict under-{format_weight(limit)} limit"
    if state.get("size") and state["size"] not in item["sizes"]:
        issues["size"] = f"Size {state['size']} unavailable"
    if state.get("color") and item["color"] != state["color"]:
        issues["color"] = f"{item['color'].title()} instead of {state['color']}"
    missing = set(state.get("features", [])) - set(item["features"])
    if missing:
        issues["features"] = "Missing " + ", ".join(sorted(missing))
    if state.get("deadline") and date.today() + timedelta(days=item["delivery_days"]) > date.fromisoformat(state["deadline"]):
        issues["delivery"] = f"Estimated in {item['delivery_days']} days, after your deadline"
    return issues


def rank(items, state):
    def score(item):
        issues = mismatches(item, state)
        preferences = set(state.get("preferences", [])) & set(item["features"])
        review_bonus = any(feature in item["review"].lower() for feature in preferences)
        weight_overage = max(0, item["weight_g"] - state.get("max_weight_g", item["weight_g"]))
        preferred_weight = item["weight_g"] if state.get("prefer_lighter") else 0
        return (len(issues), weight_overage, -len(preferences), -review_bonus,
                preferred_weight, item["price"], item["id"])

    return sorted(items, key=score)


def fallback(ranked, state):
    """Offer distinct alternatives, keeping size and shipping eligibility intact."""
    by_tradeoff = {}
    closest = []
    best_distance = None
    for item in ranked:
        issues = mismatches(item, state)
        if not issues or "size" in issues:
            continue
        distance = len(issues)
        if best_distance is None:
            best_distance = distance
        if distance > best_distance:
            break
        by_tradeoff.setdefault(tuple(sorted(issues)), item)
        closest.append(item)

    selected = {}
    keys = sorted(by_tradeoff, key=lambda key: ("budget" in key, "delivery" in key, key))
    for item in [*(by_tradeoff[key] for key in keys), *closest]:
        selected.setdefault(item["name"], item)
    return list(selected.values())[:3]


def fit_breakdown(item, state):
    checks = {}
    issues = mismatches(item, state)
    for key, label in (("product_line", "Requested model"), ("max_price", "Budget"), ("max_weight_g", "Weight limit"), ("size", "UK size"), ("color", "Color"),
                       ("features", "Requested features"), ("deadline", "Delivery deadline")):
        if key in state:
            rule = {"product_line": "model", "max_price": "budget", "max_weight_g": "weight", "deadline": "delivery"}.get(key, key)
            checks[label] = issues.get(rule, "Matches")
    if state.get("prefer_lighter"):
        checks["Lightweight preference"] = format_weight(item["weight_g"])
    if state.get("region"):
        checks["Shipping region"] = "Matches"
    if state.get("preferences"):
        preferred = set(state["preferences"]) & set(item["features"])
        checks["Preferred features"] = ", ".join(sorted(preferred)) or "No matching feature listed"
    return checks


def explain(item, state, position=0, alternative=False, lightest_shown=None):
    issues = mismatches(item, state)
    required = set(state.get("features", [])) & set(item["features"])
    preferred = set(state.get("preferences", [])) & set(item["features"])
    evidence = []
    if required:
        evidence.append("has " + ", ".join(sorted(required)))
    if preferred:
        evidence.append("matches your preference for " + ", ".join(sorted(preferred)))
    if state.get("prefer_lighter") or ("max_weight_g" in state and "weight" not in issues):
        weight = format_weight(item["weight_g"])
        if item["weight_g"] == lightest_shown:
            evidence.append(f"is the lightest option shown at {weight}")
        else:
            evidence.append(f"weighs {weight}")
        if "max_weight_g" in state and "weight" not in issues:
            evidence[-1] += f", within your {format_weight(state['max_weight_g'])} limit"
    if state.get("size") in item["sizes"]:
        evidence.append(f"is available in UK size {state['size']}")
    if "max_price" in state and "budget" not in issues:
        evidence.append(f"fits your budget at ₹{item['price']:,}")
    if state.get("color") == item["color"]:
        evidence.append(f"comes in your requested {item['color']} color")
    if state.get("region"):
        evidence.append(f"ships to the {state['region']} region")
    if state.get("deadline") and "delivery" not in issues:
        evidence.append(f"has a {item['delivery_days']}-day estimate within your deadline")
    if not evidence:
        evidence.append(f"is designed for {item['use_case'].lower()}")
    prefix = "This alternative" if alternative else ("The top match" if position == 0 else "This match")
    reason = f"{prefix} {'; it '.join(evidence)}."
    if alternative:
        reason += " Trade-off: " + "; ".join(issues.values()) + "."
    return item | {"reason": reason, "tradeoffs": list(issues.values()),
                   "fit": fit_breakdown(item, state)}


def orchestrate(db, message, previous, pending, turn, session_id, recent=None, focus=None, source="text"):
    trace = []
    def log(agent, decision):
        trace.append({"agent": agent, "decision": decision})

    query = ingest(message)
    log("Query Ingestion", {"session": session_id, "turn": turn, "normalized": query, "source": source})
    updates = extract(query, pending)
    log("Intent & Constraint Extraction", updates)
    state = remember(previous, updates, query)
    log("Session Memory", state)
    def result(reply, route, waiting=None, products=None, facts=None):
        log("Orchestrator", route)
        return {"reply": reply, "trace": trace, "state": state, "pending": waiting, "products": products or [], "facts": facts or []}

    if re.search(r"\b(?:makeup|groceries|grocery|food|lipstick|vegetables)\b", query) and not updates.get("category"):
        state = previous
        return result("This store carries outdoor and fitness gear. I can help with hiking footwear, poles, backpacks, camping gear, hydration, and fitness equipment.", "Outside store catalog", pending)
    reset = RESET_SEARCH.match(query)
    if reset:
        pending = None
    if not reset:
        facts = answer(query, recent or [], focus, updates)
        if facts is not None:
            state = previous
            log("Session Memory", "Kept the active shopping constraints for this product question")
            log("Explanation Generation", facts or "Requested fact is outside the catalog record")
            reply = "Here’s what the catalog lists." if facts else "I don’t have a catalog fact for that question. Ask about specs, sizing, materials, delivery, warranty, returns, or reviews."
            return result(reply, "Answer a question about recent products", pending, facts=facts)
        if recent and not updates and re.search(r"\?|^(?:what|which|who|when|where|why|does|do|is|are|can|how)\b", query):
            state = previous
            return result("I couldn’t find that information in this catalog. Try asking about the product’s listed specs, stock, shipping, or warranty.", "Catalog fact unavailable", pending)
    waiting, question = clarify(state, pending, query, updates)
    log("Ambiguity & Clarification", {
        "needs_clarification": bool(waiting), "missing_attribute": waiting,
        "question": question, "used_session_context": bool(previous),
    })
    if question:
        understood = []
        if "color" in updates:
            understood.append(updates["color"])
        if "prefer_lighter" in updates:
            understood.append("lighter options first")
        if "max_weight_g" in updates:
            weight_limit = format_weight(updates["max_weight_g"])
            understood.append(f"{'under' if updates['strict_weight'] else 'at most'} {weight_limit}")
        if waiting == "specifics" and understood:
            question = f"Got it: {', '.join(understood)}. {question}"
        return result(question, "Wait for shopper confirmation" if waiting == "specifics" else "Wait for clarification", waiting)
    categories = map_catalog(state)
    log("Catalog Attribute Mapping", {
        "categories": categories, "product_line": state.get("product_line"),
        "max_price_inr": state.get("max_price"), "max_weight_g": state.get("max_weight_g"),
        "prefer_lighter": state.get("prefer_lighter", False), "required_features": state.get("features", []),
        "preferred_features": state.get("preferences", []), "size_uk": state.get("size"),
    })
    candidates = retrieve(db, categories, state)
    log("Candidate Retrieval", {
        "available_candidates": len(candidates), "minimum_stock": 1,
        "region": state.get("region"), "categories": categories,
    })
    ranked = rank(candidates, state)
    exact = [item for item in ranked if not mismatches(item, state)]
    log("Ranking & Fit Scoring", {"exact_matches": len(exact), "leading_candidates": [
        {"sku": item["sku"], "constraints": fit_breakdown(item, state),
         "review_signal": [tag for tag in state.get("preferences", []) if tag in item["review"].lower()]}
        for item in ranked[:5]
    ]})
    if exact:
        unique = {}
        for item in exact:
            unique.setdefault(item["name"], item)
        selected = list(unique.values())[:3]
        reply = "Here are the best matches for your requirements."
    else:
        selected = fallback(ranked, state)
        log("Zero-Result & Fallback", {
            "exact_matches": 0, "kept": ["size", "stock", "shipping region"],
            "alternatives": [{"sku": item["sku"], "tradeoffs": mismatches(item, state)} for item in selected],
        })
        reply = ("Nothing matches every requirement. These are the closest available products, with the trade-offs shown for each."
                 if selected else "No in-stock products fit those requirements or offer a viable alternative. Would you like to change the category or delivery region?")
    weights = {item["weight_g"] for item in selected}
    lightest_shown = min(weights) if len(weights) > 1 else None
    products = [explain(item, state, index, alternative=not exact, lightest_shown=lightest_shown)
                for index, item in enumerate(selected)]
    if products and exact:
        reply = f"Best match: {products[0]['name']}. {products[0]['reason']}"
    if products and not exact:
        if state.get("color") and not any(item["color"] == state["color"] for item in candidates):
            reply = (
                f"No available {state['color']} option matches your search. "
                "These are the closest available products, with the trade-offs shown for each."
            )
    if products:
        log("Explanation Generation", [{"id": item["id"], "reason": item["reason"], "tradeoffs": item["tradeoffs"]} for item in products])
    return result(reply, "Show recommendations" if exact else "Handle zero results", products=products)
