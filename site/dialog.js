/* ---------- 对话框：输入 → 追问 → 推演 → 折叠 ---------- */
const ENGINE = {kind: "demo", key: "", model: "claude-opus-5", localState: "none"};
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const wait = ms => new Promise(r => setTimeout(r, REDUCED ? 0 : ms));
const store = {
  get(k) { try { return localStorage.getItem("shijian." + k) || ""; } catch { return ""; } },
  set(k, v) { try { v ? localStorage.setItem("shijian." + k, v) : localStorage.removeItem("shijian." + k); } catch {} },
};
const ui = {
  body: $("#dlg-body"), bar: $("#dlg-bar"), form: $("#ask-form"), thread: $("#thread"), hint: $("#dlg-hint"),
  collapseBtn: $("#dlg-collapse"), now: $("#f-now"), goal: $("#f-goal"), panel: $("#engine-panel"),
};
let busy = false;

/* 引擎设置 */
// 本机订阅的状态：none = 没检测到本地服务；login = 服务在，但 claude 没登录；ok = 可以推演
const LOCAL_HOST = ["127.0.0.1", "localhost"].includes(location.hostname);
const LOCAL_URL = "http://127.0.0.1:8765/";
const ENGINE_LABEL = () => ({demo: "示范模式",
  local: ENGINE.localState === "ok" ? "本机 Claude 订阅" : "本机 Claude 订阅（还没连上）",
  byok: `自带 API Key（${$("#f-model").selectedOptions[0].textContent}）`})[ENGINE.kind];
function renderLocalHelp() {
  const box = $("#local-help");
  box.hidden = ENGINE.kind !== "local" || ENGINE.localState === "ok";
  if (box.hidden) return;
  const login = "<li>登录一次 Claude Code（用你的 Claude 订阅）：在终端运行 <code>claude auth login</code>，按提示在浏览器里授权。</li>";
  box.innerHTML = ENGINE.localState === "login"
    ? `<p>本地服务已经连上，但你电脑上的 <code>claude</code> 命令还没登录。</p><ol>${login}<li>登录完成后点「重新检测」，不用重启服务。</li></ol>
       <div class="dlg-actions"><button type="button" class="btn btn-ghost btn-sm" id="local-recheck">重新检测</button></div>`
    : `<p>网页不能直接调用你电脑上的 <code>claude</code> 命令，要先在本机启动本地服务，再从它打开本页。</p>
       <ol>${login}<li>双击仓库根目录的 <code>启动本地推演.bat</code>，或在仓库目录运行 <code>python scripts/serve_local.py</code>。浏览器会自动打开本地页面，在那里选这一项。</li></ol>
       <div class="dlg-actions">${LOCAL_HOST ? '<button type="button" class="btn btn-ghost btn-sm" id="local-recheck">重新检测</button>'
         : `<a class="btn btn-ghost btn-sm" href="${LOCAL_URL}">已经启动了，打开本地页面</a>`}</div>`;
}
function setEngine(kind) {
  ENGINE.kind = kind;
  document.querySelectorAll('input[name="engine"]').forEach(r => { r.checked = r.value === kind; });
  $("#byok-fields").hidden = kind !== "byok";
  $("#engine-name").textContent = ENGINE_LABEL();
  renderLocalHelp();
  store.set("engine", kind);
}
function openPanel() { ui.panel.hidden = false; $("#engine-btn").setAttribute("aria-expanded", "true"); }
$("#engine-btn").addEventListener("click", () => {
  ui.panel.hidden = !ui.panel.hidden;
  $("#engine-btn").setAttribute("aria-expanded", String(!ui.panel.hidden));
});
ui.panel.addEventListener("change", e => {
  if (e.target.name === "engine") setEngine(e.target.value);
  if (e.target.id === "f-model") { ENGINE.model = e.target.value; store.set("model", ENGINE.model); setEngine(ENGINE.kind); }
  if (e.target.id === "f-remember") store.set("key", e.target.checked ? ENGINE.key : "");
});
ui.panel.addEventListener("click", e => {
  if (e.target.id === "local-recheck") { e.target.textContent = "检测中…"; e.target.disabled = true; checkLocal(); }
});
$("#f-key").addEventListener("input", e => {
  ENGINE.key = e.target.value.trim();
  if ($("#f-remember").checked) store.set("key", ENGINE.key);
});
function checkLocal() { // 只有从本地服务打开时才检测；每次都重新读登录状态
  if (!LOCAL_HOST) return Promise.resolve();
  return fetch("/api/health", {cache: "no-store"}).then(r => r.json()).then(h => {
    if (!h.ok) return;
    ENGINE.localState = h.loggedIn === false ? "login" : "ok";
    $("#local-note").textContent = ENGINE.localState === "ok"
      ? `已连上本机 Claude Code（${h.version || "版本未知"}），用你自己的订阅额度。`
      : "本地服务已连上，但本机的 claude 命令还没登录。";
  }).catch(() => {}).finally(() => setEngine(ENGINE.kind));
}
(function initEngine() {
  ENGINE.key = store.get("key");
  $("#f-key").value = ENGINE.key; $("#f-remember").checked = Boolean(ENGINE.key);
  ENGINE.model = store.get("model") || ENGINE.model; $("#f-model").value = ENGINE.model;
  const saved = store.get("engine");
  setEngine(saved || (ENGINE.key ? "byok" : "demo"));
  checkLocal().then(() => { if (ENGINE.localState === "ok" && saved !== "byok") setEngine("local"); });
})();

