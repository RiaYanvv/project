const state = {
  production: [{ country: "CN", share: "", other: "" }],
  markets: [{ country: "US", share: "", other: "" }],
  assessment: null,
  projectId: null,
  parentProjectId: null,
  reportOutdated: false,
  // True once the user actually reorders the priority list. Until then the
  // scenario score must treat every factor as equally important.
  prioritiesDeclared: false,
};
let runInFlight = false;
const draftKey = "locus-decision-draft";
const projectsKey = "locus-decision-projects";

/* Browsers can block localStorage (private mode, security software, full quota).
   Every storage call is guarded so the consultation still works without it. */
function storageAvailable() {
  try {
    localStorage.setItem("locus-storage-probe", "1");
    localStorage.removeItem("locus-storage-probe");
    return true;
  } catch {
    return false;
  }
}
const canStore = storageAvailable();

const productionCountries = [
  ["CN", "China"], ["VN", "Vietnam"], ["ID", "Indonesia"], ["IN", "India"],
  ["TH", "Thailand"], ["MX", "Mexico"], ["OTHER", "Other"], ["NOT_SURE", "Not sure"],
];
const marketCountries = [["US", "United States"], ["EU", "EU"], ["CN", "China"], ["ASEAN", "ASEAN"], ["OTHER", "Other"], ["NOT_SURE", "Not sure"]];
/* Home country is asked with a broader list than production/markets because the
   headquarters can be anywhere. Codes the Agent API knows are sent as codes;
   anything else is sent as its readable name, and "Other" accepts free text. */
const HOME_COUNTRY_NAMES = {
  CN: "China", VN: "Vietnam", ID: "Indonesia", IN: "India", TH: "Thailand",
  MY: "Malaysia", MX: "Mexico", US: "United States", JP: "Japan",
  KR: "South Korea", DE: "Germany", PL: "Poland", HU: "Hungary", FR: "France",
  ES: "Spain", IT: "Italy", TR: "Turkey", BR: "Brazil", PH: "Philippines",
  SG: "Singapore",
};
const priorities = ["Supply Chain Resilience", "Market Access", "Cost", "Compliance", "Political Stability", "Implementation Speed"];

/* Dimensions the backend can weight. Used when the user never ranked the
   priorities so every factor counts the same instead of a default order. */
const BACKEND_SCORING_DIMENSIONS = ["cost_reduction", "supply_chain_resilience", "market_access", "political_stability", "compliance"];
const EQUAL_PRIORITY_WEIGHT = 3;

/* Country codes, enum values and limits below mirror backend/app/schemas.py.
   Keeping them in sync is what lets the form talk to the Agent API. */
const BACKEND_COUNTRIES = ["CN", "VN", "ID", "IN", "TH", "MY", "MX", "US", "EU", "ASEAN"];
/* The product scope is the EV / battery supply chain, so industry is a fixed
   value rather than a form field (see profile list.md). */
const FIXED_INDUSTRY = "battery_ev";
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
const INDUSTRY_LABELS = { battery_ev: "Battery & EV", semiconductor: "Semiconductor", electronics: "Electronics", optoelectronics: "Optoelectronics", industrial_equipment: "Industrial equipment", other: "Other manufacturing" };
const STAGE_BY_AGENT = { ProfileAgent: 0, ResearchAgent: 1, RiskAgent: 2, ScenarioAgent: 3, AdvisorAgent: 3, VerificationAgent: 3 };
const TRANSITION_LABEL = { consultation: "Opening decision workspace", home: "Returning to overview", history: "Opening my decisions", news: "Opening news", analysis: "Preparing assessment", assessment: "Opening initial assessment" };

const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value = "") => String(value).replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#039;","\"":"&quot;"})[c]);
const countryName = (code) => ([...productionCountries, ...marketCountries].find(([value]) => value === code) || [code, code])[1];

/* A location row set to "Other" carries the country the user typed, so show that
   name instead of the literal word "Other" (profile list.md). */
function locationName(item) {
  if (item && typeof item === "object") {
    if (item.country === "OTHER") return String(item.other || "").trim() || "Other";
    return countryName(item.country);
  }
  return countryName(item);
}

/* Home country may be a code the API knows, a name for countries outside its
   enum, or free text typed under "Other". */
function homeCountryLabel(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  return HOME_COUNTRY_NAMES[raw] || countryName(raw);
}

function homeCountryForApi(value) {
  const raw = String(value || "").trim();
  if (!raw) return "CN";
  if (BACKEND_COUNTRIES.includes(raw)) return raw;
  return HOME_COUNTRY_NAMES[raw] || raw;
}

function readHomeCountry(form) {
  const value = form.home_country ? form.home_country.value : "CN";
  if (value !== "OTHER") return value;
  const typed = (form.home_country_other?.value || "").trim();
  return typed || "Other";
}

if ("scrollRestoration" in history) history.scrollRestoration = "manual";

/* ------------------------------------------------------------------ screens */

/* Screens are rendered on demand, so navigating "back" to a screen that was not
   rendered in this session (for example Report -> Consultation after resuming a
   decision) used to show it empty. Every navigation now guarantees content. */
function ensureScreenContent(id) {
  if (id === "history") { renderProjects(); return; }
  if (id === "chat") {
    renderChatCategories();
    renderChatContext();
    renderChatLog();
    renderChatMeta();
    return;
  }
  const assessment = state.assessment;
  if (!assessment) return;
  if (id === "assessment") renderAssessment(assessment);
  else if (id === "scenarios") renderScenarios(assessment);
  else if (id === "report") renderReportPage();
}

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
    try { ensureScreenContent(id); } catch (error) { console.error("screen render failed", error); }
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
  target.innerHTML = items.map((item, index) => {
    // "Not sure" means the location is unknown, so its share field is parked
    // and excluded from the total until a concrete location is chosen.
    const unsure = item.country === "NOT_SURE";
    return `
    <div class="location-row${unsure ? " is-unsure" : ""}">
      <select aria-label="${type} country" data-kind="${type}" data-index="${index}" data-field="country">${optionMarkup(item.country, type)}</select>
      <input class="share-slider" type="range" min="0" max="100" step="10" value="${Number(item.share) || 0}" aria-label="${type} share slider" data-kind="${type}" data-index="${index}" data-field="share" ${unsure ? "disabled" : ""} />
      <input type="number" min="0" max="100" inputmode="numeric" placeholder="${unsure ? "N/A" : "Share %"}" value="${escapeHtml(item.share)}" aria-label="${type} share" data-kind="${type}" data-index="${index}" data-field="share" ${unsure ? "disabled" : ""} />
      ${item.country === "OTHER" ? `<input class="other-location" placeholder="Enter country / region" data-kind="${type}" data-index="${index}" data-field="other" value="${escapeHtml(item.other)}" />` : ""}
      ${items.length > 1 ? `<button type="button" data-remove="${type}" data-index="${index}" aria-label="Remove location">×</button>` : "<span></span>"}
    </div>`;
  }).join("");
  updateTotal(type);
}

/* Shares may be left blank ("recommended but not required") and "Not sure"
   rows never contribute, so the total only reflects declared locations. */
function locationShareTotal(type) {
  return state[type].reduce((sum, item) => sum + (item.country === "NOT_SURE" ? 0 : (Number(item.share) || 0)), 0);
}

function updateTotal(type) {
  const total = locationShareTotal(type);
  const element = $(type === "production" ? "#production-total" : "#market-total");
  const warning = $(type === "production" ? "#production-warning" : "#market-warning");
  const over = total > 100;
  const note = over ? "exceeds 100%" : total > 0 ? "not 100% yet" : "";
  element.innerHTML = `<span>${escapeHtml(`Total ${total}%`)}</span>${note ? `<span class="total-note">${escapeHtml(note)}</span>` : ""}`;
  element.classList.toggle("invalid-total", total > 0 && !over);
  element.classList.toggle("over-total", over);
  if (warning) warning.hidden = !over;
}

function addLocation(type) {
  state[type].push({ country: type === "production" ? "VN" : "EU", share: "", other: "" });
  renderLocations(type);
}

function renderPriorityItems() {
  $("#priority-grid").innerHTML = priorities.map((item, index) => `<div class="priority-item" draggable="true" data-priority="${item}"><span class="drag-handle" aria-hidden="true">⠿</span><b>${index + 1}</b><span>${item}</span></div>`).join("");
}

function buildPriorityControls() {
  const grid = $("#priority-grid");
  renderPriorityItems();
  let dragged = null;
  grid.addEventListener("dragstart", event => { dragged = event.target.closest(".priority-item"); dragged?.classList.add("dragging"); });
  grid.addEventListener("dragend", () => {
    dragged?.classList.remove("dragging");
    dragged = null;
    refreshPriorityRanks();
    // Dragging is the only way to express a ranking, so it is what marks the
    // priorities as user-declared. The list ships with a default order that must
    // not be mistaken for the user's own ranking.
    state.prioritiesDeclared = true;
  });
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
    industry: FIXED_INDUSTRY,
    products: text("products"),
    home_country: readHomeCountry(form),
    production_locations: state.production.filter(item => item.country),
    target_markets: state.markets.filter(item => item.country),
    decision_type: text("decision_type"),
    relocate_destination: text("relocate_destination"),
    new_site_candidates: text("new_site_candidates"),
    decision_other: text("decision_other"),
    decision_question: text("decision_question"),
    restrictions,
    trigger_notes: text("trigger_notes"),
    footprint_notes: text("footprint_notes"),
    investment_budget: data.get("investment_budget"),
    time_horizon: data.get("time_horizon"),
    notes: text("notes"),
    priorities: priorityValues,
    priorities_declared: Boolean(state.prioritiesDeclared),
  };
}

/* profile list.md: submitting with missing answers should jump back to the
   question that still needs input and tell the user what is missing. */
function findValidationIssue(profile) {
  const form = $("#decision-form");
  const issues = [];
  if (!profile.company_name) issues.push({ message: "Company name is required.", target: form.company_name });
  if (!profile.products) issues.push({ message: "Main product / business is required.", target: form.products });
  if (!profile.decision_type) issues.push({ message: "Select the decision you are trying to make.", target: $("#decision-options") });
  if (!profile.production_locations.length) issues.push({ message: "Add at least one production location.", target: $("#production-list") });
  if (!profile.target_markets.length) issues.push({ message: "Add at least one target market.", target: $("#market-list") });
  if (!profile.restrictions.length) issues.push({ message: "Select at least one factor driving this decision.", target: $("#restriction-options") });
  // Shares may fall short of 100% (that is only a hint), but a total above
  // 100% is impossible and is refused here on both sections.
  const productionTotal = locationShareTotal("production");
  if (productionTotal > 100) issues.push({ message: `Production shares total ${productionTotal}%. Lower them to 100% or less.`, target: $("#production-list") });
  const marketTotal = locationShareTotal("markets");
  if (marketTotal > 100) issues.push({ message: `Market shares total ${marketTotal}%. Lower them to 100% or less.`, target: $("#market-list") });
  return issues;
}

/* ------------------------------------------------- backend API contract */

function locationLabel(item) {
  // locationName already resolves "Other" to the country the user typed.
  return locationName(item);
}

function buildDecisionQuestion(profile) {
  const detail = profile.relocate_destination || profile.new_site_candidates || profile.decision_other;
  const type = profile.decision_type || "Maintain current production structure";
  const composed = detail ? `${type} (${detail})` : type;
  // The free-text box is optional (see profile list.md), but the Agent API
  // requires a decision_question string, so the selected option stands in for it.
  return profile.decision_question ? `${composed}: ${profile.decision_question}` : composed;
}

function buildNotes(profile) {
  const parts = [];
  const unmapped = profile.restrictions.filter(value => !TRIGGER_BACKEND_VALUE[value]);
  if (unmapped.length) parts.push(`Drivers not mapped to API codes: ${unmapped.map(value => TRIGGER_LABELS[value] || value).join(", ")}.`);
  if (profile.trigger_notes) parts.push(`Driver note: ${profile.trigger_notes}`);
  if (profile.footprint_notes) parts.push(`Footprint note: ${profile.footprint_notes}`);
  // "Other" rows now travel as structured countries, so only genuinely
  // unplaceable entries ("Not sure") are listed here.
  const unmappedProduction = profile.production_locations.filter(item => item.country !== "OTHER" && !BACKEND_COUNTRIES.includes(item.country)).map(locationLabel);
  const unmappedMarkets = profile.target_markets.filter(item => item.country !== "OTHER" && !BACKEND_COUNTRIES.includes(item.country)).map(locationLabel);
  if (unmappedProduction.length) parts.push(`Production locations not specified: ${unmappedProduction.join(", ")}.`);
  if (unmappedMarkets.length) parts.push(`Target markets not specified: ${unmappedMarkets.join(", ")}.`);
  if (profile.notes) parts.push(profile.notes);
  return parts.join("\n").slice(0, 4000) || null;
}

/* Returns the request body for POST /api/v1/assessments plus the reasons the
   payload cannot be sent. The API rejects shares that do not total 100, so the
   page falls back to the local preview instead of sending a broken request. */
function buildBackendPayload(profile) {
  const issues = [];
  // A row set to "Other" carries the country the user typed. It used to be
  // dropped from the structured request and only survived as free text inside
  // `notes`, so the profile, summary and scenarios never saw the real country.
  const production = profile.production_locations
    .filter(item => item.country === "OTHER" ? Boolean(String(item.other || "").trim()) : BACKEND_COUNTRIES.includes(item.country))
    .map(item => ({ country: item.country === "OTHER" ? String(item.other).trim() : item.country, production_share: Number(item.share) || 0 }));
  const productionTotal = production.reduce((sum, item) => sum + item.production_share, 0);
  const markets = profile.target_markets
    .filter(item => item.country === "OTHER" ? Boolean(String(item.other || "").trim()) : BACKEND_COUNTRIES.includes(item.country))
    .map(item => (item.country === "OTHER" ? String(item.other).trim() : item.country));

  // "Not sure" is not a place, so it still travels in `notes`. Only an
  // impossible share total is a real API limit.
  if (!markets.length) issues.push("Add at least one target market.");
  if (productionTotal > 100) issues.push(`Production shares total ${productionTotal}%, and the assessment API accepts at most 100%.`);

  // The priority list has a default display order. Only a user who actually
  // reordered it has declared a ranking; otherwise every factor is weighted the
  // same so an unranked decision is not scored against a hidden default order.
  const mappedPriorities = profile.priorities_declared
    ? profile.priorities
        .map((item, index) => ({ dimension: BACKEND_PRIORITY_DIMENSION[item.dimension], weight: Math.max(0, 5 - index) }))
        .filter(item => item.dimension)
    : [];
  const equalPriorities = BACKEND_SCORING_DIMENSIONS.map(dimension => ({ dimension, weight: EQUAL_PRIORITY_WEIGHT }));

  const payload = {
    company: {
      company_name: profile.company_name,
      // The Agent API requires an industry value. The form follows profile list.md
      // and no longer asks for one, so the fixed EV / battery scope is sent instead.
      industry: profile.industry || FIXED_INDUSTRY,
      products: [profile.products],
      home_country: homeCountryForApi(profile.home_country),
      production_locations: production,
      target_markets: markets,
      decision_question: buildDecisionQuestion(profile),
      time_horizon: TIME_HORIZON_BACKEND_VALUE[profile.time_horizon] || "6_18_months",
      priorities: mappedPriorities.length ? mappedPriorities : equalPriorities,
      priorities_declared: Boolean(profile.priorities_declared),
      restrictions: profile.restrictions.map(value => TRIGGER_BACKEND_VALUE[value]).filter(Boolean),
      investment_budget_usd: profile.investment_budget ? Number(profile.investment_budget) : null,
      notes: buildNotes(profile),
    },
    productionTotal,
  };
  return { issues, payload };
}

/* A black-holed request (browser proxy, VPN, sleeping backend) would otherwise
   leave the interface waiting forever, so every live call is time-bounded. */
function fetchWithTimeout(url, options, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, { ...options, signal: controller.signal }).finally(() => clearTimeout(timer));
}

/* Turns an API error body into one readable line. Without this a rejected
   request only showed "Assessment service returned 422", which hid the actual
   reason (for example a validation rule on the submitted profile). */
async function describeApiError(response) {
  try {
    const body = await response.clone().json();
    const detail = body && body.detail;
    if (typeof detail === "string" && detail.trim()) return `: ${detail.trim()}`;
    if (Array.isArray(detail) && detail.length) {
      const parts = detail.slice(0, 2).map(entry => {
        const where = Array.isArray(entry.loc)
          ? entry.loc.filter(part => part !== "body").join(".")
          : "";
        return [where, entry.msg].filter(Boolean).join(": ");
      });
      return `: ${parts.join("; ")}`;
    }
  } catch { /* the body was not JSON — fall back to the status code alone */ }
  return "";
}

