const $ = (selector) => document.querySelector(selector);
const record = $("#record");
const feedback = $("#feedback");
const loginForm = $("#login-form");
const loginFeedback = $("#login-feedback");
const searchForm = $("#patient-search");
const searchInput = $("#identifier");
const patientDropdown = $("#patient-dropdown");
const patientList = $("#patient-list");
const listFeedback = $("#patient-list-feedback");
const emptyPatientList = $("#patient-list-empty");
const morePatients = $("#more-patients");
const picker = $("#encounter-select");
const labEditor = $("#lab-editor");
const logoutButton = $("#logout-button");
const overviewButton = $(".header-tab");
const radiologyForm = $("#ris-edit");
const previewUrls = new Set();
const dateFormatter = new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium", timeStyle: "short" });
const shortDate = new Intl.DateTimeFormat("fr-FR", { dateStyle: "short" });
const visitOptionDate = new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "2-digit" });
const timelineHour = new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit" });
const timelineSecond = new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const numberFormatter = new Intl.NumberFormat("fr-FR", { maximumSignificantDigits: 21 });
const visitStates = { active: "En cours", closed: "Terminée", completed: "Terminée" };
const modalities = { CT: "Scanner", MR: "IRM", US: "Échographie", CR: "Radiographie", DX: "Radiographie" };
const roles = {
  physician: "Médecin",
  radiologist: "Radiologue",
  lab_technician: "Technicien de laboratoire",
  imaging_technician: "Technicien d’imagerie",
};

let requestNumber = 0;
let currentRoles = new Set();
let currentSummary = null;
let radiologyProgress = null;
let signedIn = false;
let saving = false;
let directorySession = null;
let nextPatientOffset = 0;
let directoryPatients = [];
let filteringPatients = false;

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text != null) element.textContent = text;
  if (className) element.className = className;
  return element;
}

function tell(element, message = "", tone = "neutral") {
  element.dataset.tone = tone;
  element.textContent = message;
}

function dateTime(value) {
  return dateFormatter.format(new Date(value));
}

function visitDescription(visit) {
  return [visit.started_at && dateTime(visit.started_at), visit.external_id].filter(Boolean).join(" · ");
}

function details(fields) {
  const list = node("dl", null, "detail-list");
  for (const [label, value] of fields) {
    if (value == null || value === "") continue;
    const group = node("div");
    group.append(node("dt", label), node("dd", value));
    list.append(group);
  }
  return list;
}

function setNavigationDisabled(disabled) {
  picker.disabled = disabled;
  searchForm.querySelector('button[type="submit"]').disabled = disabled;
  searchInput.disabled = disabled;
  logoutButton.disabled = disabled;
  overviewButton.disabled = disabled || record.hidden;
  if (disabled) closePatientDropdown();
  for (const button of record.querySelectorAll("button[data-view]")) button.disabled = disabled;
}

function setEditButtonsDisabled(disabled) {
  for (const button of record.querySelectorAll('.editor-form button[type="submit"]')) button.disabled = disabled;
}

function clearPreviews() {
  for (const url of previewUrls) URL.revokeObjectURL(url);
  previewUrls.clear();
}

function setView(view) {
  record.dataset.view = view;
  overviewButton.setAttribute("aria-pressed", String(view === "overview"));
  for (const button of record.querySelectorAll(".record-nav button")) {
    button.setAttribute("aria-pressed", String(button.dataset.view === view));
  }
}

function clearRecord() {
  record.hidden = true;
  overviewButton.disabled = true;
  setView("overview");
  delete record.dataset.loading;
  record.removeAttribute("aria-busy");
  currentSummary = null;
  patientList.querySelector('[aria-current="true"]')?.removeAttribute("aria-current");
  radiologyProgress = null;
  clearPreviews();
  for (const editor of record.querySelectorAll(".editor")) {
    editor.open = false;
    editor.querySelector("form").reset();
    tell(editor.querySelector(".form-feedback"));
  }
  for (const selector of ["#patient-name", "#patient-details", "#visit-details", "#warnings", "#ris-content", "#pacs-content",
    "#lab-observations", "#record-metrics", "#record-shortcuts", "#timeline-range", "#timeline-events"]) {
    $(selector).replaceChildren();
  }
  $("#lab-results").replaceChildren(labEditor);
}

function renderLab(lab) {
  const container = $("#lab-results");
  const labels = { available: "Résultats reçus", partial: "Résultats partiels", unavailable: "Aucun résultat" };
  tell($("#lab-status"), labels[lab.status] ?? "État inconnu",
    lab.status === "available" ? "good" : lab.status === "partial" ? "warn" : "neutral");

  const reports = lab.reports.map((report) => {
    const entry = node("div", null, "entry");
    const table = node("table", null, "results-table");
    const caption = table.createCaption();
    caption.className = "entry-meta";
    caption.textContent = `Rapport du ${dateTime(report.reported_at)} · Version ${report.version}`;
    const header = table.createTHead().insertRow();
    for (const label of ["Analyse", "Résultat"]) {
      const cell = node("th", label);
      cell.scope = "col";
      header.append(cell);
    }
    const body = table.createTBody();
    for (const observation of report.observations) {
      const row = body.insertRow();
      const name = node("th", observation.display);
      name.scope = "row";
      row.append(name);
      const value = row.insertCell();
      value.className = "result-value";
      if (observation.data_status === "available") {
        value.textContent = observation.value_numeric == null
          ? observation.value_text
          : numberFormatter.format(observation.value_numeric);
        if (observation.unit) value.append(node("small", ` ${observation.unit}`));
      } else {
        value.classList.add("missing");
        value.textContent = observation.data_status === "missing" ? "Non reçu" : "Invalide";
      }
    }
    entry.append(table);
    return entry;
  });

  labEditor.hidden = !currentRoles.has("lab_technician") || !reports.length;
  if (!labEditor.hidden) renderObservationEditor(lab.reports[0].observations);
  if (reports.length) {
    container.replaceChildren(...reports);
    reports[0].append(labEditor);
  } else {
    container.replaceChildren(node("p", "Aucun résultat de laboratoire pour cette prise en charge.", "empty-copy"), labEditor);
  }
}

