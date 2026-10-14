const scenarios = {
  nominal: "/contracts/examples/summary.nominal.json",
  "missing-crp": "/contracts/examples/summary.missing-crp.json",
  "orthanc-unavailable": "/contracts/examples/summary.orthanc-unavailable.json",
};

const $ = (selector) => document.querySelector(selector);
const feedback = $("#feedback");
const record = $("#record");
const buttons = [...document.querySelectorAll("[data-scenario]")];
let selectedScenario = "nominal";
let loadedSummary = null;
let requestNumber = 0;

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
  }
  record.hidden = false;
  feedback.textContent = "";
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

loadScenario();
