const state = {
  production: [{ country: "CN", share: "", other: "" }],
  markets: [{ country: "US", share: "", other: "" }],
  assessment: null,
};
const draftKey = "locus-decision-draft";

const productionCountries = [
  ["CN", "China"], ["VN", "Vietnam"], ["ID", "Indonesia"], ["IN", "India"],
  ["TH", "Thailand"], ["MX", "Mexico"], ["OTHER", "Other"], ["NOT_SURE", "Not sure"],
];
const marketCountries = [["US", "United States"], ["EU", "EU"], ["CN", "China"], ["ASEAN", "ASEAN"], ["OTHER", "Other"], ["NOT_SURE", "Not sure"]];
const priorities = ["Supply Chain Resilience", "Market Access", "Cost", "Compliance", "Political Stability", "Implementation Speed"];

/* Country codes, enum values and limits below mirror backend/app/schemas.py.
   Keeping them in sync is what lets the form talk to the Agent API. */
const BACKEND_COUNTRIES = ["CN", "VN", "ID", "IN", "TH", "MY", "MX", "US", "EU"];
const BACKEND_PRIORITY_DIMENSION = {
  "Supply Chain Resilience": "supply_chain_resilience",
  "Market Access": "market_access",
  Cost: "cost_reduction",
  Compliance: "compliance",
  "Political Stability": "political_stability",
};
/* Only these triggers exist in the backend enum. The remaining options are kept
   in the UI because they matter to users, and are forwarded through `notes`. */
const TRIGGER_BACKEND_VALUE = {
  tariff_pressure: "tariff_pressure",
  labor_cost_increase: "labor_cost_increase",
  supplier_dependency: "supplier_dependency",
  local_regulation: "local_regulation",
};
const TRIGGER_LABELS = {
  tariff_pressure: "Tariff / trade policy changes",
  geopolitical_uncertainty: "Geopolitical uncertainty",
  labor_cost_increase: "Rising production costs",
  supplier_dependency: "Supplier dependency",
  market_access: "Market access",
  local_regulation: "Regulatory changes",
  capacity_expansion: "Capacity expansion",
  other: "Other",
};
const TIME_HORIZON_BACKEND_VALUE = {
  within_6_months: "within_6_months",
  "6_18_months": "6_18_months",
  "18m_3y": "2_5_years",
  more_than_3y: "2_5_years",
};
const STAGE_BY_AGENT = { ProfileAgent: 0, ResearchAgent: 1, RiskAgent: 2, ScenarioAgent: 3, AdvisorAgent: 3, VerificationAgent: 3 };
const TRANSITION_LABEL = { consultation: "Opening decision workspace", home: "Returning to overview", history: "Opening my decisions", news: "Opening news", analysis: "Preparing assessment", assessment: "Opening initial assessment" };

const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value = "") => String(value).replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#039;","\"":"&quot;"})[c]);
const countryName = (code) => ([...productionCountries, ...marketCountries].find(([value]) => value === code) || [code, code])[1];

if ("scrollRestoration" in history) history.scrollRestoration = "manual";

/* ------------------------------------------------------------------ screens */

function showScreen(id) {
  const current = document.querySelector(".screen.active")?.id;
  const curtain = id === "consultation" && current !== "consultation";
  window.scrollTo({ top: 0, behavior: "auto" });

  const activate = () => {
    document.querySelectorAll(".screen").forEach(screen => screen.classList.toggle("active", screen.id === id));
    const primaryNav = $("#primary-nav-action");
    const isHome = id === "home";
    primaryNav.dataset.screenTarget = isHome ? "consultation" : "home";
    primaryNav.innerHTML = isHome ? "Start New Decision <span>↗</span>" : "Home Page";
    primaryNav.classList.toggle("nav-cta", isHome);
    window.scrollTo({ top: 0, behavior: "auto" });
  };

  if (!curtain) return activate();

  const overlay = $("#page-transition");
  $("#page-transition-label").textContent = TRANSITION_LABEL[id] || "Loading";
  overlay.classList.add("active");
  setTimeout(activate, 340);
  setTimeout(() => overlay.classList.remove("active"), 460);
}

/* -------------------------------------------------------------------- form */