function renderRadiology(exams) {
  const complete = exams.length > 0 && exams.every((exam) => exam.report?.status === "final");
  const completedLabel = exams.length === 1 ? "Compte rendu validé" : "Comptes rendus validés";
  tell($("#ris-status"), complete ? completedLabel : exams.length ? "En attente de validation" : "Aucun examen",
    complete ? "good" : exams.length ? "warn" : "neutral");

  const container = $("#ris-content");
  container.replaceChildren();
  if (!exams.length) container.append(node("p", "Aucun examen de radiologie pour cette prise en charge.", "empty-copy"));
  for (const exam of exams) {
    const type = modalities[exam.modality] ?? exam.modality;
    const entry = node("div", null, "entry");
    const heading = node("div", null, "entry-head");
    heading.append(node("h4", exam.requested_procedure || type));
    if (exam.accession_number) heading.append(node("span", exam.accession_number, "entry-meta"));

    const report = exam.report;
    const reportState = report?.status === "final"
      ? report.validated_at ? `Validé le ${dateTime(report.validated_at)}` : "Validé"
      : report?.status === "draft" ? "Brouillon" : "Non renseigné";
    entry.append(heading, details([
      ["Type d’imagerie", exam.requested_procedure && type],
      ["Priorité", exam.priority === "urgent" ? "Urgente" : exam.priority === "routine" ? "Standard" : null],
      ["Examen", exam.performed_at ? `Réalisé le ${dateTime(exam.performed_at)}` :
        { scheduled: "Planifié", performed: "Réalisé", cancelled: "Annulé" }[exam.status]],
      ["Compte rendu", reportState],
    ]));
    if (report?.content) entry.append(node("p", report.content, "report-copy"));
    container.append(entry);
  }
  $("#ris-editor").hidden = !currentRoles.has("radiologist");
  const accession = $("#ris-accession");
  if (accession.value === accession.defaultValue && exams.some((exam) => exam.accession_number === accession.value)) {
    accession.value = "";
  }
}

function addPreview(entry, study, index) {
  const button = node("button", "Afficher l’aperçu", "secondary-button preview-button");
  const panel = node("div");
  const message = node("p", null, "feedback preview-feedback");
  message.setAttribute("role", "status");
  panel.id = `study-preview-${index}`;
  panel.hidden = true;
  button.type = "button";
  button.setAttribute("aria-controls", panel.id);
  button.setAttribute("aria-expanded", "false");

  button.addEventListener("click", async () => {
    if (panel.hasChildNodes()) {
      panel.hidden = !panel.hidden;
      button.setAttribute("aria-expanded", String(!panel.hidden));
      button.textContent = panel.hidden ? "Afficher l’aperçu" : "Masquer l’aperçu";
      return;
    }
    const request = requestNumber;
    const hadFocus = document.activeElement === button;
    button.disabled = true;
    tell(message, "Chargement de l’aperçu…");
    try {
      const link = await api(`/api/v1/imaging-studies/${encodeURIComponent(study.id)}/viewer-link`);
      const response = await fetch(link.url, { credentials: "same-origin", cache: "no-store" });
      if (!response.ok || !response.headers.get("content-type")?.startsWith("image/png")) {
        throw Object.assign(new Error("IMAGING_UNAVAILABLE"), { status: response.status });
      }
      const blob = await response.blob();
      if (request !== requestNumber || !button.isConnected) return;
      const url = URL.createObjectURL(blob);
      previewUrls.add(url);
      const image = node("img", null, "study-preview");
      image.alt = "Aperçu de l’étude d’imagerie";
      image.src = url;
      panel.append(image);
      panel.hidden = false;
      button.setAttribute("aria-expanded", "true");
      button.textContent = "Masquer l’aperçu";
      tell(message, "Aperçu affiché.");
    } catch (error) {
      if (request !== requestNumber || !button.isConnected) return;
      if (error.status === 401) {
        expireSession();
        return;
      }
      tell(message, "Impossible de charger l’aperçu. Vous pouvez réessayer.", "error");
    } finally {
      button.disabled = false;
      if (request === requestNumber && hadFocus && document.activeElement === document.body) button.focus();
    }
  });
  entry.append(button, message, panel);
}