async function streamAssessment(payload, onStage) {
  // `productionTotal` is a local guard value; the API schema forbids extra keys.
  const { productionTotal, ...request } = payload;
  const response = await fetchWithTimeout(`${window.LOCUS_API_BASE}/api/v1/assessments/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...request, api_key: window.LOCUS_API_KEY, llm_model: window.LOCUS_MODEL || "deepseek-flash", language: currentLanguage() === "zh" ? "zh" : "en" }),
  }, 30000);
  if (!response.ok || !response.body) {
    throw new Error(
      `Assessment service returned ${response.status}${await describeApiError(response)}`
    );
  }

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
  const evidenceFor = (id) => {
    const item = library.find(entry => entry.evidence_id === id);
    if (!item) return { evidence_id: id, title: id, publisher: "Evidence reference", date: "", authority: "", url: null, source_type: "", country_region: "", topic: "", content: "" };
    return {
      evidence_id: item.evidence_id,
      title: item.title,
      publisher: item.publisher,
      date: item.publication_date || "",
      authority: item.authority_level ? `Authority ${item.authority_level}` : "",
      url: item.url || null,
      document_url: item.document_url || null,
      source_type: item.source_type || "",
      country_region: item.country_region || "",
      topic: item.topic || "",
      content: item.content || "",
      // Phase 3 evidence-chain fields, used by the badges below.
      scope: item.evidence_scope || "",
      freshness: item.freshness || "",
      verification: item.verification_status || "",
      self_reported: Boolean(item.is_self_reported),
    };
  };
  const recommendation = api.recommendation || {};
  return {
    company_profile: { ...profile, summary: api.company_profile?.summary || "Your decision profile has been prepared." },
    risks: (api.risks || []).map(risk => ({
      severity: risk.severity || "medium",
      name: risk.name,
      category: risk.category || "",
      category_key: risk.category_key || "",
      description: risk.business_impact,
      uncertainty: risk.uncertainty || "",
      verification: risk.verification_status || "",
      basis: risk.basis || "",
      likelihood: risk.likelihood || "",
      insufficient: Boolean(risk.insufficient_evidence),
      // Attach the relation the Agent recorded for each source so the card can
      // show whether it supports, contextualises or contradicts the risk.
      evidence: (risk.evidence_ids || []).map(id => {
        const item = evidenceFor(id);
        const link = (risk.evidence_links || []).find(entry => entry.evidence_id === id);
        return { ...item, relation: link ? link.relation : "" };
      }),
    })),
    recommendation: {
      headline: recommendation.headline || "",
      rationale: recommendation.rationale || "",
      confidence: recommendation.confidence || "",
      reasons: recommendation.confidence_reasons || [],
      uncertainty: recommendation.uncertainty || [],
      next_actions: recommendation.next_actions || [],
      requires_human_review: Boolean(recommendation.requires_human_review),
    },
    company_intelligence: api.company_intelligence || null,
    limitations: api.limitations || [],
    trace: (api.trace || []).map(step => ({ agent: step.agent, action: step.action, detail: step.detail, status: step.status })),
    scenarios: (api.scenarios || []).map(item => mapScenario(item, evidenceFor, { data_mode: api.data_mode || "" })),
    meta: {
      assessment_id: api.assessment_id || "",
      model_name: api.model_name || "",
      data_mode: api.data_mode || "",
      weighting_mode: api.weighting_mode || "",
      // Which language the Agent wrote this analysis in. Kept so the UI can tell
      // the user when the content no longer matches the interface language.
      language: api.language || "",
      evidence_count: library.length,
    },
  };
}

function mockAssessment(profile) {
  const isUsMarket = profile.target_markets.some(item => item.country === "US");
  const locations = profile.production_locations.map(item => locationName(item)).join(" and ");
  const horizon = (profile.time_horizon || "6_18_months").replaceAll("_", " ");
  return {
    company_profile: { ...profile, summary: `${profile.company_name} operates across ${locations}, with a decision horizon of ${horizon}.` },
    risks: [
      { severity: "high", category: "Trade policy", name: isUsMarket ? "US tariff exposure" : "Trade-policy exposure", description: isUsMarket ? "Changes in US trade policy could materially affect the landed-cost position of products serving this market." : "Changing trade measures may affect cost, lead time and market access across your current footprint.", uncertainty: "Announced measures can change before implementation, and product-level classifications may differ from the headline policy.", verification: "partial", evidence: [
        { evidence_id: "EVD-DEMO-001", title: "Section 301 Investigations", publisher: "Office of the United States Trade Representative", date: "2026-08-14", authority: "Authority A", url: "https://ustr.gov/issue-areas/enforcement/section-301-investigations", source_type: "policy", country_region: "US", topic: "tariff_pressure", content: "Section 301 investigations cover acts, policies and practices of foreign governments affecting US commerce, and are the basis for tariff action on covered product categories." },
        { evidence_id: "EVD-DEMO-002", title: "Global Trade Outlook and Statistics", publisher: "World Trade Organization", date: "2026-04-02", authority: "Authority A", url: "https://www.wto.org/english/res_e/publications_e/gtos0326_e.htm", source_type: "report", country_region: "GLOBAL", topic: "trade_policy", content: "Trade volumes and policy measures monitored by the WTO, including tariff changes and trade-restrictive measures recorded by member economies." },
      ] },
      { severity: "high", category: "Supply chain", name: "Supplier ecosystem dependency", description: "The current footprint may depend on supplier capacity, engineering support or critical inputs located outside the production market.", uncertainty: "Supplier concentration is inferred from your inputs rather than verified bill-of-materials data.", verification: "partial", evidence: [
        { evidence_id: "EVD-DEMO-003", title: "Trade in Value Added", publisher: "OECD", date: "2026-02-19", authority: "Authority B", url: "https://www.oecd.org/en/topics/sub-issues/trade-in-value-added.html", source_type: "dataset", country_region: "GLOBAL", topic: "supplier_dependency", content: "Value-added decomposition showing where intermediate inputs originate, used to estimate how much of a finished product depends on suppliers located in a given economy." },
        { evidence_id: "EVD-DEMO-004", title: "Global Critical Minerals Outlook", publisher: "International Energy Agency", date: "2025-11-06", authority: "Authority B", url: "https://www.iea.org/reports/global-critical-minerals-outlook", source_type: "report", country_region: "GLOBAL", topic: "supply_chain_resilience", content: "Supply and refining concentration for battery-grade materials, including processing capacity by country and expected demand growth for EV batteries." },
      ] },
      { severity: "medium", category: "Regulatory & compliance", name: "Export-control and compliance screening", description: "Customer screening, product classification and licence requirements can add lead time or restrict access to specific buyers.", uncertainty: "Whether your specific products fall under current control lists is not confirmed by public sources.", verification: "partial", evidence: [
        { evidence_id: "EVD-DEMO-005", title: "Entity List", publisher: "Bureau of Industry and Security", date: "2026-07-21", authority: "Authority A", url: "https://www.bis.gov/entity-list", source_type: "regulation", country_region: "US", topic: "export_controls", content: "Listed parties subject to export licence requirements; shipments to or involving listed entities require screening before export." },
      ] },
      { severity: "medium", category: "Operational", name: "Implementation and capacity ramp-up", description: "Any change to production allocation requires time for qualification, workforce ramp-up and customer certification.", uncertainty: "Certification lead times are company specific and are not covered by public sources.", verification: "unverified", evidence: [
        { evidence_id: "EVD-DEMO-006", title: "Geopolitical risk readiness", publisher: "McKinsey & Company", date: "2025-09-30", authority: "Authority C", url: "https://www.mckinsey.com/capabilities/risk-and-resilience/our-insights/how-companies-can-strengthen-their-geopolitical-risk-readiness", source_type: "industry_report", country_region: "GLOBAL", topic: "operational_risk", content: "Survey evidence on how companies organise geopolitical risk assessment and how long operational changes such as shifting production lines typically take." },
      ] },
    ],
    scenarios: [
      {
        scenario_id: "SCN-001",
        name: "Hybrid Diversification",
        description: "Keep the existing China and Vietnam capacity and add a third qualified location for the most tariff-exposed volumes, so no single market carries the whole export book.",
        weighted_score: isUsMarket ? 84 : 80,
        cost_score: 72, resilience_score: 90, geopolitical_risk_score: 86, market_access_score: 80, implementation_score: 66,
        benefits: ["Reduces single-country tariff exposure", "Keeps the mature battery supplier ecosystem available", "Improves resilience if one location is disrupted"],
        risks: ["Higher coordination and quality overhead across sites", "Extra qualification and certification effort", "Investment is required before the cost benefit is proven"],
        applicable_conditions: ["Investment capacity for a third site or contract-manufacturing partner", "Customer acceptance of multi-origin supply", "Tariff treatment of the current locations stays broadly stable"],
        evidence_ids: ["EVD-DEMO-003", "EVD-DEMO-004"],
      },
      {
        scenario_id: "SCN-002",
        name: "Maintain Current Layout",
        description: "Keep the current production distribution and manage exposure through inventory, pricing and contract terms instead of moving capacity.",
        weighted_score: isUsMarket ? 71 : 76,
        cost_score: 88, resilience_score: 52, geopolitical_risk_score: 45, market_access_score: 62, implementation_score: 92,
        benefits: ["No relocation or qualification cost", "Existing cost base and supplier relationships preserved", "Fastest to execute — no new site required"],
        risks: ["Tariff exposure on the main export lane remains", "Supplier concentration is not addressed", "Limited room to absorb a further policy shock"],
        applicable_conditions: ["Current tariff treatment stays acceptable", "Cost parity is the dominant decision criterion", "No customer requirement forces a second origin"],
        evidence_ids: ["EVD-DEMO-001", "EVD-DEMO-002"],
      },
      {
        scenario_id: "SCN-003",
        name: "Increase China Production",
        description: "Shift a larger share of production into China to use the deeper supplier ecosystem, while keeping overseas export capacity running.",
        weighted_score: isUsMarket ? 68 : 78,
        cost_score: 82, resilience_score: 74, geopolitical_risk_score: 40, market_access_score: 52, implementation_score: 78,
        benefits: ["Stronger supplier ecosystem and engineering support", "Lower coordination complexity", "Faster manufacturing scaling for new products"],
        risks: ["Higher tariff exposure for products sold into the US", "Export-control and compliance screening burden", "Customer origin requirements may restrict where output can be sold"],
        applicable_conditions: ["US tariff treatment of China-origin goods does not deteriorate further", "Customers accept China-origin cells for the affected programmes"],
        evidence_ids: ["EVD-DEMO-001", "EVD-DEMO-005"],
      },
    ],
    recommendation: {
      recommended_scenario_id: "SCN-001",
      headline: "Indicative recommendation based on the inputs provided.",
      rationale: "This is a demonstration assessment generated in the browser. It shows the structure of the output, not an analysed result.",
      confidence: "low",
      reasons: ["Generated locally without the retrieval and analysis pipeline", "No company documents or verified bill-of-materials data"],
      uncertainty: ["Everything shown here is illustrative until the Agent service is connected."],
      next_actions: ["Connect the Agent API and re-run the assessment"],
      requires_human_review: true,
    },
    limitations: [
      "This assessment was produced without document-level verification of company data.",
      "Evidence entries are placeholders and are not clickable.",
    ],
    trace: [
      { agent: "ProfileAgent", action: "Build company profile", detail: "Company, footprint, markets and decision context standardised.", status: "completed" },
      { agent: "ResearchAgent", action: "Retrieve evidence", detail: "Skipped — the Agent service is not connected.", status: "fallback" },
      { agent: "RiskAgent", action: "Assess geopolitical risks", detail: "Rule-based preview risks used instead of model output.", status: "fallback" },
    ],
    meta: { assessment_id: "", model_name: "preview", data_mode: "preview", evidence_count: 5 },
  };
}

/* --------------------------------------------------------------- analysis */

function setStageIn(listId, index, status) {
  const item = document.querySelectorAll(`#${listId} li`)[index];
  if (!item) return;
  item.classList.toggle("working", status === "working");
  item.classList.toggle("done", status === "done");
  item.querySelector("span").textContent = status === "done" ? "Complete" : status === "working" ? "In progress" : "Waiting";
}

function eachStageIn(listId, status) {
  document.querySelectorAll(`#${listId} li`).forEach((item, index) => setStageIn(listId, index, status));
}

function setStage(index, status) { setStageIn("analysis-stages", index, status); }
function resetStages() { eachStageIn("analysis-stages", "idle"); }
function completeStages() { eachStageIn("analysis-stages", "done"); }

function updateSimProgress() {
  const items = [...document.querySelectorAll("#sim-stages li")];
  const done = items.filter(item => item.classList.contains("done")).length;
  const percent = items.length ? Math.round((done / items.length) * 100) : 0;
  const fill = $("#sim-fill");
  const label = $("#sim-label");
  if (fill) fill.style.width = `${percent}%`;
  if (label) label.textContent = `${percent}% complete`;
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

/* The submitted profile moves into My Decision, so the form is reset here and
   the next "Start New Decision" begins from a clean sheet. */
function finishRun(assessment, profile, thenSimulate = false) {
  state.assessment = assessment;
  runInFlight = false;
  const submitButton = $("#decision-form button[type='submit']");
  if (submitButton) submitButton.disabled = false;
  try { completeStages(); } catch { /* stage list is cosmetic */ }
  try { renderAssessment(assessment); } catch (error) { showToast(`Some assessment sections could not be rendered: ${error.message}`); }
  try { saveProject(assessment, profile || assessment.company_profile || {}); } catch { /* project history is optional */ }
  try { resetDecisionForm(); } catch { /* the form can be cleared manually */ }
  // Always move the user forward, whatever happened above.
  if (thenSimulate) setTimeout(() => runScenarioSimulation(), 420);
  else setTimeout(() => showScreen("assessment"), 320);
}

function runPreviewTimeline(profile, thenSimulate = false) {
  const total = document.querySelectorAll("#analysis-stages li").length;
  let position = 0;
  const timer = setInterval(() => {
    if (position > 0) setStage(position - 1, "done");
    if (position < total) { setStage(position, "working"); position += 1; }
    else clearInterval(timer);
  }, 620);
  setTimeout(() => {
    clearInterval(timer);
    finishRun(mockAssessment(profile), profile, thenSimulate);
  }, 2800);
}

async function runAnalysis(profile, thenSimulate = false) {
  if (runInFlight) return;
  runInFlight = true;
  const submitButton = $("#decision-form button[type='submit']");
  if (submitButton) submitButton.disabled = true;
  showScreen("analysis");
  resetStages();
  const configured = Boolean(window.LOCUS_API_BASE && window.LOCUS_API_KEY);
  let request = { issues: [], payload: null };
  try {
    request = buildBackendPayload(profile);
  } catch (error) {
    showToast(`Could not prepare the assessment request: ${error.message}`);
  }
  const { issues, payload } = request;

  if (configured && payload && !issues.length) {
    try {
      const api = await streamAssessment(payload, handleStageEvent);
      showAgentNotice("");
      finishRun(mapApiAssessment(api, profile), profile, thenSimulate);
      return;
    } catch (error) {
      showAgentNotice(
        `Live agent unavailable (${error.message}). Showing the local preview for this run.`,
        "warn"
      );
      showToast("Live agent unavailable — showing the local preview.");
    }
  } else if (configured && issues.length) {
    showAgentNotice(`${issues[0]} Showing the local preview instead.`, "warn");
    showToast(`${issues[0]} Showing the local preview instead.`);
  } else if (!configured) {
    showAgentNotice(
      "No analysis service is configured for this page, so results are generated locally and are indicative only.",
      "warn"
    );
  }
  runPreviewTimeline(profile, thenSimulate);
}

/* ------------------------------------------------------------- assessment */

/* UI.md risk categories. Levels stay qualitative — no numeric risk scores. */
const RISK_CATEGORIES = [
  { key: "trade", label: "Trade", match: ["tariff", "trade", "duty", "customs", "import", "关税", "贸易"] },
  { key: "political", label: "Political", match: ["geopolitic", "political", "sanction", "conflict", "地缘", "政治"] },
  { key: "supply_chain", label: "Supply chain", match: ["supplier", "supply", "ecosystem", "dependency", "logistics", "供应", "供应链"] },
  { key: "regulatory", label: "Regulation", match: ["regulat", "compliance", "export control", "licence", "license", "law", "policy", "standard", "监管", "合规", "政策"] },
  { key: "market_access", label: "Market access", match: ["market access", "customer", "rules of origin", "市场准入"] },
  { key: "operational", label: "Operational", match: ["operat", "implementation", "workforce", "labor", "labour", "cost", "ramp", "运营", "实施", "成本"] },
];
const SEVERITY_LEVEL = { critical: "high", high: "high", medium: "medium", low: "low" };
const LEVEL_LABEL = { high: "High", medium: "Medium", low: "Low", unknown: "Not assessed" };
const LEVEL_RADIUS = { high: 1, medium: 0.68, low: 0.4, unknown: 0.18 };
const BUDGET_LABELS = { 500000: "< USD 1M", 5000000: "USD 1–10M", 30000000: "USD 10–50M", 75000000: "USD 50M+" };

/* UI.md scenario page: five evaluation dimensions, overall score plus confidence. */
const SCENARIO_DIMENSIONS = [
  ["cost", "Cost impact"],
  ["resilience", "Supply resilience"],
  ["geopolitical_risk", "Geopolitical risk"],
  ["market_access", "Market access"],
  ["feasibility", "Feasibility"],
];

function evidenceConfidence(item) {
  const level = String(item.authority || "");
  if (level.includes("A")) return "High";
  if (level.includes("B")) return "Medium";
  return "Low";
}

/* The Agent API has no per-scenario confidence field, so it is derived from the
   evidence linked to the scenario and whether a real retrieval run happened. */
function scenarioConfidence(scenario, meta) {
  const items = scenario.evidence || [];
  const zh = currentLanguage() === "zh";
  if (meta?.data_mode === "preview") {
    return { label: zh ? "低" : "Low", reason: zh ? "预览估算——未经过检索或模型运行" : "preview estimate — no retrieval or model run happened" };
  }
  if (!items.length) return { label: zh ? "低" : "Low", reason: zh ? "该情景未关联任何证据" : "no evidence is linked to this scenario" };
  const strong = items.some(item => String(item.authority).includes("A"));
  if (items.length >= 3 && strong) return { label: zh ? "高" : "High", reason: zh ? `关联 ${items.length} 条来源，含 A 级权威材料` : `${items.length} linked sources including authority A material` };
  if (items.length >= 2) return { label: zh ? "中" : "Medium", reason: zh ? `关联 ${items.length} 条来源，无 A 级权威材料` : `${items.length} linked sources, no authority A material` };
  return { label: zh ? "低" : "Low", reason: zh ? "仅关联 1 条来源" : "only one linked source" };
}

function mapScenario(item, evidenceFor, meta) {
  const scenario = {
    scenario_id: item.scenario_id || "",
    name: item.name || "Scenario",
    summary: item.description || "",
    overall_score: Math.round(Number(item.weighted_score) || 0),
    scores: {
      cost: Math.round(Number(item.cost_score) || 0),
      resilience: Math.round(Number(item.resilience_score) || 0),
      geopolitical_risk: Math.round(Number(item.geopolitical_risk_score) || 0),
      market_access: Math.round(Number(item.market_access_score) || 0),
      feasibility: Math.round(Number(item.implementation_score) || 0),
    },
    benefits: item.benefits || [],
    risks: item.risks || [],
    assumptions: item.applicable_conditions || [],
    breakdown: item.score_breakdown || [],
    bands: item.dimension_bands || {},
    insufficient: Boolean(item.insufficient_evidence),
    links: item.evidence_links || [],
    evidence: (item.evidence_ids || []).map(evidenceFor),
  };
  scenario.confidence = scenarioConfidence(scenario, meta);
  return scenario;
}

/* Evidence is stored per risk on the frontend, so scenario evidence references
   are resolved through this lookup. */
function evidenceLookupFromRisks(risks) {
  const library = [];
  (risks || []).forEach(risk => (risk.evidence || []).forEach(item => {
    if (!library.some(existing => existing.evidence_id === item.evidence_id)) library.push(item);
  }));
  return (id) => library.find(item => item.evidence_id === id)
    || { evidence_id: id, title: id, publisher: "Evidence reference", date: "", authority: "", url: null };
}

/* Scenarios arrive already mapped from the Agent path, and in raw API shape from
   the local preview, so normalise whichever form is present. */
function normalizeScenarios(assessment) {
  const evidenceFor = evidenceLookupFromRisks(assessment.risks);
  const meta = { data_mode: assessment.meta?.data_mode || "" };
  return (assessment.scenarios || []).map(item => (item && item.scores ? item : mapScenario(item, evidenceFor, meta)));
}

function levelOf(risks) {
  const levels = risks.map(risk => SEVERITY_LEVEL[risk.severity] || "medium");
  if (levels.includes("high")) return "high";
  if (levels.includes("medium")) return "medium";
  return levels.length ? "low" : "unknown";
}

function riskCategoryKey(risk) {
  // The Agent returns a normalised taxonomy; fall back to keyword matching for
  // older stored assessments.
  if (risk.category_key) return risk.category_key;
  const text = `${risk.category || ""} ${risk.name || ""}`.toLowerCase();
  const found = RISK_CATEGORIES.find(category => category.match.some(token => text.includes(token)));
  return found ? found.key : "operational";
}

function renderRiskRadar(risks) {
  const radar = $("#risk-radar");
  if (!radar) return;
  const size = 330;
  const center = size / 2;
  const maxRadius = 110;
  const groups = RISK_CATEGORIES.map(category => {
    const items = risks.filter(risk => riskCategoryKey(risk) === category.key);
    return { ...category, items, level: levelOf(items) };
  });
  const points = groups.map((group, index) => {
    const angle = ((-90 + index * (360 / groups.length)) * Math.PI) / 180;
    const radius = maxRadius * LEVEL_RADIUS[group.level];
    return { ...group, angle, x: center + Math.cos(angle) * radius, y: center + Math.sin(angle) * radius };
  });
  const rings = [1, 0.68, 0.36].map(scale => `<circle class="rr-ring" cx="${center}" cy="${center}" r="${(maxRadius * scale).toFixed(1)}" />`).join("");
  const spokes = points.map(point => `<line class="rr-axis" x1="${center}" y1="${center}" x2="${(center + Math.cos(point.angle) * maxRadius).toFixed(1)}" y2="${(center + Math.sin(point.angle) * maxRadius).toFixed(1)}" />`).join("");
  const frame = `<polygon class="rr-frame" points="${points.map(point => `${(center + Math.cos(point.angle) * maxRadius).toFixed(1)},${(center + Math.sin(point.angle) * maxRadius).toFixed(1)}`).join(" ")}" />`;
  const shape = `<polygon class="rr-shape" points="${points.map(point => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ")}" />`;
  const nodes = points.map(point => `<circle class="rr-node ${point.level}" cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="5.5" />`).join("");
  const labels = points.map(point => {
    const labelRadius = maxRadius + 32;
    const x = center + Math.cos(point.angle) * labelRadius;
    const y = center + Math.sin(point.angle) * labelRadius;
    const cos = Math.cos(point.angle);
    const anchor = cos > 0.3 ? "start" : cos < -0.3 ? "end" : "middle";
    const target = point.items.length ? `#risk-${risks.indexOf(point.items[0])}` : "#risk-details";
    return `<g class="rr-label ${point.level}" data-risk-target="${target}" tabindex="0" role="button" aria-label="${escapeHtml(`${point.label}: ${LEVEL_LABEL[point.level]}`)}">
        <text x="${x.toFixed(1)}" y="${(y - 3).toFixed(1)}" text-anchor="${anchor}">${escapeHtml(point.label)}</text>
        <text class="rr-level" x="${x.toFixed(1)}" y="${(y + 12).toFixed(1)}" text-anchor="${anchor}">${escapeHtml(LEVEL_LABEL[point.level])}</text>
      </g>`;
  }).join("");
  radar.innerHTML = `<svg viewBox="0 0 ${size} ${size}" role="img" aria-label="Qualitative risk overview by category">${rings}${spokes}${frame}${shape}${nodes}${labels}</svg>`;
}

function renderRiskSummary(risks) {
  const summary = $("#risk-summary");
  if (!summary) return;
  const counts = { high: 0, medium: 0, low: 0 };
  risks.forEach(risk => { counts[SEVERITY_LEVEL[risk.severity] || "medium"] += 1; });
  const rows = [];
  if (counts.high) rows.push(["high", `${counts.high} high-priority ${counts.high === 1 ? "exposure" : "exposures"}`, "Review these before any capacity commitment."]);
  if (counts.medium) rows.push(["medium", `${counts.medium} developing ${counts.medium === 1 ? "exposure" : "exposures"}`, "Worth monitoring through the implementation window."]);
  if (counts.low) rows.push(["low", `${counts.low} monitored ${counts.low === 1 ? "exposure" : "exposures"}`, "Low severity on the current evidence."]);
  if (!rows.length) rows.push(["medium", "No risks identified yet", "Adjust the decision profile and run the assessment again."]);
  summary.innerHTML = rows.map(([level, title, note]) => `<div><span class="risk-dot ${level}-dot"></span><p><b>${escapeHtml(title)}</b><br />${escapeHtml(note)}</p></div>`).join("")
    + `<p class="muted">Levels show direction based on available evidence — not a prediction or a legal conclusion.</p>`;
}

/* The i18n dictionary translates static markup by matching English strings.
   Text this file composes itself (badges, counts, hints) is localised here. */
function L(en, zh) {
  return currentLanguage() === "zh" ? zh : en;
}

const EVIDENCE_SCOPE_LABEL = {
  company: () => L("company source", "公司来源"),
  policy: () => L("policy source", "政策来源"),
  market: () => L("market data", "市场数据"),
};

const FRESHNESS_LABEL = {
  current: () => L("current", "时效最新"),
  aging: () => L("aging", "时效下降"),
  stale: () => L("stale", "已过时"),
};

const VERIFICATION_LABEL = {
  verified: () => L("verified", "已验证"),
  partial: () => L("partial", "部分验证"),
  unverified: () => L("unverified", "未验证"),
  contested: () => L("contested", "证据冲突"),
  outdated: () => L("outdated", "已过期"),
};

const RELATION_LABEL = {
  supports: () => L("supports", "支持"),
  context: () => L("context", "背景"),
  contradicts: () => L("contradicts", "相悖"),
};

/* Phase 3 provenance badges: where a source came from, whether it still holds
   up, and how it relates to the risk or scenario that cites it. */
function evidenceBadges(item) {
  const badges = [];
  const add = (label, cls) => {
    if (label) badges.push(`<span class="ev-badge ${cls}">${escapeHtml(label)}</span>`);
  };
  if (item.relation && RELATION_LABEL[item.relation]) add(RELATION_LABEL[item.relation](), `relation-${item.relation}`);
  if (item.scope && EVIDENCE_SCOPE_LABEL[item.scope]) add(EVIDENCE_SCOPE_LABEL[item.scope](), `scope-${item.scope}`);
  if (item.self_reported) add(L("self-reported", "企业自述"), "self-reported");
  if (item.freshness && FRESHNESS_LABEL[item.freshness]) add(FRESHNESS_LABEL[item.freshness](), `freshness-${item.freshness}`);
  if (item.verification && VERIFICATION_LABEL[item.verification]) add(VERIFICATION_LABEL[item.verification](), `verify-${item.verification}`);
  return badges.join("");
}

function evidenceMarkup(evidence) {
  return (evidence || []).map(item => {
    const meta = [item.date, item.authority].filter(Boolean).join(" · ");
    const facts = [
      item.evidence_id,
      item.source_type ? item.source_type.replaceAll("_", " ") : "",
      item.country_region,
      item.topic ? item.topic.replaceAll("_", " ") : "",
    ].filter(Boolean).join(" · ");
    const link = sourceLink(item);
    const source = link
      ? `<a class="evidence-open" href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">Open original source ↗</a>`
      : `<span class="evidence-open muted">Original document is not linked in this preview — raw files live in the <b>data</b> branch and web sources come from the Agent's search.</span>`;
    return `
      <details class="evidence-card">
        <summary class="evidence-link"><span class="evidence-main"><b>${escapeHtml(item.publisher)}</b> — ${escapeHtml(item.title)}</span><span class="evidence-meta">${escapeHtml(meta)}</span>${evidenceBadges(item) ? `<span class="evidence-badges">${evidenceBadges(item)}</span>` : ""}</summary>
        <div class="evidence-preview">
          ${facts ? `<p class="evidence-facts">${escapeHtml(facts)}</p>` : ""}
          ${item.content ? `<p class="evidence-excerpt">${escapeHtml(item.content)}</p>` : `<p class="evidence-excerpt muted">No retrieved text is attached to this source.</p>`}
          ${source}
        </div>
      </details>`;
  }).join("");
}

/* Prefer the backend document endpoint (which streams the original file or
   redirects to the source URL), falling back to the raw external link. */
function sourceLink(item) {
  const path = item.document_url || "";
  if (path.startsWith("/") && window.LOCUS_API_BASE) return `${window.LOCUS_API_BASE}${path}`;
  return path || item.url || "";
}

/* Company intelligence (workflow.md): every fact carries its own source and
   status, so user statements, public sources, inferences and open questions are
   never blended together. */
/* The section order below is fixed in renderIntelligence; the profile page no
   longer repeats the user's form input section by section. */
const FACT_STATUS_LABEL = {
  user_input: "User input",
  public_source: "Public source",
  inferred: "AI inference",
  to_be_confirmed: "To be confirmed",
};

/* Step 2 of the Company Intelligence revision added structured fields whose
   labels are rendered here (the i18n dictionary only matches static markup). */
const GAP_PRIORITY_LABEL = {
  critical: () => L("Critical", "关键"),
  important: () => L("Important", "重要"),
  optional: () => L("Optional", "可选"),
};
const SITE_STATUS_LABEL = {
  verified: () => L("Verified", "已验证"),
  reported: () => L("Reported", "已报告"),
  estimated: () => L("Estimated", "估计"),
  inferred: () => L("Inferred", "推断"),
  unknown: () => L("Unknown", "未知"),
};
const SITE_SOURCE_LABEL = {
  user_input: () => L("User input", "用户提供"),
  company_filing: () => L("Company filing", "公司披露"),
  official_website: () => L("Official website", "官方网站"),
  industry_report: () => L("Industry report", "行业报告"),
  news: () => L("News", "新闻"),
};
/* Controlled supply-chain role vocabulary agreed with the product owner. The
   backend label is shown unchanged when the value is not one of these. */
const ROLE_LABEL = {
  UPSTREAM_RAW_MATERIAL: () => L("Upstream raw material", "上游原材料"),
  UPSTREAM_COMPONENT: () => L("Upstream component", "上游材料/零部件"),
  BATTERY_MANUFACTURING: () => L("Battery manufacturing", "电池制造"),
  DOWNSTREAM_APPLICATION: () => L("Downstream application", "下游应用"),
  INTEGRATED_BATTERY_COMPANY: () => L("Integrated battery company", "一体化电池企业"),
  OTHER: () => L("Other", "其他"),
};
const STAGE_LABEL = {
  raw_material: () => L("Raw materials", "原材料"),
  component: () => L("Materials / components", "材料 / 零部件"),
  manufacturing: () => L("Manufacturing", "制造"),
  downstream: () => L("Downstream", "下游应用"),
};
const SHARE_BASIS_LABEL = {
  user_input: () => L("user-provided", "用户提供"),
  disclosed: () => L("company disclosure", "公司披露"),
  sourced_estimate: () => L("sourced estimate", "有来源的估计"),
};

function roleLabel(value) {
  const key = String(value || "").trim().toUpperCase();
  return ROLE_LABEL[key] ? ROLE_LABEL[key]() : String(value || "");
}

function mappedLabel(map, key) {
  const value = String(key || "").trim();
  return map[value] ? map[value]() : value;
}

function renderIntelligence(assessment) {
  const container = $("#intelligence-body");
  if (!container) return;
  const data = assessment.company_intelligence;
  if (!data) {
    container.innerHTML = `<p class="overview-text muted">Company intelligence is not available for this assessment.</p>`;
    return;
  }
  const facts = (items) => `<ul class="intel-list">${(items || []).map(item => `
      <li><span class="intel-fact">${escapeHtml(item.fact)}</span><span class="intel-meta"><span class="intel-status ${escapeHtml(item.data_status)}">${escapeHtml(FACT_STATUS_LABEL[item.data_status] || item.data_status)}</span>${(item.source_ids || []).length ? `<span class="intel-sources">${(item.source_ids || []).slice(0, 2).map(escapeHtml).join(" · ")}</span>` : ""}</span></li>`).join("")}</ul>`;
  const block = (label, inner) => (inner
    ? `<div class="intel-block"><p class="intel-label">${escapeHtml(label)}</p>${inner}</div>`
    : "");

  const summary = String(data.executive_summary || "").trim();
  const entity = data.entity || {};
  const identity = [
    entity.legal_name ? `${L("Legal name", "法律实体")}: ${entity.legal_name}` : "",
    entity.headquarters ? `${L("Headquarters", "总部")}: ${entity.headquarters}` : "",
    entity.founded_year ? `${L("Founded", "成立")}: ${entity.founded_year}` : "",
    entity.listing && entity.listing.ticker ? `${L("Listing", "上市")}: ${entity.listing.exchange || ""} ${entity.listing.ticker}`.trim() : "",
  ].filter(Boolean);

  // Structured footprint (step 2). The narrative fact list still renders below,
  // so an assessment produced before the schema change is unaffected.
  const sites = data.manufacturing_footprint || [];
  const siteTable = sites.length
    ? `<table class="intel-table"><thead><tr>
        <th>${L("Country", "国家")}</th><th>${L("Facility", "设施")}</th><th>${L("Role", "角色")}</th>
        <th>${L("Share", "占比")}</th><th>${L("Capacity", "产能")}</th><th>${L("Source", "来源")}</th><th>${L("Status", "状态")}</th>
      </tr></thead><tbody>${sites.map(site => `<tr>
        <td>${escapeHtml(site.country || "")}</td>
        <td>${escapeHtml(site.facility || "—")}</td>
        <td>${escapeHtml(roleLabel(site.role) || "—")}</td>
        <td>${site.production_share === null || site.production_share === undefined ? "—" : `${escapeHtml(String(site.production_share))}%`}</td>
        <td>${escapeHtml(site.capacity || "unknown")}</td>
        <td>${escapeHtml(mappedLabel(SITE_SOURCE_LABEL, site.source_type))}</td>
        <td><span class="intel-status ${escapeHtml(site.status || "unknown")}">${escapeHtml(mappedLabel(SITE_STATUS_LABEL, site.status))}</span></td>
      </tr>`).join("")}</tbody></table>`
    : "";

  const roleData = data.supply_chain_role || {};
  const roleValues = [roleData.primary, ...(roleData.secondary || [])].filter(Boolean);
  const roleChips = roleValues
    .map((value, index) => `<span class="role-chip${index === 0 ? " primary" : ""}">${escapeHtml(roleLabel(value))}</span>`)
    .join("");
  const roleInner = roleChips ? `<div class="role-chips">${roleChips}</div>` : "";

  // Structured supply chain (Company Intelligence revision §3): who supplies
  // what, where, and where the output goes.
  const stages = data.supply_chain_structure || [];
  const structureInner = stages.length
    ? `${roleInner}<ul class="supply-chain-list">${stages.map(stage => `<li>
        <span class="chain-stage ${escapeHtml(stage.stage)}">${escapeHtml(STAGE_LABEL[stage.stage] ? STAGE_LABEL[stage.stage]() : stage.stage)}</span>
        <span class="chain-body">
          <b>${escapeHtml(stage.region || "unknown")}${stage.company_role ? ` · ${escapeHtml(stage.company_role)}` : ""}</b>
          ${stage.description ? `<span class="chain-text">${escapeHtml(stage.description)}</span>` : ""}
          <span class="chain-share">${L("Share", "占比")}: ${escapeHtml(stage.share || "unknown")}${stage.share_basis && stage.share_basis !== "unknown" ? ` · ${escapeHtml(mappedLabel(SHARE_BASIS_LABEL, stage.share_basis))}` : ""}</span>
        </span>
      </li>`).join("")}</ul>`
    : "";

  const profile = data.business_profile || {};
  const profileInner = (profile.model || profile.value_chain_role || (profile.products || []).length)
    ? `<ul class="intel-list">
        ${profile.model ? `<li><span class="intel-fact"><b>${L("Business model", "业务模式")}</b> · ${escapeHtml(profile.model)}</span></li>` : ""}
        ${profile.value_chain_role ? `<li><span class="intel-fact"><b>${L("Value-chain role", "价值链位置")}</b> · ${escapeHtml(profile.value_chain_role)}</span></li>` : ""}
        ${(profile.products || []).length ? `<li><span class="intel-fact"><b>${L("Products", "产品")}</b> · ${escapeHtml(profile.products.join(" · "))}</span></li>` : ""}
        ${(profile.customers || []).length ? `<li><span class="intel-fact"><b>${L("Customers", "客户")}</b> · ${escapeHtml(profile.customers.join(" · "))}</span></li>` : ""}
      </ul>`
    : "";

  const context = data.decision_context || {};
  const contextInner = (context.objective || (context.drivers || []).length)
    ? `<ul class="intel-list">
        ${context.objective ? `<li><span class="intel-fact"><b>${L("Objective", "决策目标")}</b> · ${escapeHtml(context.objective)}</span></li>` : ""}
        ${(context.drivers || []).length ? `<li><span class="intel-fact"><b>${L("Drivers", "驱动因素")}</b> · ${escapeHtml(context.drivers.join(" · "))}</span></li>` : ""}
        ${(context.constraints || []).length ? `<li><span class="intel-fact"><b>${L("Constraints", "约束")}</b> · ${escapeHtml(context.constraints.join(" · "))}</span></li>` : ""}
      </ul>`
    : "";

  // Older assessments stored plain strings; step 2 stores objects with a
  // priority, why it matters and how to obtain the information.
  const gapRow = (gap) => {
    if (typeof gap === "string" || gap === null) {
      return `<li class="gap-row"><div class="gap-head"><span class="gap-priority important">${GAP_PRIORITY_LABEL.important()}</span><span class="gap-item">${escapeHtml(gap || "")}</span></div></li>`;
    }
    const priority = GAP_PRIORITY_LABEL[gap.priority] ? gap.priority : "important";
    return `<li class="gap-row">
      <div class="gap-head"><span class="gap-priority ${priority}">${GAP_PRIORITY_LABEL[priority]()}</span><span class="gap-item">${escapeHtml(gap.item || "")}</span></div>
      ${gap.why_it_matters ? `<p class="gap-detail"><b>${L("Why it matters", "为什么重要")}</b> · ${escapeHtml(gap.why_it_matters)}</p>` : ""}
      ${gap.recommended_action ? `<p class="gap-detail"><b>${L("Next step", "建议动作")}</b> · ${escapeHtml(gap.recommended_action)}</p>` : ""}
    </li>`;
  };
  const gaps = data.information_gaps || [];
  const isOptional = (gap) => typeof gap === "object" && gap !== null && gap.priority === "optional";
  const mainGaps = gaps.filter(gap => !isOptional(gap));
  const optionalGaps = gaps.filter(isOptional);
  const gapList = (list) => `<ul class="gap-list">${list.map(gapRow).join("")}</ul>`;
  const gapInner = [
    mainGaps.length ? gapList(mainGaps) : "",
    optionalGaps.length
      ? `<details class="intel-fold"><summary>${L("Optional gaps", "可选信息缺口")} (${optionalGaps.length})</summary>${gapList(optionalGaps)}</details>`
      : "",
  ].join("");

  const references = data.evidence_references || [];
  const referenceInner = references.length
    // Collapsed by default: the page should read first and explain on demand.
    ? `<details class="intel-fold"><summary>${L("Evidence", "证据")} (${references.length})</summary><ul class="intel-list">${references.map(ref => `<li><span class="intel-fact">${escapeHtml(ref.title || ref.evidence_id)} <span class="intel-sources">${escapeHtml(ref.publisher || "")}</span></span><span class="intel-meta"><span class="intel-sources">${escapeHtml(ref.evidence_id)}</span>${ref.url ? ` <a class="evidence-open" href="${escapeHtml(ref.url)}" target="_blank" rel="noopener noreferrer">${L("Open source", "打开来源")} ↗</a>` : ""}</span></li>`).join("")}</ul></details>`
    : "";

  // Company Overview keeps identity + business model + the overview facts in one
  // place, so the same user input is not restated in several sections.
  const overviewInner = [
    identity.length ? `<ul class="intel-list">${identity.map(line => `<li><span class="intel-fact">${escapeHtml(line)}</span></li>`).join("")}</ul>` : "",
    profileInner,
    (data.overview || []).length ? facts(data.overview) : "",
  ].join("");
  const legacyFootprint = (data.production_footprint || []).length
    ? facts(data.production_footprint)
    : "";
  const legacySupplyChain = [
    roleInner,
    (data.supply_chain || []).length ? facts(data.supply_chain) : "",
  ].join("");
  const sourceLine = references.length
    ? `<p class="intel-source-line">${L(`Based on ${references.length} sources`, `基于 ${references.length} 条来源`)}</p>`
    : "";

  container.innerHTML = [
    summary ? `<p class="overview-text">${escapeHtml(summary)}</p>` : "",
    sourceLine,
    block(L("Company overview", "企业概况"), overviewInner),
    block(L("Global manufacturing footprint", "全球生产布局"), siteTable || legacyFootprint),
    block(L("Supply chain structure", "供应链结构"), structureInner || legacySupplyChain),
    block(L("Strategic context", "战略情境"), (data.strategic_context || []).length ? facts(data.strategic_context) : ""),
    block(L("Decision context", "决策情境"), contextInner),
    block(L("Information gaps", "信息缺口"), gapInner),
    block(L("Evidence sources", "证据来源"), referenceInner),
  ].join("");
}

function renderRationale(assessment) {
  const container = $("#rationale-content");
  if (!container) return;
  const profile = assessment.company_profile;
  const recommendation = assessment.recommendation || {};
  const sources = [];
  (assessment.risks || []).forEach(risk => (risk.evidence || []).forEach(item => {
    if (!sources.some(source => source.title === item.title && source.publisher === item.publisher)) sources.push(item);
  }));
  const factors = [
    `Production footprint: ${profile.production_locations.map(item => `${locationName(item)}${item.share ? ` ${item.share}%` : ""}`).join(", ") || "not specified"}`,
    `Export markets: ${profile.target_markets.map(item => locationName(item)).join(", ") || "not specified"}`,
    `Decision priorities: ${(profile.priorities || []).slice(0, 3).map(item => item.dimension).join(" > ") || "not ranked"}`,
    `Declared drivers: ${profile.restrictions.map(value => TRIGGER_LABELS[value] || value.replaceAll("_", " ")).join(", ") || "none selected"}`,
  ];
  const assumptions = [
    "Production shares entered in the form represent the current operating model.",
    "Country-level public sources may not reflect company-specific contracts, exemptions or customer terms.",
    assessment.meta?.data_mode === "preview"
      ? "This is a preview assessment: no retrieval or model analysis was run."
      : "Findings rely on the retrieved evidence listed below; unlisted internal data was not available.",
  ];
  const confidence = recommendation.confidence ? [`Reported confidence: ${recommendation.confidence}`] : [];
  const uncertainties = (assessment.risks || []).map(risk => risk.uncertainty).filter(Boolean).slice(0, 3);
  const block = (title, items) => `<div class="rationale-block"><b>${escapeHtml(title)}</b><ul>${items.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>`;
  container.innerHTML = [
    block("What Locus considered", factors),
    block("Evidence used", sources.length
      ? sources.slice(0, 5).map(item => `${item.publisher} — ${item.title}${item.authority ? ` (${item.authority})` : ""}`)
      : ["No evidence was attached to this assessment."]),
    block("Assumptions", assumptions),
    block("Confidence and uncertainties", [...confidence, ...(recommendation.reasons || []), ...uncertainties].length
      ? [...confidence, ...(recommendation.reasons || []), ...uncertainties]
      : ["No confidence or uncertainty notes were reported."]),
  ].join("");
}

function renderUncertainty(assessment) {
  const panel = $("#uncertainty-panel");
  if (!panel) return;
  const items = [
    ...(assessment.risks || []).map(risk => risk.uncertainty).filter(Boolean),
    ...((assessment.recommendation || {}).uncertainty || []),
    ...(assessment.limitations || []),
  ];
  const unique = [...new Set(items)];
  panel.innerHTML = `<span>!</span><div><b>Uncertainty to keep in view</b>${
    unique.length
      ? `<ul>${unique.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
      : "<p>No specific uncertainties were reported for this assessment.</p>"
  }${(assessment.recommendation || {}).requires_human_review ? `<p class="uncertainty-flag">High-severity or unverified findings require human review before capital is committed.</p>` : ""}</div>`;
}

/* UI.md: the company section is not a plain restatement of the form — it opens
   with a short Agent summary and analysis of the company. */
function renderProfileSummary(assessment) {
  const container = $("#profile-summary");
  if (!container) return;
  const profile = assessment.company_profile || {};
  const risks = assessment.risks || [];
  const recommendation = assessment.recommendation || {};
  const summary = (profile.summary || "").trim();
  const highs = risks.filter(risk => SEVERITY_LEVEL[risk.severity] === "high");
  const categories = [...new Set(risks.map(risk => risk.category).filter(Boolean))];
  const points = [];
  if (risks.length) {
    points.push(`${risks.length} exposures identified${highs.length ? `, ${highs.length} of them high priority` : ""}${categories.length ? ` — concentrated in ${categories.slice(0, 3).join(", ").toLowerCase()}` : ""}.`);
  }
  if (assessment.meta?.evidence_count) {
    const count = assessment.meta.evidence_count;
    points.push(`The assessment draws on ${count} retrieved evidence item${count === 1 ? "" : "s"}${assessment.meta.data_mode === "preview" ? " (preview placeholders)" : " from the project knowledge base"}.`);
  }
  if (recommendation.confidence) {
    points.push(`Reported confidence is ${recommendation.confidence}${recommendation.requires_human_review ? ", and the findings are flagged for human review" : ""}.`);
  }
  if (!summary && !points.length) {
    container.hidden = true;
    return;
  }
  container.hidden = false;
  container.innerHTML = `<p class="profile-summary-label">Agent summary</p>`
    + (summary ? `<p class="profile-summary-text">${escapeHtml(summary)}</p>` : "")
    + (points.length ? `<ul class="profile-summary-points">${points.map(point => `<li>${escapeHtml(point)}</li>`).join("")}</ul>` : "");
}

function renderAssessmentMeta(assessment) {
  const meta = assessment.meta || {};
  const live = Boolean(meta.assessment_id);
  const zh = currentLanguage() === "zh";
  const tags = [];
  if (meta.assessment_id) tags.push(`Assessment ${meta.assessment_id}`);
  tags.push(live ? (zh ? "基于证据的评估" : "Evidence-based assessment") : (zh ? "示意性评估" : "Indicative assessment"));
  if (meta.model_name && meta.model_name !== "preview") tags.push(meta.model_name);
  if (meta.evidence_count) tags.push(zh ? `已检索 ${meta.evidence_count} 条证据` : `${meta.evidence_count} evidence items retrieved`);
  // Make the content language explicit: switching the interface language does not
  // translate an analysis that was already generated.
  if (meta.language) {
    const contentZh = String(meta.language).toLowerCase() === "zh";
    tags.push(
      contentZh
        ? (zh ? "分析语言：中文" : "Analysis language: Chinese")
        : (zh ? "分析语言：英文" : "Analysis language: English")
    );
  }
  const metaLine = $("#assessment-meta");
  if (metaLine) metaLine.textContent = tags.join(" · ");
  const modeTag = $("#assessment-mode");
  if (modeTag) modeTag.textContent = live ? (zh ? "已生成" : "Prepared") : (zh ? "示意" : "Indicative");
}

/* Switching the interface language does not translate an analysis the Agent has
   already produced. Tell the user which language the content is in rather than
   leaving them with English text in a Chinese interface. */
function announceContentLanguage() {
  const assessment = state.assessment;
  if (!assessment) return;
  const generated = String(assessment.meta?.language || "").toLowerCase();
  const ui = currentLanguage();
  try { renderAssessmentMeta(assessment); } catch { /* meta line is cosmetic */ }
  if (!generated || generated === ui) return;
  showToast(
    ui === "zh"
      ? "这份分析是用英文生成的，切换界面语言不会自动翻译。重新运行分析即可得到中文结果。"
      : "This analysis was generated in Chinese. Switching the interface does not translate it — re-run the analysis for an English version."
  );
}

function renderAssessment(assessment) {
  // Each section renders independently so one bad field can never blank the page.
  const guard = (render) => { try { render(); } catch (error) { console.error("Assessment section failed:", error); } };
  const profile = assessment.company_profile || {};
  const risks = assessment.risks || [];
  const production = (profile.production_locations || []).map(item => `${locationName(item)}${item.share ? ` ${item.share}%` : ""}`).join(" · ");
  const markets = (profile.target_markets || []).map(item => `${locationName(item)}${item.share ? ` ${item.share}%` : ""}`).join(" · ");
  guard(() => {
    $("#profile-grid").innerHTML = [
      ["Company", profile.company_name],
      ["Industry", INDUSTRY_LABELS[profile.industry] || (profile.industry || "").replaceAll("_", " ")],
      ["Main product", profile.products],
      ["Home country", homeCountryLabel(profile.home_country)],
      ["Production footprint", production],
      ["Target markets", markets],
      ["Decision context", profile.decision_question],
      ["Decision drivers", (profile.restrictions || []).map(value => TRIGGER_LABELS[value] || value.replaceAll("_", " ")).join(" · ")],
      ["Priorities", (profile.priorities || []).map(item => item.dimension).join(" > ")],
      ["Investment budget", BUDGET_LABELS[profile.investment_budget] || "Not specified"],
      ["Planning horizon", (profile.time_horizon || "").replaceAll("_", " ")],
    ].map(([label, value]) => `<div><span>${escapeHtml(label)}</span><b>${escapeHtml(value || "Not specified")}</b></div>`).join("");
  });
  guard(() => { $("#profile-extra").textContent = [profile.summary, profile.notes].filter(Boolean).join(" "); });
  guard(() => renderProfileSummary(assessment));
  guard(() => renderAssessmentMeta(assessment));
  guard(() => renderRiskRadar(risks));
  guard(() => renderRiskSummary(risks));
  guard(() => {
    $("#risk-list").innerHTML = risks.map((risk, index) => {
      const level = SEVERITY_LEVEL[risk.severity] || "medium";
      const check = risk.verification && risk.verification !== "verified"
        ? `<span class="evidence-check ${escapeHtml(risk.verification)}">${escapeHtml(risk.verification)}</span>`
        : "";
      const evidenceLabel = risk.insufficient
        ? `<p class="evidence-label warn">${L("Insufficient evidence", "证据不足")} — ${L("no source supports this risk, so it is treated as an inference and capped at medium severity.", "没有证据支撑该风险，已按推断处理，严重度上限为中等。")}</p>`
        : `<p class="evidence-label">${L("Supporting evidence", "支撑证据")} ${check}</p>`;
      return `
      <article class="risk-item" id="risk-${index}">
        <div class="risk-title"><span class="severity ${level}">${escapeHtml(risk.severity)}</span><h4>${escapeHtml(risk.name)}</h4>${risk.category ? `<span class="risk-category">${escapeHtml(risk.category)}</span>` : ""}</div>
        <p class="risk-description">${escapeHtml(risk.description)}</p>
        ${evidenceLabel}
        ${evidenceMarkup(risk.evidence) || `<div class="evidence-link static"><span class="evidence-main">${L("No linked evidence for this risk.", "该风险未关联任何证据。")}</span></div>`}
        ${risk.uncertainty ? `<p class="risk-uncertainty"><b>Uncertainty</b> · ${escapeHtml(risk.uncertainty)}</p>` : ""}
      </article>`;
    }).join("");
  });
  guard(() => renderIntelligence(assessment));
  guard(() => renderRationale(assessment));
  guard(() => renderUncertainty(assessment));
}

/* ----------------------------------------------------- scenario simulation */

function runScenarioSimulation() {
  const assessment = state.assessment;
  if (!assessment) {
    showToast("Run the assessment first — scenario options come from the Agent run.");
    return;
  }
  // Projects saved before scenario results existed carry none, so the analysis is
  // re-run with the stored profile and then continues straight into the simulation.
  if (!(assessment.scenarios || []).length) {
    const profile = currentProject()?.company_profile || assessment.company_profile;
    if (!profile) {
      showToast("Run the assessment first — scenario options come from the Agent run.");
      return;
    }
    showToast("No scenario results are saved for this decision — re-running the analysis to produce them.");
    runAnalysis(profile, true);
    return;
  }
  showScreen("scenario-loading");
  eachStageIn("sim-stages", "idle");
  updateSimProgress();
  const total = document.querySelectorAll("#sim-stages li").length;
  let position = 0;
  const timer = setInterval(() => {
    if (position > 0) setStageIn("sim-stages", position - 1, "done");
    if (position < total) { setStageIn("sim-stages", position, "working"); position += 1; }
    else clearInterval(timer);
    updateSimProgress();
  }, 500);
  setTimeout(() => {
    clearInterval(timer);
    eachStageIn("sim-stages", "done");
    updateSimProgress();
    try { renderScenarios(assessment); } catch (error) { showToast(`Scenario rendering issue: ${error.message}`); }
    setTimeout(() => showScreen("scenarios"), 420);
  }, 3100);
}

/* Maps a display dimension to the Agent's score-breakdown key so each bar can
   say whether that dimension was scored from evidence or inferred. */
const SCENARIO_BREAKDOWN_KEY = {
  cost: "cost_score",
  resilience: "resilience_score",
  geopolitical_risk: "geopolitical_risk_score",
  market_access: "market_access_score",
  feasibility: "implementation_score",
};

function dimensionList(scores, breakdown) {
  const byDimension = {};
  (breakdown || []).forEach(entry => { byDimension[entry.dimension] = entry; });
  return SCENARIO_DIMENSIONS.map(([key, label]) => {
    const value = Math.max(0, Math.min(100, Number(scores[key]) || 0));
    const entry = byDimension[SCENARIO_BREAKDOWN_KEY[key]];
    const basis = !entry
      ? ""
      : entry.basis === "evidence"
        ? `<span class="dim-basis evidence" title="${escapeHtml(L("Backed by linked evidence", "有证据支撑"))}">${L("evidence", "证据")}</span>`
        : `<span class="dim-basis inference" title="${escapeHtml(L("Model inference — no evidence linked", "模型推断——未关联证据"))}">${L("inference", "推断")}</span>`;
    return `<li><span class="dim-label">${escapeHtml(label)}${basis}</span><span class="dim-bar"><i style="width:${value}%"></i></span><b>${value}</b></li>`;
  }).join("");
}

function bulletBlock(title, items, emptyText) {
  if (items && items.length) {
    return `<div class="scenario-block"><b>${title}</b><ul>${items.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>`;
  }
  return emptyText ? `<div class="scenario-block"><b>${title}</b><p class="muted">${emptyText}</p></div>` : "";
}

function scenarioDetail(scenario, index, weighting) {
  const ranked = SCENARIO_DIMENSIONS.map(([key, label]) => ({ label, value: scenario.scores[key] })).sort((a, b) => b.value - a.value);
  const strongest = ranked[0];
  const weakest = ranked[ranked.length - 1];
  const evidence = (scenario.evidence || []).length
    ? `<div class="scenario-block"><b>Evidence support</b><ul class="scenario-evidence">${scenario.evidence.map(item => `<li><span>${escapeHtml(item.publisher)} — ${escapeHtml(item.title)}</span><em>${escapeHtml([item.date, item.authority].filter(Boolean).join(" · "))}</em><span class="evidence-conf">Confidence: ${evidenceConfidence(item)}</span></li>`).join("")}</ul></div>`
    : `<div class="scenario-block"><b>Evidence support</b><p class="muted">No source is linked to this scenario yet.</p></div>`;
  return `
    <div class="scenario-detail" id="scenario-detail-${index}" hidden>
      <div class="scenario-block"><b>Scenario overview</b><p>${escapeHtml(scenario.summary || "")}</p></div>
      ${bulletBlock("Potential benefits", scenario.benefits, "No benefits were listed.")}
      ${bulletBlock("Potential risks", scenario.risks, "No risks were listed.")}
      ${bulletBlock("Key assumptions", scenario.assumptions, "No assumptions were listed.")}
      ${evidence}
      <details class="scenario-why">
        <summary>Why this assessment? <span>+</span></summary>
        <div class="scenario-why-body">
          <p><b>Scoring drivers.</b> Strongest dimension: ${escapeHtml(strongest.label)} (${strongest.value}); weakest: ${escapeHtml(weakest.label)} (${weakest.value}).</p>
          <p><b>Weighting.</b> ${escapeHtml(weighting)}</p>
          <p><b>Confidence.</b> ${escapeHtml(scenario.confidence.label)} — ${escapeHtml(scenario.confidence.reason)}.</p>
          <p><b>Not a forecast.</b> Scores are estimates built from the evidence and assumptions listed above.</p>
        </div>
      </details>
    </div>`;
}

function scenarioCard(scenario, index, recommendedId, weighting) {
  const letter = String.fromCharCode(65 + index);
  const recommended = Boolean(scenario.scenario_id && scenario.scenario_id === recommendedId);
  return `
  <article class="scenario-card${recommended ? " recommended" : ""}">
    <header class="scenario-card-head">
      <div><p class="scenario-tag">Scenario ${letter}</p><h4>${escapeHtml(scenario.name)}</h4></div>
      ${recommended ? `<span class="scenario-badge">Recommended</span>` : ""}
    </header>
    <p class="scenario-summary">${escapeHtml(scenario.summary || "")}</p>
    <div class="scenario-score"><b>${scenario.overall_score}</b><span>/ 100</span></div>
    <p class="scenario-score-label">Overall score · Confidence: <b>${escapeHtml(scenario.confidence.label)}</b></p>
    <ul class="scenario-dimensions">${dimensionList(scenario.scores, scenario.breakdown)}</ul>
    <button class="button button-secondary scenario-toggle" type="button" data-scenario-toggle="${index}" aria-expanded="false">View Analysis <span>→</span></button>
    ${scenarioDetail(scenario, index, weighting)}
  </article>`;
}

function reportSection(number, title, inner) {
  return `<div class="report-block"><p class="report-number">${number}</p><div class="report-text"><h4>${escapeHtml(title)}</h4>${inner}</div></div>`;
}

function renderStrategicReport(assessment, scenarioList) {
  const body = $("#report-body");
  if (!body) return;
  const profile = assessment.company_profile || {};
  const risks = assessment.risks || [];
  const scenarios = scenarioList || normalizeScenarios(assessment);
  const recommendation = assessment.recommendation || {};
  const best = scenarios[0];
  const runnerUp = scenarios[1];
  const footprint = (profile.production_locations || []).map(item => `${locationName(item)}${item.share ? ` ${item.share}%` : ""}`).join(" · ") || "not specified";
  const markets = (profile.target_markets || []).map(item => `${locationName(item)}${item.share ? ` ${item.share}%` : ""}`).join(" · ") || "not specified";
  const sources = [];
  scenarios.forEach(scenario => (scenario.evidence || []).forEach(item => {
    if (!sources.some(existing => existing.title === item.title && existing.publisher === item.publisher)) sources.push(item);
  }));
  const assumptions = [...new Set(scenarios.flatMap(scenario => scenario.assumptions || []))];
  const questions = [];
  const openRisks = risks.filter(risk => risk.verification === "unverified" || risk.verification === "partial");
  if (openRisks.length) questions.push(`Verify the open items behind "${openRisks[0].name}" — the current sources are not company specific.`);
  questions.push("What is the cost gap per unit between each production location, including logistics and duties?");
  questions.push("Which critical components or materials have only one qualified supplier today?");
  questions.push("What customer certifications or contract terms limit how quickly production can move?");
  const table = `<table class="report-table"><thead><tr><th>Scenario</th><th>Overall</th><th>Strongest dimension</th><th>Main risk</th></tr></thead><tbody>${scenarios.map(scenario => {
    const top = SCENARIO_DIMENSIONS.map(([key, label]) => ({ label, value: scenario.scores[key] })).sort((a, b) => b.value - a.value)[0];
    return `<tr><td>${escapeHtml(scenario.name)}</td><td>${scenario.overall_score}/100</td><td>${escapeHtml(top.label)} (${top.value})</td><td>${escapeHtml((scenario.risks || [])[0] || "—")}</td></tr>`;
  }).join("")}</tbody></table>`;
  const summaryLine = scenarios.length
    ? `${scenarios.length} options were compared. ${best.name} scores highest at ${best.overall_score}/100${runnerUp ? `, ahead of ${runnerUp.name} (${runnerUp.overall_score}/100)` : ""}.`
    : "No scenario comparison is available yet.";
  body.innerHTML = [
    reportSection("1", "Executive summary", `<p>${escapeHtml(summaryLine)}</p>${recommendation.headline ? `<p>${escapeHtml(recommendation.headline)}</p>` : ""}`),
    reportSection("2", "Company profile", `<p>${escapeHtml(`${profile.company_name || "The company"} · ${INDUSTRY_LABELS[profile.industry] || profile.industry || "industry not specified"}`)}</p><p>${escapeHtml(`Main product: ${profile.products || "not specified"}`)}</p>`),
    reportSection("3", "Current supply chain overview", `<p>${escapeHtml(`Production footprint: ${footprint}`)}</p><p>${escapeHtml(`Target markets: ${markets}`)}</p><p>${escapeHtml(`Decision: ${profile.decision_question || "not specified"}`)}</p>`),
    reportSection("4", "Key risks identified", risks.length ? `<ul>${risks.slice(0, 4).map(risk => `<li><b>${escapeHtml(risk.severity)}</b> — ${escapeHtml(risk.name)}: ${escapeHtml(risk.description || "")}</li>`).join("")}</ul>` : "<p>No risks were reported.</p>"),
    reportSection("5", "Scenario comparison", table),
    reportSection("6", "Evidence &amp; assumptions", `<p>${escapeHtml(`Sources used: ${sources.length}`)}</p>${sources.length ? `<ul>${sources.slice(0, 5).map(item => `<li>${escapeHtml(`${item.publisher} — ${item.title}${item.authority ? ` (${item.authority})` : ""}`)}</li>`).join("")}</ul>` : ""}${assumptions.length ? `<p>Key assumptions:</p><ul>${assumptions.slice(0, 5).map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}`),
    reportSection("7", "Questions for further analysis", `<ul>${questions.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`),
  ].join("");
}

function renderScenarios(assessment) {
  const profile = assessment.company_profile || {};
  const scenarios = normalizeScenarios(assessment);
  const meta = assessment.meta || {};
  const priorities = (profile.priorities || []).map(item => item.dimension);
  // The backend reports which weighting it applied. Without a user ranking the
  // five dimensions are equal, so the UI must not claim a stated priority order.
  const weightingMode = meta.weighting_mode || (profile.priorities_declared ? "user" : "equal");
  const weighting = weightingMode === "user" && priorities.length
    ? `The overall score is weighted by your stated priorities: ${priorities.join(" > ")}.`
    : "No priority ranking was provided, so the five dimensions are weighted equally.";
  $("#scenario-grid").innerHTML = scenarios.map((scenario, index) => scenarioCard(scenario, index, assessment.recommendation?.recommended_scenario_id || "", weighting)).join("");
  const metaLine = $("#scenario-meta");
  if (metaLine) {
    metaLine.textContent = [
      meta.assessment_id ? `Assessment ${meta.assessment_id}` : "",
      meta.data_mode === "preview" ? "Scenario estimates" : "Scenario analysis from the latest assessment",
      meta.model_name && meta.model_name !== "preview" ? meta.model_name : "",
      `${scenarios.length} scenario${scenarios.length === 1 ? "" : "s"} compared`,
    ].filter(Boolean).join(" · ");
  }
  const mode = $("#scenario-mode");
  if (mode) mode.textContent = meta.assessment_id ? "Prepared" : "Indicative";
  const note = $("#scenario-update-note");
  if (note) {
    const comparison = state.scenarioComparison;
    if (comparison && (comparison.after || []).length) {
      note.hidden = false;
      note.innerHTML = `<p class="section-number">UPDATED SCENARIO RESULT</p><ul class="scenario-comparison">${comparison.after.map((item, index) => {
        const previous = comparison.before[index];
        const delta = previous ? item.score - previous.score : 0;
        const arrow = delta > 0 ? `↑ +${delta}` : delta < 0 ? `↓ ${delta}` : "unchanged";
        const tone = delta > 0 ? "up" : delta < 0 ? "down" : "";
        return `<li><span>${escapeHtml(item.name)}</span><b>${previous ? `${previous.score} → ${item.score}` : item.score}</b><em class="${tone}">${arrow}</em></li>`;
      }).join("")}</ul><p class="scenario-comparison-reason">Reason: ${escapeHtml(comparison.reason)}${comparison.live ? "" : " · preview estimate"}</p>`;
    } else {
      note.hidden = true;
      note.innerHTML = "";
    }
  }
  renderStrategicReport(assessment, scenarios);
  advanceProjectStage("SCENARIO_SIMULATION");
}

function showToast(message) { const toast = $("#toast"); toast.textContent = message; toast.classList.add("show"); setTimeout(() => toast.classList.remove("show"), 4200); }

/* ---------------------------------------------- agent connection status --
   The page silently falls back to the local preview when the Agent service is
   not reachable, which is hard to distinguish from a broken page. This makes
   the connection state, and the reason for any fallback, visible. */

function setAgentStatus(state, detail, options) {
  const chip = $("#agent-status");
  if (chip) {
    chip.dataset.state = state;
    chip.textContent = state === "online" ? "Agent online" : state === "unreachable" ? "Agent offline" : state === "checking…" ? "Agent: checking…" : "Agent: indicative";
    chip.title = detail || "";
  }
  if (detail && !(options && options.silent)) {
    showAgentNotice(detail, state === "online" ? "ok" : "warn", { kind: "connection" });
  }
}

function showAgentNotice(message, tone, options) {
  const strip = $("#agent-notice");
  if (!strip) return;
  if (!message) {
    strip.hidden = true;
    strip.textContent = "";
    delete strip.dataset.kind;
    return;
  }
  strip.hidden = false;
  strip.dataset.tone = tone || "warn";
  // Connectivity warnings are tagged so a later successful check can clear them
  // without wiping warnings that belong to a specific run.
  strip.dataset.kind = (options && options.kind) || "run";
  strip.textContent = message;
}

async function checkAgentConnection(announce = false) {
  const chip = $("#agent-status");
  if (!window.LOCUS_API_BASE || !window.LOCUS_API_KEY) {
    setAgentStatus(
      "preview mode",
      "No analysis service is configured for this page, so results are generated locally and are indicative only."
    );
    if (announce) showToast("Preview mode: the page has no Agent API settings.");
    return;
  }
  if (chip) chip.textContent = "Agent: checking…";
  try {
    const response = await fetch(`${window.LOCUS_API_BASE}/health`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json().catch(() => ({}));
    setAgentStatus("online", `Analysis service online (${payload.status || "ok"}).`, { silent: true });
    // Clear a warning strip left behind by an earlier failed connection check.
    // Warnings that belong to a specific run are tagged differently and stay.
    const strip = $("#agent-notice");
    if (strip && strip.dataset.kind === "connection") showAgentNotice("");
    clearAgentRetry();
    if (announce) showToast(`Agent service reachable at ${window.LOCUS_API_BASE}.`);
  } catch (error) {
    setAgentStatus(
      "unreachable",
      "The analysis service is temporarily unreachable from this browser, so this session shows an indicative result. " +
        `(${error.message})`
    );
    scheduleAgentRetry();
    if (announce) showToast(`Agent service unreachable: ${error.message}`);
  }
}

/* The Agent service is restarted often during development. Without a retry, a
   tab that loaded while it was down stays "Agent offline" until a manual
   reload, even after the service comes back. */
let agentRetryTimer = null;

function clearAgentRetry() {
  if (agentRetryTimer) {
    clearTimeout(agentRetryTimer);
    agentRetryTimer = null;
  }
}

function scheduleAgentRetry() {
  if (agentRetryTimer) return;
  agentRetryTimer = setTimeout(() => {
    agentRetryTimer = null;
    checkAgentConnection();
  }, 15000);
}

// Coming back to the tab is a good moment to re-check, so a stale "offline"
// never survives a switch back to the page.
document.addEventListener("visibilitychange", () => {
  if (document.hidden) return;
  if ($("#agent-status")?.dataset.state === "unreachable") checkAgentConnection();
});

/* -------------------------------------------------------------- chat page */

const chatState = { messages: [], documents: [], updated: [], seeded: false, pendingCategory: "" };

const INFO_CATEGORIES = [
  "Add supplier information",
  "Add factory information",
  "Update production share",
  "Add cost information",
  "Add customer requirements",
];

function openChat() {
  if (!state.assessment) {
    showToast("Complete an assessment first — the consultation builds on it.");
    return;
  }
  if (!chatState.seeded) {
    chatState.messages.push({ id: "msg-open", role: "assistant", at: new Date().toISOString(), content: chatOpeningMessage(state.assessment), explain: true });
    chatState.seeded = true;
  }
  renderChatCategories();
  renderChatContext();
  renderChatLog();
  renderChatMeta();
  advanceProjectStage("AI_CONSULTATION");
  syncChatIntoProject();
  showScreen("chat");
}

function chatOpeningMessage(assessment) {
  const profile = assessment.company_profile || {};
  const risks = assessment.risks || [];
  const scenarios = normalizeScenarios(assessment);
  const top = scenarios[0];
  const high = risks.filter(risk => SEVERITY_LEVEL[risk.severity] === "high").length;
  const lines = [`I have reviewed the profile for **${profile.company_name || "your company"}**, the evidence set, the risk assessment and ${scenarios.length} scenario option${scenarios.length === 1 ? "" : "s"}.`];
  if (top) lines.push(`The current leading option is **${top.name}** at ${top.overall_score}/100, with ${high} high-priority exposure${high === 1 ? "" : "s"} to manage.`);
  lines.push([
    "To improve the assessment, additional information would help:",
    "1. Supplier dependency — which critical inputs or components have only one qualified source",
    "2. Cost differences between locations, including logistics and duties",
    "3. Investment constraints and budget ceiling",
    "4. Customer requirements or certifications that restrict origin",
    "5. Implementation timeline and capacity ramp-up limits",
  ].join("\n"));
  lines.push("You can answer any of these, ask a question, or use **+ Add information** to attach a document or a constraint.");
  return lines.join("\n\n");
}

function renderChatMeta() {
  const meta = state.assessment?.meta || {};
  const live = Boolean(meta.assessment_id);
  const mode = $("#chat-mode");
  if (mode) mode.textContent = live ? "Live agent" : "Preview";
  const line = $("#chat-meta");
  if (line) {
    line.textContent = [
      meta.assessment_id ? `Assessment ${meta.assessment_id}` : "",
      live ? "Consultation runs against the retrieved evidence set" : "Preview consultation · Agent service not connected",
      `${chatState.messages.length} message${chatState.messages.length === 1 ? "" : "s"} in this session`,
    ].filter(Boolean).join(" · ");
  }
}

function renderChatCategories() {
  const container = $("#chat-add-categories");
  if (!container) return;
  container.innerHTML = INFO_CATEGORIES.map(category => `<button class="chat-category" type="button" data-chat-category="${escapeHtml(category)}">${escapeHtml(category)}</button>`).join("");
}

function renderChatContext() {
  const container = $("#chat-context");
  if (!container) return;
  const assessment = state.assessment || {};
  const profile = assessment.company_profile || {};
  const risks = assessment.risks || [];
  const scenarios = normalizeScenarios(assessment);
  const footprint = (profile.production_locations || []).map(item => `${locationName(item)}${item.share ? ` ${item.share}%` : ""}`).join(" · ") || "not specified";
  const markets = (profile.target_markets || []).map(item => locationName(item)).join(" · ") || "not specified";
  container.innerHTML = `
    <div class="context-block">
      <p class="context-label">Company profile</p>
      <p class="context-strong">${escapeHtml(profile.company_name || "—")}</p>
      <p>${escapeHtml(profile.products || "")}</p>
      <p><span class="context-key">Production</span> ${escapeHtml(footprint)}</p>
      <p><span class="context-key">Markets</span> ${escapeHtml(markets)}</p>
      <p><span class="context-key">Decision</span> ${escapeHtml(profile.decision_question || "not specified")}</p>
    </div>
    <div class="context-block">
      <p class="context-label">Current risks</p>
      ${risks.length ? `<ul class="context-list">${risks.slice(0, 5).map(risk => `<li><span class="severity ${SEVERITY_LEVEL[risk.severity] || "medium"}">${escapeHtml(risk.severity)}</span> ${escapeHtml(risk.name)}</li>`).join("")}</ul>` : `<p class="muted">No risks recorded</p>`}
    </div>
    <div class="context-block">
      <p class="context-label">Scenario summary</p>
      ${scenarios.length ? `<ul class="context-scenarios">${scenarios.map(item => `<li><span>${escapeHtml(item.name)}</span><b>${item.overall_score}/100</b></li>`).join("")}</ul>` : `<p class="muted">No scenarios yet</p>`}
    </div>
    <div class="context-block">
      <p class="context-label">Updated information</p>
      ${chatState.updated.length || chatState.documents.length
        ? `<ul class="context-list">${chatState.updated.map(item => `<li>${escapeHtml(item)}</li>`).join("")}${chatState.documents.map(name => `<li>Document: ${escapeHtml(name)}</li>`).join("")}</ul>`
        : `<p class="muted">Nothing added yet</p>`}
    </div>`;
}

function chatExplainPanel() {
  const assessment = state.assessment || {};
  const profile = assessment.company_profile || {};
  const risks = assessment.risks || [];
  const recommendation = assessment.recommendation || {};
  const sources = [];
  risks.forEach(risk => (risk.evidence || []).forEach(item => {
    if (!sources.some(existing => existing.title === item.title)) sources.push(item);
  }));
  return `
    <details class="chat-explain">
      <summary>Why this assessment? <span>+</span></summary>
      <div class="chat-explain-body">
        <p><b>Factors considered.</b> ${escapeHtml(`Footprint ${(profile.production_locations || []).map(item => `${locationName(item)}${item.share ? ` ${item.share}%` : ""}`).join(", ") || "not specified"}; markets ${(profile.target_markets || []).map(item => locationName(item)).join(", ") || "not specified"}; priorities ${(profile.priorities || []).map(item => item.dimension).join(" > ") || "not ranked"}.`)}</p>
        <p><b>Evidence used.</b> ${escapeHtml(sources.length ? sources.slice(0, 4).map(item => `${item.publisher} — ${item.title}`).join("; ") : "no evidence was attached")}</p>
        <p><b>Assumptions.</b> Production shares reflect the current model; country-level public sources may not reflect company-specific contracts.</p>
        <p><b>Uncertainty.</b> ${escapeHtml([...new Set(risks.map(risk => risk.uncertainty).filter(Boolean))].slice(0, 2).join(" ") || "no specific uncertainties were reported")}</p>
        ${recommendation.confidence ? `<p><b>Confidence.</b> ${escapeHtml(recommendation.confidence)}</p>` : ""}
      </div>
    </details>`;
}

function renderRichText(text) {
  const escaped = escapeHtml(text || "");
  const blocks = escaped.split(/\n{2,}/).map(block => {
    const lines = block.split("\n").filter(line => line.trim() !== "");
    if (!lines.length) return "";
    if (lines.every(line => /^\s*[-•]\s+/.test(line))) {
      return `<ul>${lines.map(line => `<li>${line.replace(/^\s*[-•]\s+/, "")}</li>`).join("")}</ul>`;
    }
    if (lines.every(line => /^\s*\d+[.)]\s+/.test(line))) {
      return `<ol>${lines.map(line => `<li>${line.replace(/^\s*\d+[.)]\s+/, "")}</li>`).join("")}</ol>`;
    }
    return `<p>${lines.join("<br />")}</p>`;
  }).join("");
  return blocks.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
}

function chatBubble(message) {
  const mine = message.role === "user";
  return `
    <article class="chat-message${mine ? " from-user" : " from-ai"}">
      <div class="chat-bubble">
        <p class="chat-role">${mine ? "You" : "Locus consultant"}</p>
        <div class="chat-text">${renderRichText(message.content)}</div>
        ${message.explain && !mine ? chatExplainPanel() : ""}
        ${message.prompt ? `<div class="chat-prompt"><p>Would you like to update the scenario analysis?</p><div class="chat-prompt-actions"><button class="button button-secondary" type="button" data-chat-review>Review first</button><button class="button button-primary" type="button" data-chat-update>Update scenario</button></div></div>` : ""}
      </div>
    </article>`;
}

function renderChatLog() {
  const log = $("#chat-log");
  if (!log) return;
  log.innerHTML = chatState.messages.map(chatBubble).join("");
  log.scrollTop = log.scrollHeight;
}

function appendChatMessage(message) {
  const id = `msg-${chatState.messages.length + 1}-${Date.now().toString(36)}`;
  chatState.messages.push({ id, at: new Date().toISOString(), ...message });
  renderChatLog();
  renderChatMeta();
  return id;
}

function removeChatMessage(id) {
  chatState.messages = chatState.messages.filter(message => message.id !== id);
  renderChatLog();
  renderChatMeta();
}

function previewReply(question) {
  const assessment = state.assessment || {};
  const scenarios = normalizeScenarios(assessment);
  const top = scenarios[0];
  const dimensions = top ? SCENARIO_DIMENSIONS.map(([key, label]) => ({ label, value: top.scores[key] })).sort((a, b) => b.value - a.value) : [];
  return [
    "This answer is composed from the assessment currently on file; it is not a new research pass.",
    `Your question: “${question}”`,
    top ? `Within the current analysis, **${top.name}** leads at ${top.overall_score}/100 — strongest on ${dimensions[0].label.toLowerCase()} (${dimensions[0].value}), weakest on ${dimensions[dimensions.length - 1].label.toLowerCase()} (${dimensions[dimensions.length - 1].value}).` : "",
    "Add the supplier, cost or customer detail behind your question using **+ Add information**, then run **Update scenario analysis** so the scores reflect it.",
  ].filter(Boolean).join("\n\n");
}

async function sendChatMessage(text) {
  const assessment = state.assessment;
  const live = Boolean(assessment?.meta?.assessment_id && window.LOCUS_API_BASE && window.LOCUS_API_KEY);
  appendChatMessage({ role: "user", content: text });
  markReportOutdated();
  if (!live) {
    setTimeout(() => appendChatMessage({ role: "assistant", content: previewReply(text), explain: true }), 500);
    return;
  }
  const pending = appendChatMessage({ role: "assistant", content: "Reviewing your message against the evidence set…" });
  try {
    const response = await fetchWithTimeout(`${window.LOCUS_API_BASE}/api/v1/assessments/${assessment.meta.assessment_id}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, api_key: window.LOCUS_API_KEY, language: currentLanguage() === "zh" ? "zh" : "en" }),
    }, 30000);
    if (!response.ok) throw new Error(`chat service returned ${response.status}`);
    const updated = await response.json();
    const reply = (updated.chat_history || []).filter(turn => turn.role === "assistant").slice(-1)[0];
    removeChatMessage(pending);
    appendChatMessage({ role: "assistant", content: reply?.content || "I could not produce a reply for that message.", explain: true });
    state.assessment = mapApiAssessment(updated, assessment.company_profile);
    renderChatContext();
    renderChatMeta();
  } catch (error) {
    removeChatMessage(pending);
    appendChatMessage({ role: "assistant", content: `I could not reach the Agent service: ${error.message}. Your message is kept in this session.` });
  }
}

function addInformation(kind, detail) {
  markReportOutdated();
  chatState.updated.push(detail ? `${kind}: ${detail}` : kind);
  renderChatContext();
  appendChatMessage({ role: "user", content: detail ? `${kind}: ${detail}` : kind });
  appendChatMessage({ role: "assistant", content: "New information received.", prompt: true });
  $("#chat-add").hidden = true;
  $("#chat-add-field").hidden = true;
  $("#chat-add-text").value = "";
  chatState.pendingCategory = "";
}

function handleChatFiles(files) {
  const names = [...files].map(file => file.name);
  if (!names.length) return;
  chatState.documents.push(...names);
  const list = $("#chat-file-list");
  if (list) {
    list.hidden = false;
    list.innerHTML = names.map(name => `<li><span>${escapeHtml(name)}</span><span>attached</span></li>`).join("");
  }
  const note = $("#chat-file-note");
  if (note) {
    note.hidden = false;
    note.textContent = "Documents are attached to this browser session. Ingestion into the knowledge base needs the upload endpoint listed in backend changes.md.";
  }
  renderChatContext();
  appendChatMessage({ role: "user", content: `Uploaded: ${names.join(", ")}` });
  appendChatMessage({ role: "assistant", content: "New information received.", prompt: true });
}

/* Refresh only the scenario comparison through the dedicated endpoint, so the
   profile, evidence and risk work already done is reused. */
async function rerunScenariosForChat() {
  const meta = state.assessment?.meta || {};
  if (!meta.assessment_id || !window.LOCUS_API_BASE) return null;
  const constraints = [
    ...chatState.updated,
    ...chatState.documents.map(name => `Document provided: ${name}`),
  ];
  const response = await fetchWithTimeout(`${window.LOCUS_API_BASE}/api/v1/assessments/${meta.assessment_id}/scenarios`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      additional_constraints: constraints,
      api_key: window.LOCUS_API_KEY,
      llm_model: window.LOCUS_MODEL || "deepseek-flash",
      language: currentLanguage() === "zh" ? "zh" : "en",
    }),
  }, 90000);
  if (!response.ok) throw new Error(`scenario service returned ${response.status}`);
  const updated = await response.json();
  return mapApiAssessment(updated, state.assessment.company_profile);
}

async function rerunAssessmentForChat() {
  const profile = { ...(state.assessment.company_profile || {}) };
  const additions = [...chatState.updated, ...chatState.documents.map(name => `Document provided: ${name}`)];
  profile.notes = [profile.notes, ...additions.map(item => `Additional input: ${item}`)].filter(Boolean).join("\n");
  const { issues, payload } = buildBackendPayload(profile);
  if (issues.length) throw new Error(issues[0]);
  const api = await streamAssessment(payload, () => {});
  return mapApiAssessment(api, profile);
}

function comparisonText(before, after) {
  return after.map((item, index) => {
    const previous = before[index];
    if (!previous) return `${item.name}: ${item.score}/100`;
    const delta = item.score - previous.score;
    const arrow = delta > 0 ? ` ↑ +${delta}` : delta < 0 ? ` ↓ ${delta}` : " — unchanged";
    return `${item.name}: ${previous.score} → **${item.score}**${arrow}`;
  }).join("\n");
}

async function runScenarioUpdate() {
  const assessment = state.assessment;
  if (!assessment) return;
  markReportOutdated();
  const before = normalizeScenarios(assessment).map(item => ({ name: item.name, score: item.overall_score }));
  const steps = ["New business constraints", "Updated risk factors", "Additional evidence", "User preferences"];
  const panel = $("#chat-update-state");
  panel.hidden = false;
  panel.innerHTML = `<p class="section-number">UPDATING SCENARIO ANALYSIS</p><p class="chat-add-title">Updating Scenario Analysis…</p><ol class="chat-update-steps" id="chat-update-steps">${steps.map(step => `<li>${escapeHtml(step)} <span>Waiting</span></li>`).join("")}</ol>`;
  let position = 0;
  const timer = setInterval(() => {
    if (position > 0) setStageIn("chat-update-steps", position - 1, "done");
    if (position < steps.length) { setStageIn("chat-update-steps", position, "working"); position += 1; }
    else clearInterval(timer);
  }, 600);
  const live = Boolean(assessment.meta?.assessment_id && window.LOCUS_API_BASE && window.LOCUS_API_KEY);
  let rerun = null;
  if (live) {
    try {
      rerun = await rerunScenariosForChat();
    } catch (error) {
      try { rerun = await rerunAssessmentForChat(); }
      catch (fallbackError) {
        showToast(`Scenario update failed: ${fallbackError.message} — showing the previous analysis.`);
      }
    }
  }
  await new Promise(resolve => setTimeout(resolve, live ? 600 : 2600));
  clearInterval(timer);
  eachStageIn("chat-update-steps", "done");
  if (rerun) {
    state.assessment = rerun;
  } else {
    const bump = Math.min(5, Math.max(1, chatState.updated.length + chatState.documents.length) * 2);
    state.assessment = {
      ...assessment,
      scenarios: normalizeScenarios(assessment).map(item => ({ ...item, overall_score: Math.min(100, item.overall_score + bump) })),
    };
  }
  const after = normalizeScenarios(state.assessment).map(item => ({ name: item.name, score: item.overall_score }));
  const reason = [...chatState.updated, ...chatState.documents.map(name => `document: ${name}`)].join("; ") || "no new constraints were added";
  state.scenarioComparison = { before, after, reason, live };
  panel.hidden = true;
  appendChatMessage({
    role: "assistant",
    content: [
      "Scenario analysis updated.",
      comparisonText(before, after),
      `Reason: ${reason}.`,
      live ? "" : "**Preview mode:** scores were adjusted illustratively because the Agent service is not connected.",
    ].filter(Boolean).join("\n\n"),
    explain: true,
  });
  renderScenarios(state.assessment);
  renderChatContext();
  showToast(live ? "Scenario analysis updated from the Agent run." : "Scenario analysis updated (preview estimate).");
  setTimeout(() => showScreen("scenarios"), 700);
}

function reviewFirst() {
  appendChatMessage({ role: "assistant", content: "Sure — the new information is listed under **Updated information** in the context panel. Tell me when you want it folded into the scenario scores, or keep asking questions first." });
}

/* ------------------------------------------------- final decision report
   UI.md: the frontend never writes the report itself — it embeds and downloads
   the PDF returned by the backend report service. */

const REPORT_SECTIONS = [
  "Executive summary",
  "Company profile",
  "Current supply chain situation",
  "Key risk assessment",
  "Scenario comparison",
  "Consultation insights",
  "Final decision / recommendation",
  "Evidence sources",
  "Uncertainties & limitations",
];

function currentReport() {
  const versions = currentProject()?.report_versions || [];
  return versions.length ? versions[versions.length - 1] : null;
}

function reportUrlFor(assessmentId) {
  return assessmentId && window.LOCUS_API_BASE ? `${window.LOCUS_API_BASE}/api/v1/assessments/${assessmentId}/report` : null;
}

function recordReportVersion() {
  const assessmentId = state.assessment?.meta?.assessment_id || null;
  const versions = currentProject()?.report_versions || [];
  const version = {
    version: versions.length + 1,
    report_id: assessmentId,
    url: reportUrlFor(assessmentId),
    generated_at: new Date().toISOString(),
  };
  syncChatIntoProject();
  updateCurrentProject({
    current_stage: "REPORT",
    report_id: version.report_id,
    report_url: version.url,
    report_versions: [...versions, version],
  });
  state.reportOutdated = false;
}

async function runReportGeneration() {
  showScreen("report-loading");
  eachStageIn("report-stages", "idle");
  const total = document.querySelectorAll("#report-stages li").length;
  let position = 0;
  const timer = setInterval(() => {
    if (position > 0) setStageIn("report-stages", position - 1, "done");
    if (position < total) { setStageIn("report-stages", position, "working"); position += 1; }
    else clearInterval(timer);
  }, 380);
  await new Promise(resolve => setTimeout(resolve, 2400));
  clearInterval(timer);
  eachStageIn("report-stages", "done");
  try { recordReportVersion(); } catch { /* project history is optional */ }
  renderReportPage();
  setTimeout(() => showScreen("report"), 340);
}

function renderReportPage() {
  const project = currentProject() || {};
  const report = currentReport();
  const profile = state.assessment?.company_profile || project.company_profile || {};
  const generatedAt = report?.generated_at ? new Date(report.generated_at) : new Date();
  const metaLine = $("#report-meta");
  if (metaLine) {
    metaLine.textContent = [
      project.name || profile.company_name || "Decision",
      `Generated ${generatedAt.toLocaleString()}`,
      report?.version ? `Report v${report.version}` : "",
      report?.report_id ? `Assessment ${report.report_id}` : "",
    ].filter(Boolean).join(" · ");
  }
  const status = $("#report-status");
  if (status) status.textContent = report?.url ? "Generated" : "Draft";
  const name = $("#report-file-name");
  if (name) name.textContent = `${profile.company_name || "Decision"} — Executive Decision Report`;
  const fileMeta = $("#report-file-meta");
  if (fileMeta) {
    fileMeta.textContent = [
      generatedAt.toLocaleDateString(),
      report?.url ? "PDF report" : "PDF not available for this session",
    ].join(" · ");
  }
  const download = $("#report-download");
  if (download) {
    download.href = report?.url || "#";
    download.dataset.available = report?.url ? "true" : "false";
  }
  const viewer = $("#report-viewer");
  if (viewer) {
    viewer.innerHTML = report?.url
      ? `<iframe class="report-frame" title="Executive Decision Report" src="${escapeHtml(report.url)}"></iframe>`
      : `<div class="report-placeholder">
          <p class="report-placeholder-title">The PDF report is being prepared</p>
          <p class="report-placeholder-text">A PDF is available once the analysis for this decision is finalised. Until then this page shows the structure the report will follow.</p>
          <p class="report-placeholder-label">The report will contain</p>
          <ol class="report-sections">${REPORT_SECTIONS.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ol>
        </div>`;
  }
  const outdated = $("#report-outdated");
  if (outdated) {
    outdated.hidden = !state.reportOutdated;
    outdated.textContent = state.reportOutdated
      ? "This report is outdated — the analysis changed after it was generated. Generate the report again to refresh it."
      : "";
  }
}

function markReportOutdated() {
  if (!currentReport()) return;
  state.reportOutdated = true;
}

function openSaveModal() { const modal = $("#save-modal"); if (modal) modal.hidden = false; }
function closeSaveModal() { const modal = $("#save-modal"); if (modal) modal.hidden = true; }

/* §7–§9: ending the consultation saves the project and returns home. */
function endConsultationAndSave() {
  closeSaveModal();
  const report = currentReport();
  const lastUserTurn = [...chatState.messages].reverse().find(message => message.role === "user");
  const recommendation = state.assessment?.recommendation || {};
  syncChatIntoProject();
  updateCurrentProject({
    status: "COMPLETED",
    current_stage: "REPORT",
    report_id: report?.report_id || state.assessment?.meta?.assessment_id || null,
    report_url: report?.url || null,
    final_decision: {
      summary: recommendation.headline || lastUserTurn?.content || "Consultation ended without an additional final statement.",
      decided_at: new Date().toISOString(),
    },
  });
  renderProjects();
  showToast("Decision project saved to My Decisions.");
  showScreen("home");
}

function openReportModal() { const modal = $("#report-modal"); if (modal) modal.hidden = false; }
function closeReportModal() { const modal = $("#report-modal"); if (modal) modal.hidden = true; }

function confirmReport() {
  closeReportModal();
  // UI.md §2: a short transition leads to the Final Decision Report page; the
  // project is only finalised when the user ends the consultation there.
  appendChatMessage({ role: "assistant", content: "Preparing the Executive Decision Report — you can review it, download it, or come back to the consultation." });
  runReportGeneration();
}

function clearInvalidMarks() {
  document.querySelectorAll("#decision-form .field-invalid").forEach(element => element.classList.remove("field-invalid"));
}

function showValidationError(issues) {
  const first = issues[0];
  const box = $("#form-error");
  if (box) {
    const rest = issues.length > 1 ? ` (${issues.length - 1} more item${issues.length === 2 ? "" : "s"} still need input.)` : "";
    box.textContent = `${first.message}${rest}`;
    box.hidden = false;
  }
  clearInvalidMarks();
  issues.forEach(issue => issue.target?.classList?.add("field-invalid"));
  // Jump back to the question that needs an answer.
  first.target?.scrollIntoView({ behavior: "smooth", block: "center" });
  if (first.target?.matches?.("input, select, textarea")) {
    try { first.target.focus({ preventScroll: true }); } catch { first.target.focus(); }
  }
  showToast(first.message);
}

function clearValidationError() {
  const box = $("#form-error");
  if (box && !box.hidden) {
    box.hidden = true;
    box.textContent = "";
  }
  clearInvalidMarks();
}

/* ------------------------------------------------------------ draft state */

function saveDraft() {
  const form = $("#decision-form");
  const values = {};
  new FormData(form).forEach((value, key) => {
    if (value instanceof File) return;
    if (values[key] === undefined) values[key] = value;
    else values[key] = [].concat(values[key], value);
  });
  try {
    localStorage.setItem(draftKey, JSON.stringify({ values, production: state.production, markets: state.markets }));
  } catch { /* storage blocked — the form keeps working, just without a draft */ }
  updateFormProgress();
  markDraftSaved();
}

/* Advanced questions only count once the deeper assessment is open, so the
   percentage always reflects the questions the user can actually see. */
function advancedQuestionStates(form) {
  const filled = (name) => (form[name]?.value || "").trim() !== "";
  const typed = (name) => (form[name]?.value || "").trim();
  const anyChecked = (selector) => document.querySelectorAll(selector).length > 0;
  return [
    filled("site_country"),
    filled("site_region"),
    filled("site_capacity"),
    filled("site_production_share"),
    filled("site_established_year"),
    filled("production_type"),
    filled("revenue_range"),
    filled("employee_count"),
    filled("factory_count"),
    filled("capacity_utilization"),
    filled("supplier_dependency_country"),
    filled("critical_suppliers"),
    anyChecked('input[name="supplier_concentration"]:checked'),
    anyChecked("#non-relocatable-options input:checked"),
    filled("investment_type"),
    typed("cost_increase") !== "" && typed("cost_increase") !== "Not specified",
    filled("payback_period"),
    anyChecked('input[name="success_criteria"]:checked'),
    anyChecked('input[name="non_negotiable"]:checked'),
    filled("risk_posture"),
    filled("advanced_notes"),
  ];
}

function updateFormProgress() {
  const form = $("#decision-form");
  // Seeded default rows (China / United States) only count once the user has
  // actually engaged with them, so a fresh form starts at 0%.
  const answeredLocation = (item) => Boolean(item.touched) || String(item.share).trim() !== "" || item.country === "NOT_SURE";
  const quickChecks = [
    form.company_name.value,
    form.products.value,
    // profile list.md: the decision question is answered as soon as the user
    // picks any preset option — there is no pre-selected default.
    Boolean(document.querySelector('input[name="decision_type"]:checked')) || form.decision_question.value.trim() !== "",
    state.production.some(answeredLocation),
    state.markets.some(answeredLocation),
    document.querySelectorAll("#restriction-options input:checked").length,
  ];
  const advancedOpen = !$("#advanced-fields").hidden;
  const checks = advancedOpen ? [...quickChecks, ...advancedQuestionStates(form)] : quickChecks;
  const answered = checks.filter(Boolean).length;
  const percent = Math.round((answered / checks.length) * 100);
  const value = $("#completion-value");
  const count = $("#completion-count");
  const fill = $("#completion-fill");
  if (value) value.textContent = `${percent}%`;
  if (count) count.textContent = `· ${answered} / ${checks.length} answered`;
  if (fill) fill.style.width = `${percent}%`;
}

function setSavedLabel(text) {
  const label = $("#completion-saved");
  if (label) label.textContent = text;
}

function markDraftSaved() {
  if (!canStore) {
    setSavedLabel("Autosave unavailable in this browser");
    return;
  }
  const now = new Date();
  setSavedLabel(`Draft saved automatically · ${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`);
}

function clearDraft() {
  try { localStorage.removeItem(draftKey); } catch { /* storage unavailable */ }
}

/* After a consultation is submitted the profile belongs to the decision project,
   so the form returns to a clean state for the next decision. */
function resetDecisionForm() {
  const form = $("#decision-form");
  form.reset();
  state.production = [{ country: "CN", share: "", other: "" }];
  state.markets = [{ country: "US", share: "", other: "" }];
  renderLocations("production");
  renderLocations("markets");
  renderPriorityItems();
  state.prioritiesDeclared = false;
  const homeOtherField = $("#home-country-other");
  if (homeOtherField) homeOtherField.hidden = true;
  document.querySelectorAll("[data-upload-zone]").forEach(zone => renderUploadList(zone));
  $("#advanced-fields").hidden = true;
  $("#show-advanced").hidden = false;
  document.querySelector('input[name="decision_type"]:checked')?.dispatchEvent(new Event("change", { bubbles: true }));
  updateSummaryCount();
  updateFormProgress();
  clearDraft();
  setSavedLabel("Draft saves automatically as you type");
}

/* --------------------------------------------------------- decision projects
   UI.md models My Decisions around Decision Projects with exactly two
   user-facing states: In Progress (resume from the latest stage) and Completed
   (read-only decision overview). */

const PROJECT_STAGES = ["INPUT", "INITIAL_ASSESSMENT", "SCENARIO_SIMULATION", "AI_CONSULTATION", "REPORT"];
const PROJECT_STAGE_LABEL = {
  INPUT: "User input",
  INITIAL_ASSESSMENT: "Initial assessment",
  SCENARIO_SIMULATION: "Scenario simulation",
  AI_CONSULTATION: "AI consultation",
  REPORT: "Report generation",
};
const PROJECT_STAGE_SCREEN = {
  INPUT: "consultation",
  INITIAL_ASSESSMENT: "assessment",
  SCENARIO_SIMULATION: "scenarios",
  AI_CONSULTATION: "chat",
  REPORT: "chat",
};

/* Projects created before the Decision Project model used `project_id` and had
   no status/stage, so records are migrated on read (and written back once). */
function migrateProject(record) {
  if (!record) return null;
  const profile = record.company_profile || record.assessment?.company_profile || {};
  return {
    ...record,
    decision_project_id: record.decision_project_id || record.project_id || `DP-${Math.random().toString(36).slice(2, 9).toUpperCase()}`,
    status: record.status === "COMPLETED" ? "COMPLETED" : "IN_PROGRESS",
    current_stage: record.current_stage || "INITIAL_ASSESSMENT",
    name: record.name || record.company_name || projectTitle(profile),
    company_name: record.company_name || profile.company_name || "",
    industry: record.industry || profile.industry || "battery_ev",
    product: record.product || profile.products || "",
    decision_question: record.decision_question || profile.decision_question || "",
    company_profile: profile,
    user_input: record.user_input || profile,
    risk_assessment: record.risk_assessment || { risks: record.assessment?.risks || record.risks || [] },
    scenario_results: record.scenario_results || { scenarios: record.assessment?.scenarios || [] },
    conversation_history: record.conversation_history || [],
    uploaded_documents: record.uploaded_documents || [],
    updated_constraints: record.updated_constraints || [],
    final_decision: record.final_decision || null,
    report_id: record.report_id || null,
    report_url: record.report_url || null,
    parent_decision_project_id: record.parent_decision_project_id || null,
    created_at: record.created_at || new Date().toISOString(),
    updated_at: record.updated_at || record.created_at || new Date().toISOString(),
  };
}

function readProjects() {
  try {
    const raw = JSON.parse(localStorage.getItem(projectsKey)) || [];
    const projects = raw.map(migrateProject).filter(Boolean);
    if (raw.some(record => record && !record.decision_project_id)) writeProjects(projects);
    return projects;
  } catch { return []; }
}

function writeProjects(projects) {
  try { localStorage.setItem(projectsKey, JSON.stringify(projects.slice(0, 40))); } catch { /* storage unavailable */ }
}

function projectTitle(profile) {
  const question = String(profile.decision_question || "").replace(/^[^:]{0,60}:\s*/, "").trim();
  if (question) return question.length > 74 ? `${question.slice(0, 71)}…` : question;
  const type = String(profile.decision_type || "Supply chain decision");
  return `${profile.company_name || "Untitled company"} — ${type}`;
}

function saveProject(assessment, profile) {
  const now = new Date().toISOString();
  const project = {
    decision_project_id: `DP-${Date.now().toString(36).toUpperCase()}`,
    status: "IN_PROGRESS",
    current_stage: "INITIAL_ASSESSMENT",
    name: projectTitle(profile),
    company_name: profile.company_name || "",
    industry: profile.industry || "battery_ev",
    product: profile.products || "",
    decision_question: profile.decision_question || "",
    company_profile: profile,
    user_input: profile,
    production_footprint: profile.production_locations || [],
    target_markets: profile.target_markets || [],
    decision_constraints: { investment_budget: profile.investment_budget || null, time_horizon: profile.time_horizon || null, priorities: profile.priorities || [] },
    evidence: (assessment.risks || []).flatMap(risk => risk.evidence || []),
    risk_assessment: { risks: assessment.risks || [] },
    scenario_results: { scenarios: assessment.scenarios || [] },
    conversation_history: [],
    uploaded_documents: [],
    updated_constraints: [],
    final_decision: null,
    report_id: null,
    report_url: null,
    parent_decision_project_id: state.parentProjectId || null,
    assessment,
    created_at: now,
    updated_at: now,
  };
  writeProjects([project, ...readProjects().filter(item => item.decision_project_id !== project.decision_project_id)]);
  state.projectId = project.decision_project_id;
  state.parentProjectId = null;
}

function currentProject() {
  return readProjects().find(item => item.decision_project_id === state.projectId) || null;
}

function updateCurrentProject(patch) {
  if (!state.projectId) return;
  const projects = readProjects();
  const index = projects.findIndex(item => item.decision_project_id === state.projectId);
  if (index < 0) return;
  projects[index] = { ...projects[index], ...patch, updated_at: new Date().toISOString() };
  writeProjects(projects);
}

function advanceProjectStage(stage) {
  const project = currentProject();
  if (!project) return;
  const current = PROJECT_STAGES.indexOf(project.current_stage || "INPUT");
  if (PROJECT_STAGES.indexOf(stage) <= current) return;
  updateCurrentProject({ current_stage: stage });
}

function syncChatIntoProject() {
  updateCurrentProject({
    conversation_history: chatState.messages.map(message => ({ role: message.role, content: message.content, at: message.at })),
    updated_constraints: [...chatState.updated],
    uploaded_documents: [...chatState.documents],
  });
}

/* Deleting always asks for confirmation first (UI.md: delete history records). */
function askDeleteProject(id) {
  const project = readProjects().find(item => item.decision_project_id === id);
  if (!project) {
    showToast("This decision project could not be found — reload My Decisions.");
    return;
  }
  const modal = $("#confirm-modal");
  if (!modal) return;
  $("#confirm-name").textContent = project.name || project.company_name || "this decision";
  modal.dataset.projectId = id;
  modal.hidden = false;
}

function closeDeleteConfirm() {
  const modal = $("#confirm-modal");
  if (modal) {
    modal.hidden = true;
    delete modal.dataset.projectId;
  }
}

function confirmDeleteProject() {
  const modal = $("#confirm-modal");
  const id = modal?.dataset.projectId;
  closeDeleteConfirm();
  if (!id) return;
  writeProjects(readProjects().filter(item => item.decision_project_id !== id));
  if (state.projectId === id) state.projectId = null;
  renderProjects();
  showToast("Decision project deleted.");
}

function formFromProfile(profile) {
  const form = $("#decision-form");
  if (!form || !profile) return;
  form.company_name.value = profile.company_name || "";
  form.products.value = profile.products || "";
  form.decision_question.value = profile.decision_question || "";
  form.notes.value = profile.notes || "";
  // Restore the home country, falling back to the "Other" box for a value the
  // select does not carry.
  const storedHome = String(profile.home_country || "").trim();
  const homeOption = [...(form.home_country?.options || [])].find(option => option.value === storedHome);
  if (homeOption) {
    form.home_country.value = storedHome;
    if (form.home_country_other) form.home_country_other.value = "";
  } else {
    form.home_country.value = "OTHER";
    if (form.home_country_other) form.home_country_other.value = storedHome;
  }
  const homeOther = $("#home-country-other");
  if (homeOther) homeOther.hidden = form.home_country.value !== "OTHER";
  state.production = (profile.production_locations || []).map(item => ({ country: item.country, share: item.share ?? "", other: item.other || "", touched: true }));
  state.markets = (profile.target_markets || []).map(item => ({ country: item.country, share: item.share ?? "", other: item.other || "", touched: true }));
  if (!state.production.length) state.production = [{ country: "CN", share: "", other: "" }];
  if (!state.markets.length) state.markets = [{ country: "US", share: "", other: "" }];
  renderLocations("production");
  renderLocations("markets");
  const type = String(profile.decision_type || "").replace(/ \(.*\)$/, "");
  const radio = [...document.querySelectorAll('input[name="decision_type"]')].find(node => node.value === type);
  if (radio) {
    radio.checked = true;
    radio.dispatchEvent(new Event("change", { bubbles: true }));
  }
  (profile.restrictions || []).forEach(value => {
    const chip = document.querySelector(`#restriction-options input[value="${value}"]`);
    if (chip) chip.checked = true;
  });
  updateSummaryCount();
  updateFormProgress();
}

function restoreChatFromProject(project) {
  chatState.messages = (project.conversation_history || []).map((turn, index) => ({ id: `saved-${index}`, ...turn }));
  chatState.updated = [...(project.updated_constraints || [])];
  chatState.documents = [...(project.uploaded_documents || [])];
  chatState.seeded = chatState.messages.length > 0;
}

function openProjectById(id) {
  const project = readProjects().find(item => item.decision_project_id === id);
  if (!project) {
    showToast("This decision project could not be found — reload My Decisions.");
    return;
  }
  if (project.status === "COMPLETED") {
    renderDecisionOverview(project);
    showScreen("overview");
    return;
  }
  state.projectId = project.decision_project_id;
  if (!project.assessment) {
    formFromProfile(project.company_profile || {});
    chatState.messages = [];
    chatState.updated = [];
    chatState.documents = [];
    chatState.seeded = false;
    showToast("This project has no saved assessment yet — review the profile and run the analysis.");
    showScreen("consultation");
    return;
  }
  if (project.assessment) state.assessment = project.assessment;
  formFromProfile(project.company_profile || {});
  restoreChatFromProject(project);
  const stage = project.current_stage || "INITIAL_ASSESSMENT";
  // Decisions saved before the analysis service was reachable hold indicative
  // content only; refresh them instead of showing stale results.
  const profile = project.company_profile || project.assessment?.company_profile;
  const storedPreview = !(project.assessment?.meta?.assessment_id);
  if (storedPreview && profile && window.LOCUS_API_BASE && window.LOCUS_API_KEY) {
    showToast("Refreshing this decision with the analysis service…");
    runAnalysis(profile, stage === "SCENARIO_SIMULATION");
    return;
  }
  if (stage === "INPUT") {
    showScreen("consultation");
  } else if (stage === "INITIAL_ASSESSMENT" && state.assessment) {
    renderAssessment(state.assessment);
    showScreen("assessment");
  } else if (stage === "SCENARIO_SIMULATION" && state.assessment) {
    renderScenarios(state.assessment);
    showScreen("scenarios");
  } else if (stage === "REPORT" && currentReport()) {
    renderReportPage();
    showScreen("report");
  } else if (state.assessment) {
    openChat();
  } else {
    showScreen("consultation");
  }
  const stageLabel = PROJECT_STAGE_LABEL[stage] || "the latest step";
  showToast(currentLanguage() === "zh"
    ? `已从「${ZH_TEXT[stageLabel] || stageLabel}」继续。`
    : `Resumed at ${stageLabel}.`);
}

function reassessProject(id) {
  const project = readProjects().find(item => item.decision_project_id === id);
  if (!project) {
    showToast("This decision project could not be found — reload My Decisions.");
    return;
  }
  state.parentProjectId = project.decision_project_id;
  state.projectId = null;
  formFromProfile(project.company_profile || {});
  chatState.messages = [];
  chatState.updated = [];
  chatState.documents = [];
  chatState.seeded = false;
  showToast("New assessment created from this decision — review the profile and run the analysis again.");
  showScreen("consultation");
}

function renderDecisionOverview(project) {
  const profile = project.company_profile || {};
  const risks = project.risk_assessment?.risks || [];
  const rawScenarios = project.scenario_results?.scenarios || [];
  const scenarios = rawScenarios.map(item => (item && item.scores ? item : mapScenario(item, evidenceLookupFromRisks(risks), { data_mode: "preview" })));
  const title = $("#overview-title");
  const meta = $("#overview-meta");
  const body = $("#overview-body");
  const status = $("#overview-status");
  if (!body) return;
  if (title) title.textContent = project.name || project.company_name || "Decision record";
  if (status) status.textContent = "Completed";
  const reassess = $("#overview-reassess");
  if (reassess) reassess.dataset.projectId = project.decision_project_id;
  if (meta) {
    meta.textContent = [
      project.decision_project_id,
      project.company_name || "",
      INDUSTRY_LABELS[project.industry] || "",
      `Updated ${new Date(project.updated_at || project.created_at).toLocaleDateString()}`,
      project.report_id ? `Report ${project.report_id}` : "",
    ].filter(Boolean).join(" · ");
  }
  const footprint = (profile.production_locations || []).map(item => `${locationName(item)}${item.share ? ` ${item.share}%` : ""}`).join(" · ") || "not specified";
  const markets = (profile.target_markets || []).map(item => `${locationName(item)}${item.share ? ` ${item.share}%` : ""}`).join(" · ") || "not specified";
  const section = (id, number, heading, inner) => `<section class="assessment-section" id="${id}"><div class="section-title-row"><div><p class="section-number">${number}</p><h3>${escapeHtml(heading)}</h3></div></div>${inner}</section>`;
  const consultation = [
    ...(project.updated_constraints || []).map(item => `Added: ${item}`),
    ...(project.uploaded_documents || []).map(name => `Document: ${name}`),
  ];
  body.innerHTML = [
    section("overview-company", "01 / SITUATION", "Company situation", `
      <div class="profile-grid">${[
        ["Company", project.company_name], ["Product", project.product],
        ["Production footprint", footprint], ["Target markets", markets],
        ["Decision question", project.decision_question],
      ].map(([label, value]) => `<div><span>${escapeHtml(label)}</span><b>${escapeHtml(value || "Not specified")}</b></div>`).join("")}</div>`),
    section("overview-assessment", "02 / ASSESSMENT", "Initial assessment", risks.length
      ? `${profile.summary ? `<p class="overview-text">${escapeHtml(profile.summary)}</p>` : ""}<ul class="overview-list">${risks.map(risk => `<li><span class="severity ${SEVERITY_LEVEL[risk.severity] || "medium"}">${escapeHtml(risk.severity)}</span> <b>${escapeHtml(risk.name)}</b> — ${escapeHtml(risk.description || "")}</li>`).join("")}</ul>`
      : `<p class="overview-text muted">No risk assessment was recorded.</p>`),
    section("overview-scenarios", "03 / SCENARIOS", "Scenario analysis", scenarios.length
      ? `<table class="report-table"><thead><tr><th>Scenario</th><th>Overall</th><th>Main trade-off</th></tr></thead><tbody>${scenarios.map(item => `<tr><td>${escapeHtml(item.name)}</td><td>${item.overall_score}/100</td><td>${escapeHtml((item.risks || [])[0] || "—")}</td></tr>`).join("")}</tbody></table>`
      : `<p class="overview-text muted">No scenario analysis was recorded.</p>`),
    section("overview-consultation", "04 / CONSULTATION", "Consultation summary", consultation.length
      ? `<ul class="overview-list">${consultation.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul><p class="overview-note">The full conversation is not shown in this record.</p>`
      : `<p class="overview-text muted">No additional information was added during the consultation.</p>`),
    section("overview-decision", "05 / DECISION", "Final decision", `
      <p class="overview-text">${escapeHtml(project.final_decision?.summary || "No final decision statement was recorded for this project.")}</p>
      ${project.report_url ? `<p class="overview-text"><a class="evidence-open" href="${escapeHtml(project.report_url)}" target="_blank" rel="noopener noreferrer">Open the decision report ↗</a></p>` : `<p class="overview-note">No generated report is attached to this project.</p>`}`),
  ].join("");
}

function projectCard(project) {
  const completed = project.status === "COMPLETED";
  const risks = project.risk_assessment?.risks || [];
  const artifacts = [
    ["Profile", true],
    ["Evidence", risks.some(risk => (risk.evidence || []).length)],
    ["Risks", risks.length > 0],
    ["Scenarios", (project.scenario_results?.scenarios || []).length > 0],
    ["Conversation", (project.conversation_history || []).length > 0],
    ["Report", Boolean(project.report_id)],
  ];
  const updated = new Date(project.updated_at || project.created_at).toLocaleDateString();
  return `
    <article class="project-card${completed ? " completed" : ""}">
      <div class="project-main">
        <p class="project-meta">${escapeHtml(project.decision_project_id)} · Updated: ${escapeHtml(updated)}</p>
        <h3>${escapeHtml(project.name || project.company_name || "Untitled decision")}</h3>
        <p class="project-sub">${escapeHtml([project.company_name, INDUSTRY_LABELS[project.industry] || ""].filter(Boolean).join(" · "))}</p>
        <p class="project-question">${escapeHtml(project.decision_question || "")}</p>
        <div class="project-tags">
          <span class="project-status ${completed ? "completed" : "in-progress"}">${completed ? "Completed" : "In progress"}</span>
          ${!completed && project.current_stage ? `<span class="project-stage">${escapeHtml(PROJECT_STAGE_LABEL[project.current_stage] || project.current_stage)}</span>` : ""}
          ${artifacts.filter(([, present]) => present).map(([label]) => `<span class="project-artifact">${escapeHtml(label)}</span>`).join("")}
        </div>
      </div>
      <div class="project-actions">
        <button class="button button-primary" type="button" data-open-project="${escapeHtml(project.decision_project_id)}">${completed ? "Open decision overview" : "Resume Decision"} <span>→</span></button>
        ${completed ? `<button class="button button-secondary" type="button" data-reassess-project="${escapeHtml(project.decision_project_id)}">Re-assess Decision <span>↻</span></button>` : ""}
        <button class="text-button project-delete" type="button" data-delete-project="${escapeHtml(project.decision_project_id)}">Delete</button>
      </div>
    </article>`;
}

function renderProjects() {
  const list = $("#project-list");
  if (!list) return;
  const projects = readProjects();
  if (!projects.length) {
    list.innerHTML = `<p class="project-empty">No decision projects yet. Complete a consultation and the Agent stores the company profile here.</p>`;
    return;
  }
  const inProgress = projects.filter(project => project.status !== "COMPLETED");
  const completed = projects.filter(project => project.status === "COMPLETED");
  const group = (label, items) => items.length
    ? `<section class="project-group"><p class="project-group-label">${escapeHtml(label)} <b>${items.length}</b></p>${items.map(projectCard).join("")}</section>`
    : "";
  list.innerHTML = group("In progress", inProgress) + group("Completed", completed);
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
    if (Array.isArray(draft.production)) state.production = draft.production.map(item => ({ other: "", ...item, touched: true }));
    if (Array.isArray(draft.markets)) state.markets = draft.markets.map(item => ({ other: "", ...item, touched: true }));
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
  if (event.target.closest("#show-advanced")) { $("#advanced-fields").hidden = false; $("#show-advanced").hidden = true; updateFormProgress(); }
  if (event.target.closest("#hide-advanced")) { $("#advanced-fields").hidden = true; $("#show-advanced").hidden = false; updateFormProgress(); }
  if (event.target.closest("#profile-expand")) { const extra = $("#profile-extra"); extra.hidden = !extra.hidden; $("#profile-expand").innerHTML = extra.hidden ? "View full profile <span>↓</span>" : "Hide full profile <span>↑</span>"; }
  if (event.target.closest("#simulate-button")) runScenarioSimulation();
  if (event.target.closest("#consultation-button")) openChat();
  if (event.target.closest("#lang-toggle")) {
    toggleLanguage();
    announceContentLanguage();
  }
  if (event.target.closest("#agent-status")) checkAgentConnection(true);
  if (event.target.closest("#chat-update") || event.target.closest("[data-chat-update]")) runScenarioUpdate();
  if (event.target.closest("[data-chat-review]")) reviewFirst();
  if (event.target.closest("#chat-report")) openReportModal();
  if (event.target.closest("#report-cancel")) closeReportModal();
  if (event.target.closest("#report-confirm")) confirmReport();
  if (event.target.closest("#chat-add-toggle")) { const panel = $("#chat-add"); if (panel) panel.hidden = !panel.hidden; }
  if (event.target.closest("#chat-add-close")) { const panel = $("#chat-add"); if (panel) panel.hidden = true; }
  const chatCategory = event.target.closest("[data-chat-category]");
  if (chatCategory) {
    chatState.pendingCategory = chatCategory.dataset.chatCategory;
    const field = $("#chat-add-field");
    if (field) field.hidden = false;
    $("#chat-add-text")?.focus();
  }
  if (event.target.closest("#chat-add-submit")) {
    const detail = ($("#chat-add-text")?.value || "").trim();
    if (!detail) showToast("Add a short description before submitting.");
    else addInformation(chatState.pendingCategory || "Additional information", detail);
  }
  const scenarioToggle = event.target.closest("[data-scenario-toggle]");
  if (scenarioToggle) {
    const detail = $(`#scenario-detail-${scenarioToggle.dataset.scenarioToggle}`);
    if (detail) {
      const open = detail.hidden;
      detail.hidden = !open;
      scenarioToggle.setAttribute("aria-expanded", String(open));
      scenarioToggle.innerHTML = open ? "Hide analysis <span>↑</span>" : "View Analysis <span>→</span>";
    }
  }
  const openProject = event.target.closest("[data-open-project]");
  const radarTarget = event.target.closest("[data-risk-target]");
  if (radarTarget) {
    document.querySelector(radarTarget.dataset.riskTarget)?.scrollIntoView({ behavior: "smooth", block: "center" });
    return;
  }
  if (event.target.closest("#export-button")) {
    const meta = state.assessment?.meta || {};
    if (meta.assessment_id && window.LOCUS_API_BASE) {
      window.open(`${window.LOCUS_API_BASE}/api/v1/assessments/${meta.assessment_id}/report`, "_blank", "noopener");
    } else {
      showToast("The briefing is prepared once the scenario step is complete.");
    }
  }
  if (openProject) return openProjectById(openProject.dataset.openProject);
  const reassessButton = event.target.closest("[data-reassess-project]");
  if (reassessButton) return reassessProject(reassessButton.dataset.reassessProject);
  const deleteButton = event.target.closest("[data-delete-project]");
  if (deleteButton) return askDeleteProject(deleteButton.dataset.deleteProject);
  if (event.target.closest("#confirm-cancel")) return closeDeleteConfirm();
  if (event.target.closest("#confirm-delete")) return confirmDeleteProject();
  if (event.target.closest("#report-back")) {
    showScreen("chat");
    showToast("Back in the consultation — the generated report stays available.");
    return;
  }
  if (event.target.closest("#report-end")) return openSaveModal();
  if (event.target.closest("#save-cancel")) return closeSaveModal();
  if (event.target.closest("#save-confirm")) return endConsultationAndSave();
  const download = event.target.closest("#report-download");
  if (download && download.dataset.available !== "true") {
    event.preventDefault();
    showToast("The PDF needs a live Agent run — connect the report service to download it.");
    return;
  }
  const overviewReassess = event.target.closest("#overview-reassess");
  if (overviewReassess?.dataset.projectId) return reassessProject(overviewReassess.dataset.projectId);
});

document.addEventListener("change", event => {
  const changed = event.target;
  if (changed.dataset.kind && changed.dataset.field === "country") {
    const item = state[changed.dataset.kind][Number(changed.dataset.index)];
    if (item) {
      item.touched = true;
      item.country = changed.value;
      // "Not sure" locations have no known share, so drop any value already set.
      if (item.country === "NOT_SURE") item.share = "";
    }
    renderLocations(changed.dataset.kind);
    updateFormProgress();
    return;
  }
  if (changed.name === "decision_type") {
    $("#relocate-country").hidden = changed.value !== "Relocate production";
    $("#new-site-country").hidden = changed.value !== "Establish a new production site";
    $("#decision-other").hidden = changed.value !== "Other";
    updateFormProgress();
    return;
  }
  if (changed.name === "home_country") {
    const other = $("#home-country-other");
    if (other) other.hidden = changed.value !== "OTHER";
    updateFormProgress();
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

document.addEventListener("keydown", event => {
  if (event.key !== "Enter" && event.key !== " ") return;
  const radarTarget = event.target.closest("[data-risk-target]");
  if (!radarTarget) return;
  event.preventDefault();
  document.querySelector(radarTarget.dataset.riskTarget)?.scrollIntoView({ behavior: "smooth", block: "center" });
});

document.addEventListener("input", event => {
  const input = event.target;
  if (input.dataset.kind) {
    const item = state[input.dataset.kind][Number(input.dataset.index)];
    if (!item) return;
    item[input.dataset.field] = input.value;
    item.touched = true;
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

$("#decision-form").addEventListener("input", () => { clearValidationError(); saveDraft(); });
$("#decision-form").addEventListener("change", () => { clearValidationError(); saveDraft(); });

$("#chat-form").addEventListener("submit", event => {
  event.preventDefault();
  const input = $("#chat-input");
  const text = (input?.value || "").trim();
  if (!text) { showToast("Type a message first."); return; }
  input.value = "";
  sendChatMessage(text);
});

$("#chat-file")?.addEventListener("change", event => handleChatFiles(event.target.files || []));

$("#decision-form").addEventListener("submit", event => {
  event.preventDefault();
  if (runInFlight) return;
  let profile;
  try {
    profile = readForm();
  } catch (error) {
    return showValidationError([{ message: `Could not read the form: ${error.message}`, target: $("#decision-form") }]);
  }
  const issues = findValidationIssue(profile);
  if (issues.length) return showValidationError(issues);
  clearValidationError();
  runAnalysis(profile);
});

restoreDraft();
renderLocations("production");
renderLocations("markets");
buildPriorityControls();
setupUploadZones();
buildEstablishedYears();
renderProjects();
updateSummaryCount();
document.querySelector('input[name="decision_type"]:checked')?.dispatchEvent(new Event("change", { bubbles: true }));
updateFormProgress();

/* Language: translate the rendered page and keep translating anything added later. */
i18nObserver.observe(document.body, { childList: true, subtree: true });
applyLanguage(storedLanguage());
checkAgentConnection();
