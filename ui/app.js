// ui/app.js - Plain JS client for CFO Copilot
// Security Rule: Every piece of model, filing, and user text is set strictly
// via textContent to prevent markdown/HTML prompt injection and exfiltration attacks.

(function () {
  "use strict";

  let currentSessionId = null;

  // DOM Elements
  const apiKeyInput = document.getElementById("apiKeyInput");
  const sessionsList = document.getElementById("sessionsList");
  const newSessionBtn = document.getElementById("newSessionBtn");
  const chatMessages = document.getElementById("chatMessages");
  const chatForm = document.getElementById("chatForm");
  const questionInput = document.getElementById("questionInput");
  const sendBtn = document.getElementById("sendBtn");
  const charCount = document.getElementById("charCount");
  const degradedBanner = document.getElementById("degradedBanner");
  const degradedText = document.getElementById("degradedText");

  // Show Your Work Elements
  const requestTrackingId = document.getElementById("requestTrackingId");
  const auditRoute = document.getElementById("auditRoute");
  const auditStage = document.getElementById("auditStage");
  const telemetryFirstContent = document.getElementById("telemetryFirstContent");
  const telemetryVerified = document.getElementById("telemetryVerified");
  const telemetryLlmCalls = document.getElementById("telemetryLlmCalls");
  const telemetryCache = document.getElementById("telemetryCache");
  const slotCompany = document.getElementById("slotCompany");
  const slotPeriod = document.getElementById("slotPeriod");
  const slotKpi = document.getElementById("slotKpi");
  const slotBasis = document.getElementById("slotBasis");
  const auditFactsList = document.getElementById("auditFactsList");
  const auditRules = document.getElementById("auditRules");
  const auditPassages = document.getElementById("auditPassages");
  const auditVerifier = document.getElementById("auditVerifier");

  // Modal
  const provenanceModal = document.getElementById("provenanceModal");
  const provenanceContent = document.getElementById("provenanceContent");
  const closeModalBtn = document.getElementById("closeModalBtn");

  // Event Listeners
  questionInput.addEventListener("input", function () {
    charCount.textContent = `${questionInput.value.length}/2000`;
  });

  newSessionBtn.addEventListener("click", createNewSession);
  chatForm.addEventListener("submit", handleChatSubmit);
  closeModalBtn.addEventListener("click", () => {
    provenanceModal.style.display = "none";
  });

  // Sample Query Buttons
  document.querySelectorAll(".sample-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      questionInput.value = btn.dataset.query;
      charCount.textContent = `${questionInput.value.length}/2000`;
      questionInput.focus();
    });
  });

  function getHeaders() {
    return {
      "Content-Type": "application/json",
      "X-API-Key": apiKeyInput.value.trim() || "cfo_key_acme_dev",
    };
  }

  // Session Management
  async function loadSessions() {
    try {
      const resp = await fetch("/v1/sessions", { headers: getHeaders() });
      if (!resp.ok) return;
      const data = await resp.json();
      sessionsList.textContent = "";

      if (data.sessions && data.sessions.length > 0) {
        data.sessions.forEach((sess) => {
          const item = document.createElement("div");
          item.className = `session-item ${sess.session_id === currentSessionId ? "active" : ""}`;
          item.textContent = sess.title || sess.session_id;
          item.addEventListener("click", () => selectSession(sess.session_id));
          sessionsList.appendChild(item);
        });
      } else {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent = "No sessions yet.";
        sessionsList.appendChild(empty);
      }
    } catch (err) {
      console.error("Failed to load sessions:", err);
    }
  }

  async function createNewSession() {
    try {
      const resp = await fetch("/v1/sessions", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ title: `Session ${new Date().toLocaleTimeString()}` }),
      });
      if (resp.ok) {
        const sess = await resp.json();
        currentSessionId = sess.session_id;
        await loadSessions();
        chatMessages.textContent = "";
        appendSystemMessage(`New session initialized: ${sess.session_id}`);
      }
    } catch (err) {
      console.error("Failed to create session:", err);
    }
  }

  async function selectSession(sessionId) {
    currentSessionId = sessionId;
    await loadSessions();
    try {
      const resp = await fetch(`/v1/sessions/${sessionId}/messages`, { headers: getHeaders() });
      if (!resp.ok) return;
      const data = await resp.json();
      chatMessages.textContent = "";
      if (data.messages && data.messages.length > 0) {
        data.messages.forEach((msg) => {
          appendMessageRow(msg.role, msg.content);
        });
      } else {
        appendSystemMessage(`Session ${sessionId} loaded (empty).`);
      }
    } catch (err) {
      console.error("Failed to load messages:", err);
    }
  }

  function appendMessageRow(role, text) {
    const row = document.createElement("div");
    row.className = `message-row ${role}`;

    const sender = document.createElement("span");
    sender.className = "message-sender";
    sender.textContent = role === "user" ? "CFO Executive" : "CFO Copilot";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    // Strictly textContent to prevent injection
    bubble.textContent = text;

    row.appendChild(sender);
    row.appendChild(bubble);
    chatMessages.appendChild(row);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return bubble;
  }

  function appendSystemMessage(text) {
    const card = document.createElement("div");
    card.className = "empty-state";
    card.style.textAlign = "center";
    card.style.margin = "1rem 0";
    card.textContent = text;
    chatMessages.appendChild(card);
  }

  // Progressive Chat Streaming Handling
  async function handleChatSubmit(e) {
    e.preventDefault();
    const question = questionInput.value.trim();
    if (!question) return;

    // Reset degraded banner
    degradedBanner.style.display = "none";

    // UI state
    questionInput.value = "";
    charCount.textContent = "0/2000";
    sendBtn.disabled = true;
    appendMessageRow("user", question);

    // Prepare assistant placeholder bubble
    const assistantBubble = appendMessageRow("assistant", "Admitting request to queue...");
    auditStage.textContent = "Admitting...";

    try {
      const payload = {
        question: question,
        session_id: currentSessionId,
        stream: true,
      };

      const resp = await fetch("/v1/chat/stream", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        const errJson = await resp.json().catch(() => ({}));
        const errMsg = errJson.message || `Server error (${resp.status})`;
        assistantBubble.textContent = `Error: ${errMsg}`;
        auditStage.textContent = "Failed";
        sendBtn.disabled = false;
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop(); // keep last unfinished chunk

        for (const rawEvt of events) {
          if (!rawEvt.trim()) continue;
          processSseEvent(rawEvt, assistantBubble);
        }
      }

      auditStage.textContent = "Completed";
      await loadSessions();
    } catch (err) {
      assistantBubble.textContent = `Connection error: ${err.message}`;
      auditStage.textContent = "Error";
    } finally {
      sendBtn.disabled = false;
    }
  }

  function processSseEvent(rawBlock, assistantBubble) {
    const lines = rawBlock.split("\n");
    let eventName = "message";
    let dataStr = "";

    for (const line of lines) {
      if (line.startsWith("event: ")) {
        eventName = line.substring(7).trim();
      } else if (line.startsWith("data: ")) {
        dataStr = line.substring(6).trim();
      }
    }

    if (!dataStr) return;
    if (dataStr === "[DONE]") return;

    try {
      const data = JSON.parse(dataStr);

      if (eventName === "meta") {
        requestTrackingId.textContent = data.request_id || "req_live";
        auditRoute.textContent = data.route || "UNKNOWN";
        auditStage.textContent = "Fetching Facts...";
      } else if (eventName === "facts") {
        auditStage.textContent = "Drafting & Verifying...";
        telemetryFirstContent.textContent = `${data.ttft_first_content_ms} ms`;
        renderFactsList(data.facts || []);
        renderPassagesList(data.facts || []);
      } else if (eventName === "progress") {
        auditStage.textContent = data.stage || "Processing...";
      } else if (eventName === "answer") {
        // Render verified answer text strictly as plain text
        assistantBubble.textContent = data.answer;

        if (data.status === "ok_extractive" || data.degraded) {
          degradedBanner.style.display = "flex";
          degradedText.textContent = data.status === "ok_extractive" ? "Excerpts from filings; not a synthesized answer" : `Degraded Mode Active: ${data.degraded_reason || "Extractive fallback served."}`;
        }
      } else if (eventName === "final") {
        // Populate all metadata from AnswerEnvelope
        telemetryVerified.textContent = `${data.latency_ms} ms`;
        telemetryLlmCalls.textContent = data.llm_calls_made || "0";

        if (data.status === "ok_extractive") {
          auditVerifier.textContent = "";
          const badge = document.createElement("span");
          badge.className = "status-badge extractive";
          badge.style.background = "#fff3cd";
          badge.style.color = "#856404";
          badge.style.borderColor = "#ffeeba";
          badge.textContent = "Excerpts from filings; not a synthesized answer";
          auditVerifier.appendChild(badge);
        } else if (data.verification) {
          auditVerifier.textContent = "";
          const badge = document.createElement("span");
          badge.className = `status-badge ${data.verification.is_valid ? "valid" : "invalid"}`;
          badge.textContent = data.verification.is_valid ? "VERIFIED GROUNDED (100%)" : "INTERCEPTED / FALLBACK";
          auditVerifier.appendChild(badge);
        }

        renderPolicyRules(data.caveats || []);
      } else if (eventName === "error") {
        assistantBubble.textContent = `Error: ${data.message}`;
        auditStage.textContent = "Rejected / Error";
      }
    } catch (e) {
      console.warn("Could not parse SSE JSON:", dataStr);
    }
  }

  function renderFactsList(facts) {
    auditFactsList.textContent = "";
    const kpiFacts = facts.filter((f) => f.kpi_id);

    if (kpiFacts.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "No numeric KPI facts required for this query.";
      auditFactsList.appendChild(empty);
      return;
    }

    // Update slots from first fact
    const first = kpiFacts[0];
    slotCompany.textContent = first.company_id || "—";
    slotPeriod.textContent = `FY${first.fiscal_year} Q${first.fiscal_quarter}`;
    slotKpi.textContent = first.kpi_id || "—";
    slotBasis.textContent = first.basis || "as_restated";

    kpiFacts.forEach((fact) => {
      const card = document.createElement("div");
      card.className = "fact-card";

      const header = document.createElement("div");
      header.className = "fact-header";

      const title = document.createElement("span");
      title.textContent = `${fact.company_id} ${fact.kpi_id}`;

      const statusSpan = document.createElement("span");
      statusSpan.style.color = fact.status === "ok" ? "var(--accent-green)" : "var(--accent-amber)";
      statusSpan.textContent = fact.status;

      header.appendChild(title);
      header.appendChild(statusSpan);

      const valRow = document.createElement("div");
      valRow.style.fontSize = "0.9rem";
      valRow.style.fontWeight = "600";
      valRow.textContent = fact.value !== null ? `${fact.value.toLocaleString()} ${fact.unit}` : "N/A";

      const provRow = document.createElement("div");
      provRow.style.marginTop = "0.35rem";
      provRow.style.fontSize = "0.75rem";

      if (fact.kpi_value_id) {
        const link = document.createElement("span");
        link.className = "provenance-link";
        link.textContent = "🔍 View Provenance Trace";
        link.addEventListener("click", () => fetchProvenance(fact.kpi_value_id));
        provRow.appendChild(link);
      } else {
        provRow.textContent = `Source: ${fact.source_filing || "Certified SQL"}`;
      }

      card.appendChild(header);
      card.appendChild(valRow);
      card.appendChild(provRow);
      auditFactsList.appendChild(card);
    });
  }

  function renderPassagesList(facts) {
    auditPassages.textContent = "";
    const textFacts = facts.filter((f) => !f.kpi_id && f.text);

    if (textFacts.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "No qualitative filing passages retrieved.";
      auditPassages.appendChild(empty);
      return;
    }

    textFacts.forEach((tf, idx) => {
      const card = document.createElement("div");
      card.className = "passage-card";

      const textEl = document.createElement("div");
      // STRICT textContent
      textEl.textContent = `[${idx + 1}] "${tf.text}"`;

      const citeEl = document.createElement("div");
      citeEl.className = "passage-citation";
      citeEl.textContent = `Source: ${tf.source_filing || tf.fact_id || "SEC Disclosure"}`;

      card.appendChild(textEl);
      card.appendChild(citeEl);
      auditPassages.appendChild(card);
    });
  }

  function renderPolicyRules(caveats) {
    auditRules.textContent = "";
    if (caveats.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "Standard accounting policy applied. No comparability adjustments.";
      auditRules.appendChild(empty);
      return;
    }

    caveats.forEach((c) => {
      const item = document.createElement("div");
      item.style.padding = "0.35rem 0";
      item.style.fontSize = "0.75rem";
      item.style.color = "var(--accent-amber)";
      item.textContent = `• ${c}`;
      auditRules.appendChild(item);
    });
  }

  async function fetchProvenance(kpiValueId) {
    try {
      const resp = await fetch(`/v1/provenance/${kpiValueId}`, { headers: getHeaders() });
      if (!resp.ok) {
        alert("Failed to load provenance trace.");
        return;
      }
      const trace = await resp.json();
      provenanceContent.textContent = JSON.stringify(trace, null, 2);
      provenanceModal.style.display = "block";
    } catch (err) {
      console.error("Provenance fetch error:", err);
    }
  }

  // Initial load
  loadSessions();
})();