function renderImaging(imaging, exams) {
  const available = imaging.availability_status === "available";
  const unavailable = imaging.availability_status === "unavailable";
  const container = $("#pacs-content");
  container.replaceChildren();
  const label = available ? "Images disponibles" : unavailable ? "Imagerie indisponible"
    : imaging.studies.length ? "Images partielles" : "Aucune image";
  tell($("#pacs-status"), label, available ? "good" : unavailable || imaging.studies.length ? "warn" : "neutral");
  if (!imaging.studies.length) {
    container.append(node("p", unavailable ? "Le service d’imagerie est temporairement indisponible."
      : "Aucune image n’est associée aux examens de cette prise en charge.", "empty-copy"));
  }

  const examsById = new Map(exams.map((exam) => [exam.id, exam]));
  imaging.studies.forEach((study, index) => {
    const entry = node("div", null, "entry");
    const exam = examsById.get(study.exam_id);
    const heading = node("div", null, "entry-head");
    heading.append(node("h4", exam ? (modalities[exam.modality] ?? exam.modality) : "Étude d’imagerie"));
    if (exam?.accession_number) heading.append(node("span", exam.accession_number, "entry-meta"));
    entry.append(heading, details([["Séries", study.series_count], ["Images DICOM", study.instance_count]]));
    if (study.last_synced_at) {
      const sync = node("div", null, "imaging-sync");
      sync.append(node("span", "Dernière synchronisation"), node("time", dateTime(study.last_synced_at)));
      sync.lastChild.dateTime = study.last_synced_at;
      entry.append(sync);
    }
    const technical = node("details", null, "technical-details");
    technical.append(node("summary", "Détails techniques"), details([
      ["Identifiant DICOM de l’étude", study.study_instance_uid],
    ]));
    entry.append(technical);
    if (study.availability_status === "unavailable") {
      entry.append(node("p", "Aperçu temporairement indisponible.", "section-note"));
    } else {
      addPreview(entry, study, index);
    }
    container.append(entry);
  });
  $("#imaging-editor").hidden = !currentRoles.has("imaging_technician");
}

function renderOverview({ laboratory, radiology: { exams }, imaging: { studies } }) {
  const analyses = laboratory.reports.flatMap((report) => report.observations);
  const measures = [
    ["Analyses renseignées", analyses.filter((item) => item.data_status === "available").length, analyses.length],
    ["Comptes rendus validés", exams.filter((exam) => exam.report?.status === "final").length, exams.length],
    ["Examens réalisés", exams.filter((exam) => exam.status === "performed").length, exams.length],
    ["Études disponibles", studies.filter((study) => study.availability_status === "available").length, studies.length],
  ];
  $("#record-metrics").replaceChildren(...measures.map(([label, count, total]) => {
    const metric = node("div", null, "metric");
    const heading = node("div", null, "metric-heading");
    const tone = total === 0 ? "empty" : count === total ? "good" : "warn";
    metric.dataset.tone = tone;
    heading.append(node("span", label), node("span", `${count}/${total}`, "metric-count"));
    const bar = node("div", null, "meter");
    bar.setAttribute("aria-hidden", "true");
    const fill = node("span");
    fill.style.inlineSize = total ? `${100 * count / total}%` : "0";
    bar.append(fill);
    metric.append(heading, bar);
    return metric;
  }));

  const actions = [
    ["laboratory", "Résultats d’analyses", "Mettre à jour", "lab"],
    ["radiology", "Examens et comptes rendus", "Ajouter un examen", "ris"],
    ["imaging", "Images et études DICOM", "Importer des images", "imaging"],
  ];
  $("#record-shortcuts").replaceChildren(...actions.map(([view, label, editLabel, editorId]) => {
    const item = node("div", null, "shortcut");
    const editable = !$(`#${editorId}-editor`).hidden;
    const button = node("button", editable ? editLabel : "Consulter", "primary-button");
    button.type = "button";
    button.dataset.view = view;
    button.setAttribute("aria-label", editable ? editLabel : `Consulter · ${label}`);
    if (editable) button.dataset.editor = `${editorId}-editor`;
    item.append(node("p", label), button);
    return item;
  }));
}

function timelineIcon(kind) {
  const paths = {
    start: "M12 5v14M5 12h14",
    laboratory: "M9 3h6M10 3v7l-5 8a2 2 0 0 0 1.7 3h10.6a2 2 0 0 0 1.7-3l-5-8V3M8 15h8",
    exam: "M4 3h16v14H4zM8 21h8M12 17v4M12 6a3 3 0 1 0 0 6a3 3 0 1 0 0-6",
    report: "M14 3H5v18h14V8zM14 3v5h5M8 14l3 3 5-6",
    imaging: "M4 4h16v16H4zM4 16l5-5 4 4 3-3 4 4M15 8h.01",
  };
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  for (const [name, value] of Object.entries({
    viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": "1.6",
    "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true", focusable: "false",
  })) svg.setAttribute(name, value);
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", paths[kind]);
  svg.append(path);
  return svg;
}

