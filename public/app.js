const state = {
  config: null,
  session: null,
  wheelAngle: 0,
  isAnimating: false
};

const sessionStorageKey = "fortune_spin_session_id";

const elements = {
  setupCard: document.getElementById("setupCard"),
  gameCard: document.getElementById("gameCard"),
  startForm: document.getElementById("startForm"),
  playerName: document.getElementById("playerName"),
  difficultySelect: document.getElementById("difficultySelect"),
  sessionIdInput: document.getElementById("sessionIdInput"),
  resumeBtn: document.getElementById("resumeBtn"),
  resumeHint: document.getElementById("resumeHint"),
  playerHeading: document.getElementById("playerHeading"),
  sessionMeta: document.getElementById("sessionMeta"),
  scoreValue: document.getElementById("scoreValue"),
  categoryChip: document.getElementById("categoryChip"),
  statusChip: document.getElementById("statusChip"),
  puzzleBoard: document.getElementById("puzzleBoard"),
  revealedMeta: document.getElementById("revealedMeta"),
  usedLettersList: document.getElementById("usedLettersList"),
  spinBtn: document.getElementById("spinBtn"),
  spinNote: document.getElementById("spinNote"),
  consonantInput: document.getElementById("consonantInput"),
  guessConsonantBtn: document.getElementById("guessConsonantBtn"),
  vowelInput: document.getElementById("vowelInput"),
  buyVowelBtn: document.getElementById("buyVowelBtn"),
  vowelCostLabel: document.getElementById("vowelCostLabel"),
  solveInput: document.getElementById("solveInput"),
  solveBtn: document.getElementById("solveBtn"),
  replayBtn: document.getElementById("replayBtn"),
  refreshSessionBtn: document.getElementById("refreshSessionBtn"),
  statusBar: document.getElementById("statusBar"),
  leaderboardList: document.getElementById("leaderboardList"),
  timelineList: document.getElementById("timelineList"),
  wheelCanvas: document.getElementById("wheelCanvas")
};

const wheelCtx = elements.wheelCanvas.getContext("2d");

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    }
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || "Request failed");
  }
  return payload;
}

function formatCoins(value) {
  const amount = Number(value || 0);
  return `${amount.toLocaleString()} coin`;
}

function setStatus(text, isError = false) {
  elements.statusBar.textContent = text;
  elements.statusBar.style.borderLeftColor = isError ? "#b91c1c" : "#f15c22";
}

function drawWheel(highlightIndex = null) {
  const segments = state.config?.wheelSegments || [];
  const n = segments.length;
  const { width, height } = elements.wheelCanvas;
  const radius = Math.min(width, height) / 2 - 10;

  wheelCtx.clearRect(0, 0, width, height);
  wheelCtx.save();
  wheelCtx.translate(width / 2, height / 2);
  wheelCtx.rotate(state.wheelAngle);

  for (let i = 0; i < n; i += 1) {
    const segment = segments[i];
    const label = String(segment.label || "");
    const start = (i * Math.PI * 2) / n;
    const end = ((i + 1) * Math.PI * 2) / n;

    wheelCtx.beginPath();
    wheelCtx.moveTo(0, 0);
    wheelCtx.arc(0, 0, radius, start, end);
    wheelCtx.closePath();
    wheelCtx.fillStyle = segment.color;
    wheelCtx.fill();

    if (highlightIndex === i) {
      wheelCtx.save();
      wheelCtx.globalAlpha = 0.28;
      wheelCtx.fillStyle = "#fff";
      wheelCtx.fill();
      wheelCtx.restore();
    }

    wheelCtx.save();
    wheelCtx.rotate(start + (end - start) / 2);
    wheelCtx.translate(radius * 0.66, 0);
    wheelCtx.rotate(Math.PI / 2);
    wheelCtx.fillStyle = "#fff";
    wheelCtx.textAlign = "center";
    wheelCtx.textBaseline = "middle";
    const arcLength = (end - start) * radius * 0.66;
    const perChar = label.length > 0 ? arcLength / label.length : 16;
    const fontSize = Math.max(11, Math.min(17, Math.floor(perChar * 1.55)));
    wheelCtx.font = `700 ${fontSize}px 'Nunito Sans'`;
    wheelCtx.fillText(label, 0, 0);
    wheelCtx.restore();
  }

  wheelCtx.beginPath();
  wheelCtx.arc(0, 0, radius * 0.14, 0, Math.PI * 2);
  wheelCtx.fillStyle = "#ffffff";
  wheelCtx.fill();
  wheelCtx.strokeStyle = "#f15c22";
  wheelCtx.lineWidth = 5;
  wheelCtx.stroke();

  wheelCtx.restore();
}

