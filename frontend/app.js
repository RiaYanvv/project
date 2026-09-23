const state = {
  production: [{ country: "CN", share: "" }],
  markets: [{ country: "US", share: "" }],
  assessment: null,
};
const draftKey = "locus-decision-draft";

const productionCountries = [
  ["CN", "China"], ["VN", "Vietnam"], ["ID", "Indonesia"], ["IN", "India"],
  ["TH", "Thailand"], ["MX", "Mexico"], ["OTHER", "Other"], ["NOT_SURE", "Not sure"],
];
const marketCountries = [["US", "United States"], ["EU", "EU"], ["CN", "China"], ["ASEAN", "ASEAN"], ["OTHER", "Other"], ["NOT_SURE", "Not sure"]];
const priorities = ["Supply Chain Resilience", "Market Access", "Cost", "Compliance", "Political Stability", "Implementation Speed"];

const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value = "") => String(value).replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#039;","\"":"&quot;"})[c]);

function showScreen(id) {
  const transition = id === "consultation" && $("#home").classList.contains("active");
  const activate = () => {
    document.querySelectorAll(".screen").forEach(screen => screen.classList.toggle("active", screen.id === id));
    const primaryNav = $("#primary-nav-action");
    const isHome = id === "home";
    primaryNav.dataset.screenTarget = isHome ? "consultation" : "home";
    primaryNav.innerHTML = isHome ? "Start New Decision <span>↗</span>" : "Home Page";
    primaryNav.classList.toggle("nav-cta", isHome);
    window.scrollTo({ top: 0, behavior: "instant" });
  };
  if (!transition) return activate();
  const wipe = $("#page-transition");
  wipe.classList.add("active");
  setTimeout(activate, 190);
  setTimeout(() => wipe.classList.remove("active"), 620);
}

function optionMarkup(selected, type) {
  const options = type === "production" ? productionCountries : marketCountries;
  return options.map(([value, label]) => `<option value="${value}" ${value === selected ? "selected" : ""}>${label}</option>`).join("");
}

function renderLocations(type) {
  const items = state[type];
  const target = $(`#${type === "production" ? "production" : "market"}-list`);
  const total = items.reduce((sum, item) => sum + (Number(item.share) || 0), 0);
  target.innerHTML = items.map((item, index) => `
    <div class="location-row">
      <select aria-label="${type} country" data-kind="${type}" data-index="${index}" data-field="country">${optionMarkup(item.country, type)}</select>
      <input class="share-slider" type="range" min="0" max="100" step="10" value="${Number(item.share) || 0}" aria-label="Production share slider" data-kind="${type}" data-index="${index}" data-field="share" />
      <input type="number" min="0" max="100" inputmode="numeric" placeholder="Share %" value="${item.share}" aria-label="Production share" data-kind="${type}" data-index="${index}" data-field="share" />
      ${(item.country === "OTHER") ? `<input class="other-location" placeholder="Enter country / region" data-kind="${type}" data-index="${index}" data-field="other" value="${item.other || ""}" />` : ""}
      ${items.length > 1 ? `<button type="button" data-remove="${type}" data-index="${index}" aria-label="Remove location">×</button>` : "<span></span>"}
    </div>`).join("");
  $(`#${type === "production" ? "production" : "market"}-total`).textContent = `Total ${total}%`;
  $(`#${type === "production" ? "production" : "market"}-total`).classList.toggle("invalid-total", total > 100);
}

function addLocation(type) {
  state[type].push({ country: type === "production" ? "VN" : "EU", share: "" });
  renderLocations(type);
}

function buildPriorityControls() {
  const grid = $("#priority-grid");
  grid.innerHTML = priorities.map((item, index) => `<div class="priority-item" draggable="true" data-priority="${item}"><span class="drag-handle" aria-hidden="true">⠿</span><b>${index + 1}</b><span>${item}</span></div>`).join("");
  let dragged = null;
  grid.addEventListener("dragstart", event => { dragged = event.target.closest(".priority-item"); dragged?.classList.add("dragging"); });
  grid.addEventListener("dragend", () => { dragged?.classList.remove("dragging"); dragged = null; refreshPriorityRanks(); });
  grid.addEventListener("dragover", event => {
    event.preventDefault();
    const target = event.target.closest(".priority-item");
    if (dragged && target && target !== dragged) grid.insertBefore(dragged, target);
  });
}

function refreshPriorityRanks() {
  document.querySelectorAll("#priority-grid .priority-item").forEach((item, index) => { item.querySelector("b").textContent = index + 1; });
}

