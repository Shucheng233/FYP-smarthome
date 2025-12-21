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

// Health Check
document.getElementById("btnHealth").addEventListener("click", async () => {
  try {
    const res = await apiGet("/health");
    document.getElementById("healthOut").textContent = pretty(res);
    document.getElementById("sysStatus").textContent = `System: OK | Model: ${res.ollama_model}`;
  } catch (e) {
    document.getElementById("healthOut").textContent = `ERROR: ${e.message}`;
    document.getElementById("sysStatus").textContent = `System: ERROR`;
  }
});

// LLM Test
document.getElementById("btnLlm").addEventListener("click", async () => {
  const prompt = document.getElementById("llmPrompt").value;
  if (!prompt.trim()) {
    document.getElementById("llmOut").textContent = "Please enter a prompt";
    return;
  }
  try {
    const res = await apiPost("/llm", { prompt });
    document.getElementById("llmOut").textContent = pretty(res.response || res);
  } catch (e) {
    document.getElementById("llmOut").textContent = `ERROR: ${e.message}`;
  }
});

document.getElementById("btnLlmClear").addEventListener("click", () => {
  document.getElementById("llmOut").textContent = "Response will appear here...";
});

// Sensors (Mock)
document.getElementById("btnSensorRefresh").addEventListener("click", () => {
  document.getElementById("tVal").textContent = (20 + Math.random() * 10).toFixed(1);
  document.getElementById("hVal").textContent = (50 + Math.random() * 20).toFixed(0);
  document.getElementById("cVal").textContent = (350 + Math.random() * 100).toFixed(0);
  document.getElementById("sensorOut").textContent = "Mock data refreshed - API not implemented";
});

// IoT Command
document.getElementById("btnIot").addEventListener("click", async () => {
  const prompt = document.getElementById("iotPrompt").value;
  if (!prompt.trim()) {
    document.getElementById("iotOut").textContent = "Please enter a command";
    return;
  }
  try {
    const res = await apiPost("/iot/command", { prompt });
    document.getElementById("iotOut").textContent = pretty(res.commands);
  } catch (e) {
    document.getElementById("iotOut").textContent = `ERROR: ${e.message}`;
  }
});

document.getElementById("btnIotClear").addEventListener("click", () => {
  document.getElementById("iotOut").textContent = "Commands will appear here...";
});

// IoT Control (Mock) - keep for manual testing
document.querySelectorAll(".btnGrid button").forEach((btn) => {
  btn.addEventListener("click", () => {
    const device = btn.getAttribute("data-device");
    const action = btn.getAttribute("data-action");
    document.getElementById("iotOut").textContent = `Mock: ${device} ${action} - API not implemented`;
  });
});

// STT/TTS (Mock)
document.getElementById("btnSttStatus").addEventListener("click", () => {
  document.getElementById("sttTtsOut").textContent = "STT service not implemented yet";
});

document.getElementById("btnTtsStatus").addEventListener("click", () => {
  document.getElementById("sttTtsOut").textContent = "TTS service not implemented yet";
});

// Initialize
document.getElementById("btnHealth").click();

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
