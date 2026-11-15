# TrailGuide

TrailGuide is a local conversational shopping assistant for outdoor and fitness gear. It was built for **PS-12, Agentic AI & Enterprise Automation**. Describe what you need, refine your requirements across turns, and compare up to three catalog products. Each result explains how it fits. When no product meets every requirement, the assistant shows the closest available alternatives and identifies the trade-offs.

## Run locally

**Requirements:** Python 3.10 or later and a web browser. The default workflow runs locally without an API key.

From the repository root on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

On macOS or Linux, create the environment with `python3 -m venv .venv` and replace `.\.venv\Scripts\python.exe` with `.venv/bin/python` in the last two commands.

Open [http://127.0.0.1:8000](http://127.0.0.1:8000/). On first launch, TrailGuide creates `trailguide.sqlite3` and seeds its catalog. Sessions and agent traces are saved to this file across restarts. Click **Home** to return to the storefront and use the sidebar to reopen a session.

## Try the demo

| Scenario | What to enter | What to look for |
| --- | --- | --- |
| Clarification and comparison | **I need a backpack** → **Under ₹3,000** → **It should be light and weigh less than 2 kg** → **No** | The top result explains its weight and price. The comparison shows how each product meets the constraints. |
| Fallback | Repeat the backpack search and add **Color should be red** before confirming. | The assistant states that red is unavailable and shows alternatives with the color trade-off. |
| Required attribute and memory | **Waterproof hiking boots** → **9** → **Actually, under ₹3,500** → **No** | It asks for UK shoe size and retains size 9 after the budget changes. |
| Product follow-up | After seeing results, ask **Compare #1 and #3 by material and warranty**, or click **Ask about this product**. | The answer uses the relevant products and facts recorded in the catalog. |

Choose a category to start a scoped search. After the assistant asks whether you want to add anything else, say **No** or select **No, show matches**. Expand **Agent decisions** under a response to see which roles ran and what they decided.

## Agent workflow

| Agent | Responsibility |
| --- | --- |
| Query Ingestion | Normalizes the text or submitted voice transcript and records the session and turn. |
| Intent & Constraint Extraction | Reads purchase intent, explicit requirements, and inferred preferences from supported phrasing. |
| Ambiguity & Clarification | Asks for missing information and waits for the shopper to confirm before searching. |
| Catalog Attribute Mapping | Maps shopping language to catalog categories and structured requirements. |
| Candidate Retrieval | Retrieves in-stock candidates from SQLite and checks shipping eligibility. |
| Ranking & Fit Scoring | Orders candidates by constraint fit, relevant preference and review signals, and price. |
| Explanation Generation | Explains each result using specific catalog facts and reports any unmet requirements. |
| Zero-Result & Fallback | Selects close alternatives and shows their trade-offs while retaining availability, size, and shipping eligibility. |
| Session Memory | Carries confirmed requirements forward and updates them when the shopper changes direction. |
| Orchestrator | Routes each turn to clarification, catalog search, product follow-up, or fallback. |

The default interpretation is rule-based and covers supported catalog categories, attributes, and phrasing. Search, ranking, and displayed facts are grounded in SQLite.

## Catalog and voice input

The [bundled JSON export](data/trailguide-catalog.json) contains **180 synthetic listings from 36 product models** across hiking footwear, trekking poles, backpacks, camping gear, hydration, and home fitness. It includes INR prices, inventory, delivery regions and estimates, materials, weights, warranty, and specifications. Illustrations, reviews, prices, and stock levels are fictional demo data. The running app also offers a direct [catalog export](http://127.0.0.1:8000/api/catalog/download).

**Dictate** uses the browser’s speech recognition and fills the composer for review before sending. It requires a compatible browser and microphone permission. The browser may use a remote speech provider, while the application receives the text you submit.

### Optional Ollama integration

If Ollama is running on the default local port and you already have a model installed, set `TRAILGUIDE_OLLAMA_MODEL` to that model’s name before starting Uvicorn:

```powershell
$env:TRAILGUIDE_OLLAMA_MODEL = 'qwen2.5:3b'
```

The optional integration maps additional product follow-up phrasing to catalog fields. The response facts still come from SQLite. The standard demo runs without Ollama.

## Project structure

```text
app.py                       FastAPI routes and SQLite persistence
trailguide/
  agents.py                  Agent roles, ranking, and orchestration
  catalog.py                 Product lines and synthetic variants
  specs.py                   Model specifications
  followups.py               Product references and catalog-backed answers
  model.py                   Optional Ollama question planner
  illustrations.py           Optional Pillow-based illustration generator
templates/index.html         Jinja storefront
static/
  chat.js                    Chat, navigation, speech input, and comparisons
  styles.css                 Responsive storefront styles
  products/                  Local product images
data/trailguide-catalog.json Bundled catalog export
tests/test_workflows.py      Shopping workflow regression tests
requirements.txt             Runtime dependencies
```

The frontend uses Jinja, HTML, CSS, and JavaScript. The backend uses Python, FastAPI, Pydantic, and SQLite. Product images are included. To regenerate them, install Pillow in your development environment and run `python -m trailguide.illustrations`.

## Run tests

After installing the requirements:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The tests cover clarification and confirmation, session memory, filtering, ranking, fallback, product follow-ups, and catalog and image consistency.