function targetAngleForIndex(index) {
  const n = state.config.wheelSegments.length;
  const slice = (Math.PI * 2) / n;
  const centerAngle = index * slice + slice / 2;
  return -Math.PI / 2 - centerAngle;
}

function normalizeAngle(value) {
  let angle = value % (Math.PI * 2);
  if (angle < 0) {
    angle += Math.PI * 2;
  }
  return angle;
}

async function animateSpinTo(index) {
  const startAngle = state.wheelAngle;
  const target = targetAngleForIndex(index);
  const currentNorm = normalizeAngle(startAngle);
  const targetNorm = normalizeAngle(target);

  let delta = targetNorm - currentNorm;
  if (delta < 0) {
    delta += Math.PI * 2;
  }

  const rotations = (4 + Math.random() * 2) * Math.PI * 2;
  const endAngle = startAngle + delta + rotations;
  const duration = 4300;
  const startTime = performance.now();

  state.isAnimating = true;

  await new Promise((resolve) => {
    function frame(timestamp) {
      const t = Math.min(1, (timestamp - startTime) / duration);
      const eased = 1 - Math.pow(1 - t, 4);
      state.wheelAngle = startAngle + (endAngle - startAngle) * eased;
      drawWheel(t === 1 ? index : null);

      if (t < 1) {
        requestAnimationFrame(frame);
      } else {
        state.wheelAngle = normalizeAngle(endAngle);
        state.isAnimating = false;
        resolve();
      }
    }

    requestAnimationFrame(frame);
  });
}

function renderPuzzle(maskedPhrase) {
  elements.puzzleBoard.innerHTML = "";
  maskedPhrase.split("").forEach((char) => {
    const tile = document.createElement("div");
    tile.className = "tile";

    if (char === " ") {
      tile.classList.add("blank");
      tile.textContent = "";
    } else {
      tile.textContent = char;
    }

    elements.puzzleBoard.appendChild(tile);
  });
}

function renderTimeline(actionLog = []) {
  elements.timelineList.innerHTML = "";
  const latest = [...actionLog].slice(-14).reverse();

  if (latest.length === 0) {
    elements.timelineList.innerHTML = "<li>No events yet.</li>";
    return;
  }

  latest.forEach((event) => {
    const li = document.createElement("li");
    const time = new Date(event.timestamp).toLocaleTimeString();
    li.innerHTML = `<strong>${event.type.replaceAll("_", " ")}</strong><br><span class="tiny">${time}</span>`;
    elements.timelineList.appendChild(li);
  });
}

function renderUsedLetters(letters = []) {
  elements.usedLettersList.innerHTML = "";
  if (letters.length === 0) {
    elements.usedLettersList.textContent = "None";
    return;
  }

  letters.forEach((letter) => {
    const span = document.createElement("span");
    span.className = "used-letter";
    span.textContent = letter;
    elements.usedLettersList.appendChild(span);
  });
}

