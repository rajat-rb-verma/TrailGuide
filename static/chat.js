const byId = id => document.getElementById(id);
const thread = byId("thread");
const input = byId("message");
const status = byId("status");
let active = new URLSearchParams(location.search).get("session");
let voiceDraft = null;
let focusProduct = null;
let busy = false;

function node(tag, text = "", css = "") {
  const element = document.createElement(tag);
  element.textContent = text;
  if (css) element.className = css;
  return element;
}

async function request(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error("The request failed (" + response.status + "). Please try again.");
  return response.json();
}

function productImage(id, name = "") {
  const img = node("img");
  img.src = "/static/products/" + String(id).padStart(3, "0") + ".png?v=2";
  img.alt = name;
  img.loading = "lazy";
  return img;
}

function setFocus(product) {
  focusProduct = product;
  byId("focus").hidden = !product;
  byId("focused-name").textContent = product ? "Asking about " + product.name : "";
  input.placeholder = product ? "Ask about this product…" : "Describe what you need…";
}

function card(item, index) {
  const box = node("section", "", "card");
  const body = node("div", "", "card-body");
  body.append(node("p", (index + 1) + " · " + (item.brand || item.category), "meta"),
    node("h3", item.name), node("strong", "₹" + item.price.toLocaleString("en-IN")),
    node("p", item.color + " · " + item.delivery_days + " days estimated", "meta"),
    node("p", item.reason));
  for (const issue of item.tradeoffs || []) body.append(node("p", issue, "trade"));
  const action = node("button", "Ask about this product");
  action.type = "button";
  action.onclick = () => { setFocus(item); input.focus(); };
  body.append(action);
  box.append(productImage(item.id, "Illustration of " + item.name + " in " + item.color), body);
  return box;
}

function comparison(products) {
  const panel = node("details");
  panel.open = true;
  panel.append(node("summary", "Compare " + products.length + " products"));
  const table = node("table");
  const head = node("thead");
  const heading = node("tr");
  heading.append(node("th", "Attribute"));
  for (const item of products) {
    const cell = node("th", "", "comparison-product");
    cell.append(productImage(item.id), node("span", item.name));
    heading.append(cell);
  }
  for (const cell of heading.children) cell.scope = "col";
  head.append(heading);
  const body = node("tbody");
  const attributes = [
    ["Price", item => "₹" + item.price.toLocaleString("en-IN")],
    ["Best for", item => item.use_case],
    ["Weight", item => item.weight_g ? item.weight_g + " g" : ""],
    ["Materials", item => item.material],
    ["Specs", item => item.specification],
    ["Warranty", item => item.warranty],
    ["Delivery", item => item.delivery_days + " days estimated"],
  ];
  const fit = new Set(products.flatMap(item => Object.keys(item.fit || {})));
  for (const label of fit) attributes.push([label, item => item.fit?.[label]]);
  if (products.some(item => item.tradeoffs?.length)) {
    attributes.push(["Trade-offs", item => item.tradeoffs?.join(" · ") || "None flagged"]);
  }
  for (const [label, value] of attributes) {
    if (!products.some(value)) continue;
    const row = node("tr");
    const name = node("th", label);
    name.scope = "row";
    row.append(name, ...products.map(item => node("td", value(item) || "Unlisted")));
    body.append(row);
  }
  table.append(head, body);
  const scroll = node("div", "", "table-scroll");
  scroll.tabIndex = 0;
  scroll.setAttribute("aria-label", "Product comparison table");
  scroll.append(table);
  panel.append(scroll);
  return panel;
}

function draw(turn) {
  const article = node("article");
  article.append(node("p", turn.message, "shopper"), node("p", turn.reply, "reply"));
  if (["specifics", "priority", "budget", "size"].includes(turn.pending)) {
    const action = node("button", turn.pending === "specifics" ? "No, show matches" : "Skip", "clarification-action");
    action.type = "button";
    action.onclick = () => run(() => send(turn.pending === "specifics" ? "No" : "Skip"));
    article.append(action);
  }
  if (turn.products.length) {
    const cards = node("div", "", "cards");
    cards.append(...turn.products.map(card));
    article.append(cards);
    if (turn.products.length > 1) article.append(comparison(turn.products));
  }
  for (const entry of turn.facts || []) {
    const block = node("section", "", "facts");
    block.append(node("h3", entry.name));
    for (const [label, value] of Object.entries(entry.facts)) {
      const line = node("p");
      line.append(node("strong", label + " · "), document.createTextNode(value));
      block.append(line);
    }
    article.append(block);
  }
  const details = node("details");
  details.append(node("summary", "Agent decisions (" + turn.trace.length + ")"));
  for (const entry of turn.trace) {
    const step = node("div", "", "trace");
    step.append(node("strong", entry.agent), node("pre", JSON.stringify(entry.decision, null, 2)));
    details.append(step);
  }
  article.append(details);
  thread.append(article);
}

