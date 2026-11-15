"""Regression checks for the PDF's shopping-assistant behaviors."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import app as routes
from trailguide.catalog import LINES


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        original = routes.DB
        self.addCleanup(setattr, routes, "DB", original)
        routes.DB = Path(self.folder.name) / "test.sqlite3"
        with closing(sqlite3.connect(original)) as source, closing(routes.connect()) as target:
            source.backup(target)
        self.session = routes.new_session()["id"]

    def chat(self, text, focus=None, source="text"):
        return routes.chat(self.session, routes.Message(text=text, focus=focus, source=source))

    def test_ingestion_and_extraction_hiking_gift(self):
        turn = self.chat("Hey, a gift for my dad who likes hiking and has sore knees, under INR 4000", source="voice")
        trace = {step["agent"]: step["decision"] for step in turn["trace"]}
        self.assertEqual(trace["Query Ingestion"]["source"], "voice")
        self.assertFalse(trace["Query Ingestion"]["normalized"].startswith("hey"))
        self.assertEqual(turn["state"]["recipient"], "dad")
        self.assertEqual(turn["state"]["max_price"], 4000)
        self.assertIn("shock absorbing", turn["state"]["preferences"])
        self.assertEqual(turn["pending"], "priority")
        self.assertFalse(turn["products"])
        self.assertEqual(self.chat("Skip")["pending"], "specifics")
        shown = self.chat("No")
        self.assertIn("shock absorbing", shown["products"][0]["features"])
        self.assertIn("shock absorbing", shown["products"][0]["reason"])

    def test_clarification_and_memory(self):
        first = self.chat("Waterproof hiking boots")
        self.assertEqual(first["pending"], "size")
        self.assertFalse(first["products"])
        second = self.chat("Nine.", source="voice")
        self.assertEqual(second["pending"], "specifics")
        self.assertFalse(second["products"])
        self.assertEqual(second["state"]["size"], 9)
        third = self.chat("Actually, under INR 3500")
        self.assertEqual(third["state"]["size"], 9)
        self.assertIn("waterproof", third["state"]["features"])
        self.assertEqual(third["pending"], "specifics")
        self.assertFalse(third["products"])
        shown = self.chat("No")
        self.assertTrue(shown["products"])
        saved = routes.history(self.session)
        self.assertEqual(len(saved), 4)
        self.assertEqual(saved[3]["state"]["max_price"], 3500)

    def test_retrieval_filters_on_delivery_stock_and_region(self):
        turn = self.chat("Backpack delivery to Chennai within 5 days")
        self.assertNotIn("max_price", turn["state"])
        self.assertEqual(turn["state"]["region"], "south")
        self.assertEqual(turn["pending"], "budget")
        self.chat("Skip")
        turn = self.chat("No")
        self.assertTrue(turn["products"])
        self.assertTrue(all(p["delivery_days"] <= 5 and "south" in p["regions"] and p["stock"] > 0 for p in turn["products"]))

    def test_fallback_tradeoffs_and_all_ten_agent_roles(self):
        self.assertEqual(self.chat("Carbon trekking poles under INR 2000")["pending"], "priority")
        self.assertEqual(self.chat("Skip")["pending"], "specifics")
        turn = self.chat("No")
        self.assertIn("closest", turn["reply"])
        self.assertTrue(all("Trade-off:" in p["reason"] for p in turn["products"]))
        self.assertEqual(len({step["agent"] for step in turn["trace"]}), 10)
        self.assertTrue(any(p["price"] < 2000 and p["tradeoffs"] for p in turn["products"]))
        self.assertTrue(any(p["price"] > 2000 and p["tradeoffs"] for p in turn["products"]))
        self.assertTrue(self.chat("Why the second one?")["facts"])
        replacement = self.chat("Actually, switch to aluminum")
        self.assertNotIn("carbon", replacement["state"]["features"])

    def test_category_mapping_and_comparison(self):
        for category in LINES:
            with self.subTest(category=category):
                turn = self.chat("Switch to " + category)
                if turn["pending"] == "size":
                    self.chat("9")
                else:
                    self.chat("4500")
                turn = self.chat("No")
                self.assertEqual(len(turn["products"]), 3)
                self.assertEqual(len({p["image"] for p in turn["products"]}), 3)
                self.assertTrue(all(p["category"] == category for p in turn["products"]))
        self.chat("Switch to hydration, show me a 600 ml bottle")
        self.chat("Skip")
        bottles = self.chat("No")
        self.assertTrue(bottles["products"])
        self.assertTrue(all("600 ml" in p["features"] for p in bottles["products"]))

    def test_unscripted_followups_use_recent_products_and_preserve_state(self):
        self.chat("Backpacks under INR 4500")
        self.chat("Skip")
        turn = self.chat("No")
        first, second, third = turn["products"]
        facts = self.chat("Compare #1 and #3 by material and warranty")["facts"]
        self.assertEqual([item["name"] for item in facts], [first["name"], third["name"]])
        self.assertEqual(facts[1]["facts"]["Warranty"], third["warranty"])
        facts = self.chat("How heavy is it and what is it made from?", second["id"])["facts"]
        self.assertEqual(facts[0]["facts"]["Weight"], f"{second['weight_g']:,} g")
        self.assertEqual(facts[0]["facts"]["Materials"], second["material"])
        self.assertEqual(self.chat("Does it come with insurance?", second["id"])["products"], [])
        self.assertEqual(self.chat("Will the second one ship to Mumbai?")["state"], turn["state"])

    def test_backpack_screenshot_preserves_lightness_weight_and_unavailable_color(self):
        self.chat("I need a backpack")
        self.chat("Under 3000 rupees")
        self.assertIn("lighter options first", self.chat("also the weight should be light")["reply"])
        self.assertIn("under 2 kg", self.chat("the bag weight should be less than 2 kg")["reply"])
        self.assertIn("red", self.chat("color should be red")["reply"])
        turn = self.chat("No")
        self.assertEqual(turn["state"]["max_price"], 3000)
        self.assertEqual(turn["state"]["max_weight_g"], 2000)
        self.assertIn("No available red", turn["reply"])
        self.assertEqual(len(turn["products"]), 3)
        first = turn["products"][0]
        self.assertEqual(first["name"], "Lightweight 18 L daypack")
        self.assertIn("lightest option shown at 410 g", first["reason"])
        self.assertIn("within your 2 kg limit", first["reason"])
        self.assertEqual(first["fit"]["Weight limit"], "Matches")
        self.assertTrue(all("instead of red" in p["fit"]["Color"] for p in turn["products"]))

    def test_weight_and_color_checks_apply_outside_backpacks(self):
        self.chat("I need a light bottle under 2000 rupees")
        self.chat("it should weigh less than 500 g")
        turn = self.chat("No")
        self.assertIn("Best match:", turn["reply"])
        self.assertIn("lightest option shown", turn["reply"])
        self.assertTrue(all(item["category"] == "hydration" and item["weight_g"] < 500 for item in turn["products"]))
        self.chat("color should be purple")
        turn = self.chat("No")
        self.assertIn("No available purple", turn["reply"])
        self.assertTrue(all(item["tradeoffs"] for item in turn["products"]))

    def test_catalog_matches_export_and_images_are_distinct(self):
        export = json.loads((routes.ROOT / "data/trailguide-catalog.json").read_text(encoding="utf-8"))
        response = routes.download_catalog()
        self.assertEqual(json.loads(response.body), export)
        self.assertEqual(export["listing_count"], 180)
        self.assertEqual(len({p["name"] for p in export["products"]}), 36)
        hashes = set()
        for product in export["products"]:
            path = routes.ROOT / product["image"].lstrip("/")
            hashes.add(hashlib.sha256(path.read_bytes()).digest())
        self.assertEqual(len(hashes), 180)


if __name__ == "__main__":
    unittest.main()
