const params = new URLSearchParams(location.search);
const DEFAULT_BASE = "http://127.0.0.1:8000";
const DEFAULT_DOWNLOAD =
  "https://github.com/jamesdileva/CommunityCompute/releases";
const DEFAULT_DASHBOARD = "http://localhost:5173";

function resolveBase() {
  return (
    params.get("api") ||
    localStorage.getItem("cc_api_base") ||
    DEFAULT_BASE
  );
}

function setBase(value) {
  const clean = (value || "").replace(/\/+$/, "");
  if (clean) localStorage.setItem("cc_api_base", clean);
  return clean || DEFAULT_BASE;
}

const baseInput = document.getElementById("api-base");
baseInput.value = resolveBase();

document.getElementById("bundle-link").href =
  params.get("download") || DEFAULT_DOWNLOAD;
document.getElementById("dashboard-link").href =
  params.get("dashboard") || DEFAULT_DASHBOARD;

function renderWorkloads(workloads, base) {
  const list = document.getElementById("workload-list");
  const note = document.getElementById("workload-note");
  list.innerHTML = "";
  if (!workloads.length) {
    note.textContent = "The coordinator reported no workloads.";
    return;
  }
  for (const w of workloads) {
    const card = document.createElement("article");
    card.className = "card";
    const title = document.createElement("h3");
    title.textContent = w.name;
    const tag = document.createElement("span");
    tag.className = w.gpu ? "tag gpu" : "tag";
    tag.textContent = w.gpu ? "GPU" : "CPU";
    title.appendChild(tag);
    card.appendChild(title);

    const desc = document.createElement("p");
    desc.textContent = w.description || "No description.";
    card.appendChild(desc);

    const meta = document.createElement("p");
    meta.className = "fineprint";
    const reqs = Object.entries(w.requirements || {})
      .map(([k, v]) => `${k}=${v}`)
      .join(", ");
    meta.textContent = `v${w.version} · requires ${reqs || "any worker"}`;
    card.appendChild(meta);

    list.appendChild(card);
  }
  note.textContent = `Loaded from ${base}/workloads`;
}

async function loadWorkloads() {
  const base = setBase(baseInput.value);
  const note = document.getElementById("workload-note");
  note.textContent = `Loading ${base}/workloads …`;
  try {
    const resp = await fetch(`${base}/workloads`);
    if (!resp.ok) throw new Error(`${resp.status}`);
    renderWorkloads(await resp.json(), base);
  } catch (err) {
    document.getElementById("workload-list").innerHTML = "";
    note.textContent =
      `Could not reach ${base}/workloads (${err}). ` +
      "Check the coordinator URL and that the coordinator is running.";
  }
}

document.getElementById("load-workloads").addEventListener("click", loadWorkloads);
baseInput.addEventListener("change", loadWorkloads);

loadWorkloads();