function renderTimeline({ encounter, laboratory, radiology: { exams }, imaging: { studies } }) {
  const events = [];
  function add(timestamp, kind, label, context) {
    const time = Date.parse(timestamp);
    if (timestamp && Number.isFinite(time)) events.push({ timestamp, time, kind, label, context });
  }
  add(encounter.started_at, "start", "Début de la prise en charge", "Prise en charge");
  for (const report of laboratory.reports) {
    add(report.reported_at, "laboratory", "Rapport de laboratoire reçu", `Laboratoire · Version ${report.version}`);
  }
  for (const exam of exams) {
    const reference = exam.accession_number ? ` · ${exam.accession_number}` : "";
    add(exam.performed_at, "exam", "Examen réalisé", `Radiologie${reference}`);
    add(exam.report?.validated_at, "report", "Compte rendu validé", `Radiologie${reference}`);
  }
  for (const study of studies) {
    add(study.last_synced_at, "imaging", "Images synchronisées", "Imagerie · Dernière synchronisation");
  }
  events.sort((a, b) => a.time - b.time);

  const first = events[0]?.timestamp;
  const last = events.at(-1)?.timestamp;
  const from = first ? shortDate.format(new Date(first)) : "";
  const to = last ? shortDate.format(new Date(last)) : "";
  $("#timeline-range").textContent = !events.length ? "Aucune date" : from === to ? from : `${from} au ${to}`;
  $("#timeline-empty").hidden = Boolean(events.length);
  const clock = events.some((event) => new Date(event.time).getSeconds() !== 0) ? timelineSecond : timelineHour;
  $("#timeline-events").replaceChildren(...events.map(({ timestamp, kind, label, context }) => {
    const event = node("li", null, "care-event");
    const time = node("time", null, "care-event-time");
    time.dateTime = timestamp;
    time.title = dateTime(timestamp);
    time.append(node("span", clock.format(new Date(timestamp))));
    time.append(node("small", shortDate.format(new Date(timestamp))));
    const marker = node("span", null, "care-event-marker");
    marker.append(timelineIcon(kind));
    const description = node("div", null, "care-event-description");
    description.append(node("strong", label), node("span", context));
    event.append(time, marker, description);
    return event;
  }));
}

function render(summary) {
  clearPreviews();
  const { patient, encounter, laboratory, radiology, imaging, warnings } = summary;
  $("#patient-name").textContent = patient.display_name;
  $("#patient-details").textContent = patient.external_id;
  const visitState = $("#encounter-status");
  visitState.hidden = !Object.hasOwn(visitStates, encounter.status);
  tell(visitState, visitStates[encounter.status], encounter.status === "active" ? "good" : "neutral");
  const visitDetails = $("#visit-details");
  visitDetails.textContent = visitDescription(encounter);
  visitDetails.hidden = picker.options.length > 1;
  picker.hidden = !visitDetails.hidden;

  const notices = $("#warnings");
  const otherWarnings = warnings.filter(({ code }) => code !== "LAB_RESULT_MISSING" && code !== "IMAGING_UNAVAILABLE");
  notices.replaceChildren(...otherWarnings.map(({ message }) => node("p", message)));
  notices.hidden = !otherWarnings.length;
  renderLab(laboratory);
  renderRadiology(radiology.exams);
  renderImaging(imaging, radiology.exams);
  renderOverview(summary);
  renderTimeline(summary);
  record.hidden = false;
  overviewButton.disabled = saving;
}

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", cache: "no-store", ...options });
  if (!response.ok) {
    let code = "SERVICE_UNAVAILABLE";
    try { code = (await response.json()).code ?? code; } catch { /* The server may return no JSON. */ }
    throw Object.assign(new Error(code), { status: response.status });
  }
  return response.json();
}

function csrfHeaders(extra = {}) {
  const token = document.cookie.split("; ").find((item) => item.startsWith("csrf_token="))?.split("=")[1];
  return { "X-CSRF-Token": decodeURIComponent(token ?? ""), ...extra };
}

