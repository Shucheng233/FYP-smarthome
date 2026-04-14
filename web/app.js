async function apiGet(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(await r.text());
  return await r.json();
}

async function apiPost(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return await r.json();
}

function pretty(obj) {
  return typeof obj === "string" ? obj : JSON.stringify(obj, null, 2);
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

async function refreshHealth() {
  try {
    const res = await apiGet("/health");
    const model = res.remote_llm_model || res.ollama_model || "unknown";
    const extractorReady = res.extractor_ready === true ? "ready" : "not ready";

    setText(
      "sysStatus",
      `System: OK | Mode: ${res.llm_api_mode} | Model: ${model} | Extractor: ${extractorReady}`
    );
  } catch (e) {
    setText("sysStatus", `System: ERROR | ${e.message}`);
  }
}

const btnIot = document.getElementById("btnIot");
if (btnIot) {
  btnIot.addEventListener("click", async () => {
    const prompt = document.getElementById("iotPrompt")?.value || "";
    if (!prompt.trim()) {
      setText("iotOut", "Please enter a command");
      return;
    }

    try {
      const res = await apiPost("/iot/command", { prompt });
      setText("iotOut", pretty(res.commands));
    } catch (e) {
      setText("iotOut", `ERROR: ${e.message}`);
    }
  });
}

const btnIotClear = document.getElementById("btnIotClear");
if (btnIotClear) {
  btnIotClear.addEventListener("click", () => {
    setText("iotOut", "Commands will appear here...");
  });
}

// Initialize
refreshHealth();
setInterval(refreshHealth, 5000);
