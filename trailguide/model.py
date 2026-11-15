"""Optional local model for mapping product questions to catalog fields."""
import json
import os
from urllib.error import URLError
from urllib.request import Request, urlopen


def plan_product_question(query, products, allowed_fields):
    model = os.getenv("TRAILGUIDE_OLLAMA_MODEL")
    if not model:
        return None
    schema = {
        "type": "object",
        "properties": {
            "positions": {"type": "array", "items": {"type": "integer", "minimum": 1, "maximum": len(products)}},
            "fields": {"type": "array", "items": {"type": "string", "enum": list(allowed_fields)}},
        },
        "required": ["positions", "fields"],
        "additionalProperties": False,
    }
    payload = {
        "model": model, "stream": False, "format": schema, "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": (
                "Map a shopper question to existing product positions and catalog fields. "
                "Return empty fields if the question requests an unavailable fact or a new search. "
                "Use all positions for a general comparison. Output field names and positions only."
            )},
            {"role": "user", "content": json.dumps({
                "question": query,
                "products": [item["name"] for item in products],
                "fields": list(allowed_fields),
            })},
        ],
    }
    request = Request("http://127.0.0.1:11434/api/chat", json.dumps(payload).encode(),
                      {"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=8) as response:
            plan = json.loads(json.load(response)["message"]["content"])
        positions = plan["positions"]
        fields = plan["fields"]
        if not isinstance(positions, list) or not isinstance(fields, list):
            return None
        return (
            sorted({index - 1 for index in positions if type(index) is int and 1 <= index <= len(products)}),
            list(dict.fromkeys(field for field in fields if isinstance(field, str) and field in allowed_fields)),
        )
    except (URLError, TimeoutError, KeyError, TypeError, ValueError):
        return None