/* 线程里的各种消息 */
function startThread(ctx) {
  ui.form.hidden = true; ui.thread.hidden = false; ui.collapseBtn.hidden = false; ui.hint.hidden = true;
  ui.thread.innerHTML = `<div class="msg-user"><div><b>当前处境</b>${esc(ctx.question)}</div>${ctx.goal ? `<div><b>所求为何</b>${esc(ctx.goal)}</div>` : ""}</div>`;
}
function addBot(html) {
  const el = document.createElement("div");
  el.className = "msg-bot"; el.innerHTML = html; ui.thread.append(el);
  return el;
}
const STEP_NAMES = ["立局", "定母题", "照镜", "推演", "换位", "太史公曰"];
const progHTML = (done, now) => `<div class="prog">${STEP_NAMES.map((n, i) =>
  `<span class="${i < done ? "done" : i === now ? "now" : ""}"><i>${i + 1}</i>${n}</span>`).join("")}</div>`;
function renderQuestions(qs, interactive) {
  const el = addBot(`<p>先问 ${qs.length} 个会改变结论的问题，其余按常见情况假设，并在结果里标出来。</p>
    ${qs.map((q, i) => `<div class="q" data-i="${i}"><div class="q-t"><span>${"一二三"[i]}</span>${esc(q.q)}</div>
      <div class="q-opts" role="group" aria-label="${esc(q.q)}">${q.options.map(o =>
        `<button type="button" class="q-opt" aria-pressed="false"${interactive ? "" : " disabled"}>${esc(o)}</button>`).join("")}</div></div>`).join("")}`);
  return el;
}
function pickOption(block, i, text) {
  block.querySelectorAll(`.q[data-i="${i}"] .q-opt`).forEach(b => b.setAttribute("aria-pressed", String(b.textContent === text)));
}
function askUser(qs) { // 等用户点完所有追问
  return new Promise(resolve => {
    const block = renderQuestions(qs, true);
    const go = addBot(`<label class="visually-hidden" for="f-extra">补充说明</label>
      <input class="more-in" id="f-extra" type="text" placeholder="还有要补充的，写在这里（可以不写）">
      <div class="dlg-actions"><button type="button" class="btn btn-primary" id="go-plan" disabled>继续推演</button></div>`);
    block.addEventListener("click", e => {
      const b = e.target.closest(".q-opt"); if (!b) return;
      const i = Number(b.closest(".q").dataset.i);
      qs[i].pick = b.textContent; pickOption(block, i, b.textContent);
      $("#go-plan").disabled = !qs.every(q => q.pick);
    });
    $("#go-plan").addEventListener("click", () => {
      block.querySelectorAll(".q-opt").forEach(b => { b.disabled = true; });
      const extra = $("#f-extra").value.trim();
      go.remove();
      if (extra) addBot(`<div class="msg-user" style="align-self: flex-end"><b>补充</b>${esc(extra)}</div>`);
      resolve(extra);
    });
    block.querySelector(".q-opt").focus();
  });
}
function showError(err, retry) {
  const el = addBot(`<div class="alert" role="alert">${esc(err.message || String(err))}
    <div class="dlg-actions"><button type="button" class="btn btn-ghost btn-sm" data-act="retry">重试</button>
    <button type="button" class="linkish" data-act="settings">换一种推演引擎</button></div></div>`);
  el.addEventListener("click", e => {
    const act = e.target.dataset.act;
    if (act === "retry") { el.remove(); retry(); }
    if (act === "settings") { ui.panel.hidden = false; $("#engine-btn").setAttribute("aria-expanded", "true"); }
  });
  busy = false;
}
function showCare(text) {
  const el = addBot(`<div class="care" role="status">${esc(text)}
    <p style="margin: 10px 0 0">如果你正处在危险中，请马上联系身边信任的人，或拨打 110、120；也可以拨打全国心理援助热线 12356。这一次先不做推演。</p>
    <div class="dlg-actions" style="margin-top: 10px"><button type="button" class="linkish" data-act="restart">重新开始</button></div></div>`);
  el.addEventListener("click", e => { if (e.target.dataset.act === "restart") restart(); });
  busy = false;
}

