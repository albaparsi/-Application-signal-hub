const API_BASE = "http://localhost:8000";

const form = document.getElementById("save-form");
const saveButton = document.getElementById("save-button");
const statusMessage = document.getElementById("status-message");

const fields = {
  company: document.getElementById("company"),
  role: document.getElementById("role"),
  location: document.getElementById("location"),
  url: document.getElementById("url"),
  status: document.getElementById("status"),
  notes: document.getElementById("notes"),
};

function setMessage(text, kind) {
  statusMessage.textContent = text;
  if (kind) {
    statusMessage.dataset.kind = kind;
  } else {
    delete statusMessage.dataset.kind;
  }
}

// Runs inside the page (via chrome.scripting.executeScript), not in the
// extension's own context — keep this self-contained, no closures over
// popup.js variables.
function extractPageData() {
  const getMeta = (name) => {
    const el = document.querySelector(`meta[property="${name}"], meta[name="${name}"]`);
    return el && el.content ? el.content.trim() : "";
  };

  const h1 = document.querySelector("h1");
  const role = (h1 && h1.innerText.trim()) || document.title.trim();

  let company = getMeta("og:site_name");
  if (!company) {
    const host = location.hostname.replace(/^www\./, "");
    const base = host.split(".").slice(0, -1).join(".") || host;
    company = base.charAt(0).toUpperCase() + base.slice(1);
  }

  return { role, company, url: location.href };
}

async function prefillFromActiveTab() {
  // Extraction can fail for all sorts of reasons that aren't errors worth
  // surfacing — browser-internal pages (chrome://, the Web Store), a
  // permissions edge case, etc. The form is always usable blank; the user
  // just fills it in by hand if this doesn't work.
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.id) return;

    fields.url.value = tab.url || "";

    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractPageData,
    });
    if (result) {
      fields.company.value = result.company || "";
      fields.role.value = result.role || "";
      fields.url.value = result.url || fields.url.value;
    }
  } catch (err) {
    console.debug("Application Signal Hub: page extraction skipped", err);
  }
}

async function handleSubmit(event) {
  event.preventDefault();
  setMessage("", null);
  saveButton.disabled = true;
  saveButton.textContent = "Saving…";

  const payload = {
    company: fields.company.value.trim(),
    role: fields.role.value.trim(),
    url: fields.url.value.trim() || null,
    location: fields.location.value.trim() || null,
    status: fields.status.value,
    source: "extension",
    notes: fields.notes.value.trim() || null,
  };

  try {
    const response = await fetch(`${API_BASE}/applications`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail ? JSON.stringify(body.detail) : `Server returned ${response.status}`);
    }

    setMessage("Saved.", "success");
    setTimeout(() => window.close(), 900);
  } catch (err) {
    setMessage(`Couldn't save: ${err.message}`, "error");
    saveButton.disabled = false;
    saveButton.textContent = "Save application";
  }
}

form.addEventListener("submit", handleSubmit);
prefillFromActiveTab();