function countryName(code) { return ([...productionCountries, ...marketCountries].find(([value]) => value === code) || [code, code])[1]; }
function readForm() {
  const form = $("#decision-form");
  const data = new FormData(form);
  const restrictions = [...document.querySelectorAll("#restriction-options input:checked")].map(item => item.value);
  const priorityValues = [...document.querySelectorAll("#priority-grid [data-priority]")].map((item, index) => ({ dimension: item.dataset.priority, weight: 6 - index }));
  return {
    company_name: data.get("company_name").trim(),
    industry: "other",
    products: data.get("products").trim(),
    home_country: data.get("home_country"),
    production_locations: state.production.filter(item => item.country),
    target_markets: state.markets.filter(item => item.country),
    decision_type: data.get("decision_type"),
    decision_question: data.get("decision_question").trim(),
    restrictions,
    investment_budget: data.get("investment_budget"),
    time_horizon: data.get("time_horizon"),
    notes: data.get("notes").trim(),
    key_supplier_count: data.get("key_supplier_count"),
    largest_supplier_share: data.get("largest_supplier_share"),
    priorities: priorityValues,
  };
}

function validateDecision(profile) {
  if (!profile.company_name || !profile.products || !profile.decision_question) return "Please complete the required company and decision fields.";
  if (!profile.production_locations.length || !profile.target_markets.length) return "Please add at least one production location and target market.";
  if (!profile.restrictions.length) return "Select at least one factor driving this decision.";
  return null;
}

function profileToBackend(profile) {
  const dimensions = { "Supply Chain Resilience": "supply_chain_resilience", "Market Access": "market_access", Cost: "cost_reduction", Compliance: "compliance", "Political Stability": "political_stability" };
  const production = profile.production_locations.map(item => ({ country: item.country, production_share: Number(item.share) || 0 }));
  const total = production.reduce((sum, item) => sum + item.production_share, 0);
  return {
    company: {
      company_name: profile.company_name,
      industry: "other",
      products: [profile.products],
      home_country: profile.home_country,
      production_locations: production,
      target_markets: profile.target_markets.map(item => item.country).filter(country => ["CN", "VN", "ID", "IN", "TH", "MY", "MX", "US", "EU"].includes(country)),
      decision_question: profile.decision_question,
      time_horizon: { "18m_3y": "2_5_years", "more_than_3y": "2_5_years" }[profile.time_horizon] || profile.time_horizon,
      priorities: profile.priorities.filter(item => dimensions[item.dimension]).map(item => ({ dimension: dimensions[item.dimension], weight: Number(item.weight) || 3 })),
      restrictions: profile.restrictions.filter(item => ["tariff_pressure", "export_controls", "sanctions_concerns", "local_regulation", "supplier_dependency", "labor_cost_increase", "logistics_problems", "none"].includes(item)),
      investment_budget_usd: profile.investment_budget ? Number(profile.investment_budget) : null,
      key_supplier_count: profile.key_supplier_count ? Number(profile.key_supplier_count) : null,
      largest_supplier_share: profile.largest_supplier_share ? Number(profile.largest_supplier_share) : null,
      notes: profile.notes || null,
    },
    productionTotal: total,
  };
}

function mockAssessment(profile) {
  const isUsMarket = profile.target_markets.some(item => item.country === "US");
  const locations = profile.production_locations.map(item => countryName(item.country)).join(" and ");
  return {
    company_profile: { ...profile, summary: `${profile.company_name} operates across ${locations}, with a decision horizon of ${profile.time_horizon.replaceAll("_", " ")}.` },
    risks: [
      { severity: "high", name: isUsMarket ? "US tariff exposure" : "Trade-policy exposure", description: isUsMarket ? "Changes in US trade policy could materially affect the landed-cost position of products serving this market." : "Changing trade measures may affect cost, lead time and market access across your current footprint.", evidence: [{ title: "Section 301 Investigations", publisher: "Office of the United States Trade Representative", date: "Official policy source" }, { title: "Global Trade Outlook and Statistics", publisher: "World Trade Organization", date: "Official source · 2026" }] },
      { severity: "high", name: "Supplier ecosystem dependency", description: "The current footprint may depend on supplier capacity, engineering support or critical inputs located outside the production market.", evidence: [{ title: "Trade in Value Added", publisher: "OECD", date: "Official dataset" }, { title: "Global Critical Minerals Outlook", publisher: "International Energy Agency", date: "Official report · 2025" }] },
      { severity: "medium", name: "Implementation and capacity risk", description: "Any change to production allocation requires time for qualification, workforce ramp-up and customer certification.", evidence: [{ title: "Geopolitical risk readiness", publisher: "McKinsey & Company", date: "Industry research" }] },
    ],
  };
}

