const promptInput = document.getElementById("promptInput");
const sendBtn = document.getElementById("sendBtn");
const clearPromptBtn = document.getElementById("clearPromptBtn");
const commandOutput = document.getElementById("commandOutput");
const quickTests = document.getElementById("quickTests");
const stateGrid = document.getElementById("stateGrid");
const logPanel = document.getElementById("logPanel");
const apiStatus = document.getElementById("apiStatus");
const deviceStatus = document.getElementById("deviceStatus");
const dashStatus = document.getElementById("dashStatus");
const copyLogBtn = document.getElementById("copyLogBtn");
const downloadLogBtn = document.getElementById("downloadLogBtn");
const clearLogBtn = document.getElementById("clearLogBtn");

let logLines = [];
let dashboardSocket = null;

const testPrompts = [
  "Turn on the living room light.",
  "Turn off the living room light.",
  "Set the living room light brightness to 40%.",
  "Make the living room light brighter.",
  "Dim the living room light.",
  "Set the living room light to warm white.",
  "Set the living room light to blue.",
  "Turn on the bedroom light.",
  "Turn on the living room fan.",
  "Set the living room fan speed to 70%.",
  "Increase the living room fan speed.",
  "Decrease the living room fan speed.",
  "Turn on the bedroom fan.",
  "Turn off all the fans.",
  "Turn off all devices.",
  "Set the living room light brightness to 200%."
];

function setPill(el, text, cls) {
  el.textContent = text;
  el.className = `pill ${cls}`;
}

async function apiGet(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

async function apiPost(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

function appendLog(event) {
  const dataText = event.data === undefined || event.data === null
    ? ""
    : JSON.stringify(event.data, null, 2);

  const lineText = `[${event.time}] [${event.source}] [${event.level}] ${event.message}` +
    (dataText ? `\n${dataText}` : "");
  logLines.push(lineText);

  const div = document.createElement("div");
  div.className = "log-line";
  div.innerHTML =
    `<span class="time">[${event.time}]</span> ` +
    `<span class="source">[${event.source}]</span> ` +
    `<span class="level ${event.level}">[${event.level}]</span> ` +
    `${escapeHtml(event.message)}` +
    (dataText ? `<span class="data">${escapeHtml(dataText)}</span>` : "");

  logPanel.appendChild(div);
  logPanel.scrollTop = logPanel.scrollHeight;
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderState(state) {
  if (!state || Object.keys(state).length === 0) {
    stateGrid.innerHTML = `<div class="empty">Waiting for ESP32 state...</div>`;
    return;
  }

  stateGrid.innerHTML = "";
  for (const [device, values] of Object.entries(state)) {
    const card = document.createElement("div");
    card.className = "state-card";
    const kv = Object.entries(values)
      .map(([key, value]) => `<div class="key">${escapeHtml(key)}</div><div>${escapeHtml(value)}</div>`)
      .join("");
    card.innerHTML = `<h3>${escapeHtml(device)}</h3><div class="kv">${kv}</div>`;
    stateGrid.appendChild(card);
  }
}

async function refreshHealth() {
  try {
    const health = await apiGet("/health");
    setPill(apiStatus, `API ok | ${health.llm_api_mode || "unknown"}`, "ok");
    if (health.connected_devices > 0) {
      setPill(deviceStatus, `ESP32 connected: ${health.connected_devices}`, "ok");
    } else {
      setPill(deviceStatus, "ESP32 disconnected", "warn");
    }
  } catch (err) {
    setPill(apiStatus, "API error", "error");
    setPill(deviceStatus, "ESP32 unknown", "grey");
  }
}

async function sendPrompt(prompt) {
  const text = (prompt || promptInput.value || "").trim();
  if (!text) return;

  sendBtn.disabled = true;
  commandOutput.textContent = "Sending...";

  try {
    const result = await apiPost("/iot/command", { prompt: text });
    commandOutput.textContent = JSON.stringify(result, null, 2);
    await refreshHealth();
  } catch (err) {
    commandOutput.textContent = String(err);
  } finally {
    sendBtn.disabled = false;
  }
}

function setupQuickTests() {
  quickTests.innerHTML = "";
  for (const prompt of testPrompts) {
    const btn = document.createElement("button");
    btn.className = "secondary";
    btn.textContent = prompt;
    btn.addEventListener("click", () => {
      promptInput.value = prompt;
      sendPrompt(prompt);
    });
    quickTests.appendChild(btn);
  }
}

function connectDashboardSocket() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const url = `${protocol}://${window.location.host}/ws/dashboard`;
  dashboardSocket = new WebSocket(url);

  dashboardSocket.onopen = () => {
    setPill(dashStatus, "Dashboard WS connected", "ok");
  };

  dashboardSocket.onmessage = (event) => {
    const payload = JSON.parse(event.data);

    if (payload.type === "snapshot") {
      logPanel.innerHTML = "";
      logLines = [];
      if (payload.events) payload.events.forEach(appendLog);
      if (payload.state) renderState(payload.state);
      if (payload.health) {
        if (payload.health.connected_devices > 0) {
          setPill(deviceStatus, `ESP32 connected: ${payload.health.connected_devices}`, "ok");
        } else {
          setPill(deviceStatus, "ESP32 disconnected", "warn");
        }
      }
    }

    if (payload.type === "event" && payload.event) appendLog(payload.event);
    if (payload.type === "state" && payload.state) renderState(payload.state);
    if (payload.type === "device_message" && payload.message && payload.message.state) renderState(payload.message.state);
    if (payload.type === "health" && payload.health) {
      if (payload.health.connected_devices > 0) setPill(deviceStatus, `ESP32 connected: ${payload.health.connected_devices}`, "ok");
      else setPill(deviceStatus, "ESP32 disconnected", "warn");
    }
  };

  dashboardSocket.onclose = () => {
    setPill(dashStatus, "Dashboard WS disconnected", "warn");
    setTimeout(connectDashboardSocket, 3000);
  };

  dashboardSocket.onerror = () => {
    setPill(dashStatus, "Dashboard WS error", "error");
  };
}

sendBtn.addEventListener("click", () => sendPrompt());
clearPromptBtn.addEventListener("click", () => { promptInput.value = ""; });
promptInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) sendPrompt();
});

copyLogBtn.addEventListener("click", async () => {
  await navigator.clipboard.writeText(logLines.join("\n\n"));
});

downloadLogBtn.addEventListener("click", () => {
  const blob = new Blob([logLines.join("\n\n")], { type: "text/plain;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `fyp-test-log-${new Date().toISOString().replaceAll(":", "-")}.txt`;
  link.click();
  URL.revokeObjectURL(link.href);
});

clearLogBtn.addEventListener("click", () => {
  logPanel.innerHTML = "";
  logLines = [];
});

setupQuickTests();
refreshHealth();
connectDashboardSocket();
setInterval(refreshHealth, 5000);
