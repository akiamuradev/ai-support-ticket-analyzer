const form = document.querySelector("#ticket-form");
const textarea = document.querySelector("#ticket-text");
const analyzeButton = document.querySelector("#analyze-button");
const charCount = document.querySelector("#char-count");
const formMessage = document.querySelector("#form-message");
const resultEmpty = document.querySelector("#result-empty");
const resultCard = document.querySelector("#result-card");
const resultCategory = document.querySelector("#result-category");
const resultPriority = document.querySelector("#result-priority");
const resultSummary = document.querySelector("#result-summary");
const resultReply = document.querySelector("#result-reply");
const copyReplyButton = document.querySelector("#copy-reply-button");
const refreshHistoryButton = document.querySelector("#refresh-history-button");
const historyMessage = document.querySelector("#history-message");
const historyList = document.querySelector("#history-list");

const maxTicketLength = 5000;
const minTicketLength = 5;
let isSubmitting = false;
let currentSuggestedReply = "";

const priorityClasses = {
  Низкий: "priority-low",
  Средний: "priority-medium",
  Высокий: "priority-high",
  Критический: "priority-critical",
};

form?.addEventListener("submit", (event) => {
  event.preventDefault();
  void analyzeTicket();
});

textarea?.addEventListener("input", () => {
  updateCharCount();
  if (formMessage?.classList.contains("is-error")) {
    showFormMessage("", false);
  }
});

copyReplyButton?.addEventListener("click", () => {
  void copySuggestedReply();
});

refreshHistoryButton?.addEventListener("click", () => {
  void loadHistory();
});

historyList?.addEventListener("toggle", (event) => {
  const target = event.target;
  if (target instanceof HTMLDetailsElement && target.open) {
    void loadTicketDetails(target);
  }
}, true);

historyList?.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) {
    return;
  }

  const deleteButton = target.closest("[data-delete-ticket]");
  if (deleteButton instanceof HTMLButtonElement) {
    void deleteTicket(deleteButton);
  }

  const copyButton = target.closest("[data-copy-reply]");
  if (copyButton instanceof HTMLButtonElement) {
    void copyText(copyButton.dataset.copyReply ?? "");
  }
});

document.addEventListener("DOMContentLoaded", () => {
  updateCharCount();
  void loadHistory();
});

async function analyzeTicket() {
  if (isSubmitting) {
    return;
  }

  const ticketText = textarea?.value.trim() ?? "";
  const validationError = validateTicketText(ticketText);
  if (validationError) {
    showFormMessage(validationError, true);
    textarea?.focus();
    return;
  }

  setSubmitting(true);
  showFormMessage("Анализируем обращение...", false);

  try {
    const response = await fetch("/api/tickets/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: ticketText }),
    });
    const payload = await readJson(response);

    if (!response.ok) {
      throw new Error(getErrorMessage(response.status, payload));
    }

    renderResult(payload);
    textarea.value = "";
    updateCharCount();
    showFormMessage("Анализ готов.", false);
    await loadHistory();
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Не удалось выполнить анализ.";
    showFormMessage(message, true);
  } finally {
    setSubmitting(false);
  }
}

async function loadHistory() {
  if (!historyList || !historyMessage) {
    return;
  }

  historyMessage.textContent = "Загружаем историю...";
  refreshHistoryButton?.setAttribute("aria-busy", "true");

  try {
    const response = await fetch("/api/tickets?limit=20");
    const payload = await readJson(response);
    if (!response.ok) {
      throw new Error(getErrorMessage(response.status, payload));
    }

    renderHistory(payload);
    historyMessage.textContent = "";
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Не удалось загрузить историю.";
    historyMessage.textContent = message;
    historyList.innerHTML = "";
  } finally {
    refreshHistoryButton?.removeAttribute("aria-busy");
  }
}

async function loadTicketDetails(details) {
  if (details.dataset.loaded === "true") {
    return;
  }

  const ticketId = details.dataset.ticketId;
  const body = details.querySelector("[data-ticket-body]");
  if (!ticketId || !body) {
    return;
  }

  body.innerHTML = '<p class="muted-text">Загружаем обращение...</p>';

  try {
    const response = await fetch(`/api/tickets/${ticketId}`);
    const payload = await readJson(response);
    if (!response.ok) {
      throw new Error(getErrorMessage(response.status, payload));
    }

    body.replaceChildren(createTicketDetailsBody(payload));
    details.dataset.loaded = "true";
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Не удалось открыть обращение.";
    body.innerHTML = `<p class="error-text">${escapeHtml(message)}</p>`;
  }
}

async function deleteTicket(button) {
  const ticketId = button.dataset.deleteTicket;
  if (!ticketId) {
    return;
  }

  const confirmed = window.confirm("Удалить это обращение из истории?");
  if (!confirmed) {
    return;
  }

  button.disabled = true;
  button.textContent = "Удаляем...";

  try {
    const response = await fetch(`/api/tickets/${ticketId}`, { method: "DELETE" });
    if (!response.ok) {
      const payload = await readJson(response);
      throw new Error(getErrorMessage(response.status, payload));
    }
    await loadHistory();
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Не удалось удалить запись.";
    showHistoryMessage(message);
    button.disabled = false;
    button.textContent = "Удалить";
  }
}