async function tryAgent(profile) {
  const base = window.LOCUS_API_BASE || "";
  const apiKey = window.LOCUS_API_KEY;
  if (!base || !apiKey) return null;
  const payload = profileToBackend(profile);
  const supportedCountries = ["CN", "VN", "ID", "IN", "TH", "MY", "MX", "US", "EU"];
  if (payload.productionTotal !== 100 || !payload.company.target_markets.length || payload.company.production_locations.some(item => !supportedCountries.includes(item.country))) return null;
  const response = await fetch(`${base}/api/v1/assessments`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...payload, api_key: apiKey, llm_model: "deepseek-flash" }) });
  if (!response.ok) throw new Error("The assessment service could not complete this request.");
  return response.json();
}

function mapApiAssessment(api, profile) {
  if (!api) return mockAssessment(profile);
  return {
    company_profile: { ...profile, summary: api.company_profile?.summary || "Your decision profile has been prepared." },
    risks: (api.risks || []).map(risk => ({ severity: risk.severity || "medium", name: risk.name, description: risk.business_impact, evidence: (risk.evidence_ids || []).map(id => { const item = (api.evidence || []).find(evidence => evidence.evidence_id === id); return item ? { title: item.title, publisher: item.publisher, date: `${item.publication_date} · Authority ${item.authority_level}` } : { title: id, publisher: "Evidence reference", date: "" }; }) })),
  };
}

function renderAssessment(assessment) {
  const profile = assessment.company_profile;
  const productionText = profile.production_locations.map(item => `${countryName(item.country)}${item.share ? ` ${item.share}%` : ""}`).join(" · ");
  const marketsText = profile.target_markets.map(item => `${countryName(item.country)}${item.share ? ` ${item.share}%` : ""}`).join(" · ");
  $("#profile-grid").innerHTML = [
    ["Company", profile.company_name], ["Industry", profile.industry.replaceAll("_", " ")], ["Main product", profile.products],
    ["Home country", countryName(profile.home_country)], ["Production footprint", productionText], ["Target markets", marketsText],
    ["Decision context", profile.decision_question], ["Timeline", profile.time_horizon.replaceAll("_", " ")], ["Decision trigger", profile.restrictions.map(value => value.replaceAll("_", " ")).join(" · ")],
  ].map(([label, value]) => `<div><span>${escapeHtml(label)}</span><b>${escapeHtml(value || "Not specified")}</b></div>`).join("");
  $("#profile-extra").textContent = profile.notes || profile.summary;
  $("#risk-list").innerHTML = assessment.risks.map((risk, index) => `
    <article class="risk-item" id="${index === 0 ? "trade" : index === 1 ? "supply" : "political"}">
      <div class="risk-title"><span class="severity ${escapeHtml(risk.severity)}">${escapeHtml(risk.severity)}</span><h4>${escapeHtml(risk.name)}</h4></div>
      <p class="risk-description">${escapeHtml(risk.description)}</p>
      <p class="evidence-label">Supporting evidence</p>
      ${(risk.evidence || []).map(item => `<a class="evidence-link" href="#" onclick="return false"><span><b>${escapeHtml(item.publisher)}</b> — ${escapeHtml(item.title)}</span><span>${escapeHtml(item.date)} ↗</span></a>`).join("")}
    </article>`).join("");
}

function runAnalysis(profile) {
  showScreen("analysis");
  const stages = [...document.querySelectorAll("#analysis-stages li")];
  stages.forEach(item => { item.className = ""; item.querySelector("span").textContent = "Waiting"; });
  let position = 0;
  const timer = setInterval(() => {
    if (position > 0) { stages[position - 1].className = "done"; stages[position - 1].querySelector("span").textContent = "Complete"; }
    if (position < stages.length) { stages[position].className = "working"; stages[position].querySelector("span").textContent = "In progress"; position += 1; } else clearInterval(timer);
  }, 620);
  setTimeout(async () => {
    try {
      const api = await tryAgent(profile);
      state.assessment = mapApiAssessment(api, profile);
    } catch (error) {
      state.assessment = mockAssessment(profile);
      showToast("Showing the design preview. Connect the Agent service to use live analysis.");
    }
    stages.forEach(item => { item.className = "done"; item.querySelector("span").textContent = "Complete"; });
    renderAssessment(state.assessment);
    setTimeout(() => showScreen("assessment"), 480);
  }, 2800);
}