function write(path, method, body) {
  return api(path, {
    method,
    headers: csrfHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
}

function showLogin(message = "", tone = "neutral", focus = false) {
  signedIn = false;
  directorySession?.abort();
  directorySession = null;
  directoryPatients = [];
  filteringPatients = false;
  closePatientDropdown();
  patientList.replaceChildren();
  tell(listFeedback);
  emptyPatientList.hidden = true;
  morePatients.hidden = true;
  morePatients.disabled = false;
  currentRoles.clear();
  ++requestNumber;
  clearRecord();
  picker.replaceChildren();
  searchInput.value = searchInput.defaultValue;
  $("#workspace").hidden = true;
  searchForm.hidden = true;
  $("#login-context").hidden = false;
  $("#session-controls").hidden = true;
  $("#role-label").textContent = "";
  $("#sign-in").hidden = false;
  $("#password").value = "";
  setPasswordVisible(false);
  tell(loginFeedback, message, tone);
  loginForm.querySelector('[type="submit"]').disabled = false;
  if (focus) $("#login-title").focus();
}

function expireSession() {
  showLogin("Votre session a expiré. Reconnectez-vous pour continuer.", "error", true);
}

function showWorkspace(session) {
  signedIn = true;
  directorySession = new AbortController();
  nextPatientOffset = 0;
  currentRoles = new Set(session.roles);
  $("#sign-in").hidden = true;
  $("#workspace").hidden = false;
  searchForm.hidden = false;
  $("#login-context").hidden = true;
  $("#session-controls").hidden = false;
  $("#role-label").textContent = session.roles.map((role) => roles[role] ?? "Accès de démonstration").join(" · ");
}

function readError(error, notFound) {
  if (error.status === 403) return "Votre compte n’a pas accès à ce dossier.";
  if (error.status === 404) return notFound;
  if (error.status === 422) return "Vérifiez l’identifiant saisi, puis relancez la recherche.";
  return "Le service ne répond pas. Réessayez dans quelques instants.";
}

async function loadSummary(encounterId, refresh = false) {
  const request = ++requestNumber;
  if (!refresh) tell(feedback, "Chargement du dossier…");
  try {
    const summary = await api(`/api/v1/encounters/${encodeURIComponent(encounterId)}/summary`);
    if (request !== requestNumber || !signedIn) return false;
    currentSummary = summary;
    render(summary);
    for (const option of patientList.children) {
      if (option.dataset.patientId === summary.patient.id) option.setAttribute("aria-current", "true");
      else option.removeAttribute("aria-current");
    }
    tell(feedback, `Dossier de ${summary.patient.display_name} affiché.`);
    feedback.classList.add("visually-hidden");
    return true;
  } catch (error) {
    if (request !== requestNumber) return false;
    if (error.status === 401) expireSession();
    else if (!refresh) tell(feedback, readError(error, "Cette prise en charge n’est plus disponible."), "error");
    return false;
  }
}

function beginPatientRequest(message) {
  const request = ++requestNumber;
  clearRecord();
  picker.replaceChildren();
  feedback.classList.remove("visually-hidden");
  tell(feedback, message);
  return request;
}

async function loadPatientEncounters(patient, request) {
  const { encounters } = await api(`/api/v1/patients/${encodeURIComponent(patient.id)}/encounters`);
  if (request !== requestNumber || !signedIn) return false;
  encounters.sort((a, b) => Number(b.status === "active") - Number(a.status === "active")
    || Date.parse(b.started_at) - Date.parse(a.started_at));
  for (const visit of encounters) {
    const label = [visit.started_at && visitOptionDate.format(new Date(visit.started_at)), visit.external_id].filter(Boolean).join(" ");
    picker.add(new Option(label, visit.id));
  }
  if (picker.options.length) return loadSummary(picker.value);
  tell(feedback, "Aucune prise en charge accessible pour ce patient.");
  return false;
}

async function openPatient(patient, focusRecord = false) {
  if (!signedIn || saving || logoutButton.disabled) return;
  const request = beginPatientRequest("Chargement du dossier…");
  filteringPatients = false;
  searchInput.value = patient.external_id;
  try {
    const loaded = await loadPatientEncounters(patient, request);
    if (loaded && currentSummary?.patient.id === patient.id && focusRecord) $("#patient-name").focus();
  } catch (error) {
    if (request !== requestNumber) return;
    if (error.status === 401) expireSession();
    else tell(feedback, readError(error, "Ce dossier n’est plus disponible."), "error");
  }
}

function activePatientOption() {
  const id = searchInput.getAttribute("aria-activedescendant");
  return id ? document.getElementById(id) : null;
}

function highlightPatientOption(option) {
  activePatientOption()?.setAttribute("aria-selected", "false");
  if (option) {
    option.setAttribute("aria-selected", "true");
    searchInput.setAttribute("aria-activedescendant", option.id);
  } else {
    searchInput.removeAttribute("aria-activedescendant");
  }
}

function closePatientDropdown() {
  if (patientDropdown.hidden) return;
  patientDropdown.hidden = true;
  searchInput.setAttribute("aria-expanded", "false");
  highlightPatientOption(null);
}

function searchText(value) {
  return value.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
}

function renderPatientOptions(resetScroll = false) {
  const query = filteringPatients ? searchText(searchInput.value.trim()) : "";
  const visible = directoryPatients.filter(patient =>
    searchText(`${patient.display_name} ${patient.external_id}`).includes(query));
  const activeId = activePatientOption()?.id;
  highlightPatientOption(null);
  patientList.replaceChildren(...visible.map(patient => {
    const option = node("li", null, "patient-option");
    option.id = `patient-option-${patient.id}`;
    option.dataset.patientId = patient.id;
    option.setAttribute("role", "option");
    option.setAttribute("aria-selected", "false");
    if (currentSummary?.patient.id === patient.id) option.setAttribute("aria-current", "true");
    option.append(node("span", patient.display_name), node("small", patient.external_id));
    option.addEventListener("click", () => {
      closePatientDropdown();
      openPatient(patient, true);
    });
    return option;
  }));
  if (resetScroll) patientList.scrollTop = 0;
  else if (activeId) highlightPatientOption(document.getElementById(activeId));
  emptyPatientList.hidden = visible.length > 0 || (!directoryPatients.length && nextPatientOffset !== null);
  emptyPatientList.textContent = directoryPatients.length ? "Aucun patient correspondant." : "Aucun patient accessible.";
}

function openPatientDropdown() {
  if (!signedIn || searchInput.disabled || !patientDropdown.hidden) return;
  filteringPatients = searchInput.value !== (currentSummary?.patient.external_id ?? searchInput.defaultValue);
  patientDropdown.hidden = false;
  searchInput.setAttribute("aria-expanded", "true");
  renderPatientOptions(true);
}

async function loadPatientDirectory() {
  if (!directorySession || nextPatientOffset === null || morePatients.disabled) return;
  const { signal } = directorySession;
  const offset = nextPatientOffset;
  morePatients.disabled = true;
  tell(listFeedback, "Chargement des patients…");
  try {
    const { patients, next_offset: nextOffset } = await api(`/api/v1/patients/available?offset=${offset}`, { signal });
    if (signal.aborted) return;
    directoryPatients.push(...patients);
    nextPatientOffset = nextOffset;
    morePatients.hidden = nextOffset === null;
    morePatients.textContent = "Voir plus de patients";
    tell(listFeedback);
    renderPatientOptions();
    return patients;
  } catch (error) {
    if (signal.aborted) return;
    if (error.status === 401) expireSession();
    else {
      tell(listFeedback, "Impossible de charger la liste des patients.", "error");
      morePatients.hidden = false;
      morePatients.textContent = "Réessayer";
    }
  } finally {
    if (!signal.aborted) morePatients.disabled = false;
  }
}

morePatients.addEventListener("click", loadPatientDirectory);

searchInput.addEventListener("focus", openPatientDropdown);
searchInput.addEventListener("click", openPatientDropdown);
searchInput.addEventListener("input", () => {
  openPatientDropdown();
  filteringPatients = true;
  renderPatientOptions(true);
});
searchInput.addEventListener("keydown", event => {
  if (event.isComposing) return;
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    openPatientDropdown();
    const active = activePatientOption();
    const next = event.key === "ArrowDown" ? (active ? active.nextElementSibling : patientList.firstElementChild)
      : (active ? active.previousElementSibling : patientList.lastElementChild);
    if (next) {
      highlightPatientOption(next);
      next.scrollIntoView({ block: "nearest" });
    }
  } else if (event.key === "Escape" && !patientDropdown.hidden) {
    event.preventDefault();
    closePatientDropdown();
  } else if (event.key === "Enter" && activePatientOption()) {
    event.preventDefault();
    activePatientOption().click();
  }
});

const searchField = searchInput.closest(".search-field");
patientList.addEventListener("mousedown", event => {
  if (event.target.closest('[role="option"]')) event.preventDefault();
});
searchField.addEventListener("focusout", event => {
  if (event.relatedTarget && !searchField.contains(event.relatedTarget)) closePatientDropdown();
});
document.addEventListener("pointerdown", event => {
  if (!searchField.contains(event.target)) closePatientDropdown();
});

async function openWorkspace(session) {
  showWorkspace(session);
  const request = requestNumber;
  const patients = await loadPatientDirectory();
  if (!signedIn || request !== requestNumber) return;
  const patient = patients?.find(item => item.external_id === searchInput.defaultValue) ?? patients?.[0];
  if (patient) await openPatient(patient);
  else if (!patients) await searchPatient();
}

async function searchPatient() {
  if (!signedIn || saving || logoutButton.disabled) return;
  const identifier = searchInput.value.trim();
  if (!identifier) {
    tell(feedback, "Saisissez l’identifiant du patient.", "error");
    feedback.classList.remove("visually-hidden");
    searchInput.focus();
    return;
  }
  const request = beginPatientRequest("Recherche du patient…");
  try {
    const query = new URLSearchParams({ identifier_domain: "DEMO", identifier });
    const { patients } = await api(`/api/v1/patients?${query}`);
    if (request !== requestNumber || !signedIn) return;
    if (!patients.length) throw Object.assign(new Error("NOT_FOUND"), { status: 404 });
    await loadPatientEncounters(patients[0], request);
  } catch (error) {
    if (request !== requestNumber) return;
    if (error.status === 401) expireSession();
    else tell(feedback, readError(error, "Aucun patient trouvé. Vérifiez l’identifiant et réessayez."), "error");
  }
}

function setPasswordVisible(visible) {
  $("#password").type = visible ? "text" : "password";
  const button = $("#toggle-password");
  button.textContent = visible ? "Masquer" : "Afficher";
  button.setAttribute("aria-label", visible ? "Masquer le mot de passe" : "Afficher le mot de passe");
}

$("#toggle-password").addEventListener("click", () => setPasswordVisible($("#password").type === "password"));

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = loginForm.querySelector('[type="submit"]');
  if (button.disabled) return;
  button.disabled = true;
  tell(loginFeedback, "Connexion en cours…");
  try {
    const session = await write("/api/v1/auth/login", "POST", {
      username: $("#username").value.trim(),
      password: $("#password").value,
    });
    $("#password").value = "";
    setPasswordVisible(false);
    await openWorkspace(session);
    if (currentSummary && document.activeElement === document.body) $("#patient-name").focus();
  } catch (error) {
    tell(loginFeedback, [401, 422].includes(error.status) ? "Identifiant ou mot de passe incorrect."
      : "Connexion impossible pour le moment. Réessayez dans quelques instants.", "error");
  } finally {
    button.disabled = false;
  }
});

