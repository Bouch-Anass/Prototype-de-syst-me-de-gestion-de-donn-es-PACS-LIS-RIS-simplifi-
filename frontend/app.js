const scenarios = {
  nominal: "/contracts/examples/summary.nominal.json",
  "missing-crp": "/contracts/examples/summary.missing-crp.json",
  "orthanc-unavailable": "/contracts/examples/summary.orthanc-unavailable.json",
};

const $ = (selector) => document.querySelector(selector);
const feedback = $("#feedback");
const record = $("#record");
const buttons = [...document.querySelectorAll("[data-scenario]")];
const modeButtons = [...document.querySelectorAll("[data-mode]")];
let selectedScenario = "nominal";
let loadedSummary = null;
let requestNumber = 0;
let mode = "mock";
let liveSession = false;
let currentPreviewUrl = null;

function setText(selector, value) {
  $(selector).textContent = value == null ? "—" : String(value);
}

function setStatus(selector, label, tone) {
  const element = $(selector);
  element.textContent = label;
  element.dataset.tone = tone;
}

function dateTime(value) {
  if (!value) return "Date indisponible";
  return new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function detail(label, value) {
  const group = document.createElement("div");
  const title = document.createElement("dt");
  const body = document.createElement("dd");
  title.textContent = label;
  body.textContent = value;
  group.append(title, body);
  return group;
}

function render(summary) {
  if (currentPreviewUrl) URL.revokeObjectURL(currentPreviewUrl);
  currentPreviewUrl = null;
  const patient = summary.patient;
  const encounter = summary.encounter;
  setText("#patient-name", patient.display_name);
  setText("#patient-details", `${patient.identifier_domain} · ${patient.external_id}  /  Rencontre ${encounter.external_id} · ${dateTime(encounter.started_at)}`);
  setStatus("#encounter-status", encounter.status === "active" ? "Rencontre active" : encounter.status, "neutral");

  const warnings = $("#warnings");
  warnings.replaceChildren();
  warnings.hidden = summary.warnings.length === 0;
  for (const warning of summary.warnings) {
    const item = document.createElement("p");
    item.textContent = warning.message;
    warnings.append(item);
  }

  const lab = summary.laboratory;
  const labLabel = { available: "Complet", partial: "Partiel", unavailable: "Indisponible" }[lab.status] ?? lab.status;
  setStatus("#lab-status", labLabel, lab.status === "available" ? "good" : "warn");
  const labResults = $("#lab-results");
  labResults.replaceChildren();
  for (const report of lab.reports) {
    for (const observation of report.observations) {
      const row = document.createElement("div");
      row.className = "result-row";
      const identity = document.createElement("div");
      const name = document.createElement("p");
      name.className = "result-name";
      name.textContent = observation.display;
      const code = document.createElement("p");
      code.className = "result-code";
      code.textContent = `${observation.coding_system}:${observation.code}`;
      identity.append(name, code);
      const result = document.createElement("p");
      result.className = "result-value";
      if (observation.data_status === "available") {
        result.textContent = observation.value_numeric ?? observation.value_text;
        const unit = document.createElement("small");
        unit.textContent = ` ${observation.unit ?? ""}`;
        result.append(unit);
      } else {
        result.classList.add("missing");
        result.textContent = observation.data_status === "missing" ? "Résultat manquant" : "Résultat invalide";
      }
      row.append(identity, result);
      labResults.append(row);
    }
  }
  const currentReport = lab.reports[0];
  setText("#lab-meta", currentReport ? `Rapport v${currentReport.version} · ${dateTime(currentReport.reported_at)}` : "Aucun rapport");

  const exam = summary.radiology.exams[0];
  setStatus("#ris-status", exam?.report?.status === "final" ? "Validé" : "En attente", exam?.report?.status === "final" ? "good" : "warn");
  const risContent = $("#ris-content");
  risContent.replaceChildren();
  if (exam) {
    const details = document.createElement("dl");
    details.className = "detail-list";
    details.append(
      detail("Examen", `${exam.modality} · ${exam.accession_number}`),
      detail("Réalisé le", dateTime(exam.performed_at)),
      detail("Compte rendu", exam.report?.status === "final" ? `Validé le ${dateTime(exam.report.validated_at)}` : "Non validé"),
    );
    risContent.append(details);
    if (exam.report?.content) {
      const text = document.createElement("p");
      text.className = "report-copy";
      text.textContent = exam.report.content;
      risContent.append(text);
    }
  }

  const imaging = summary.imaging;
  const available = imaging.availability_status === "available";
  const imagingLabel = { available: "Disponible", incomplete: "Incomplet", unavailable: "Indisponible" }[imaging.availability_status] ?? imaging.availability_status;
  setStatus("#pacs-status", imagingLabel, available ? "good" : "warn");
  const pacsContent = $("#pacs-content");
  pacsContent.replaceChildren();
  const study = imaging.studies[0];
  if (study) {
    const details = document.createElement("dl");
    details.className = "detail-list";
    details.append(
      detail("Study Instance UID", study.study_instance_uid),
      detail("Séries / instances", `${study.series_count} / ${study.instance_count}`),
      detail("Dernière synchronisation", dateTime(study.last_synced_at)),
    );
    pacsContent.append(details);
    if (mode === "live" && available) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "scenario-button preview-button";
      button.textContent = "Afficher l’aperçu";
      button.addEventListener("click", async () => {
        const thisRequest = requestNumber;
        button.disabled = true;
        button.textContent = "Chargement de l’aperçu…";
        try {
          const link = await api(`/api/v1/imaging-studies/${encodeURIComponent(study.id)}/viewer-link`);
          const response = await fetch(link.url, { credentials: "same-origin", cache: "no-store" });
          if (!response.ok || !response.headers.get("content-type")?.startsWith("image/png")) throw new Error("preview");
          const blob = await response.blob();
          if (thisRequest !== requestNumber || mode !== "live") return;
          if (currentPreviewUrl) URL.revokeObjectURL(currentPreviewUrl);
          currentPreviewUrl = URL.createObjectURL(blob);
          const image = document.createElement("img");
          image.className = "study-preview";
          image.alt = "Aperçu synthétique non diagnostique de l’étude";
          image.src = currentPreviewUrl;
          pacsContent.append(image);
          button.remove();
        } catch {
          if (thisRequest !== requestNumber || mode !== "live") return;
          button.disabled = false;
          button.textContent = "Réessayer l’aperçu";
          feedback.textContent = "Aperçu d’imagerie indisponible.";
        }
      });
      pacsContent.append(button);
    }
  }
  record.hidden = false;
  $("#data-source").textContent = mode === "live" ? "API locale avec accès par rencontre et audit." : "Réponses synthétiques du contrat API T02.";
  feedback.textContent = "";
}

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", cache: "no-store", ...options });
  if (!response.ok) {
    let code = "SERVICE_UNAVAILABLE";
    try { code = (await response.json()).code ?? code; } catch { /* A proxy may return no JSON. */ }
    const error = new Error(code);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function liveError(error) {
  if (error.status === 401) {
    liveSession = false;
    $("#login-form").hidden = false;
    $("#live-controls").hidden = true;
    return "Session expirée. Connectez-vous à nouveau.";
  }
  if (error.status === 403) return "Accès refusé pour cette rencontre.";
  if (error.status === 404) return "Aucun patient fictif ne correspond à cet identifiant exact.";
  if (error.status === 503) return "Service métier temporairement indisponible.";
  return "Impossible de joindre l'API locale. Ouvrez cette page depuis le serveur FastAPI.";
}

async function loadLiveSummary(encounterId) {
  const thisRequest = ++requestNumber;
  record.hidden = true;
  feedback.textContent = "Chargement du dossier…";
  try {
    const summary = await api(`/api/v1/encounters/${encodeURIComponent(encounterId)}/summary`);
    if (thisRequest !== requestNumber || mode !== "live") return;
    render(summary);
  } catch (error) {
    if (thisRequest !== requestNumber) return;
    feedback.textContent = liveError(error);
  }
}

async function searchLivePatient() {
  if (!liveSession) {
    feedback.textContent = "Connectez-vous pour rechercher un patient dans l'API locale.";
    record.hidden = true;
    return;
  }
  const thisRequest = ++requestNumber;
  record.hidden = true;
  feedback.textContent = "Recherche du patient…";
  const identifier = $("#identifier").value.trim();
  try {
    const params = new URLSearchParams({ identifier_domain: "DEMO", identifier });
    const patients = await api(`/api/v1/patients?${params}`);
    if (thisRequest !== requestNumber || mode !== "live") return;
    const patient = patients.patients[0];
    const result = await api(`/api/v1/patients/${encodeURIComponent(patient.id)}/encounters`);
    if (thisRequest !== requestNumber || mode !== "live") return;
    const picker = $("#encounter-select");
    picker.replaceChildren();
    for (const encounter of result.encounters) {
      const option = document.createElement("option");
      option.value = encounter.id;
      option.textContent = `${encounter.external_id} · ${dateTime(encounter.started_at)}`;
      picker.append(option);
    }
    if (!picker.options.length) {
      feedback.textContent = "Aucune rencontre accessible pour ce patient.";
      return;
    }
    await loadLiveSummary(picker.value);
  } catch (error) {
    if (thisRequest !== requestNumber) return;
    feedback.textContent = liveError(error);
  }
}

async function loadScenario() {
  const thisRequest = ++requestNumber;
  loadedSummary = null;
  record.hidden = true;
  feedback.textContent = "Chargement du scénario…";
  try {
    const response = await fetch(scenarios[selectedScenario], { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const summary = await response.json();
    if (thisRequest !== requestNumber) return;
    loadedSummary = summary;
    searchPatient();
  } catch {
    if (thisRequest !== requestNumber) return;
    loadedSummary = null;
    feedback.textContent = "Impossible de charger les données de démonstration. Lancez le serveur depuis la racine du dépôt.";
  }
}

function searchPatient() {
  if (mode === "live") return searchLivePatient();
  if (!loadedSummary) return;
  const identifier = $("#identifier").value.trim();
  if (identifier !== loadedSummary.patient.external_id) {
    record.hidden = true;
    feedback.textContent = "Aucun patient fictif ne correspond à cet identifiant exact.";
    return;
  }
  render(loadedSummary);
}

$("#patient-search").addEventListener("submit", (event) => {
  event.preventDefault();
  searchPatient();
});

for (const button of buttons) {
  button.addEventListener("click", () => {
    selectedScenario = button.dataset.scenario;
    for (const item of buttons) item.setAttribute("aria-pressed", String(item === button));
    loadScenario();
  });
}

for (const button of modeButtons) {
  button.addEventListener("click", () => {
    mode = button.dataset.mode;
    ++requestNumber;
    if (currentPreviewUrl) URL.revokeObjectURL(currentPreviewUrl);
    currentPreviewUrl = null;
    record.hidden = true;
    for (const item of modeButtons) item.setAttribute("aria-pressed", String(item === button));
    $(".scenario-group").hidden = mode === "live";
    $("#login-form").hidden = mode !== "live" || liveSession;
    $("#live-controls").hidden = mode !== "live" || !liveSession;
    if (mode === "live") {
      if (liveSession) searchLivePatient();
      else feedback.textContent = "Connectez-vous pour lire un dossier autorisé.";
    } else {
      loadScenario();
    }
  });
}

$("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  feedback.textContent = "Connexion…";
  try {
    await api("/api/v1/auth/login", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: $("#username").value.trim(), password: $("#password").value }) });
    $("#password").value = "";
    liveSession = true;
    $("#login-form").hidden = true;
    $("#live-controls").hidden = false;
    await searchLivePatient();
  } catch (error) {
    feedback.textContent = error.status === 401 ? "Identifiants invalides." : liveError(error);
  }
});

$("#logout-button").addEventListener("click", async () => {
  const csrf = document.cookie.split("; ").find((item) => item.startsWith("csrf_token="))?.split("=")[1];
  try {
    await api("/api/v1/auth/logout", { method: "POST", headers: { "X-CSRF-Token": decodeURIComponent(csrf ?? "") } });
  } catch { /* Clear this screen even when the session has already expired. */ }
  liveSession = false;
  ++requestNumber;
  if (currentPreviewUrl) URL.revokeObjectURL(currentPreviewUrl);
  currentPreviewUrl = null;
  record.hidden = true;
  $("#login-form").hidden = false;
  $("#live-controls").hidden = true;
  feedback.textContent = "Déconnecté.";
});

$("#encounter-select").addEventListener("change", (event) => loadLiveSummary(event.target.value));

loadScenario();
