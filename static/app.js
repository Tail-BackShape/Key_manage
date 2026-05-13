const PHASE = {
  INDEX: "phase-1",
  USER_SELECT: "phase-2",
  ACTION_SELECT: "phase-3",
};

const appState = {
  lockState: "LOCKED",
  users: [],
  selectedUser: "",
  pendingEntryAction: null,
  currentPhase: PHASE.INDEX,
  version: -1,
};

const phaseIds = Object.values(PHASE);

const stateBadge = document.getElementById("state-badge");
const notice = document.getElementById("notice");
const selectedUserLabel = document.getElementById("selected-user-label");
const phase2Instruction = document.getElementById("phase-2-instruction");
const userButtonsContainer = document.getElementById("user-buttons");

const btnUnlock = document.getElementById("btn-unlock");
const btnHomeIndex = document.getElementById("btn-home-index");
const btnBackToPhase1 = document.getElementById("btn-back-to-phase-1");
const btnActionHome = document.getElementById("btn-action-home");
const btnActionTempLock = document.getElementById("btn-action-temp-lock");
let eventSource = null;

function setNotice(message, type = "info") {
  if (!notice) {
    return;
  }

  notice.textContent = message;
  notice.className = `notice notice-${type}`;
}

function showPhase(phaseId) {
  for (const id of phaseIds) {
    const element = document.getElementById(id);
    element.classList.toggle("hidden", id !== phaseId);
  }
}

function renderState() {
  const stateLabel = appState.lockState === "TEMP_LOCKED" ? "一時施錠" : "通常";
  stateBadge.textContent = `状態: ${stateLabel}`;

  btnHomeIndex.style.display = appState.lockState === "TEMP_LOCKED" ? "inline-flex" : "none";
}

function renderSelectedUser() {
  const label = appState.selectedUser ? appState.selectedUser : "未選択";
  selectedUserLabel.textContent = `操作者: ${label}`;
}

function renderPhase2Instruction() {
  if (!phase2Instruction) {
    return;
  }

  if (appState.pendingEntryAction === "temp_lock") {
    phase2Instruction.textContent = "一時施錠する人を選択してください";
    return;
  }

  if (appState.pendingEntryAction === "home") {
    phase2Instruction.textContent = "施錠・帰宅する人を選択してください";
    return;
  }

  phase2Instruction.textContent = "操作者を選択してください";
}

function applyFlowPayload(payload) {
  if (payload.state) {
    appState.lockState = payload.state;
  }

  if (payload.currentPhase) {
    appState.currentPhase = payload.currentPhase;
  }

  if (typeof payload.selectedUser === "string") {
    appState.selectedUser = payload.selectedUser;
  }

  if (Object.prototype.hasOwnProperty.call(payload, "pendingEntryAction")) {
    appState.pendingEntryAction = payload.pendingEntryAction;
  }

  if (typeof payload.version === "number") {
    appState.version = payload.version;
  }

  renderState();
  renderSelectedUser();
  renderPhase2Instruction();
  showPhase(appState.currentPhase);
}

function initializeSse() {
  if (!window.EventSource) {
    return;
  }

  if (eventSource) {
    eventSource.close();
  }

  eventSource = new EventSource("/api/events");

  eventSource.addEventListener("state", (event) => {
    try {
      const payload = JSON.parse(event.data);
      const incomingVersion = typeof payload.version === "number" ? payload.version : null;
      if (incomingVersion !== null && incomingVersion <= appState.version) {
        return;
      }
      applyFlowPayload(payload);
    } catch (error) {
      console.error("SSE payload parse error", error);
    }
  });

  eventSource.onerror = () => {
    console.warn("SSE connection issue; browser will retry automatically");
  };
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  const payload = await response.json();
  if (!response.ok && response.status !== 202) {
    throw new Error(payload.error || "通信に失敗しました");
  }

  return payload;
}

function renderUsers() {
  userButtonsContainer.innerHTML = "";

  if (appState.users.length === 0) {
    const fallback = document.createElement("p");
    fallback.textContent = "ユーザーが設定されていません。.env の USERS を確認してください。";
    userButtonsContainer.appendChild(fallback);
    return;
  }

  for (const user of appState.users) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-secondary";
    button.textContent = user;
    button.addEventListener("click", async () => {
      try {
        const payload = await postJson("/api/flow/select-user", { user });
        applyFlowPayload(payload);

        if (payload.entryActionLog) {
          const log = payload.entryActionLog;
          const statusLabel = log.notificationStatus === "sent" ? "通知送信済み" : "通知失敗";
          const noticeType = log.notificationStatus === "sent" ? "success" : "warn";
          setNotice(`[${log.timestamp}] ${log.user} - ${log.actionLabel} (${statusLabel})`, noticeType);
        } else {
          setNotice("操作を選択", "info");
        }
      } catch (error) {
        setNotice(error.message, "error");
      }
    });
    userButtonsContainer.appendChild(button);
  }
}

async function bootstrap() {
  const response = await fetch("/api/bootstrap");
  if (!response.ok) {
    throw new Error("初期化に失敗しました");
  }

  const payload = await response.json();
  appState.users = payload.users;
  renderUsers();
  applyFlowPayload(payload);
  setNotice("準備完了", "info");
}

async function submitAction(action) {
  const user = appState.selectedUser;
  if (!user) {
    setNotice("先にユーザーを選択してください。", "warn");
    showPhase(PHASE.USER_SELECT);
    return;
  }

  const payload = await postJson("/api/action", {
    user,
    action,
  });
  applyFlowPayload(payload);

  const statusLabel = payload.notificationStatus === "sent" ? "通知送信済み" : "通知失敗";
  const noticeType = payload.notificationStatus === "sent" ? "success" : "warn";
  setNotice(`[${payload.timestamp}] ${payload.user} - ${payload.actionLabel} (${statusLabel})`, noticeType);
}

btnUnlock.addEventListener("click", async () => {
  try {
    const payload = await postJson("/api/flow/start", { entryAction: "unlock" });
    applyFlowPayload(payload);
    setNotice("操作者を選択", "info");
  } catch (error) {
    setNotice(error.message, "error");
  }
});

btnHomeIndex.addEventListener("click", async () => {
  try {
    const payload = await postJson("/api/flow/start", { entryAction: "home" });
    applyFlowPayload(payload);
    setNotice("操作者を選択", "info");
  } catch (error) {
    setNotice(error.message, "error");
  }
});

btnBackToPhase1.addEventListener("click", async () => {
  try {
    const payload = await postJson("/api/flow/back", {});
    applyFlowPayload(payload);
    const message = payload.currentPhase === PHASE.ACTION_SELECT ? "操作を選択" : "初期画面";
    setNotice(message, "info");
  } catch (error) {
    setNotice(error.message, "error");
  }
});

btnActionHome.addEventListener("click", async () => {
  try {
    const payload = await postJson("/api/flow/start", { entryAction: "home" });
    applyFlowPayload(payload);
    setNotice("施錠・帰宅する人を選択してください", "info");
  } catch (error) {
    setNotice(error.message, "error");
  }
});

btnActionTempLock.addEventListener("click", async () => {
  try {
    const payload = await postJson("/api/flow/start", { entryAction: "temp_lock" });
    applyFlowPayload(payload);
    setNotice("一時施錠する人を選択してください", "info");
  } catch (error) {
    setNotice(error.message, "error");
  }
});

(async () => {
  try {
    await bootstrap();
    initializeSse();
  } catch (error) {
    if (notice) {
      setNotice(error.message, "error");
      return;
    }
    console.error(error);
  }
})();