logoutButton.addEventListener("click", async () => {
  setNavigationDisabled(true);
  try {
    await api("/api/v1/auth/logout", { method: "POST", headers: csrfHeaders() });
    showLogin("Vous êtes déconnecté.", "neutral", true);
  } catch (error) {
    if (error.status === 401) showLogin("Vous êtes déconnecté.", "neutral", true);
    else {
      feedback.classList.remove("visually-hidden");
      tell(feedback, "Déconnexion impossible. Réessayez dans quelques instants.", "error");
    }
  } finally {
    setNavigationDisabled(false);
  }
});

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (filteringPatients && searchInput.value.trim() && patientList.children.length) {
    if (patientList.children.length === 1) patientList.firstElementChild.click();
    else {
      searchInput.focus();
      openPatientDropdown();
    }
    return;
  }
  closePatientDropdown();
  searchPatient();
});

overviewButton.addEventListener("click", () => setView("overview"));

record.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-view]");
  if (!button || saving || !currentSummary) return;
  const { view, editor } = button.dataset;
  setView(view);
  if (!button.closest(".shortcut")) return;
  if (editor) {
    const details = document.getElementById(editor);
    details.open = true;
    details.querySelector("summary").focus();
  } else {
    $(`#${view}-panel h3`).focus();
  }
});

