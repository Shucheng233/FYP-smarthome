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

async function refreshHealth() {
  try {
    const h = await apiGet("/health");
    document.getElementById("sysStatus").textContent =
      `System: OK | model=${h.ollama_model} | ollama=${h.ollama_base_url}`;
  } catch (e) {
    document.getElementById("sysStatus").textContent =
      `System: ERROR | ${e.message}`;
  }
}

async function refreshSensor() {
  try {
    const res = await apiGet("/sensor/latest");
    const d = res.data || {};
    document.getElementById("tVal").textContent = d.temperature ?? "-";
    document.getElementById("hVal").textContent = d.humidity ?? "-";
    document.getElementById("cVal").textContent = d.co2 ?? "-";
    document.getElementById("uVal").textContent = d.updated_at ?? "-";
    document.getElementById("sensorOut").textContent = pretty(res);
  } catch (e) {
    document.getElementById("sensorOut").textContent = `ERROR: ${e.message}`;
  }
}

document.getElementById("btnLlm").addEventListener("click", async () => {
  const prompt = document.getElementById("llmPrompt").value;
  try {
    const res = await apiPost("/llm", { prompt });
    document.getElementById("llmOut").textContent = pretty(res);
  } catch (e) {
    document.getElementById("llmOut").textContent = `ERROR: ${e.message}`;
  }
});

document.getElementById("btnLlmClear").addEventListener("click", () => {
  document.getElementById("llmOut").textContent = "...";
});

document.getElementById("btnSensorRefresh").addEventListener("click", refreshSensor);

document.getElementById("btnSensorUpdate").addEventListener("click", async () => {
  const t = document.getElementById("tIn").value;
  const h = document.getElementById("hIn").value;
  const c = document.getElementById("cIn").value;
  const payload = {};
  if (t !== "") payload.temperature = Number(t);
  if (h !== "") payload.humidity = Number(h);
  if (c !== "") payload.co2 = Number(c);

  try {
    const res = await apiPost("/sensor/update", payload);
    document.getElementById("sensorOut").textContent = pretty(res);
    await refreshSensor();
  } catch (e) {
    document.getElementById("sensorOut").textContent = `ERROR: ${e.message}`;
  }
});

document.querySelectorAll(".btnGrid button").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const device = btn.getAttribute("data-device");
    const action = btn.getAttribute("data-action");
    try {
      const res = await apiPost("/iot/command", { device, action });
      document.getElementById("iotOut").textContent = pretty(res);
    } catch (e) {
      document.getElementById("iotOut").textContent = `ERROR: ${e.message}`;
    }
  });
});

document.getElementById("btnSttStatus").addEventListener("click", async () => {
  try {
    const res = await apiGet("/stt/status");
    document.getElementById("sttTtsOut").textContent = pretty(res);
  } catch (e) {
    document.getElementById("sttTtsOut").textContent = `ERROR: ${e.message}`;
  }
});

document.getElementById("btnTtsStatus").addEventListener("click", async () => {
  try {
    const res = await apiGet("/tts/status");
    document.getElementById("sttTtsOut").textContent = pretty(res);
  } catch (e) {
    document.getElementById("sttTtsOut").textContent = `ERROR: ${e.message}`;
  }
});

// init
refreshHealth();
refreshSensor();
setInterval(refreshHealth, 5000);
setInterval(refreshSensor, 5000);
