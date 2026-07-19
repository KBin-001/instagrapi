const state = {running: false, paused: false, taskId: null, startUrl: null, current: null, lastError: null, delayMin: 4, delayMax: 8};
let loopActive = false;

chrome.sidePanel.setPanelBehavior({openPanelOnActionClick: true}).catch(console.error);

async function config() {
  const data = await chrome.storage.local.get(["apiUrl", "apiToken"]);
  return {apiUrl: (data.apiUrl || "").replace(/\/+$/, ""), token: data.apiToken || ""};
}

async function api(path, options = {}) {
  const cfg = await config();
  if (!cfg.apiUrl || !cfg.token) throw new Error("请先配置本地接口地址和令牌");
  const response = await fetch(cfg.apiUrl + path, {
    ...options,
    headers: {"Content-Type": "application/json", "X-Extension-Token": cfg.token, ...(options.headers || {})},
  });
  if (!response.ok) {
    const error = new Error(`${response.status} ${await response.text()}`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function notify() { chrome.runtime.sendMessage({type: "BATCH_STATE", state: {...state}}).catch(() => {}); }

async function activeTab() {
  const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
  if (!tab?.id) throw new Error("没有可用的当前标签页");
  return tab;
}

function waitLoaded(tabId, timeout = 30000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { chrome.tabs.onUpdated.removeListener(listener); reject(new Error("页面加载超时")); }, timeout);
    function listener(id, info) {
      if (id === tabId && info.status === "complete") {
        clearTimeout(timer); chrome.tabs.onUpdated.removeListener(listener); setTimeout(resolve, 1500);
      }
    }
    chrome.tabs.onUpdated.addListener(listener);
  });
}

async function collect(tabId, item) {
  try { return await chrome.tabs.sendMessage(tabId, {type: "COLLECT_TASK_ITEM", pageType: item.page_type}); }
  catch (_) {
    await chrome.scripting.executeScript({target: {tabId}, files: ["content.js"]});
    return chrome.tabs.sendMessage(tabId, {type: "COLLECT_TASK_ITEM", pageType: item.page_type});
  }
}

async function submit(item, result) {
  if (!result || result.ok !== true || !result.payload) {
    const error = result?.error || "采集脚本未返回有效数据";
    await api(`/api/extension/tasks/${state.taskId}/failure`, {method: "POST", body: JSON.stringify({queue_item_id: item.id, error, safe_stop: !!result?.safeStop, retryable: !!result?.retryable, error_code: result?.safeStop ? "instagram_safety_stop" : (result?.errorCode || "collection_error"), diagnostics: result?.diagnostics || {}})});
    if (result?.safeStop) state.running = false;
    state.lastError = error; notify(); return;
  }
  const base = {queue_item_id: item.id};
  if (item.page_type === "profile") {
    await api(`/api/extension/tasks/${state.taskId}/profile`, {method: "POST", body: JSON.stringify({...result.payload, ...base})});
  } else if (item.page_type === "media") {
    await api(`/api/extension/tasks/${state.taskId}/media`, {method: "POST", body: JSON.stringify({...result.payload, ...base})});
  } else {
    await api(`/api/extension/tasks/${state.taskId}/candidates`, {method: "POST", body: JSON.stringify({...result.payload, ...base})});
  }
}

async function loop() {
  if (loopActive) return;
  loopActive = true;
  try { while (state.running) {
    if (state.paused) { await new Promise(r => setTimeout(r, 800)); continue; }
    let next;
    try { next = await api(`/api/extension/tasks/${state.taskId}/next`, {method: "POST"}); }
    catch (error) { state.lastError = error.message; state.running = false; notify(); break; }
    if (!next.item) { state.running = false; notify(); break; }
    state.current = next.item; notify();
    const tab = await activeTab();
    await chrome.tabs.update(tab.id, {url: next.item.url, active: true});
    try {
      await waitLoaded(tab.id);
      const result = await collect(tab.id, next.item);
      await submit(next.item, result);
    } catch (error) {
      const retryable = ![400, 401, 403, 404, 422].includes(error.status);
      await api(`/api/extension/tasks/${state.taskId}/failure`, {method: "POST", body: JSON.stringify({queue_item_id: next.item.id, error: error.message, safe_stop: false, retryable, error_code: error.status === 422 ? "payload_validation" : "navigation_or_submit"})}).catch(() => {});
    }
    const delay = state.delayMin + Math.random() * Math.max(0, state.delayMax - state.delayMin);
    await new Promise(r => setTimeout(r, Math.round(delay * 1000)));
  }} finally { loopActive = false; }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  (async () => {
    if (message.type === "START_BATCH") {
      const active = await api("/api/extension/tasks/active");
      if (!active.task) throw new Error("没有等待中的发现任务");
      await api(`/api/extension/tasks/${active.task.task_id}/resume`, {method: "POST"});
      const tab = await activeTab();
      Object.assign(state, {running: true, paused: false, taskId: active.task.task_id, startUrl: tab.url, lastError: null, delayMin: active.task.request_delay_min_seconds || 4, delayMax: active.task.request_delay_max_seconds || 8});
      notify(); loop();
    } else if (message.type === "PAUSE_BATCH") {
      state.paused = true; await api(`/api/extension/tasks/${state.taskId}/pause`, {method: "POST"}); notify();
    } else if (message.type === "RESUME_BATCH") {
      state.paused = false; state.running = true; await api(`/api/extension/tasks/${state.taskId}/resume`, {method: "POST"}); notify(); loop();
    } else if (message.type === "STOP_BATCH") {
      state.running = false; await api(`/api/extension/tasks/${state.taskId}/stop`, {method: "POST"}); notify();
    } else if (message.type === "RETURN_START" && state.startUrl) {
      const tab = await activeTab(); await chrome.tabs.update(tab.id, {url: state.startUrl});
    } else if (message.type === "GET_BATCH_STATE") sendResponse({...state});
    sendResponse({ok: true, state: {...state}});
  })().catch(error => sendResponse({ok: false, error: error.message}));
  return true;
});