picker.addEventListener("change", async () => {
  if (saving) return;
  const previous = currentSummary?.encounter.id;
  const selected = picker.value;
  if (selected === previous) return;
  currentSummary = null;
  radiologyProgress = null;
  // Keep the selection focused while concealing the previous visit’s data.
  record.dataset.loading = "";
  record.setAttribute("aria-busy", "true");
  $("#encounter-status").hidden = true;
  feedback.classList.remove("visually-hidden");
  for (const editor of record.querySelectorAll(".editor")) {
    editor.open = false;
    editor.querySelector("form").reset();
    tell(editor.querySelector(".form-feedback"));
  }
  const loading = loadSummary(selected);
  const request = requestNumber;
  const success = await loading;
  if (request === requestNumber) {
    record.removeAttribute("aria-busy");
    if (success) delete record.dataset.loading;
  }
});

function addObservationRow(observation = {}) {
  const row = node("div", null, "observation-row");
  for (const [field, label, value, maxLength] of [
    ["code", "Code", observation.code ?? "", 60],
    ["display", "Analyse", observation.display ?? "", 120],
    ["value", "Valeur", observation.value_numeric ?? "", null],
    ["unit", "Unité", observation.unit ?? "", 20],
  ]) {
    const wrapper = node("label", label);
    const input = node("input");
    input.dataset.field = field;
    input.type = field === "value" ? "number" : "text";
    input.value = value;
    if (field === "value") input.step = "any";
    else {
      input.maxLength = maxLength;
      input.required = true;
    }
    wrapper.append(input);
    row.append(wrapper);
  }
  const remove = node("button", "Retirer", "quiet-button");
  remove.type = "button";
  remove.setAttribute("aria-label", observation.display ? `Retirer l’analyse ${observation.display}` : "Retirer cette analyse");
  remove.addEventListener("click", () => {
    const next = row.nextElementSibling?.querySelector("input") ?? $("#add-observation");
    row.remove();
    $("#add-observation").disabled = false;
    next.focus();
  });
  row.append(remove);
  $("#lab-observations").append(row);
  $("#add-observation").disabled = $("#lab-observations").childElementCount >= 200;
  return row;
}

function renderObservationEditor(observations) {
  $("#lab-observations").replaceChildren();
  for (const observation of observations) addObservationRow(observation);
  $("#add-observation").disabled = observations.length >= 200;
  const hasTextResults = observations.some((observation) => observation.value_text != null);
  const hint = $("#lab-edit").firstElementChild;
  hint.textContent = "Une nouvelle version sera créée. Les résultats précédents seront conservés."
    + (hasTextResults ? " Ce formulaire enregistre uniquement les valeurs numériques dans la nouvelle version." : "");
}

$("#add-observation").addEventListener("click", () => addObservationRow().querySelector("input").focus());

function editError(error) {
  const messages = {
    ACCESSION_CONFLICT: "Ce numéro d’examen est déjà utilisé. Choisissez-en un autre.",
    INVALID_OBSERVATION: "Vérifiez les codes et les unités des analyses. Chaque code doit être unique.",
    INVALID_REPORT_SEQUENCE: "Le rapport a été modifié entre-temps. Rechargez le dossier avant de réessayer.",
    INVALID_TIME: "La date de l’examen doit être comprise dans la période de prise en charge.",
    INVALID_TRANSITION: "L’examen a changé depuis l’ouverture du dossier. Rechargez le dossier avant de réessayer.",
    INVALID_INPUT: "Vérifiez les informations saisies.",
    NO_OBSERVATIONS: "Saisissez au moins une valeur numérique.",
  };
  if (error.status === 403) return "Votre compte ne permet pas cette modification.";
  return messages[error.message] ?? "Enregistrement impossible. Réessayez dans quelques instants.";
}