function showToast(message) { const toast = $("#toast"); toast.textContent = message; toast.classList.add("show"); setTimeout(() => toast.classList.remove("show"), 3600); }

function saveDraft() {
  const form = $("#decision-form");
  const values = {};
  new FormData(form).forEach((value, key) => {
    if (value instanceof File) return;
    if (values[key] === undefined) values[key] = value;
    else values[key] = [].concat(values[key], value);
  });
  localStorage.setItem(draftKey, JSON.stringify({ values, production: state.production, markets: state.markets }));
  updateFormProgress();
}

function updateFormProgress() {
  const form = $("#decision-form");
  const completed = [form.company_name.value, form.products.value, form.decision_question.value, state.production.some(item => item.country), state.markets.some(item => item.country), document.querySelectorAll("#restriction-options input:checked").length].filter(Boolean).length;
  $("#form-progress").textContent = `${Math.round((completed / 6) * 100)}% complete`;
}

function restoreDraft() {
  try {
    const draft = JSON.parse(localStorage.getItem(draftKey));
    if (!draft) return;
    if (Array.isArray(draft.production)) state.production = draft.production;
    if (Array.isArray(draft.markets)) state.markets = draft.markets;
    Object.entries(draft.values || {}).forEach(([name, rawValue]) => {
      const values = Array.isArray(rawValue) ? rawValue : [rawValue];
      document.querySelectorAll(`[name="${name}"]`).forEach(field => {
        if (field.type === "checkbox" || field.type === "radio") field.checked = values.includes(field.value);
        else if (field.type !== "file") field.value = values[0];
      });
    });
  } catch { localStorage.removeItem(draftKey); }
}

document.addEventListener("click", event => {
  const target = event.target.closest("[data-screen-target]");
  if (target) showScreen(target.dataset.screenTarget);
  if (event.target.closest("#add-production")) addLocation("production");
  if (event.target.closest("#add-market")) addLocation("markets");
  const remove = event.target.closest("[data-remove]");
  if (remove) { state[remove.dataset.remove].splice(Number(remove.dataset.index), 1); renderLocations(remove.dataset.remove); }
  if (event.target.closest("#show-advanced")) { $("#advanced-fields").hidden = false; $("#show-advanced").hidden = true; }
  if (event.target.closest("#hide-advanced")) { $("#advanced-fields").hidden = true; $("#show-advanced").hidden = false; }
  if (event.target.closest("#profile-expand")) { const extra = $("#profile-extra"); extra.hidden = !extra.hidden; $("#profile-expand").innerHTML = extra.hidden ? "View full profile <span>↓</span>" : "Hide full profile <span>↑</span>"; }
  if (event.target.closest("#simulate-button")) showToast("Scenario simulation is the next Agent step to connect.");
});

document.addEventListener("change", event => {
  const choice = event.target;
  if (choice.name === "decision_type") {
    $("#relocate-country").hidden = choice.value !== "Relocate production";
    $("#new-site-country").hidden = choice.value !== "Establish a new production site";
    $("#decision-other").hidden = choice.value !== "Other";
  }
  if (choice.closest("#restriction-options")) {
    $("#trigger-other").hidden = ![...document.querySelectorAll('#restriction-options input:checked')].some(item => item.value === "other");
  }
  if (choice.closest("#non-relocatable-options")) {
    $("#non-relocatable-other").hidden = ![...document.querySelectorAll('#non-relocatable-options input:checked')].some(item => item.value === "Other");
  }
});

document.addEventListener("input", event => {
  const input = event.target;
  if (!input.dataset.kind) return;
  const collection = state[input.dataset.kind];
  collection[Number(input.dataset.index)][input.dataset.field] = input.value;
  renderLocations(input.dataset.kind);
});

$("#decision-form").addEventListener("input", saveDraft);
$("#decision-form").addEventListener("change", saveDraft);

$("#decision-form").addEventListener("submit", event => {
  event.preventDefault();
  const profile = readForm();
  const error = validateDecision(profile);
  if (error) return showToast(error);
  runAnalysis(profile);
});

restoreDraft();
renderLocations("production");
renderLocations("markets");
buildPriorityControls();
document.querySelector('input[name="decision_type"]:checked')?.dispatchEvent(new Event("change", { bubbles: true }));
updateFormProgress();