function optionMarkup(selected, type) {
  const options = type === "production" ? productionCountries : marketCountries;
  return options.map(([value, label]) => `<option value="${value}" ${value === selected ? "selected" : ""}>${label}</option>`).join("");
}

function renderLocations(type) {
  const items = state[type];
  const target = $(type === "production" ? "#production-list" : "#market-list");
  target.innerHTML = items.map((item, index) => `
    <div class="location-row">
      <select aria-label="${type} country" data-kind="${type}" data-index="${index}" data-field="country">${optionMarkup(item.country, type)}</select>
      <input class="share-slider" type="range" min="0" max="100" step="10" value="${Number(item.share) || 0}" aria-label="${type} share slider" data-kind="${type}" data-index="${index}" data-field="share" />
      <input type="number" min="0" max="100" inputmode="numeric" placeholder="Share %" value="${escapeHtml(item.share)}" aria-label="${type} share" data-kind="${type}" data-index="${index}" data-field="share" />
      ${item.country === "OTHER" ? `<input class="other-location" placeholder="Enter country / region" data-kind="${type}" data-index="${index}" data-field="other" value="${escapeHtml(item.other)}" />` : ""}
      ${items.length > 1 ? `<button type="button" data-remove="${type}" data-index="${index}" aria-label="Remove location">×</button>` : "<span></span>"}
    </div>`).join("");
  updateTotal(type);
}

function updateTotal(type) {
  const total = state[type].reduce((sum, item) => sum + (Number(item.share) || 0), 0);
  const element = $(type === "production" ? "#production-total" : "#market-total");
  element.textContent = `Total ${total}%`;
  element.classList.toggle("invalid-total", total > 0 && total !== 100);
}