async function submitEdit(form, operation, pending, successMessage) {
  if (saving || !currentSummary || logoutButton.disabled) return;
  const summary = currentSummary;
  const button = form.querySelector('button[type="submit"]');
  const message = form.querySelector(".form-feedback");
  const hadFocus = form.contains(document.activeElement);
  saving = true;
  setNavigationDisabled(true);
  setEditButtonsDisabled(true);
  tell(message, pending);
  try {
    const outcome = await operation(summary, message);
    if (!signedIn) return;
    const refreshed = !outcome?.skipRefresh && await loadSummary(summary.encounter.id, true);
    if (!signedIn) return;
    if (outcome?.message) {
      tell(message, outcome.message, outcome.tone);
    } else {
      tell(message, refreshed ? successMessage
        : `${successMessage} Relancez la recherche pour afficher la mise à jour.`, "good");
    }
  } catch (error) {
    if (!signedIn) return;
    if (error.status === 401) expireSession();
    else tell(message, editError(error), "error");
  } finally {
    saving = false;
    setNavigationDisabled(false);
    setEditButtonsDisabled(false);
    if (signedIn && hadFocus && document.activeElement === document.body) button.focus();
  }
}

$("#lab-edit").addEventListener("submit", (event) => {
  event.preventDefault();
  submitEdit(event.currentTarget, async (summary) => {
    const observations = [];
    for (const row of $("#lab-observations").children) {
      const field = (name) => row.querySelector(`[data-field="${name}"]`).value.trim();
      if (field("value") !== "") {
        observations.push({ code: field("code"), display: field("display"), value_numeric: Number(field("value")), unit: field("unit") });
      }
    }
    if (!observations.length) throw new Error("NO_OBSERVATIONS");
    const { lab_order_id: orderId } = summary.laboratory.reports[0];
    await write(`/api/v1/lab-orders/${encodeURIComponent(orderId)}/reports`, "POST", { observations });
  }, "Enregistrement des résultats…", "Nouvelle version enregistrée.");
});

radiologyForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  submitEdit(form, async (summary, message) => {
    const accession = $("#ris-accession").value.trim();
    const procedure = $("#ris-procedure").value.trim();
    const content = $("#ris-report").value.trim();
    if (!accession || !procedure || !content) throw new Error("INVALID_INPUT");

    try {
      if (!radiologyProgress || radiologyProgress.accession !== accession) {
        const created = await write("/api/v1/radiology-orders", "POST", {
          encounter_id: summary.encounter.id,
          accession_number: accession,
          requested_procedure: procedure,
          modality: $("#ris-modality").value,
          priority: $("#ris-priority").value,
        });
        radiologyProgress = { accession, examId: created.exam_id, performed: false };
      }
      const progress = radiologyProgress;
      const path = `/api/v1/radiology-exams/${encodeURIComponent(progress.examId)}`;
      if (!progress.performed) {
        tell(message, "Enregistrement de la réalisation de l’examen…");
        await write(path, "PATCH", { status: "performed", performed_at: new Date().toISOString() });
        progress.performed = true;
      }
      await write(`${path}/report`, "PUT", { content });
      tell(message, "Validation du compte rendu…");
      await write(`${path}/report/validate`, "POST", { validated_at: new Date().toISOString() });
      radiologyProgress = null;
      form.reset();
      $("#ris-accession").value = "";
    } catch (error) {
      if (error.status === 401 || radiologyProgress?.accession !== accession) throw error;
      return { message: `Examen créé. ${editError(error)}`, tone: "error" };
    }
  }, "Enregistrement de l’examen…", "Examen enregistré et compte rendu validé.");
});

$("#imaging-edit").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = $("#dicom-file");
  const files = [...input.files];
  if (!files.length) return;
  const operation = submitEdit(event.currentTarget, async (summary, message) => {
    let imported = 0;
    const failed = [];
    const reasons = {
      DICOM_MISMATCH: "fichier incompatible avec le patient ou l’examen",
      INVALID_DICOM: "fichier DICOM invalide",
      UNKNOWN_ACCESSION: "examen introuvable",
      MODALITY_MISMATCH: "type d’imagerie différent de celui de l’examen",
      PAYLOAD_TOO_LARGE: "plus de 8 Mio",
      ACCESS_DENIED: "accès refusé",
    };
    for (const [index, file] of files.entries()) {
      if (!signedIn) return;
      tell(message, `Import du fichier ${index + 1} sur ${files.length}…`);
      if (file.size > 8 * 1024 * 1024) {
        failed.push({ file, reason: "plus de 8 Mio" });
        continue;
      }
      try {
        await api(`/api/v1/encounters/${encodeURIComponent(summary.encounter.id)}/imaging-studies`, {
          method: "POST", headers: csrfHeaders({ "Content-Type": "application/dicom" }), body: file,
        });
        imported += 1;
      } catch (error) {
        if (error.status === 401) throw error;
        failed.push({ file, reason: reasons[error.message] ?? "import impossible" });
      }
    }
    const retry = new DataTransfer();
    for (const { file } of failed) retry.items.add(file);
    input.files = retry.files;
    const count = imported === 1 ? "1 fichier importé." : `${imported} fichiers importés.`;
    const errors = failed.map(({ file, reason }) => `${file.name} (${reason})`).join(", ");
    return { message: errors ? `${count} À vérifier : ${errors}.` : count,
      tone: failed.length ? "error" : "good", skipRefresh: !imported };
  }, "Import des fichiers…");
  input.disabled = true;
  operation.finally(() => { input.disabled = false; });
});

try {
  const session = await api("/api/v1/auth/me");
  await openWorkspace(session);
} catch (error) {
  if (error.status === 401) showLogin();
  else showLogin("Impossible de vérifier la session. Vous pouvez réessayer de vous connecter.", "error");
}