function renderSession() {
  if (!state.session) {
    document.body.classList.add("pre-session");
    elements.setupCard.hidden = false;
    elements.gameCard.hidden = true;
    return;
  }

  document.body.classList.remove("pre-session");
  const s = state.session;
  const isActive = s.status === "active";

  elements.setupCard.hidden = true;
  elements.gameCard.hidden = false;

  elements.playerHeading.textContent = s.playerName;
  elements.sessionMeta.textContent = `Session ID: ${s.id} | Spins: ${s.spins} | Wrong Guesses: ${s.wrongGuesses}`;
  elements.scoreValue.textContent = formatCoins(s.score);
  elements.categoryChip.textContent = `Category: ${s.puzzle.category}`;
  elements.statusChip.textContent = s.status.toUpperCase();
  elements.statusChip.dataset.status = s.status;
  elements.revealedMeta.textContent = `${s.puzzle.revealedLetters}/${s.puzzle.totalLetters} letters revealed`;

  if (s.status === "won" && s.puzzle.phrase) {
    elements.revealedMeta.textContent += ` | Answer: ${s.puzzle.phrase}`;
  }

  renderPuzzle(s.puzzle.maskedPhrase);
  renderUsedLetters(s.usedLetters);
  renderTimeline(s.actionLog);

  const needsConsonant = s.pendingConsonantValue !== null;
  elements.spinBtn.disabled = !isActive || needsConsonant || state.isAnimating;
  elements.guessConsonantBtn.disabled = !isActive || !needsConsonant || state.isAnimating;
  elements.buyVowelBtn.disabled = !isActive || needsConsonant || s.score < state.config.vowelCost || state.isAnimating;
  elements.solveBtn.disabled = !isActive || state.isAnimating;
  elements.replayBtn.disabled = state.isAnimating;

  elements.spinNote.textContent = needsConsonant
    ? `Use a consonant for ${formatCoins(s.pendingConsonantValue)} per reveal.`
    : "Spin and guess a consonant.";

  if (!isActive && s.status === "won") {
    setStatus(`Round complete! Final score ${formatCoins(s.score)}.`);
  }
}

async function refreshLeaderboard() {
  try {
    const data = await api("/api/leaderboard?limit=10");
    elements.leaderboardList.innerHTML = "";

    if (!data.leaderboard.length) {
      elements.leaderboardList.innerHTML = "<li>No completed rounds yet.</li>";
      return;
    }

    data.leaderboard.forEach((row) => {
      const li = document.createElement("li");
      li.innerHTML = `<strong>${row.playerName}</strong> — ${formatCoins(row.score)} <span class="tiny">(${row.difficulty}, ${row.durationSeconds}s)</span>`;
      elements.leaderboardList.appendChild(li);
    });
  } catch (error) {
    elements.leaderboardList.innerHTML = `<li>${error.message}</li>`;
  }
}

async function loadSessionById(sessionId, silent = false) {
  const data = await api(`/api/session/${sessionId}`);
  state.session = data.session;
  localStorage.setItem(sessionStorageKey, state.session.id);
  elements.sessionIdInput.value = state.session.id;
  renderSession();
  if (!silent) {
    setStatus("Session loaded.");
  }
}

async function loadConfig() {
  const config = await api("/api/config");
  state.config = config;

  elements.vowelCostLabel.textContent = formatCoins(config.vowelCost);

  config.difficulties.forEach((difficulty) => {
    const option = document.createElement("option");
    option.value = difficulty;
    option.textContent = difficulty[0].toUpperCase() + difficulty.slice(1);
    elements.difficultySelect.appendChild(option);
  });

  drawWheel();
}

