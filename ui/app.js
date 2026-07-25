const navItems = [...document.querySelectorAll(".nav-item[data-page]")];
const pages = [...document.querySelectorAll(".page")];
const sidebar = document.getElementById("sidebar");
const toast = document.getElementById("toast");
const chatInput = document.getElementById("chatInput");
const chatStream = document.getElementById("chatStream");

const state = {
  dashboard: null,
  loading: false,
  modalMode: null,
  analysisPoll: null,
  managedMemoryStatus: "active",
  managedMemoriesLoaded: false,
  managedMemories: [],
  currentMemory: null,
};

const formModal = document.getElementById("formModal");
const modalForm = document.getElementById("modalForm");
const modalTextInput = document.getElementById("modalTextInput");
const modalGoalSelect = document.getElementById("modalGoalSelect");
const memoryModal = document.getElementById("memoryModal");
const memoryEditForm = document.getElementById("memoryEditForm");

function showToast(message, isError = false) {
  toast.textContent = message;
  toast.style.background = isError ? "#9f3f4c" : "#4b3de0";
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("show"), 2600);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  let data;
  try {
    data = await response.json();
  } catch {
    data = {
      error: response.status === 501
        ? "当前地址是旧的静态页面服务，请关闭后重新运行两个启动脚本"
        : `服务返回了无法识别的内容（${response.status}）`,
    };
  }
  if (!response.ok) throw new Error(data.error || `请求失败（${response.status}）`);
  return data;
}

function switchPage(name) {
  pages.forEach(page => page.classList.toggle("active", page.id === `page-${name}`));
  navItems.forEach(item => item.classList.toggle("active", item.dataset.page === name));
  sidebar.classList.remove("open");
  if (name === "chat") {
    scrollChatToBottom();
  } else {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  if (name === "memory") {
    loadMemoryManagement({ quiet: true });
  }
}

function scrollChatToBottom(behavior = "auto") {
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      if (!document.getElementById("page-chat").classList.contains("active")) return;
      window.scrollTo({
        top: document.documentElement.scrollHeight,
        behavior,
      });
    });
  });
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function formatTime(value) {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

function formatChineseDate(value) {
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  }).replace("星期", " · 星期");
}