function addLocation(type) {
  state[type].push({ country: type === "production" ? "VN" : "EU", share: "", other: "" });
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

function updateSummaryCount() {
  const value = $("#decision-form").notes.value.trim();
  const words = value ? value.split(/\s+/).length : 0;
  const counter = $("#summary-count");
  counter.textContent = `${words} / 100 words`;
  counter.classList.toggle("over", words > 100);
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function renderUploadList(zone) {
  const input = zone.querySelector('input[type="file"]');
  const list = zone.querySelector("[data-upload-list]");
  const files = [...(input.files || [])];
  list.hidden = files.length === 0;
  list.innerHTML = files.map(file => `<li><span>${escapeHtml(file.name)}</span><span>${formatSize(file.size)}</span></li>`).join("");
  zone.classList.toggle("has-files", files.length > 0);
}

function setupUploadZones() {
  document.querySelectorAll("[data-upload-zone]").forEach(zone => {
    const input = zone.querySelector('input[type="file"]');
    input.addEventListener("change", () => renderUploadList(zone));
    zone.addEventListener("dragover", event => { event.preventDefault(); zone.classList.add("dragover"); });
    zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
    zone.addEventListener("drop", event => {
      event.preventDefault();
      zone.classList.remove("dragover");
      const dropped = [...(event.dataTransfer?.files || [])];
      if (!dropped.length) return;
      try {
        const transfer = new DataTransfer();
        [...(input.files || []), ...dropped].forEach(file => transfer.items.add(file));
        input.files = transfer.files;
      } catch { /* browsers without DataTransfer keep the browse path only */ }
      renderUploadList(zone);
    });
  });
}

function readForm() {
  const form = $("#decision-form");
  const data = new FormData(form);
  const restrictions = [...document.querySelectorAll("#restriction-options input:checked")].map(item => item.value);
  const priorityValues = [...document.querySelectorAll("#priority-grid [data-priority]")].map(item => ({ dimension: item.dataset.priority }));
  const text = (name) => (data.get(name) || "").toString().trim();
  return {
    company_name: text("company_name"),
    products: text("products"),
    home_country: data.get("home_country"),
    production_locations: state.production.filter(item => item.country),
    target_markets: state.markets.filter(item => item.country),
    decision_type: text("decision_type"),
    relocate_destination: text("relocate_destination"),
    new_site_candidates: text("new_site_candidates"),
    decision_other: text("decision_other"),
    decision_question: text("decision_question"),
    restrictions,
    trigger_notes: text("trigger_notes"),
    investment_budget: data.get("investment_budget"),
    time_horizon: data.get("time_horizon"),
    notes: text("notes"),
    priorities: priorityValues,
  };
}

function validateDecision(profile) {
  if (!profile.company_name || !profile.products || !profile.decision_question) return "Please complete the required company and decision fields.";
  if (!profile.production_locations.length || !profile.target_markets.length) return "Please add at least one production location and target market.";
  if (!profile.restrictions.length) return "Select at least one factor driving this decision.";
  return null;
}

/* ------------------------------------------------- backend API contract */

function locationLabel(item) {
  const name = countryName(item.country);
  return item.country === "OTHER" && item.other ? `${name} (${item.other})` : name;
}

function buildDecisionQuestion(profile) {
  const detail = profile.relocate_destination || profile.new_site_candidates || profile.decision_other;
  if (!profile.decision_type) return profile.decision_question;
  return detail ? `${profile.decision_type} (${detail}): ${profile.decision_question}` : `${profile.decision_type}: ${profile.decision_question}`;
}

function buildNotes(profile) {
  const parts = [];
  const unmapped = profile.restrictions.filter(value => !TRIGGER_BACKEND_VALUE[value]);
  if (unmapped.length) parts.push(`Drivers not mapped to API codes: ${unmapped.map(value => TRIGGER_LABELS[value] || value).join(", ")}.`);
  if (profile.trigger_notes) parts.push(`Driver note: ${profile.trigger_notes}`);
  const outsideProduction = profile.production_locations.filter(item => !BACKEND_COUNTRIES.includes(item.country)).map(locationLabel);
  const outsideMarkets = profile.target_markets.filter(item => !BACKEND_COUNTRIES.includes(item.country)).map(locationLabel);
  if (outsideProduction.length) parts.push(`Production locations outside API country codes: ${outsideProduction.join(", ")}.`);
  if (outsideMarkets.length) parts.push(`Target markets outside API country codes: ${outsideMarkets.join(", ")}.`);
  if (profile.notes) parts.push(profile.notes);
  return parts.join("\n").slice(0, 4000) || null;
}

/* Returns the request body for POST /api/v1/assessments plus the reasons the
   payload cannot be sent. The API rejects shares that do not total 100, so the
   page falls back to the local preview instead of sending a broken request. */
function buildBackendPayload(profile) {
  const issues = [];
  const production = profile.production_locations
    .filter(item => BACKEND_COUNTRIES.includes(item.country))
    .map(item => ({ country: item.country, production_share: Number(item.share) || 0 }));
  const productionTotal = production.reduce((sum, item) => sum + item.production_share, 0);
  const markets = profile.target_markets.filter(item => BACKEND_COUNTRIES.includes(item.country)).map(item => item.country);

  const outsideProduction = profile.production_locations.filter(item => !BACKEND_COUNTRIES.includes(item.country)).map(locationLabel);
  const outsideMarkets = profile.target_markets.filter(item => !BACKEND_COUNTRIES.includes(item.country)).map(locationLabel);
  if (outsideProduction.length) issues.push(`The assessment API has no country code for: ${outsideProduction.join(", ")}.`);
  if (outsideMarkets.length) issues.push(`The assessment API has no country code for: ${outsideMarkets.join(", ")}.`);
  if (!markets.length) issues.push("Add at least one target market.");
  if (production.length && productionTotal !== 100) issues.push(`Production shares total ${productionTotal}%, and the assessment API requires exactly 100%.`);

  const mappedPriorities = profile.priorities
    .map((item, index) => ({ dimension: BACKEND_PRIORITY_DIMENSION[item.dimension], weight: Math.max(0, 5 - index) }))
    .filter(item => item.dimension);

  const payload = {
    company: {
      company_name: profile.company_name,
      // The Agent API requires an industry value. The form follows profile list.md
      // and no longer asks for one, so it is reported as "other".
      industry: "other",
      products: [profile.products],
      home_country: profile.home_country,
      production_locations: production,
      target_markets: markets,
      decision_question: buildDecisionQuestion(profile),
      time_horizon: TIME_HORIZON_BACKEND_VALUE[profile.time_horizon] || "6_18_months",
      priorities: mappedPriorities.length ? mappedPriorities : [{ dimension: "supply_chain_resilience", weight: 3 }],
      restrictions: profile.restrictions.map(value => TRIGGER_BACKEND_VALUE[value]).filter(Boolean),
      investment_budget_usd: profile.investment_budget ? Number(profile.investment_budget) : null,
      notes: buildNotes(profile),
    },
    productionTotal,
  };
  return { issues, payload };
}

async function streamAssessment(payload, onStage) {
  const response = await fetch(`${window.LOCUS_API_BASE}/api/v1/assessments/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload, api_key: window.LOCUS_API_KEY, llm_model: window.LOCUS_MODEL || "deepseek-flash" }),
  });
  if (!response.ok || !response.body) throw new Error(`Assessment service returned ${response.status}`);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let assessment = null;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (!line.trim()) continue;
      let event;
      try { event = JSON.parse(line); } catch { continue; }
      if (event.type === "stage") onStage(event);
      else if (event.type === "assessment") assessment = event.assessment;
      else if (event.type === "error") throw new Error(event.message || "Assessment failed");
    }
  }
  if (!assessment) throw new Error("Assessment service returned no result");
  return assessment;
}

function mapApiAssessment(api, profile) {
  const library = api.evidence || [];
  return {
    company_profile: { ...profile, summary: api.company_profile?.summary || "Your decision profile has been prepared." },
    risks: (api.risks || []).map(risk => ({
      severity: risk.severity || "medium",
      name: risk.name,
      description: risk.business_impact,
      uncertainty: risk.uncertainty || "",
      evidence: (risk.evidence_ids || []).map(id => {
        const item = library.find(entry => entry.evidence_id === id);
        if (!item) return { title: id, publisher: "Evidence reference", date: "", url: null };
        return {
          title: item.title,
          publisher: item.publisher,
          date: [item.publication_date, item.authority_level ? `Authority ${item.authority_level}` : ""].filter(Boolean).join(" · "),
          url: item.url || null,
        };
      }),
    })),
  };
}

function mockAssessment(profile) {
  const isUsMarket = profile.target_markets.some(item => item.country === "US");
  const locations = profile.production_locations.map(item => countryName(item.country)).join(" and ");
  const horizon = (profile.time_horizon || "6_18_months").replaceAll("_", " ");
  return {
    company_profile: { ...profile, summary: `${profile.company_name} operates across ${locations}, with a decision horizon of ${horizon}.` },
    risks: [
      { severity: "high", name: isUsMarket ? "US tariff exposure" : "Trade-policy exposure", description: isUsMarket ? "Changes in US trade policy could materially affect the landed-cost position of products serving this market." : "Changing trade measures may affect cost, lead time and market access across your current footprint.", uncertainty: "Announced measures can change before implementation, and product-level classifications may differ from the headline policy.", evidence: [{ title: "Section 301 Investigations", publisher: "Office of the United States Trade Representative", date: "Official policy source", url: null }, { title: "Global Trade Outlook and Statistics", publisher: "World Trade Organization", date: "Official source · 2026", url: null }] },
      { severity: "high", name: "Supplier ecosystem dependency", description: "The current footprint may depend on supplier capacity, engineering support or critical inputs located outside the production market.", uncertainty: "Supplier concentration is inferred from your inputs rather than verified bill-of-materials data.", evidence: [{ title: "Trade in Value Added", publisher: "OECD", date: "Official dataset", url: null }, { title: "Global Critical Minerals Outlook", publisher: "International Energy Agency", date: "Official report · 2025", url: null }] },
      { severity: "medium", name: "Implementation and capacity risk", description: "Any change to production allocation requires time for qualification, workforce ramp-up and customer certification.", uncertainty: "Certification lead times are company specific and are not covered by public sources.", evidence: [{ title: "Geopolitical risk readiness", publisher: "McKinsey & Company", date: "Industry research", url: null }] },
    ],
  };
}

/* --------------------------------------------------------------- analysis */

function setStage(index, status) {
  const item = document.querySelectorAll("#analysis-stages li")[index];
  if (!item) return;
  item.classList.toggle("working", status === "working");
  item.classList.toggle("done", status === "done");
  item.querySelector("span").textContent = status === "done" ? "Complete" : status === "working" ? "In progress" : "Waiting";
}

function resetStages() {
  document.querySelectorAll("#analysis-stages li").forEach((item, index) => setStage(index, "idle"));
}

function completeStages() {
  document.querySelectorAll("#analysis-stages li").forEach((item, index) => setStage(index, "done"));
}

function handleStageEvent(event) {
  const index = STAGE_BY_AGENT[event.agent];
  if (index === undefined) return;
  if (event.status === "started") {
    for (let earlier = 0; earlier < index; earlier += 1) setStage(earlier, "done");
    setStage(index, "working");
  } else {
    setStage(index, "done");
  }
}

function runPreviewTimeline(profile) {
  const total = document.querySelectorAll("#analysis-stages li").length;
  let position = 0;
  const timer = setInterval(() => {
    if (position > 0) setStage(position - 1, "done");
    if (position < total) { setStage(position, "working"); position += 1; }
    else clearInterval(timer);
  }, 620);
  setTimeout(() => {
    clearInterval(timer);
    completeStages();
    state.assessment = mockAssessment(profile);
    renderAssessment(state.assessment);
    setTimeout(() => showScreen("assessment"), 420);
  }, 2800);
}

async function runAnalysis(profile) {
  showScreen("analysis");
  resetStages();
  const { issues, payload } = buildBackendPayload(profile);
  const configured = Boolean(window.LOCUS_API_BASE && window.LOCUS_API_KEY);

  if (configured && !issues.length) {
    try {
      const api = await streamAssessment(payload, handleStageEvent);
      state.assessment = mapApiAssessment(api, profile);
      completeStages();
      renderAssessment(state.assessment);
      setTimeout(() => showScreen("assessment"), 320);
      return;
    } catch (error) {
      showToast("Live agent unavailable — showing the local preview.");
    }
  } else if (configured && issues.length) {
    showToast(`${issues[0]} Showing the local preview instead.`);
  }
  runPreviewTimeline(profile);
}

/* ------------------------------------------------------------- assessment */

function renderAssessment(assessment) {
  const profile = assessment.company_profile;
  const productionText = profile.production_locations.map(item => `${countryName(item.country)}${item.share ? ` ${item.share}%` : ""}`).join(" · ");
  const marketsText = profile.target_markets.map(item => `${countryName(item.country)}${item.share ? ` ${item.share}%` : ""}`).join(" · ");
  $("#profile-grid").innerHTML = [
    ["Company", profile.company_name], ["Industry", (profile.industry || "other").replaceAll("_", " ")], ["Main product", profile.products],
    ["Home country", countryName(profile.home_country)], ["Production footprint", productionText], ["Target markets", marketsText],
    ["Decision context", profile.decision_question], ["Timeline", (profile.time_horizon || "").replaceAll("_", " ")], ["Decision trigger", profile.restrictions.map(value => TRIGGER_LABELS[value] || value.replaceAll("_", " ")).join(" · ")],
  ].map(([label, value]) => `<div><span>${escapeHtml(label)}</span><b>${escapeHtml(value || "Not specified")}</b></div>`).join("");
  $("#profile-extra").textContent = profile.notes || profile.summary;
  $("#risk-list").innerHTML = assessment.risks.map((risk, index) => `
    <article class="risk-item" id="${index === 0 ? "trade" : index === 1 ? "supply" : "political"}">
      <div class="risk-title"><span class="severity ${escapeHtml(risk.severity)}">${escapeHtml(risk.severity)}</span><h4>${escapeHtml(risk.name)}</h4></div>
      <p class="risk-description">${escapeHtml(risk.description)}</p>
      <p class="evidence-label">Supporting evidence</p>
      ${(risk.evidence || []).map(item => {
        const body = `<span><b>${escapeHtml(item.publisher)}</b> — ${escapeHtml(item.title)}</span><span>${escapeHtml(item.date)}${item.url ? " ↗" : ""}</span>`;
        return item.url
          ? `<a class="evidence-link" href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">${body}</a>`
          : `<div class="evidence-link static">${body}</div>`;
      }).join("")}
      ${risk.uncertainty ? `<p class="risk-uncertainty"><b>Uncertainty</b> · ${escapeHtml(risk.uncertainty)}</p>` : ""}
    </article>`).join("");
}

function showToast(message) { const toast = $("#toast"); toast.textContent = message; toast.classList.add("show"); setTimeout(() => toast.classList.remove("show"), 4200); }

/* ------------------------------------------------------------ draft state */

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
  markDraftSaved();
}

function updateFormProgress() {
  const form = $("#decision-form");
  const checks = [
    form.company_name.value,
    form.products.value,
    form.decision_question.value,
    state.production.some(item => item.country),
    state.markets.some(item => item.country),
    document.querySelectorAll("#restriction-options input:checked").length,
  ];
  const percent = Math.round((checks.filter(Boolean).length / checks.length) * 100);
  const value = $("#completion-value");
  const fill = $("#completion-fill");
  if (value) value.textContent = `${percent}%`;
  if (fill) fill.style.width = `${percent}%`;
}

function markDraftSaved() {
  const label = $("#completion-saved");
  if (!label) return;
  const now = new Date();
  label.textContent = `Draft saved automatically · ${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
}

function buildEstablishedYears() {
  const list = $("#established-years");
  if (!list) return;
  const current = new Date().getFullYear();
  const years = [];
  for (let year = current; year >= current - 160; year -= 1) years.push(`<option value="${year}"></option>`);
  list.innerHTML = years.join("");
}

function restoreDraft() {
  try {
    const draft = JSON.parse(localStorage.getItem(draftKey));
    if (!draft) return;
    if (Array.isArray(draft.production)) state.production = draft.production.map(item => ({ other: "", ...item }));
    if (Array.isArray(draft.markets)) state.markets = draft.markets.map(item => ({ other: "", ...item }));
    Object.entries(draft.values || {}).forEach(([name, rawValue]) => {
      const values = Array.isArray(rawValue) ? rawValue : [rawValue];
      document.querySelectorAll(`[name="${name}"]`).forEach(field => {
        if (field.type === "checkbox" || field.type === "radio") field.checked = values.includes(field.value);
        else if (field.type !== "file") field.value = values[0];
      });
    });
  } catch { localStorage.removeItem(draftKey); }
}

/* --------------------------------------------------------------- bindings */

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
  if (event.target.closest("#simulate-button")) showToast("Scenario simulation connects to the Agent in the next build step.");
});

document.addEventListener("change", event => {
  const changed = event.target;
  if (changed.dataset.kind && changed.dataset.field === "country") { renderLocations(changed.dataset.kind); return; }
  if (changed.name === "decision_type") {
    $("#relocate-country").hidden = changed.value !== "Relocate production";
    $("#new-site-country").hidden = changed.value !== "Establish a new production site";
    $("#decision-other").hidden = changed.value !== "Other";
    return;
  }
  if (changed.closest("#restriction-options")) {
    $("#trigger-other").hidden = ![...document.querySelectorAll("#restriction-options input:checked")].some(item => item.value === "other");
    return;
  }
  if (changed.closest("#non-relocatable-options")) {
    $("#non-relocatable-other").hidden = ![...document.querySelectorAll("#non-relocatable-options input:checked")].some(item => item.value === "Other");
  }
});

document.addEventListener("input", event => {
  const input = event.target;
  if (input.dataset.kind) {
    const item = state[input.dataset.kind][Number(input.dataset.index)];
    if (!item) return;
    item[input.dataset.field] = input.value;
    if (input.dataset.field === "share") {
      const row = input.closest(".location-row");
      const twin = row.querySelector(input.type === "range" ? 'input[type="number"]' : 'input[type="range"]');
      if (twin) twin.value = input.type === "range" ? input.value : (Number(input.value) || 0);
      updateTotal(input.dataset.kind);
    }
    return;
  }
  if (input.name === "notes") updateSummaryCount();
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
setupUploadZones();
buildEstablishedYears();
updateSummaryCount();
document.querySelector('input[name="decision_type"]:checked')?.dispatchEvent(new Event("change", { bubbles: true }));
updateFormProgress();