async function handleStartSession(event) {
  event.preventDefault();
  const playerName = elements.playerName.value.trim();
  if (!playerName) {
    setStatus("Player name is required.", true);
    elements.playerName.focus();
    return;
  }

  try {
    const payload = {
      playerName,
      difficulty: elements.difficultySelect.value
    };
    const data = await api("/api/session", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    state.session = data.session;
    localStorage.setItem(sessionStorageKey, state.session.id);
    elements.sessionIdInput.value = state.session.id;
    renderSession();
    setStatus(data.message);
    await refreshLeaderboard();
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function handleResume() {
  const id = elements.sessionIdInput.value.trim();
  if (!id) {
    setStatus("Enter a session ID to resume.", true);
    return;
  }

  try {
    await loadSessionById(id);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function handleSpin() {
  if (!state.session || state.isAnimating) {
    return;
  }

  try {
    elements.spinBtn.disabled = true;
    const data = await api(`/api/session/${state.session.id}/spin`, {
      method: "POST",
      body: JSON.stringify({})
    });

    await animateSpinTo(data.spin.segmentIndex);

    state.session = data.session;
    renderSession();
    setStatus(data.message);
  } catch (error) {
    renderSession();
    setStatus(error.message, true);
  }
}

function collectSingleLetter(inputEl) {
  return String(inputEl.value || "").trim().toUpperCase().slice(0, 1);
}

async function submitGuess(type, inputEl) {
  if (!state.session || state.isAnimating) {
    return;
  }

  const letter = collectSingleLetter(inputEl);
  if (!letter) {
    setStatus("Enter a letter first.", true);
    return;
  }

  try {
    const data = await api(`/api/session/${state.session.id}/guess`, {
      method: "POST",
      body: JSON.stringify({ type, letter })
    });

    inputEl.value = "";
    state.session = data.session;
    renderSession();
    setStatus(data.message);

    if (state.session.status === "won") {
      await refreshLeaderboard();
    }
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function handleSolve() {
  if (!state.session || state.isAnimating) {
    return;
  }

  const attempt = elements.solveInput.value.trim();
  if (!attempt) {
    setStatus("Type your puzzle solution.", true);
    return;
  }

  try {
    const data = await api(`/api/session/${state.session.id}/solve`, {
      method: "POST",
      body: JSON.stringify({ attempt })
    });

    elements.solveInput.value = "";
    state.session = data.session;
    renderSession();
    setStatus(data.message);

    if (state.session.status === "won") {
      await refreshLeaderboard();
    }
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function handleReplay() {
  if (!state.session || state.isAnimating) {
    return;
  }

  try {
    const data = await api(`/api/session/${state.session.id}/replay`, {
      method: "POST",
      body: JSON.stringify({ difficulty: elements.difficultySelect.value })
    });

    state.session = data.session;
    localStorage.setItem(sessionStorageKey, state.session.id);
    elements.sessionIdInput.value = state.session.id;
    renderSession();
    setStatus("New replay session created.");
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function handleRefreshSession() {
  if (!state.session) {
    return;
  }

  try {
    await loadSessionById(state.session.id, true);
    setStatus("Session state refreshed from backend.");
  } catch (error) {
    setStatus(error.message, true);
  }
}

function wireEvents() {
  elements.startForm.addEventListener("submit", handleStartSession);
  elements.resumeBtn.addEventListener("click", handleResume);
  elements.spinBtn.addEventListener("click", handleSpin);
  elements.guessConsonantBtn.addEventListener("click", () => submitGuess("consonant", elements.consonantInput));
  elements.buyVowelBtn.addEventListener("click", () => submitGuess("vowel", elements.vowelInput));
  elements.solveBtn.addEventListener("click", handleSolve);
  elements.replayBtn.addEventListener("click", handleReplay);
  elements.refreshSessionBtn.addEventListener("click", handleRefreshSession);

  [elements.consonantInput, elements.vowelInput].forEach((inputEl) => {
    inputEl.addEventListener("input", () => {
      inputEl.value = inputEl.value.replace(/[^a-z]/gi, "").slice(0, 1).toUpperCase();
    });
  });
}

async function init() {
  try {
    wireEvents();
    renderSession();
    await Promise.all([loadConfig(), refreshLeaderboard()]);

    const saved = localStorage.getItem(sessionStorageKey);
    if (saved) {
      elements.resumeHint.textContent = `Last session found: ${saved}`;
      elements.sessionIdInput.value = saved;
      try {
        await loadSessionById(saved, true);
        setStatus("Resumed last saved session.");
      } catch (error) {
        localStorage.removeItem(sessionStorageKey);
        elements.resumeHint.textContent = "Last session no longer exists.";
      }
    }
  } catch (error) {
    setStatus(`Initialization error: ${error.message}`, true);
  }
}

init();