function formatDateTime(value) {
  if (!value) return "未记录";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function renderTasks(tasks) {
  const list = document.getElementById("todayTaskList");
  list.replaceChildren();
  if (!tasks.length) {
    const empty = element("div", "api-empty", "本周还没有任务，点击下方添加一项。");
    list.appendChild(empty);
    return;
  }
  tasks.slice(0, 6).forEach((task, index) => {
    const label = element("label", `task-row${task.completed ? " done" : ""}`);
    const input = element("input");
    input.type = "checkbox";
    input.checked = Boolean(task.completed);
    input.dataset.taskId = task.id;
    const checkmark = element("span", "checkmark");
    const copy = element("span", "task-copy");
    const scopeLabel = task.scope === "day" ? "今天" : "本周";
    copy.append(
      element("strong", "", task.description),
      element("small", "", `${scopeLabel}任务 · ${task.completed ? "已完成" : "待完成"}`),
    );
    const dot = element("i", `task-api-dot tone-${index % 3}`);
    copy.querySelector("small").prepend(dot);
    const menu = element("button", "row-menu", "•••");
    menu.type = "button";
    menu.dataset.taskMenu = task.id;
    menu.dataset.completed = task.completed ? "1" : "0";
    menu.setAttribute("aria-label", "更多");
    label.append(input, checkmark, copy, menu);
    list.appendChild(label);
  });
}

function renderGoals(goals, tasks) {
  const weekly = document.getElementById("weeklyGoalList");
  weekly.replaceChildren();
  const scopeRows = [
    {
      title: "今天任务",
      tasks: tasks.filter(task => task.scope === "day"),
      color: "green",
    },
    {
      title: "本周任务",
      tasks: tasks.filter(task => task.scope !== "day"),
      color: "blue",
    },
  ];
  scopeRows.forEach(rowData => {
    const done = rowData.tasks.filter(task => task.completed).length;
    const row = element("div");
    const title = element("span", "", rowData.title);
    title.prepend(element("i", `tag-dot ${rowData.color}`));
    row.append(title, element("strong", "", `${done} / ${rowData.tasks.length}`));
    weekly.appendChild(row);
  });

  const grid = document.getElementById("goalsGrid");
  grid.replaceChildren();
  goals.forEach((goal, index) => {
    const card = element("article", "card goal-card");
    card.dataset.goalId = goal.id;
    const number = element("span", "goal-number", String(index + 1).padStart(2, "0"));
    const title = element("h2", "", goal.title);
    const copy = element("p", "", "长期方向 · 本地保存");
    const meta = element("div", "goal-meta");
    meta.append(element("span", "", "保持方向，任务在下方单独管理"));
    card.append(number, title, copy, meta);
    grid.appendChild(card);
  });
  const add = element("button", "card new-goal");
  add.type = "button";
  add.dataset.addGoal = "true";
  add.innerHTML = "<span>＋</span><strong>添加长期目标</strong><small>创建一个新的长期方向</small>";
  grid.appendChild(add);
}

function renderGoalTaskList(tasks) {
  const list = document.getElementById("goalTaskList");
  list.replaceChildren();
  const todayTasks = tasks.filter(task => task.scope === "day");
  const weekTasks = tasks.filter(task => task.scope !== "day");
  document.getElementById("todayChecklistCount").textContent = `今天 ${todayTasks.length} 项`;
  document.getElementById("weekChecklistCount").textContent = `本周 ${weekTasks.length} 项`;
  if (!tasks.length) {
    list.appendChild(element("div", "api-empty", "任务清单还是空的，点击“添加任务”创建第一项。"));
    return;
  }
  tasks.forEach(task => {
    const row = element("label", `goal-task-item${task.completed ? " done" : ""}`);
    const input = element("input");
    input.type = "checkbox";
    input.checked = Boolean(task.completed);
    input.dataset.checklistTaskId = task.id;
    const copy = element("span", "goal-task-copy");
    copy.append(
      element("strong", "", task.description),
      element("small", "", task.completed ? "已完成" : "待完成"),
    );
    const badge = element(
      "span",
      `scope-badge${task.scope === "day" ? " day" : ""}`,
      task.scope === "day" ? "今天" : "本周",
    );
    row.append(input, copy, badge);
    list.appendChild(row);
  });
}

function renderProgress(tasks) {
  const done = tasks.filter(task => task.completed).length;
  const percent = tasks.length ? Math.round(done / tasks.length * 100) : 0;
  const ring = document.querySelector(".progress-ring");
  ring.style.setProperty("--progress", percent);
  ring.querySelector("strong").textContent = `${percent}%`;
  ring.querySelector("small").textContent = `${done} / ${tasks.length} 已完成`;
  document.getElementById("quickTaskCount").textContent = `${tasks.length} 项本周任务 →`;
}

function memoryTypeLabel(type) {
  const labels = {
    profile: "档案",
    preference: "偏好",
    goal: "目标",
    project: "项目",
    skill: "技能",
    experience: "经历",
  };
  return labels[type] || type || "记忆";
}

function memoryStatusLabel(status) {
  const labels = {
    active: "使用中",
    archived: "已归档",
    expired: "已过期",
    deleted: "已删除",
  };
  return labels[status] || status || "未知";
}

function renderDailySummaries(summaries) {
  const list = document.getElementById("dailySummaryList");
  document.getElementById("dailySummaryCount").textContent = `${summaries.length} 天`;
  list.replaceChildren();
  if (!summaries.length) {
    list.appendChild(element(
      "div",
      "card api-empty large",
      "还没有每日摘要。前一天的聊天会在次日自动分析后显示在这里。",
    ));
    return;
  }
  summaries.forEach(summary => {
    const card = element("article", "card daily-summary-card");
    const header = element("header");
    header.append(
      element("strong", "", summary.analysis_date),
      element("span", "", summary.mood || "已分析"),
    );
    const footer = element("footer");
    footer.append(
      element("span", "", `${summary.message_count || 0} 条消息`),
      element("span", "", `可信度 ${Math.round(Number(summary.confidence || .5) * 100)}%`),
    );
    card.append(header, element("p", "", summary.summary || "无摘要"), footer);
    list.appendChild(card);
  });
}

function renderMemories(candidates, memories, pendingDates, analysisRunning) {
  const count = candidates.length;
  document.getElementById("navMemoryCount").textContent = count;
  document.getElementById("quickMemoryCount").textContent = `${count} 条候选待审核 →`;
  document.getElementById("reviewCount").textContent = `${count} 条待处理`;
  document.querySelector(".memory-card .badge").textContent = `${count} 条待审核`;

  const list = document.getElementById("memoryReviewList");
  list.replaceChildren();
  if (!count) {
    const empty = element("div", "card api-empty large");
    const message = analysisRunning
      ? "正在分析未处理的聊天，完成后会自动刷新候选记忆。"
      : pendingDates.length
        ? `发现 ${pendingDates.length} 天聊天尚未分析：${pendingDates.join("、")}`
        : "当前没有待审核候选。若日报已经生成但这里为空，表示模型没有发现值得长期保存的信息。";
    empty.appendChild(element("p", "", message));
    if (pendingDates.length || analysisRunning) {
      const analyzeButton = element(
        "button",
        "secondary-button memory-analyze-button",
        analysisRunning ? "正在分析…" : "立即分析未处理聊天",
      );
      analyzeButton.dataset.analyzeMemory = "true";
      analyzeButton.disabled = analysisRunning;
      empty.appendChild(analyzeButton);
    }
    list.appendChild(empty);
  } else {
    candidates.forEach(candidate => {
      const item = element("article", "card review-item");
      item.dataset.candidateId = candidate.id;
      const type = element("div", `review-type ${candidate.type || ""}`, memoryTypeLabel(candidate.type));
      const copy = element("div", "review-copy");
      copy.append(
        element("small", "", `候选记忆 #${candidate.id} · 可信度 ${Math.round((candidate.confidence || 0) * 100)}%`),
        element("h2", "", candidate.content),
      );
      const evidenceButton = element("button", "evidence-toggle", "查看来源信息 ⌄");
      const detail = element("div", "evidence-detail", `来源日期：${candidate.source_date || "未记录"}`);
      detail.appendChild(element("small", "", "正式保存前需要由你确认"));
      copy.append(evidenceButton, detail);
      const actions = element("div", "review-actions");
      const reject = element("button", "reject", "忽略");
      reject.dataset.action = "reject";
      const accept = element("button", "accept", "确认保存");
      accept.dataset.action = "accept";
      actions.append(reject, accept);
      item.append(type, copy, actions);
      list.appendChild(item);
    });
  }

  if (!state.managedMemoriesLoaded) {
    renderManagedMemories(memories);
  }
}

function renderManagedMemories(memories) {
  const list = document.getElementById("activeMemoryList");
  document.getElementById("activeMemoryCount").textContent = `${memories.length} 条`;
  list.replaceChildren();
  if (!memories.length) {
    list.appendChild(element(
      "div",
      "card api-empty large",
      state.managedMemoryStatus === "active"
        ? "还没有正式长期记忆。候选记忆经过你的确认后会保存在这里。"
        : "当前状态下没有长期记忆。",
    ));
    return;
  }
  memories.forEach(memory => {
    const item = element("article", "card active-memory-item");
    item.dataset.memoryId = memory.id;
    const header = element("header");
    header.append(
      element("span", "", memoryTypeLabel(memory.type)),
      element("small", "", `#${memory.id} · ${memoryStatusLabel(memory.status)}`),
    );
    const meta = element("div", "active-memory-meta");
    meta.append(
      element("span", "", `重要性 ${Math.round(Number(memory.importance || 0) * 100)}%`),
      element("span", "", `创建 ${formatDateTime(memory.created_at)}`),
      element("span", "", `来源 ${memory.source || "未记录"}`),
      element("span", "", `已使用 ${memory.use_count || 0} 次`),
    );
    const actions = element("div", "memory-card-actions");
    [
      ["view", "查看详情"],
      ["edit", "编辑"],
      ["delete", "删除"],
    ].forEach(([action, label]) => {
      const button = element("button", "", label);
      button.type = "button";
      button.dataset.memoryAction = action;
      button.dataset.memoryId = memory.id;
      actions.appendChild(button);
    });
    item.append(
      header,
      element("p", "", memory.content),
      meta,
      actions,
    );
    list.appendChild(item);
  });
}

async function loadMemoryManagement({ quiet = false } = {}) {
  const filter = document.getElementById("memoryStatusFilter");
  const status = filter?.value || state.managedMemoryStatus || "active";
  state.managedMemoryStatus = status;
  try {
    const data = await api(`/api/memory?status=${encodeURIComponent(status)}`);
    state.managedMemories = data.memories || [];
    state.managedMemoriesLoaded = true;
    renderManagedMemories(state.managedMemories);
  } catch (error) {
    if (!quiet) showToast(error.message, true);
  }
}

function memoryMetaItem(label, value) {
  const item = element("div");
  item.append(
    element("small", "", label),
    element("strong", "", String(value ?? "未记录")),
  );
  return item;
}

function renderMemoryDetail(memory) {
  state.currentMemory = memory;
  document.getElementById("memoryModalTitle").textContent = `记忆 #${memory.id}`;
  document.getElementById("memoryModalStatus").textContent = memoryStatusLabel(memory.status);
  const meta = document.getElementById("memoryDetailMeta");
  meta.replaceChildren(
    memoryMetaItem("类型", memoryTypeLabel(memory.type)),
    memoryMetaItem("重要性", `${Math.round(Number(memory.importance || 0) * 100)}%`),
    memoryMetaItem("可信度", `${Math.round(Number(memory.confidence || 0) * 100)}%`),
    memoryMetaItem("创建时间", formatDateTime(memory.created_at)),
    memoryMetaItem("更新时间", formatDateTime(memory.updated_at)),
    memoryMetaItem("来源", memory.source || "未记录"),
  );
  document.getElementById("memoryDetailContent").textContent = memory.content;

  const sources = document.getElementById("memorySourceList");
  sources.replaceChildren();
  if (!(memory.provenance || []).length) {
    sources.appendChild(element("p", "", memory.source || "未记录独立来源条目"));
  } else {
    memory.provenance.forEach(source => {
      const item = element("article", "memory-source-item");
      item.append(
        element("strong", "", `${source.source_type || "来源"} · ${source.source_id || "未编号"}`),
        element("p", "", source.created_reason || "未记录创建原因"),
        element("small", "", formatDateTime(source.created_at)),
      );
      sources.appendChild(item);
    });
  }

  const evidence = document.getElementById("memoryEvidenceList");
  evidence.replaceChildren();
  if (!(memory.evidence || []).length) {
    evidence.appendChild(element("p", "", "这条记忆没有关联可展示的 Evidence。"));
  } else {
    memory.evidence.forEach(source => {
      const item = element("article", "memory-evidence-item");
      item.append(
        element("strong", "", source.claim || source.evidence_type || "Evidence"),
        element("p", "", source.quote || "未保留原始引用"),
        element(
          "small",
          "",
          `消息 #${source.message_id || "?"} · ${formatDateTime(source.message_created_at)}`,
        ),
      );
      evidence.appendChild(item);
    });
  }

  const jsonView = document.getElementById("memoryJsonView");
  jsonView.textContent = JSON.stringify(memory, null, 2);
  jsonView.classList.remove("visible");
  document.getElementById("memoryJsonButton").textContent = "查看 JSON";
  document.getElementById("memoryDetailView").hidden = false;
  memoryEditForm.hidden = true;
}

async function openMemoryDetail(memoryId, edit = false) {
  try {
    const memory = await api(`/api/memory/${memoryId}`);
    renderMemoryDetail(memory);
    memoryModal.classList.add("open");
    memoryModal.setAttribute("aria-hidden", "false");
    if (edit) openMemoryEdit();
  } catch (error) {
    showToast(error.message, true);
  }
}

function closeMemoryModal() {
  memoryModal.classList.remove("open");
  memoryModal.setAttribute("aria-hidden", "true");
  state.currentMemory = null;
  memoryEditForm.hidden = true;
  document.getElementById("memoryDetailView").hidden = false;
}

function openMemoryEdit() {
  const memory = state.currentMemory;
  if (!memory) return;
  document.getElementById("memoryTypeInput").value = memory.type;
  document.getElementById("memoryStatusInput").value = memory.status;
  document.getElementById("memoryContentInput").value = memory.content;
  document.getElementById("memoryImportanceInput").value = Number(memory.importance || 0.5);
  document.getElementById("memoryDetailView").hidden = true;
  memoryEditForm.hidden = false;
  setTimeout(() => document.getElementById("memoryContentInput").focus(), 80);
}

function appendMessage(role, content, time = "刚刚") {
  const message = element("div", `message ${role === "user" ? "user" : "assistant"}`);
  const body = element("div");
  body.append(
    element("small", "", `${role === "user" ? "你" : "Personal AI"} · ${time}`),
    element("p", "", content),
  );
  if (role === "user") {
    message.appendChild(body);
  } else {
    message.append(element("div", "message-avatar", "AI"), body);
  }
  chatStream.appendChild(message);
  return message;
}

function renderMessages(messages) {
  chatStream.replaceChildren();
  if (!messages.length) {
    appendMessage("assistant", "你好，我已经连接到本地 Personal Agent。今天想从哪里开始？", "现在");
    scrollChatToBottom();
    return;
  }
  messages.forEach(message => appendMessage(
    message.role,
    message.content,
    formatTime(message.created_at),
  ));
  scrollChatToBottom();
}

function renderDashboard(data) {
  state.dashboard = data;
  document.querySelector(".date-nav span").textContent = formatChineseDate(data.date);
  renderTasks(data.tasks || []);
  renderGoals(data.goals || [], data.tasks || []);
  renderGoalTaskList(data.tasks || []);
  renderProgress(data.tasks || []);
  renderDailySummaries(data.daily_summaries || []);
  renderMemories(
    data.memory_candidates || [],
    data.memories || [],
    data.pending_analysis_dates || [],
    Boolean(data.analysis_running),
  );
  renderMessages(data.messages || []);
  const model = data.model || {};
  document.getElementById("modelSettingValue").textContent =
    `${model.provider || "ollama"} · ${model.configured_name || model.name || "gemma3:12b"}`;
  const reminderHour = data.settings?.reminder_hour;
  document.getElementById("reminderSettingValue").textContent =
    reminderHour === null || reminderHour === undefined
      ? "尚未设置每日提醒"
      : `每天 ${String(reminderHour).padStart(2, "0")}:00 提醒`;
  clearTimeout(state.analysisPoll);
  if (data.analysis_running) {
    state.analysisPoll = setTimeout(() => loadDashboard({ quiet: true }), 3000);
  }
}

async function loadDashboard({ quiet = false } = {}) {
  const status = document.getElementById("backendStatus");
  try {
    const data = await api("/api/dashboard");
    renderDashboard(data);
    if (
      document.getElementById("page-memory").classList.contains("active")
      && state.managedMemoriesLoaded
    ) {
      await loadMemoryManagement({ quiet: true });
    }
    status.classList.toggle("offline", !data.model);
    status.querySelector("span").textContent = data.model
      ? "本地服务 · 已连接"
      : "本地服务 · 版本过旧，请重启";
    if (!quiet) showToast("已连接 Personal Agent 本地数据");
  } catch (error) {
    status.classList.add("offline");
    status.querySelector("span").textContent = "本地服务 · 连接失败";
    if (!quiet) showToast(error.message, true);
  }
}

navItems.forEach(item => item.addEventListener("click", () => switchPage(item.dataset.page)));
document.querySelectorAll("[data-page-link]").forEach(item => item.addEventListener("click", () => switchPage(item.dataset.pageLink)));
document.querySelectorAll("[data-open-chat]").forEach(item => item.addEventListener("click", () => {
  switchPage("chat");
  setTimeout(() => chatInput.focus(), 250);
}));

document.getElementById("menuButton").addEventListener("click", () => sidebar.classList.toggle("open"));
document.addEventListener("click", event => {
  if (window.innerWidth <= 760 && sidebar.classList.contains("open") && !sidebar.contains(event.target) && !event.target.closest("#menuButton")) {
    sidebar.classList.remove("open");
  }
});

document.getElementById("todayTaskList").addEventListener("change", async event => {
  const input = event.target.closest("input[data-task-id]");
  if (!input) return;
  try {
    await api(`/api/tasks/${input.dataset.taskId}`, {
      method: "POST",
      body: JSON.stringify({ completed: input.checked }),
    });
    await loadDashboard({ quiet: true });
    showToast(input.checked ? "任务已完成" : "任务已重新打开");
  } catch (error) {
    input.checked = !input.checked;
    showToast(error.message, true);
  }
});

document.getElementById("todayTaskList").addEventListener("click", async event => {
  const menu = event.target.closest("[data-task-menu]");
  if (!menu) return;
  event.preventDefault();
  event.stopPropagation();
  const completed = menu.dataset.completed === "1";
  const actionText = completed ? "重新打开" : "标记完成";
  if (!window.confirm(`要将这项任务${actionText}吗？`)) return;
  try {
    await api(`/api/tasks/${menu.dataset.taskMenu}`, {
      method: "POST",
      body: JSON.stringify({ completed: !completed }),
    });
    await loadDashboard({ quiet: true });
    showToast(`任务已${actionText}`);
  } catch (error) {
    showToast(error.message, true);
  }
});

function openFormModal(mode, selectedGoalId = null) {
  const goals = state.dashboard?.goals || [];
  state.modalMode = mode;
  const isGoal = mode === "goal";
  const isTask = mode === "task";
  const content = {
    goal: ["NEW DIRECTION", "添加长期目标", "写下你希望长期推进的方向，之后可以在这个目标下安排每周任务。", "目标名称", "例如：系统学习产品设计"],
    task: ["NEW TASK", "添加本周任务", "选择所属目标，并写下本周可以明确完成的一项行动。", "任务内容", "例如：完成第一版交互流程"],
    reminder: ["DAILY RHYTHM", "修改提醒时间", "设置每天希望收到复盘提醒的小时，修改后立即生效。", "提醒小时（0-23）", "20"],
    model: ["LOCAL MODEL", "配置模型", "填写 Ollama 中已经安装的模型名称。新模型将在重启服务后生效。", "模型名称", "例如：gemma3:12b"],
    backup: ["DATA SAFETY", "数据库备份", "创建当前 SQLite 数据库的完整安全备份。", "", ""],
  }[mode];
  document.getElementById("modalEyebrow").textContent = content[0];
  document.getElementById("modalTitle").textContent = content[1];
  document.getElementById("modalDescription").textContent = content[2];
  document.getElementById("modalInputLabel").textContent = content[3];
  modalTextInput.placeholder = content[4];
  document.getElementById("goalSelectField").style.display = isTask ? "block" : "none";
  modalTextInput.closest(".modal-field").style.display = mode === "backup" ? "none" : "block";
  modalTextInput.type = mode === "reminder" ? "number" : "text";
  modalTextInput.min = mode === "reminder" ? "0" : "";
  modalTextInput.max = mode === "reminder" ? "23" : "";
  document.getElementById("modalSubmit").textContent = mode === "backup" ? "立即创建备份" : "保存";
  modalGoalSelect.replaceChildren();
  if (isTask) {
    const todayOption = element("option", "", "今天");
    todayOption.value = "day";
    const weekOption = element("option", "", "本周");
    weekOption.value = "week";
    modalGoalSelect.append(todayOption, weekOption);
  }
  modalTextInput.value = mode === "reminder"
    ? String(state.dashboard?.settings?.reminder_hour ?? 20)
    : mode === "model"
      ? String(state.dashboard?.model?.configured_name || state.dashboard?.model?.name || "")
      : "";
  formModal.classList.add("open");
  formModal.setAttribute("aria-hidden", "false");
  setTimeout(() => modalTextInput.focus(), 100);
}

function closeFormModal() {
  formModal.classList.remove("open");
  formModal.setAttribute("aria-hidden", "true");
  state.modalMode = null;
}

document.getElementById("addTaskButton").addEventListener("click", () => openFormModal("task"));

document.getElementById("goalsGrid").addEventListener("click", event => {
  if (event.target.closest("[data-add-goal]")) openFormModal("goal");
});

modalForm.addEventListener("submit", async event => {
  event.preventDefault();
  const value = modalTextInput.value.trim();
  if (state.modalMode !== "backup" && !value) {
    modalTextInput.focus();
    showToast("请填写内容", true);
    return;
  }
  const submit = document.getElementById("modalSubmit");
  submit.disabled = true;
  submit.textContent = "正在保存…";
  try {
    let path;
    let payload;
    if (state.modalMode === "goal") {
      path = "/api/goals";
      payload = { title: value };
    } else if (state.modalMode === "task") {
      path = "/api/tasks";
      payload = { scope: modalGoalSelect.value, description: value };
    } else if (state.modalMode === "reminder") {
      path = "/api/settings/reminder";
      payload = { hour: Number(value) };
    } else if (state.modalMode === "model") {
      path = "/api/settings/model";
      payload = { model_name: value };
    } else {
      path = "/api/backups";
      payload = {};
    }
    const result = await api(path, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (state.modalMode !== "backup") await loadDashboard({ quiet: true });
    const completedMode = state.modalMode;
    closeFormModal();
    const messages = {
      goal: "长期目标已创建",
      task: "任务已添加",
      reminder: "提醒时间已更新",
      model: result.restart_required ? "模型已保存，重启后生效" : "模型已更新",
      backup: `备份已创建：${result.name}`,
    };
    showToast(messages[completedMode]);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    submit.disabled = false;
    submit.textContent = "保存";
  }
});

document.getElementById("manageTasksButton").addEventListener("click", () => switchPage("goals"));
document.getElementById("addTaskShortcut").addEventListener("click", () => openFormModal("task"));
document.getElementById("addChecklistTask").addEventListener("click", () => openFormModal("task"));
document.getElementById("goalTaskList").addEventListener("change", async event => {
  const input = event.target.closest("[data-checklist-task-id]");
  if (!input) return;
  try {
    await api(`/api/tasks/${input.dataset.checklistTaskId}`, {
      method: "POST",
      body: JSON.stringify({ completed: input.checked }),
    });
    await loadDashboard({ quiet: true });
    showToast(input.checked ? "任务已完成" : "任务已重新打开");
  } catch (error) {
    input.checked = !input.checked;
    showToast(error.message, true);
  }
});
document.getElementById("configureModelButton").addEventListener("click", () => openFormModal("model"));
document.getElementById("configureReminderButton").addEventListener("click", () => openFormModal("reminder"));
document.getElementById("manageBackupsButton").addEventListener("click", async () => {
  try {
    const data = await api("/api/backups");
    openFormModal("backup");
    const recent = data.backups.slice(0, 5);
    document.getElementById("modalDescription").textContent = recent.length
      ? `现有 ${data.backups.length} 份备份，最近：${recent.map(item => item.name).join("、")}`
      : "当前还没有数据库备份。点击下方按钮立即创建第一份备份。";
  } catch (error) {
    showToast(error.message, true);
  }
});
document.getElementById("modalClose").addEventListener("click", closeFormModal);
document.getElementById("modalCancel").addEventListener("click", closeFormModal);
formModal.addEventListener("click", event => {
  if (event.target === formModal) closeFormModal();
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && formModal.classList.contains("open")) closeFormModal();
});

function renderReportLines(report) {
  const parts = [
    `总结\n${report.summary || "无"}`,
    `进展\n${(report.progress || []).map(item => `• ${item}`).join("\n") || "• 无"}`,
    `模式\n${(report.patterns || []).map(item => `• ${item}`).join("\n") || "• 无"}`,
    `状态\n${report.mood || "无"}`,
    `下一步\n${(report.next_actions || []).map(item => `• ${item}`).join("\n") || "• 无"}`,
    `可信度\n${Math.round(Number(report.confidence || .5) * 100)}%`,
  ];
  return parts.join("\n\n");
}

document.getElementById("openDailyReport").addEventListener("click", async () => {
  const button = document.getElementById("openDailyReport");
  button.disabled = true;
  button.textContent = "正在读取…";
  try {
    const report = await api("/api/daily");
    switchPage("insights");
    document.getElementById("insightHeading").textContent = "完整日报";
    document.getElementById("insightSummary").textContent = `${report.analysis_date} · 所有结论来自本地记录`;
    document.getElementById("insightFeatureTitle").textContent = report.summary || "当日回顾";
    document.getElementById("insightFeatureCopy").textContent = `共保留 ${report.evidence?.length || 0} 条证据`;
    document.querySelector(".week-bars").style.display = "none";
    const output = document.getElementById("weeklyReportOutput");
    output.textContent = renderReportLines(report);
    output.classList.add("visible");
    document.getElementById("generateWeeklyButton").textContent = "生成本周回顾";
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
    button.innerHTML = "查看完整日报 <span>→</span>";
  }
});

document.getElementById("generateWeeklyButton").addEventListener("click", async event => {
  const button = event.currentTarget;
  button.disabled = true;
  button.textContent = "本地模型正在生成…";
  const output = document.getElementById("weeklyReportOutput");
  try {
    const result = await api("/api/weekly", {
      method: "POST",
      body: "{}",
    });
    document.getElementById("insightHeading").textContent = "本周回顾";
    document.getElementById("insightSummary").textContent = `周起始日期：${result.week_start}`;
    document.getElementById("insightFeatureTitle").textContent = "基于真实记录生成";
    document.getElementById("insightFeatureCopy").textContent = "已综合本周任务与每日分析";
    document.querySelector(".week-bars").style.display = "none";
    output.textContent = result.report;
    output.classList.add("visible");
    showToast("本周回顾已生成");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "重新生成";
  }
});

document.getElementById("memoryReviewList").addEventListener("click", async event => {
  const analyze = event.target.closest("[data-analyze-memory]");
  if (analyze) {
    analyze.disabled = true;
    analyze.textContent = "正在分析，请稍候…";
    try {
      const result = await api("/api/memory/analyze", {
        method: "POST",
        body: "{}",
      });
      await loadDashboard({ quiet: true });
      if (result.running) {
        showToast("分析任务已在后台运行");
      } else if (result.processed_dates.length) {
        showToast(`已完成 ${result.processed_dates.length} 天的聊天分析`);
      } else {
        showToast("没有需要补做的聊天分析");
      }
    } catch (error) {
      analyze.disabled = false;
      analyze.textContent = "立即分析未处理聊天";
      showToast(error.message, true);
    }
    return;
  }
  const evidence = event.target.closest(".evidence-toggle");
  if (evidence) {
    evidence.nextElementSibling.classList.toggle("open");
    return;
  }
  const action = event.target.closest("[data-action]");
  if (!action) return;
  const item = action.closest(".review-item");
  action.disabled = true;
  try {
    await api(`/api/memories/${item.dataset.candidateId}/${action.dataset.action}`, {
      method: "POST",
      body: "{}",
    });
    await loadDashboard({ quiet: true });
    showToast(action.dataset.action === "accept" ? "记忆已确认并保存" : "候选记忆已忽略");
  } catch (error) {
    action.disabled = false;
    showToast(error.message, true);
  }
});

async function deleteMemory(memoryId) {
  if (!window.confirm("确认删除这条长期记忆吗？系统只会把状态改为“已删除”，来源和 Evidence 会继续保留。")) {
    return;
  }
  try {
    await api(`/api/memory/${memoryId}`, { method: "DELETE" });
    closeMemoryModal();
    await loadDashboard({ quiet: true });
    await loadMemoryManagement({ quiet: true });
    showToast("记忆已标记为删除");
  } catch (error) {
    showToast(error.message, true);
  }
}

document.getElementById("memoryStatusFilter").addEventListener("change", async event => {
  state.managedMemoryStatus = event.target.value;
  await loadMemoryManagement();
});

document.getElementById("activeMemoryList").addEventListener("click", async event => {
  const action = event.target.closest("[data-memory-action]");
  if (!action) return;
  const memoryId = Number(action.dataset.memoryId);
  if (action.dataset.memoryAction === "delete") {
    await deleteMemory(memoryId);
    return;
  }
  await openMemoryDetail(memoryId, action.dataset.memoryAction === "edit");
});

document.getElementById("memoryModalClose").addEventListener("click", closeMemoryModal);
document.getElementById("memoryDoneButton").addEventListener("click", closeMemoryModal);
document.getElementById("memoryEditButton").addEventListener("click", openMemoryEdit);
document.getElementById("memoryEditCancel").addEventListener("click", () => {
  memoryEditForm.hidden = true;
  document.getElementById("memoryDetailView").hidden = false;
});
document.getElementById("memoryJsonButton").addEventListener("click", event => {
  const view = document.getElementById("memoryJsonView");
  const visible = view.classList.toggle("visible");
  event.currentTarget.textContent = visible ? "收起 JSON" : "查看 JSON";
});
document.getElementById("memoryDeleteButton").addEventListener("click", async () => {
  if (state.currentMemory) await deleteMemory(state.currentMemory.id);
});
memoryModal.addEventListener("click", event => {
  if (event.target === memoryModal) closeMemoryModal();
});

memoryEditForm.addEventListener("submit", async event => {
  event.preventDefault();
  if (!state.currentMemory) return;
  const save = document.getElementById("memorySaveButton");
  const content = document.getElementById("memoryContentInput").value.trim();
  if (!content) {
    showToast("记忆内容不能为空", true);
    return;
  }
  save.disabled = true;
  save.textContent = "正在保存…";
  try {
    const updated = await api(`/api/memory/${state.currentMemory.id}`, {
      method: "PUT",
      body: JSON.stringify({
        type: document.getElementById("memoryTypeInput").value,
        content,
        importance: Number(document.getElementById("memoryImportanceInput").value),
        status: document.getElementById("memoryStatusInput").value,
      }),
    });
    renderMemoryDetail(updated);
    await loadDashboard({ quiet: true });
    await loadMemoryManagement({ quiet: true });
    showToast("长期记忆已更新");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    save.disabled = false;
    save.textContent = "保存修改";
  }
});

document.addEventListener("keydown", event => {
  if (event.key === "Escape" && memoryModal.classList.contains("open")) {
    closeMemoryModal();
  }
});

chatInput.addEventListener("input", () => {
  chatInput.style.height = "auto";
  chatInput.style.height = `${Math.min(chatInput.scrollHeight, 130)}px`;
});

chatInput.addEventListener("keydown", event => {
  if (
    event.key === "Enter"
    && !event.shiftKey
    && !event.isComposing
    && event.keyCode !== 229
  ) {
    event.preventDefault();
    document.getElementById("chatForm").requestSubmit();
  }
});

document.getElementById("chatForm").addEventListener("submit", async event => {
  event.preventDefault();
  const value = chatInput.value.trim();
  if (!value || state.loading) return;
  state.loading = true;
  const submit = event.currentTarget.querySelector("button[type=submit]");
  submit.disabled = true;
  appendMessage("user", value);
  chatInput.value = "";
  chatInput.style.height = "auto";
  const pending = appendMessage("assistant", "正在通过本地模型思考…", "处理中");
  pending.classList.add("pending-message");
  pending.scrollIntoView({ behavior: "smooth", block: "center" });
  try {
    const result = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message: value }),
    });
    pending.remove();
    appendMessage("assistant", result.reply);
    await loadDashboard({ quiet: true });
    scrollChatToBottom();
    showToast("回复已保存到本地");
  } catch (error) {
    pending.querySelector("p").textContent = error.message;
    pending.classList.add("error-message");
    showToast(error.message, true);
  } finally {
    state.loading = false;
    submit.disabled = false;
  }
});

loadDashboard();
