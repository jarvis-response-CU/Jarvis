export async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`${response.status} from ${new URL(url).host}`);
  return response.json();
}

export function formatDate(ms) {
  return ms ? new Date(ms).toLocaleString() : null;
}

export function setStatus(name, text) {
  document.querySelector(`[data-status="${name}"]`).textContent = text ? `· ${text}` : "";
}

// External data goes in via textContent only, never innerHTML.
const details = document.getElementById("details");

export function showDetails(title, rows) {
  const list = document.createElement("dl");
  const heading = document.createElement("strong");
  heading.textContent = title;
  details.replaceChildren(heading, list);
  for (const [label, value] of rows) {
    if (value === null || value === undefined || value === "") continue;
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = label;
    dd.textContent = value;
    list.append(dt, dd);
  }
}
