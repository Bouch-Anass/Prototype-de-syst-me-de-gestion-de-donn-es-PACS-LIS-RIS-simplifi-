const $ = (selector) => document.querySelector(selector);
const feedback = $("#feedback");
const record = $("#record");
let requestNumber = 0;
let liveSession = false;
let currentRoles = new Set();
let liveSummary = null;
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

  const exams = summary.radiology.exams;
  setStatus("#ris-status", exams.length && exams.every((exam) => exam.report?.status === "final") ? "Validé" : "En attente",
    exams.length && exams.every((exam) => exam.report?.status === "final") ? "good" : "warn");
  const risContent = $("#ris-content");
  risContent.replaceChildren();
  for (const exam of exams) {
    const details = document.createElement("dl");
    details.className = "detail-list";
    details.append(
      detail("Examen", `${exam.modality} · ${exam.accession_number}`),
      detail("Procédure", exam.requested_procedure ?? "—"),
      detail("Priorité", exam.priority === "urgent" ? "Urgent" : "Routine"),
      detail("État", `${exam.order_status ?? "—"} / ${exam.status ?? "—"}`),
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
  for (const study of imaging.studies) {
    const details = document.createElement("dl");
    details.className = "detail-list";
    details.append(
      detail("Study Instance UID", study.study_instance_uid),
      detail("Séries / instances", `${study.series_count} / ${study.instance_count}`),
      detail("Dernière synchronisation", dateTime(study.last_synced_at)),
    );
    pacsContent.append(details);
    if (study.availability_status !== "unavailable") {
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
          if (thisRequest !== requestNumber || !liveSession) return;
          if (currentPreviewUrl) URL.revokeObjectURL(currentPreviewUrl);
          currentPreviewUrl = URL.createObjectURL(blob);
          const image = document.createElement("img");
          image.className = "study-preview";
          image.alt = "Aperçu DICOM non diagnostique de l’étude";
          image.src = currentPreviewUrl;
          pacsContent.append(image);
          button.remove();
        } catch {
          if (thisRequest !== requestNumber || !liveSession) return;
          button.disabled = false;
          button.textContent = "Réessayer l’aperçu";
          feedback.textContent = "Aperçu d’imagerie indisponible.";
        }
      });
      pacsContent.append(button);
    }
  }
  $("#lab-edit").hidden = !currentRoles.has("lab_technician") || !currentReport;
  $("#ris-edit").hidden = !currentRoles.has("radiologist");
  $("#imaging-edit").hidden = !currentRoles.has("imaging_technician");
  if (currentRoles.has("lab_technician") && currentReport) renderObservationEditor(currentReport.observations);
  record.hidden = false;
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
    currentRoles = new Set();
    showLogin();
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
    if (thisRequest !== requestNumber || !liveSession) return;
    liveSummary = summary;
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
    if (thisRequest !== requestNumber || !liveSession) return;
    const patient = patients.patients[0];
    const result = await api(`/api/v1/patients/${encodeURIComponent(patient.id)}/encounters`);
    if (thisRequest !== requestNumber || !liveSession) return;
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

$("#patient-search").addEventListener("submit", (event) => {
  event.preventDefault();
  searchLivePatient();
});

function showLogin() {
  $("#login-form").hidden = false;
  $("#control-bar").hidden = true;
  $("#live-controls").hidden = true;
  $("#role-label").textContent = "Connexion requise";
  record.hidden = true;
}

function showWorkspace(session) {
  liveSession = true;
  currentRoles = new Set(session.roles);
  $("#login-form").hidden = true;
  $("#control-bar").hidden = false;
  $("#live-controls").hidden = false;
  const names = { physician: "Médecin", radiologist: "Radiologue", lab_technician: "Technicien de laboratoire",
    imaging_technician: "Technicien d’imagerie" };
  $("#role-label").textContent = session.roles.map((role) => names[role] ?? role).join(" · ");
}

$("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  feedback.textContent = "Connexion…";
  try {
    const session = await api("/api/v1/auth/login", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: $("#username").value.trim(), password: $("#password").value }) });
    $("#password").value = "";
    showWorkspace(session);
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
  currentRoles = new Set();
  liveSummary = null;
  ++requestNumber;
  if (currentPreviewUrl) URL.revokeObjectURL(currentPreviewUrl);
  currentPreviewUrl = null;
  showLogin();
  feedback.textContent = "Déconnecté.";
});

$("#encounter-select").addEventListener("change", (event) => loadLiveSummary(event.target.value));

function csrfHeaders(extra = {}) {
  const token = document.cookie.split("; ").find((item) => item.startsWith("csrf_token="))?.split("=")[1];
  return { "X-CSRF-Token": decodeURIComponent(token ?? ""), ...extra };
}