/* 折叠与展开 */
function collapse() { ui.body.hidden = true; ui.bar.hidden = false; }
function expand() { ui.body.hidden = false; ui.bar.hidden = true; ui.collapseBtn.focus(); }
ui.collapseBtn.addEventListener("click", () => {
  if (!$("#bar-sum").textContent) $("#bar-sum").textContent = ui.now.value.trim().slice(0, 24);
  if (!$("#bar-meta").textContent) $("#bar-meta").textContent = busy ? "推演进行中" : "对话进行中";
  collapse(); $("#dlg-expand").focus();
});
$("#dlg-expand").addEventListener("click", expand);
function restart() {
  if (busy) return;
  ui.thread.innerHTML = ""; ui.thread.hidden = true; ui.form.hidden = false; ui.collapseBtn.hidden = true; ui.hint.hidden = false;
  $("#bar-sum").textContent = ""; $("#bar-meta").textContent = ""; $("#mine").hidden = true;
  expand(); ui.now.focus();
}
$("#dlg-restart").addEventListener("click", restart);

function finish(d, meta) {
  $("#bar-sum").textContent = meta.summary;
  $("#bar-meta").textContent = meta.replay ? "示范回放，推演已完成" : `追问了 ${meta.n} 个问题，推演已完成`;
  addBot(progHTML(6, -1) + `<p>推演完成，结果在下面。</p>`);
  collapse();
  $("#mine-intro").innerHTML = meta.replay
    ? "这是示范回放：问题和推演都是预先做好的。想推演你自己的事，在上面的对话框里点「重新推演」，再到「设置」里换一种推演引擎。"
    : `由${esc(ENGINE_LABEL())}推演。拿不准的地方标成了"假设"；出现的古文都已和原文逐字核对。` +
      (meta.dropped?.length ? `<span class="dropped" style="display: block">${meta.dropped.map(esc).join("<br>")}</span>` : "");
  $("#mine-body").innerHTML = planHTML(d);
  $("#mine").hidden = false;
  $("#mine").scrollIntoView({behavior: REDUCED ? "auto" : "smooth"});
  $("#mine-title").focus({preventScroll: true});
  busy = false;
}

/* 三种流程 */
async function runReplay(d) {
  busy = true;
  ui.now.value = d.question; ui.goal.value = d.goal;
  startThread(d);
  addBot(`<p class="note">这是示范回放：追问和推演都是预先做好的，用来展示流程。</p>`);
  await wait(500);
  const block = renderQuestions(d.questions, false);
  for (let i = 0; i < d.questions.length; i++) { await wait(600); pickOption(block, i, d.questions[i].pick); }
  await wait(500);
  const prog = addBot(progHTML(0, 0));
  for (let i = 1; i <= 6; i++) { await wait(380); prog.innerHTML = progHTML(i, i); }
  prog.remove();
  finish(d, {summary: d.summary, n: d.questions.length, replay: true});
}