function showCategory(category) {
  for (const button of byId("categories").children) {
    button.setAttribute("aria-pressed", String(button.dataset.category === category));
  }
}

async function refreshSessions() {
  const sessions = await request("/api/sessions");
  const nav = byId("sessions");
  nav.replaceChildren();
  for (const session of sessions) {
    const button = node("button", session.title);
    button.type = "button";
    button.setAttribute("aria-current", String(session.id === active));
    button.onclick = () => run(() => openSession(session.id));
    nav.append(button);
  }
  return sessions;
}

async function openSession(id) {
  const turns = await request("/api/sessions/" + id);
  active = id;
  if (new URLSearchParams(location.search).get("session") !== id) {
    history.pushState(null, "", "/?session=" + encodeURIComponent(id));
  }
  setFocus(null);
  thread.replaceChildren();
  turns.forEach(draw);
  showCategory(turns.at(-1)?.state?.category);
  await refreshSessions();
}

async function newSession() {
  const session = await request("/api/sessions", {method:"POST"});
  await openSession(session.id);
}

async function run(action) {
  if (busy) return;
  busy = true;
  byId("send").disabled = true;
  status.textContent = "";
  try { await action(); }
  catch (error) { status.textContent = error.message; }
  finally { busy = false; byId("send").disabled = false; }
}

async function send(text, focus = undefined) {
  if (!active) await newSession();
  const turn = await request("/api/sessions/" + active + "/turns", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body:JSON.stringify({text, focus, source: voiceDraft === text ? "voice" : "text"})
  });
  draw(turn);
  showCategory(turn.state.category);
  if (input.value.trim() === text) { input.value = ""; voiceDraft = null; }
  thread.lastElementChild.scrollIntoView({block:"nearest"});
  await refreshSessions();
}

async function loadCategories() {
  const categories = await request("/api/catalog/categories");
  const categoryImages = [1, 11, 41, 71, 81, 106];
  categories.forEach((category, index) => {
    const button = node("button");
    button.type = "button";
    button.dataset.category = category;
    button.setAttribute("aria-pressed", "false");
    button.append(productImage(categoryImages[index]), node("span", category[0].toUpperCase() + category.slice(1)));
    button.onclick = () => run(async () => {
      setFocus(null);
      await send("Switch to " + category);
    });
    byId("categories").append(button);
  });
}

byId("clear-focus").onclick = () => { setFocus(null); input.focus(); };
byId("new").onclick = () => run(newSession);
document.querySelector("form").onsubmit = event => {
  event.preventDefault();
  const text = input.value.trim();
  if (text) run(() => send(text, focusProduct?.id));
};
run(async () => {
  await loadCategories();
  const sessions = await refreshSessions();
  const selected = sessions.find(session => session.id === active);
  if (selected) await openSession(selected.id);
  else if (active) { active = null; history.replaceState(null, "", "/"); }
});

window.addEventListener("popstate", () => location.reload());

const voiceButton = byId("voice");
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
voiceButton.onclick = () => {
  if (!SpeechRecognition) {
    status.textContent = "Voice input is unavailable in this browser. Open the site in a browser with speech recognition or type your question.";
    return;
  }
  if (recognition) {
    recognition.stop();
    return;
  }
  const listener = new SpeechRecognition();
  listener.lang = "en-IN";
  listener.interimResults = false;
  listener.onend = () => {
    recognition = null;
    voiceButton.setAttribute("aria-pressed", "false");
    if (status.textContent === "Listening…") status.textContent = "";
  };
  listener.onerror = event => {
    status.textContent = event.error === "not-allowed"
      ? "Allow microphone access in your browser to dictate."
      : "Speech recognition could not complete. Try again or type your question.";
  };
  listener.onresult = event => {
    voiceDraft = event.results[0][0].transcript.trim();
    input.value = voiceDraft;
    status.textContent = "Review the transcript, then press Send.";
    input.focus();
  };
  try {
    listener.start();
    recognition = listener;
    voiceButton.setAttribute("aria-pressed", "true");
    status.textContent = "Listening…";
  } catch {
    status.textContent = "The microphone could not start.";
  }
};