function addObservationRow(observation = {}) {
  const row = document.createElement("div");
  row.className = "observation-row";
  for (const [field, label, value, type] of [
    ["code", "Code", observation.code ?? "", "text"],
    ["display", "Analyse", observation.display ?? "", "text"],
    ["value", "Valeur", observation.data_status === "available" ? observation.value_numeric ?? "" : "", "number"],
    ["unit", "Unité", observation.unit ?? "", "text"],
  ]) {
    const wrapper = document.createElement("label");
    wrapper.textContent = label;
    const input = document.createElement("input");
    input.dataset.field = field;
    input.type = type;
    input.value = value;
    input.required = field !== "value";
    if (field === "value") input.step = "any";
    wrapper.append(input);
    row.append(wrapper);
  }
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "scenario-button";
  remove.textContent = "Retirer";
  remove.setAttribute("aria-label", `Retirer l’analyse ${observation.display ?? ""}`);
  remove.addEventListener("click", () => row.remove());
  row.append(remove);
  $("#lab-observations").append(row);
  return row;
}

function renderObservationEditor(observations) {
  $("#lab-observations").replaceChildren();
  for (const observation of observations) addObservationRow(observation);
}

$("#add-observation").addEventListener("click", () => addObservationRow().querySelector("input").focus());

async function submitEdit(form, operation) {
  const button = form.querySelector("button[type=submit]");
  const message = $("#action-feedback");
  button.disabled = true;
  message.textContent = "Enregistrement…";
  try {
    await operation();
    await loadLiveSummary(liveSummary.encounter.id);
    message.textContent = "Modification enregistrée dans le dossier fictif.";
  } catch (error) {
    message.textContent = error.status ? `Modification refusée (${error.status}).` : "Modification impossible. Vérifiez les données et le service.";
  } finally {
    button.disabled = false;
  }
}

$("#lab-edit").addEventListener("submit", (event) => {
  event.preventDefault();
  submitEdit(event.currentTarget, async () => {
    const observations = [...document.querySelectorAll("#lab-observations .observation-row")].flatMap((row) => {
      const field = (name) => row.querySelector(`[data-field="${name}"]`).value.trim();
      if (field("value") === "") return [];
      return [{ code: field("code"), display: field("display"), value_numeric: Number(field("value")), unit: field("unit") }];
    });
    if (!observations.length) throw new Error("empty-observations");
    const orderId = liveSummary.laboratory.reports[0].lab_order_id;
    await api(`/api/v1/lab-orders/${encodeURIComponent(orderId)}/reports`, { method: "POST",
      headers: csrfHeaders({ "Content-Type": "application/json" }), body: JSON.stringify({ observations }) });
  });
});

$("#ris-edit").addEventListener("submit", (event) => {
  event.preventDefault();
  submitEdit(event.currentTarget, async () => {
    const created = await api("/api/v1/radiology-orders", { method: "POST",
      headers: csrfHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ encounter_id: liveSummary.encounter.id,
        accession_number: $("#ris-accession").value.trim(),
        requested_procedure: $("#ris-procedure").value.trim(),
        modality: $("#ris-modality").value, priority: $("#ris-priority").value }) });
    const path = `/api/v1/radiology-exams/${encodeURIComponent(created.exam_id)}`;
    await api(path, { method: "PATCH", headers: csrfHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ status: "performed", performed_at: new Date().toISOString() }) });
    await api(`${path}/report`, { method: "PUT", headers: csrfHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ content: $("#ris-report").value.trim() }) });
    await api(`${path}/report/validate`, { method: "POST", headers: csrfHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ validated_at: new Date().toISOString() }) });
  });
});

$("#imaging-edit").addEventListener("submit", (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const files = [...$("#dicom-file").files];
  if (!files.length) return;
  const button = form.querySelector("button[type=submit]");
  const message = $("#action-feedback");
  button.disabled = true;
  (async () => {
    let imported = 0;
    const failed = [];
    for (const file of files) {
      message.textContent = `Import DICOM ${imported + failed.length + 1}/${files.length} : ${file.name}`;
      if (file.size > 8 * 1024 * 1024) {
        failed.push(`${file.name} (plus de 8 Mio)`);
        continue;
      }
      try {
        await api(`/api/v1/encounters/${encodeURIComponent(liveSummary.encounter.id)}/imaging-studies`, {
          method: "POST", headers: csrfHeaders({ "Content-Type": "application/dicom" }), body: file });
        imported += 1;
      } catch (error) {
        failed.push(`${file.name} (${error.status ?? "réseau"})`);
      }
    }
    if (imported) await loadLiveSummary(liveSummary.encounter.id);
    message.textContent = `${imported}/${files.length} fichier(s) importé(s).` + (failed.length ? ` Échecs : ${failed.join(", ")}.` : "");
    if (!failed.length) $("#dicom-file").value = "";
  })().finally(() => { button.disabled = false; });
});

api("/api/v1/auth/me").then((session) => {
  showWorkspace(session);
  searchLivePatient();
}).catch(() => showLogin());