function renderResult(item) {
  if (
    !resultEmpty ||
    !resultCard ||
    !resultCategory ||
    !resultPriority ||
    !resultSummary ||
    !resultReply
  ) {
    return;
  }

  currentSuggestedReply = item.suggested_reply ?? "";
  resultCategory.textContent = item.category;
  resultPriority.textContent = item.priority;
  resultPriority.className = `priority-badge ${priorityClasses[item.priority] ?? ""}`;
  resultSummary.textContent = item.summary;
  resultReply.textContent = currentSuggestedReply;
  resultEmpty.hidden = true;
  resultCard.hidden = false;
  if (copyReplyButton) {
    copyReplyButton.hidden = !currentSuggestedReply;
  }
}

function renderHistory(items) {
  if (!historyList) {
    return;
  }

  if (!Array.isArray(items) || items.length === 0) {
    historyList.innerHTML = '<p class="empty-state">История пока пуста.</p>';
    return;
  }

  historyList.replaceChildren(...items.map(createHistoryItem));
}

function createHistoryItem(item) {
  const wrapper = document.createElement("article");
  wrapper.className = "history-item";

  const details = document.createElement("details");
  details.dataset.ticketId = String(item.id);

  const summary = document.createElement("summary");
  summary.className = "history-summary";

  const title = document.createElement("span");
  title.className = "history-title";
  title.textContent = item.category;

  const priority = document.createElement("span");
  priority.className = `priority-badge ${priorityClasses[item.priority] ?? ""}`;
  priority.textContent = item.priority;

  const date = document.createElement("time");
  date.dateTime = item.created_at;
  date.textContent = formatDate(item.created_at);

  const brief = document.createElement("span");
  brief.className = "history-brief";
  brief.textContent = item.summary;

  summary.append(title, priority, date, brief);

  const body = document.createElement("div");
  body.className = "history-body";
  body.dataset.ticketBody = "";

  details.append(summary, body);
  wrapper.append(details);
  return wrapper;
}

function createTicketDetailsBody(item) {
  const fragment = document.createDocumentFragment();

  const originalBlock = createDetailBlock("Исходное обращение", item.original_text);
  const replyBlock = createDetailBlock("Рекомендуемый ответ", item.suggested_reply);

  const actions = document.createElement("div");
  actions.className = "history-actions";

  const copyButton = document.createElement("button");
  copyButton.type = "button";
  copyButton.className = "secondary-button";
  copyButton.dataset.copyReply = item.suggested_reply;
  copyButton.textContent = "Копировать ответ";

  const deleteButton = document.createElement("button");
  deleteButton.type = "button";
  deleteButton.className = "danger-button";
  deleteButton.dataset.deleteTicket = String(item.id);
  deleteButton.textContent = "Удалить";

  actions.append(copyButton, deleteButton);
  fragment.append(originalBlock, replyBlock, actions);
  return fragment;
}

function createDetailBlock(label, value) {
  const block = document.createElement("section");
  block.className = "detail-block";

  const heading = document.createElement("h3");
  heading.textContent = label;

  const text = document.createElement("p");
  text.textContent = value || "Нет данных.";

  block.append(heading, text);
  return block;
}

async function copySuggestedReply() {
  if (!currentSuggestedReply) {
    return;
  }

  await copyText(currentSuggestedReply);
  showFormMessage("Рекомендуемый ответ скопирован.", false);
}

async function copyText(text) {
  if (!text) {
    return;
  }

  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }
  } catch {
    // Fallback below handles browsers where clipboard permissions are blocked.
  }

  const temporaryInput = document.createElement("textarea");
  temporaryInput.value = text;
  temporaryInput.setAttribute("readonly", "");
  temporaryInput.style.position = "fixed";
  temporaryInput.style.opacity = "0";
  document.body.append(temporaryInput);
  temporaryInput.select();
  document.execCommand("copy");
  temporaryInput.remove();
}

async function readJson(response) {
  try {
    return await response.json();
  } catch {
    return { error: "Сервер вернул некорректный ответ." };
  }
}

function validateTicketText(text) {
  if (!text) {
    return "Вставьте текст обращения перед анализом.";
  }
  if (text.length < minTicketLength) {
    return `Текст должен содержать не менее ${minTicketLength} символов.`;
  }
  if (text.length > maxTicketLength) {
    return `Текст должен содержать не более ${maxTicketLength} символов.`;
  }
  return "";
}

function getErrorMessage(status, payload) {
  if (status === 422) {
    return "Проверьте текст обращения: он должен содержать от 5 до 5000 символов.";
  }
  if (status === 503) {
    return "Сервис анализа временно недоступен. Попробуйте повторить позже.";
  }
  if (status === 404) {
    return "Запись не найдена.";
  }
  return payload?.error || "Не удалось выполнить запрос.";
}

function updateCharCount() {
  if (!charCount || !textarea) {
    return;
  }

  const length = textarea.value.length;
  charCount.textContent = `${length} / ${maxTicketLength}`;
  charCount.classList.toggle("is-near-limit", length > maxTicketLength * 0.9);
}

function setSubmitting(value) {
  isSubmitting = value;
  if (!analyzeButton || !form || !textarea) {
    return;
  }

  form.setAttribute("aria-busy", String(value));
  textarea.disabled = value;
  analyzeButton.disabled = value;
  analyzeButton.textContent = value ? "Анализируем..." : "Проанализировать";
}

function showFormMessage(message, isError) {
  if (!formMessage) {
    return;
  }

  formMessage.textContent = message;
  formMessage.classList.toggle("is-error", isError);
}

function showHistoryMessage(message) {
  if (historyMessage) {
    historyMessage.textContent = message;
  }
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return date.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value;
  return div.innerHTML;
}
