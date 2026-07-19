const $ = id => document.getElementById(id);
const log = message => {
  $("log").textContent = `${new Date().toLocaleTimeString()} ${message}\n` + $("log").textContent;
};
let activeTask = null;
let reviewCreator = null;

async function cfg() {
  return chrome.storage.local.get(["apiUrl", "apiToken"]);
}

async function api(path, options = {}) {
  const config = await cfg();
  const response = await fetch((config.apiUrl || "").replace(/\/+$/, "") + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Extension-Token": config.apiToken || "",
      ...(options.headers || {}),
    },
  });
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json();
}

async function request(type) {
  const result = await chrome.runtime.sendMessage({type});
  if (!result?.ok) throw new Error(result?.error || "操作失败");
  return result;
}

function formatNumber(value) {
  if (value === null || value === undefined) return "不可用";
  if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
  return String(value);
}

function renderReview(creator) {
  reviewCreator = creator;
  $("review-card").classList.toggle("hidden", !creator);
  $("review-empty").classList.toggle("hidden", Boolean(creator));
  if (!creator) return;
  $("creator-avatar").src = creator.profile_pic_url || "";
  $("creator-name").textContent = creator.full_name || creator.username;
  $("creator-username").textContent = `@${creator.username} · ${creator.primary_niche}`;
  $("creator-score").textContent = `${Math.round(creator.total_score || 0)}分`;
  $("creator-bio").textContent = creator.biography || "暂无公开简介";
  $("creator-metrics").innerHTML = [
    ["相似度", `${Math.round(creator.similarity_score || 0)}分`],
    ["粉丝", formatNumber(creator.follower_count)],
    ["Reels中位播放", formatNumber(creator.median_visible_reel_views)],
    ["墨西哥可信度", `${Math.round((creator.mexico_confidence_score || 0) * 100)}%`],
    ["公开邮箱", creator.public_email || "无"],
  ].map(([label, value]) => `<div><b>${label}</b><br>${value}</div>`).join("");
  const reasons = creator.filter_reasons?.length ? ` · ${creator.filter_reasons.join("；")}` : "";
  const seed = creator.reference_seed ? ` · 相似种子 @${creator.reference_seed}` : "";
  $("creator-source").textContent = `来源：${(creator.discovery_sources || []).join(" / ") || "未知"}${seed} · 数据：${creator.data_quality_status || "incomplete"}${reasons}`;
}

async function loadReview() {
  if (!activeTask?.task_id) {
    renderReview(null);
    return;
  }
  const data = await api(`/api/extension/tasks/${activeTask.task_id}/review/next`);
  renderReview(data.creator);
}

async function refresh() {
  const config = await cfg();
  if (!config.apiUrl || !config.apiToken) return;
  try {
    const data = await api("/api/extension/tasks/active");
    if (data.task) activeTask = data.task;
    else {
      const reviewData = await api("/api/extension/tasks/review-active");
      activeTask = reviewData.task;
    }
    $("status").textContent = "已连接";
    $("task").textContent = activeTask ? `${activeTask.task_id} · ${activeTask.status}` : "当前无任务";
    const current = activeTask?.current_username || activeTask?.current_hashtag || "-";
    $("progress").textContent = activeTask
      ? `候选 ${activeTask.candidates_found} / 已分析 ${activeTask.profiles_analyzed} / 匹配 ${activeTask.profiles_matched} / 当前 ${current}`
      : "";
    const recent = activeTask?.recent_candidates || [];
    $("recent-candidates").textContent = recent.length
      ? `最近发现：${recent.map(item => `@${item.username}（${item.data_quality_status || item.status}）`).join("、")}`
      : "尚未从公开内容解析出新作者";
    if (activeTask?.task_id) {
      const eventData = await api(`/api/extension/tasks/${activeTask.task_id}/events?limit=5`);
      $("diagnostics").textContent = (eventData.events || [])
        .map(event => `${event.event_type}${event.error_code ? ` · ${event.error_code}` : ""}${event.message ? ` · ${event.message}` : ""}`)
        .join("\n") || "暂无诊断事件";
    }
    await loadReview();
  } catch (error) {
    $("status").textContent = `连接失败：${error.message}`;
  }
}

async function review(action) {
  if (!activeTask?.task_id || !reviewCreator?.username) return;
  await api(`/api/extension/tasks/${activeTask.task_id}/review/${reviewCreator.username}/${action}`, {
    method: "POST",
    body: JSON.stringify({list_name: "默认达人库"}),
  });
  log(action === "save" ? `已加入达人库：@${reviewCreator.username}` : `已跳过：@${reviewCreator.username}`);
  await loadReview();
}

document.addEventListener("DOMContentLoaded", async () => {
  const config = await cfg();
  $("api-url").value = config.apiUrl || "";
  $("api-token").value = config.apiToken || "";
  await refresh();
  setInterval(refresh, 2500);
});

$("save").onclick = async () => {
  const apiUrl = $("api-url").value.trim().replace(/\/+$/, "");
  const apiToken = $("api-token").value.trim();
  await chrome.storage.local.set({apiUrl, apiToken});
  try {
    await api("/api/extension/handshake", {
      method: "POST",
      body: JSON.stringify({
        extension_version: chrome.runtime.getManifest().version,
        user_agent: navigator.userAgent,
      }),
    });
    log("配置已保存，连接成功");
  } catch (error) {
    log(`连接失败：${error.message}`);
  }
  await refresh();
};

for (const [id, type] of [
  ["start", "START_BATCH"],
  ["pause", "PAUSE_BATCH"],
  ["resume", "RESUME_BATCH"],
  ["stop", "STOP_BATCH"],
  ["return", "RETURN_START"],
]) {
  $(id).onclick = () => request(type).then(() => log(`${id} 成功`)).catch(error => log(error.message));
}

$("save-creator").onclick = () => review("save").catch(error => log(error.message));
$("skip-creator").onclick = () => review("skip").catch(error => log(error.message));
$("retry-failed").onclick = async () => {
  if (!activeTask?.task_id) return;
  const result = await api(`/api/extension/tasks/${activeTask.task_id}/retry-failed`, {method: "POST"});
  log(`已重新排队 ${result.retried || 0} 个失败项`);
  await refresh();
};
$("open-profile").onclick = async () => {
  if (!reviewCreator?.profile_url) return;
  const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
  if (tab?.id) await chrome.tabs.update(tab.id, {url: reviewCreator.profile_url});
};

chrome.runtime.onMessage.addListener(message => {
  if (message.type !== "BATCH_STATE") return;
  const batch = message.state;
  $("progress").textContent = `${batch.running ? (batch.paused ? "已暂停" : "运行中") : "已停止"} · ${batch.current?.username || batch.current?.url || "-"}`;
  if (batch.lastError) log(batch.lastError);
});