async function runLive(ctx) {
  busy = true;
  const thinking = addBot(`<p>先看看还缺什么信息……</p>`);
  let ask;
  try { ask = await callModel(ASK_SYSTEM, buildAskPrompt(ctx), ASK_SCHEMA); }
  catch (e) { thinking.remove(); return showError(e, () => runLive(ctx)); }
  thinking.remove();
  if (ask.care) return showCare(ask.care);
  ctx.summary = (ask.summary || ctx.question).slice(0, 24);
  ctx.questions = (ask.questions || []).filter(q => q.q && q.options?.length >= 2).slice(0, 3)
    .map(q => ({q: q.q, options: q.options.slice(0, 4), pick: ""}));
  const themes = (ask.themes || []).map(t => String(t).padStart(2, "0")).filter(t => themeByCode[t]).slice(0, 3);
  ctx.themes = themes.length ? themes : ["01"];
  if (ctx.questions.length) ctx.extra = await askUser(ctx.questions);
  return runPlan(ctx);
}
async function runPlan(ctx) {
  busy = true;
  const prog = addBot(`${progHTML(0, 0)}<p>正在推演：从 ${DATA.cases.length} 个案例里找正反两面的先例。通常要半分钟到两分钟，已用 <span id="elapsed">0</span> 秒。</p>`);
  const t0 = Date.now();
  const timer = setInterval(() => { const el = $("#elapsed"); if (el) el.textContent = Math.round((Date.now() - t0) / 1000); }, 1000);
  let raw;
  try { raw = await callModel(PLAN_SYSTEM, buildPlanPrompt(ctx), PLAN_SCHEMA); }
  catch (e) { clearInterval(timer); prog.remove(); return showError(e, () => runPlan(ctx)); }
  clearInterval(timer); prog.remove();
  if (raw.care) return showCare(raw.care);
  const {plan, dropped} = sanitizePlan(raw, ctx.themes);
  finish({...plan, question: ctx.question, goal: ctx.goal, questions: ctx.questions, extra: ctx.extra},
    {summary: ctx.summary, n: ctx.questions.length, dropped});
}

function explainDemoMode(ctx) {
  const el = addBot(`<p>现在是示范模式，页面没有接模型，没法推演你自己的事。二选一：</p>
    <div class="dlg-actions"><button type="button" class="btn btn-primary btn-sm" data-act="byok">填我自己的 API Key</button>
    <button type="button" class="btn btn-ghost btn-sm" data-act="local">在本机用 Claude 订阅</button></div>
    <p class="note">也可以先看一个示范，看看完整推演长什么样：</p>
    <div class="dlg-actions">${DATA.demos.map((d, i) => `<button type="button" class="demo-pick" data-demo="${i}">${esc(d.tab)}</button>`).join("")}</div>`);
  el.addEventListener("click", e => {
    const demo = e.target.closest("[data-demo]");
    if (demo) { runReplay(DATA.demos[Number(demo.dataset.demo)]); return; }
    const act = e.target.dataset.act;
    if (act !== "byok" && act !== "local") return;
    setEngine(act); openPanel();
    if (act === "byok") $("#f-key").focus(); else $("#local-help").scrollIntoView({block: "nearest"});
    el.remove(); ui.thread.hidden = true; ui.form.hidden = false; ui.collapseBtn.hidden = true; ui.hint.hidden = false;
  });
}

ui.form.addEventListener("submit", e => {
  e.preventDefault();
  if (busy) return;
  const ctx = {question: ui.now.value.trim(), goal: ui.goal.value.trim(), questions: [], extra: ""};
  if (ctx.question.length < 10) {
    ui.now.setCustomValidity("再多写几句：你现在在什么位置、有哪些选项、担心什么。");
    ui.now.reportValidity(); ui.now.setCustomValidity("");
    return;
  }
  if (ENGINE.kind === "byok" && !ENGINE.key) { openPanel(); $("#f-key").focus(); return; }
  if (ENGINE.kind === "local" && ENGINE.localState !== "ok") {
    openPanel(); renderLocalHelp(); $("#local-help").scrollIntoView({block: "nearest"}); return;
  }
  startThread(ctx);
  if (ENGINE.kind === "demo") return explainDemoMode(ctx);
  runLive(ctx);
});

$("#demo-picks").insertAdjacentHTML("beforeend", DATA.demos.map((d, i) =>
  `<button type="button" class="demo-pick" data-i="${i}">${esc(d.tab)}</button>`).join(""));
$("#demo-picks").addEventListener("click", e => {
  const b = e.target.closest(".demo-pick");
  if (b && !busy) runReplay(DATA.demos[Number(b.dataset.i)]);
});
