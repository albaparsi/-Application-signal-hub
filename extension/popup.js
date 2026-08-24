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
// popup.js variables. Gathers everything the backend's /extraction/infer
// (LLM-assisted) endpoint needs, plus a fully-local fallback in case that
// call can't be reached at all (API down, offline, etc).
function gatherPageContext() {
  // Most real job boards (LinkedIn, Indeed, Greenhouse, Lever, Workday...)
  // embed schema.org JobPosting structured data for Google Jobs SEO. It's
  // far more reliable than scraping visible headings: e.g. on LinkedIn,
  // the page's og:site_name is always "LinkedIn" itself, never the actual
  // hiring company, but the JobPosting JSON-LD has the real one.
  const readJobPosting = () => {
    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
    for (const script of scripts) {
      let parsed;
      try {
        parsed = JSON.parse(script.textContent);
      } catch {
        continue;
      }
      const candidates = Array.isArray(parsed) ? parsed : parsed["@graph"] || [parsed];
      for (const item of candidates) {
        const type = item && item["@type"];
        const isJobPosting = type === "JobPosting" || (Array.isArray(type) && type.includes("JobPosting"));
        if (isJobPosting) return item;
      }
    }
    return null;
  };

  const flattenLocation = (jobLocation) => {
    const loc = Array.isArray(jobLocation) ? jobLocation[0] : jobLocation;
    if (!loc) return "";
    if (typeof loc === "string") return loc;
    const address = loc.address;
    if (!address) return "";
    if (typeof address === "string") return address;
    return [address.addressLocality, address.addressRegion, address.addressCountry]
      .filter(Boolean)
      .join(", ");
  };

  const getMeta = (name) => {
    const el = document.querySelector(`meta[property="${name}"], meta[name="${name}"]`);
    return el && el.content ? el.content.trim() : "";
  };

  const jobPosting = readJobPosting();
  const jobPostingHints = {
    company:
      jobPosting && jobPosting.hiringOrganization
        ? String(
            typeof jobPosting.hiringOrganization === "string"
              ? jobPosting.hiringOrganization
              : jobPosting.hiringOrganization.name || ""
          ).trim()
        : "",
    role: jobPosting && jobPosting.title ? String(jobPosting.title).trim() : "",
    location: jobPosting ? flattenLocation(jobPosting.jobLocation) : "",
  };

  // Pure local heuristic — used only if the backend call fails entirely
  // (server extraction handles JSON-LD-less pages far better via the LLM).
  let fallbackRole = jobPostingHints.role;
  let fallbackCompany = jobPostingHints.company;
  if (!fallbackRole) {
    const h1 = document.querySelector("h1");
    fallbackRole = (h1 && h1.innerText.trim()) || document.title.trim();
  }
  if (!fallbackCompany) {
    fallbackCompany = getMeta("og:site_name");
    if (!fallbackCompany) {
      const host = location.hostname.replace(/^www\./, "");
      const base = host.split(".").slice(0, -1).join(".") || host;
      fallbackCompany = base.charAt(0).toUpperCase() + base.slice(1);
    }
  }

  return {
    url: location.href,
    title: document.title,
    // Capped to keep the payload small — this is sent off-device to the
    // configured LLM, so it's deliberately a bounded excerpt, not the
    // full page.
    visibleText: (document.body ? document.body.innerText : "").slice(0, 6000),
    jobPostingHints,
    localFallback: {
      company: fallbackCompany,
      role: fallbackRole,
      location: jobPostingHints.location,
    },
  };
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
      func: gatherPageContext,
    });
    if (!result) return;

    fields.url.value = result.url || fields.url.value;

    try {
      const hints = result.jobPostingHints;
      const hasHints = hints && (hints.company || hints.role || hints.location);

      const response = await fetch(`${API_BASE}/extraction/infer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: result.url,
          title: result.title,
          job_posting_hints: hasHints ? hints : null,
          visible_text: result.visibleText,
        }),
      });
      if (!response.ok) throw new Error(`extraction endpoint returned ${response.status}`);

      const data = await response.json();
      fields.company.value = data.company || "";
      fields.role.value = data.role || "";
      fields.location.value = data.location || "";
      if (data.status) fields.status.value = data.status;
      return;
    } catch (err) {
      console.debug("Application Signal Hub: server extraction unavailable, using local fallback", err);
    }

    const fb = result.localFallback || {};
    fields.company.value = fb.company || "";
    fields.role.value = fb.role || "";
    fields.location.value = fb.location || "";
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
