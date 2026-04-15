const PHASE = {
  INDEX: "phase-1",
  USER_SELECT: "phase-2",
  ACTION_SELECT: "phase-3",
};

const appState = {
  lockState: "LOCKED",
  users: [],
  selectedUser: "",
};

const phaseIds = Object.values(PHASE);

const stateBadge = document.getElementById("state-badge");
const notice = document.getElementById("notice");
const selectedUserLabel = document.getElementById("selected-user-label");
const userButtonsContainer = document.getElementById("user-buttons");

const btnUnlock = document.getElementById("btn-unlock");
const btnHomeIndex = document.getElementById("btn-home-index");
const btnBackToPhase1 = document.getElementById("btn-back-to-phase-1");
const btnActionHome = document.getElementById("btn-action-home");
const btnActionTempLock = document.getElementById("btn-action-temp-lock");
const btnChangeUser = document.getElementById("btn-change-user");

function setNotice(message, type = "info") {
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
    button.addEventListener("click", () => {
      appState.selectedUser = user;
      selectedUserLabel.textContent = `操作者: ${user}`;
      showPhase(PHASE.ACTION_SELECT);
      setNotice("操作を選択", "info");
    });
    userButtonsContainer.appendChild(button);
  }
}

async function refreshState() {
  const response = await fetch("/api/state");
  if (!response.ok) {
    throw new Error("状態取得に失敗しました");
  }

  const payload = await response.json();
  appState.lockState = payload.state;
  renderState();
}

async function bootstrap() {
  const response = await fetch("/api/bootstrap");
  if (!response.ok) {
    throw new Error("初期化に失敗しました");
  }

  const payload = await response.json();
  appState.lockState = payload.state;
  appState.users = payload.users;

  renderState();
  renderUsers();
  showPhase(PHASE.INDEX);
  setNotice("準備完了", "info");
}

async function submitAction(action) {
  if (!appState.selectedUser) {
    setNotice("先にユーザーを選択してください。", "warn");
    showPhase(PHASE.USER_SELECT);
    return;
  }

  const response = await fetch("/api/action", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      user: appState.selectedUser,
      action,
    }),
  });

  const payload = await response.json();

  if (!response.ok && response.status !== 202) {
    throw new Error(payload.error || "操作に失敗しました");
  }

  appState.lockState = payload.state;
  renderState();

  const statusLabel = payload.notificationStatus === "sent" ? "通知送信済み" : "通知失敗";
  const noticeType = payload.notificationStatus === "sent" ? "success" : "warn";
  setNotice(`[${payload.timestamp}] ${payload.user} - ${payload.actionLabel} (${statusLabel})`, noticeType);

  if (payload.nextPhase === PHASE.INDEX) {
    appState.selectedUser = "";
    selectedUserLabel.textContent = "操作者: 未選択";
    showPhase(PHASE.INDEX);
    return;
  }

  showPhase(PHASE.USER_SELECT);
}

btnUnlock.addEventListener("click", () => {
  showPhase(PHASE.USER_SELECT);
  setNotice("操作者を選択", "info");
});

btnHomeIndex.addEventListener("click", () => {
  showPhase(PHASE.USER_SELECT);
  setNotice("操作者を選択", "info");
});

btnBackToPhase1.addEventListener("click", () => {
  showPhase(PHASE.INDEX);
  setNotice("初期画面", "info");
});

btnActionHome.addEventListener("click", async () => {
  try {
    await submitAction("home");
  } catch (error) {
    setNotice(error.message, "error");
  }
});

btnActionTempLock.addEventListener("click", async () => {
  try {
    await submitAction("temp_lock");
  } catch (error) {
    setNotice(error.message, "error");
  }
});

btnChangeUser.addEventListener("click", () => {
  showPhase(PHASE.USER_SELECT);
  setNotice("操作者を選び直し", "info");
});

(async () => {
  try {
    await bootstrap();
    await refreshState();
  } catch (error) {
    setNotice(error.message, "error");
  }
})();
