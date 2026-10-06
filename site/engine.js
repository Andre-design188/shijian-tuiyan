/* ---------- 推演引擎：提示词、输出结构、模型调用、引文校验 ---------- */
// 自带 Key 模式：浏览器里按需加载官方 SDK（锁定版本）
const SDK_URL = "https://cdn.jsdelivr.net/npm/@anthropic-ai/sdk@0.128.0/+esm";

// 与 scripts/caselib.py 的归一规则一致：去标点、统一常见异体字，再做子串比对
const PUNCT = /[\s，。、；：？！“”‘’「」『』《》〈〉（）()［］\[\]〔〕【】…—·,.;:?!'"-]/g;
const VARIANTS = {馀: "余", 阬: "坑", 彊: "强", 県: "县", 鉅: "巨", 脩: "修", 闲: "间", 嚮: "向", 蚤: "早", 倍: "背",
  劎: "剑", 倶: "俱", 讬: "托", 棬: "卷", 擣: "捣", 鬬: "斗", 鬭: "斗", 鬥: "斗", 呉: "吴"};
const normQ = s => [...String(s || "").replace(PUNCT, "")].map(ch => VARIANTS[ch] || ch).join("");
const quotesIn = s => (String(s || "").match(/「(.+?)」/g) || []).map(normQ);
// 太史公曰只许从「原文」摘；其余字段里的「」古文，只要见于任何案例已校验的引文就算数
const caseQuotes = Object.fromEntries(DATA.cases.map(c => [c.id, quotesIn(c.fields["原文"])]));
const allQuotes = DATA.cases.flatMap(c => Object.values(c.fields).flatMap(quotesIn));
const GRADE_NOTE = Object.entries(DATA.grades).map(([k, v]) => `${k} ${v}`).join("；");

const THEME_LIST = DATA.themes.map(t => `${t.code} ${t.name}：${t.modern}`).join("\n");
const YIJING_STEPS = DATA.yijing.workflow.map((id, i) => {
  const p = DATA.yijing.principles.find(item => item.id === id);
  return `${i + 1}. ${p.name}｜原典：${p.phrase}（${p.source}）｜含义：${p.reading}｜自检：${p.question}｜边界：${p.boundary}`;
}).join("\n");

const ASK_SYSTEM = `你是「史鉴推演」的立局助手。用户会给出"当前处境"和"所求为何"。

你要做四件事：
1. 找出还缺哪些会改变结论的关键信息，提出 0 到 3 个追问。用户已经说过的不要再问；信息已经够了就不问。每个追问配 2 到 4 个互斥、口语化的备选答案。
2. 从下面 16 个母题里选出 1 到 3 个最相关的编号（只写两位数字）。
3. 用不超过 20 个字概括用户的处境，用作对话折叠后的摘要。
4. 如果用户流露出自伤或轻生的念头，把 care 写成一段温和、关心的话，不推演、不追问；否则 care 留空字符串。

16 个母题：
${THEME_LIST}`;

const PLAN_SYSTEM = `你是「史鉴推演」：把用户现实处境、《史记》《资治通鉴》的历史案例和《易经》决策思想放进同一条推演链。历史提供可核对的行动与后果，不提供答案；《易经》提供逐步检查变化与行动的方法，不是占筮或预测。

三源分工必须清楚：
- 《史记》案例侧重具体人物的位置、关系、动机、关键选择及其得失；只能依据下方提供的案例文字与史料等级。
- 《资治通鉴》案例侧重事件时序、各方行动、局势演变及连锁后果；只能依据下方提供的案例文字与史料等级。
- 《易经》只按固定九步工作流检查处境、变化、时机、责任、风险、调整和复盘；用可观察事实与行动表达，不把古文解释成预言。
- mirrors 是史书证据，yijingAnalysis 是决策检查方法。综合推荐时要说明历史类比成立的条件和现实差异，不可把三种来源混成一句古训。

按七步产出，每一步对应输出里的一个字段：
- board（立局）：位、力、人、时、势、退六个要素各写一句，紧扣用户的处境。位是他在结构里的位置；力是手里的资源，分清哪些带得走；人是关键他人的性格与利益；时是窗口期；势是大势；退是最坏结果能否承受、能否挽回。拿不准的地方写成合理假设，并把 assume 设为 true。
- themes（定母题）：1 到 3 个母题编号。
- mirrors（照镜）：3 到 5 条，case 只能填下面"可用案例"里的编号。每个选项至少配一个正例和一个反例。若可用案例中两部书都有相关材料，镜子应覆盖《史记》和《资治通鉴》，并利用各自不同视角；若其中一本没有相关案例，不得伪造或声称使用。same 写像在哪里，diff 写不像的地方。如果不像的地方正好落在该案例的"决定变量"上，use 写"降为参考"，否则写"可作依据"，可以加一句前提。每个案例都标了史料等级（${GRADE_NOTE}）：B 级只依据抉择和结局，不依据对话和场面细节；C 级是传说、有争议或史家的议论，use 只能写"降为参考"，也不能单独撑起一个选项。
- options（推演）：2 到 3 个选项；合适的话，主动加一个低成本试探的中间选项（先兼职、先签短约、先谈条款）。每个选项写 near（0–6 个月）、mid（1–2 年）、far（3–5 年）的走向，fail 写它会像哪个反例那样翻车，signal 写成"一旦出现某个情况，就做某件事"。恰好一个选项的 pick 为 true。
- swap（换位）：2 个关键他人，who 写身份，v 写他此刻最怕什么、会怎么想。
- yijingAnalysis（易经决策方法）：按完整工作流输出每一步；每一步写 principle（下列固定 ID）、reading（1句结合本处境的分析）、evidence（可观察事实或明确标为未知）、action（下一步可执行动作）。不得删步骤。古文原句与出处由程序按原则 ID 补入，不要自行生成。必须标明这是项目的现代综合，不是占筮，不预测结果。
- verdict（太史公曰）：pick 写推荐；quote 必须是某个可用案例"原文"里逐字的一小段（不超过 20 个字），quote_case 填该案例编号；why 写一两句理由；premise 写推荐成立的前提；stop 写止损线。
- actions（行动卡）：do 写本周就能做的 3 件事，watch 写要盯住的 2 个信号，line 写 1 条底线。

纪律：
- 古文只能逐字摘自可用案例的"原文"，不许凭记忆写古文；引古文一律用「」括起来，转述不加引号。页面会逐字核对，对不上的引文会被隐藏。
- 不讲宿命论：史书里"赐死""族诛"这类结局，翻译成现代的出局、背锅、被清洗，给建议时不出现${DATA.plain.scary.join("、")}这些词。成功的先例背后有幸存者偏差，孤注一掷、出头单干类的正例要打折扣。
- 涉及医疗、法律、税务或具体投资标的时，在 premise 里写明需要专业意见。
- 如果用户流露出自伤或轻生的念头，只写 care（一段温和、关心的话），其余字段给空值；否则 care 留空字符串。
- 易经决策方法工作流（完整应用，古文只可引用下面固定目录）：\n${YIJING_STEPS}
- 用简体中文，说人话，具体，落在用户下一步做什么；每个字段一两句、不超过 ${DATA.plain.cap} 个字，不堆典故，不用感叹号，不用这些词：${DATA.plain.banned.join("、")}。`;

const S = {type: "string"};
const obj = (props, req = Object.keys(props)) => ({type: "object", additionalProperties: false, required: req, properties: props});
const arr = items => ({type: "array", items});
const ASK_SCHEMA = obj({summary: S, questions: arr(obj({q: S, options: arr(S)})), themes: arr(S), care: S});
const PLAN_SCHEMA = obj({
  care: S,
  board: arr(obj({k: {type: "string", enum: ["位", "力", "人", "时", "势", "退"]}, v: S, assume: {type: "boolean"}})),
  themes: arr(S),
  mirrors: arr(obj({option: S, case: S, role: {type: "string", enum: ["正例", "反例"]}, same: S, diff: S, use: S})),
  options: arr(obj({name: S, near: S, mid: S, far: S, fail: S, signal: S, pick: {type: "boolean"}})),
  swap: arr(obj({who: S, v: S})),
  yijingAnalysis: arr(obj({principle: {type: "string", enum: DATA.yijing.principles.map(item => item.id)}, reading: S, evidence: S, action: S})),
  verdict: obj({pick: S, quote: S, quote_case: S, why: S, premise: S, stop: S}),
  actions: obj({do: arr(S), watch: arr(S), line: S}),
});

function buildAskPrompt(ctx) {
  return `当前处境：${ctx.question}\n所求为何：${ctx.goal || "（没写，按常理推断）"}`;
}

// 只把相关母题的案例（加上它们"对照"里提到的案例）放进提示词
function casesFor(themes) {
  const ids = new Set(DATA.cases.filter(c => themes.includes(c.theme)).map(c => c.id));
  for (const id of [...ids]) for (const r of String(caseById[id].fields["对照"] || "").match(/\d{2}-\d{2}/g) || []) if (caseById[r]) ids.add(r);
  const candidates = [...ids].map(id => caseById[id]);
  const selected = [];
  for (const book of ["史记", "资治通鉴"]) {
    const found = candidates.find(c => String(c.src).includes(book));
    if (found) selected.push(found);
  }
  for (const c of candidates) if (!selected.includes(c) && selected.length < 30) selected.push(c);
  return selected;
}
function buildPlanPrompt(ctx) {
  const qa = ctx.questions.map(q => `- ${q.q} 回答：${q.pick}`).join("\n");
  const cases = casesFor(ctx.themes).map(c => {
    const f = c.fields;
    return `## ${c.id} ${c.title}（${c.src}）\n史料：${f["史料"]}\n处境：${f["处境"]}\n抉择：${f["抉择"]}\n结果：${f["结果"]}\n决定变量：${f["决定变量"]}\n可迁移：${f["可迁移"]}\n边界：${f["边界"]}\n原文：${f["原文"]}`;
  }).join("\n\n");
  return `当前处境：${ctx.question}\n所求为何：${ctx.goal || "（没写，按常理推断）"}\n` +
    (qa ? `追问与回答：\n${qa}\n` : "") + (ctx.extra ? `补充：${ctx.extra}\n` : "") +
    `相关母题：${ctx.themes.join("、")}\n\n可用案例：\n\n${cases}\n\n必须完整应用易经决策方法，逐步结合处境。仅可使用以下原则 ID；原句与来源由程序补入：\n${YIJING_STEPS}`;
}

function parseJSON(text) {
  try { return JSON.parse(text); } catch {}
  const a = text.indexOf("{"), b = text.lastIndexOf("}");
  if (a >= 0 && b > a) { try { return JSON.parse(text.slice(a, b + 1)); } catch {} }
  throw new Error("模型没有按约定的格式回答，请再试一次。");
}

async function callAnthropic(system, prompt, schema) {
  const {default: Anthropic} = await import(SDK_URL);
  const client = new Anthropic({apiKey: ENGINE.key, dangerouslyAllowBrowser: true});
  const req = {model: ENGINE.model, max_tokens: 16000, system, messages: [{role: "user", content: prompt}],
    output_config: {format: {type: "json_schema", schema}}};
  let msg;
  try {
    msg = ENGINE.model === "claude-opus-5"
      // 被安全分类器拒答时，由服务端自动换模型重试
      ? await client.beta.messages.create({...req, betas: ["server-side-fallback-2026-07-01"], fallbacks: "default"}, {timeout: 300000})
      : await client.messages.create(req, {timeout: 300000});
  } catch (e) {
    if (e instanceof Anthropic.AuthenticationError) throw new Error("API Key 无效或已过期（401）。检查 Key 后再试。");
    if (e instanceof Anthropic.PermissionDeniedError) throw new Error("这个 Key 没有调用该模型的权限（403）。换个模型或检查账户。");
    if (e instanceof Anthropic.RateLimitError) throw new Error("请求太频繁或额度不足（429），稍等一会儿再试。");
    if (e instanceof Anthropic.BadRequestError) throw new Error(`请求被拒绝（400）：${e.message}`);
    if (e instanceof Anthropic.APIConnectionError) throw new Error("连不上 Anthropic 的服务器。检查网络（在国内可能需要代理），或者改用本机 Codex。");
    if (e instanceof Anthropic.APIError) throw new Error(`模型服务出错（${e.status ?? "未知"}），稍后再试。`);
    throw e;
  }
  if (msg.stop_reason === "refusal") throw new Error("模型拒绝回答这个请求。换个说法，只描述处境本身，再试一次。");
  if (msg.stop_reason === "max_tokens") throw new Error("回答太长被截断了，请再试一次。");
  return parseJSON(msg.content.filter(b => b.type === "text").map(b => b.text).join(""));
}

async function callLocal(system, prompt, schema) {
  let r;
  try {
    r = await fetch("/api/codex", {method: "POST", headers: {"Content-Type": "application/json", "X-Shijian-Local": "1"},
      body: JSON.stringify({system, prompt, schema})});
  } catch {
    // 连接直接断了：再探一次，分清是服务停了还是这一次意外断开
    const alive = await fetch("/api/health", {cache: "no-store"}).then(r => r.ok).catch(() => false);
    throw new Error(alive
      ? "和本地服务的连接意外断开了，点「重试」再来一次。反复出现的话，看一下仓库里 logs/serve_local.log 的记录。"
      : "本地服务没有在运行，可能是电脑重启过，或者停止过它。双击仓库里的「启动本地推演.bat」，它会在后台启动，再点「重试」。");
  }
  const j = await r.json().catch(() => ({}));
  if (!r.ok || !j.ok) throw new Error(j.error || `本地服务出错（${r.status}）。`);
  return j.data;
}

const callModel = (system, prompt, schema) =>
  ENGINE.kind === "local" ? callLocal(system, prompt, schema) : callAnthropic(system, prompt, schema);

// 模型输出 → 页面可渲染的推演；顺带做案例编号、史料等级和引文的逐字核对
function sanitizePlan(p, fallbackThemes) {
  const dropped = [];
  // 各字段里的「」古文：见于已校验的案例引文才显示，否则隐藏并说明
  const clean = s => String(s ?? "").replace(/「(.+?)」/g, (all, q) => {
    const nq = normQ(q);
    if (nq.length >= 2 && allQuotes.some(v => v.includes(nq))) return all;
    dropped.push(`模型写的古文「${q}」在原文里对不上，已隐藏。`);
    return "〔引文已隐藏〕";
  });
  const deep = o => typeof o === "string" ? clean(o) : Array.isArray(o) ? o.map(deep)
    : o && typeof o === "object" ? Object.fromEntries(Object.entries(o).map(([k, v]) => [k, k === "quote" ? v : deep(v)])) : o;
  p = deep(p);
  const board = ["位", "力", "人", "时", "势", "退"].map(k => (p.board || []).find(b => b.k === k)).filter(Boolean);
  let themes = (p.themes || []).filter(t => themeByCode[t]);
  if (!themes.length) themes = fallbackThemes;
  const mirrors = (p.mirrors || []).filter(m => {
    if (caseById[m.case]) return true;
    dropped.push(`照镜里提到的案例编号 ${m.case} 不存在，已去掉。`);
    return false;
  });
  for (const m of mirrors) {
    const c = caseById[m.case];
    if (c.grade === "C" && !String(m.use).startsWith("降为参考")) {
      m.use = "降为参考";
      dropped.push(`${c.id} ${c.title} 是 C 级史料（传说、有争议或史家议论），已从依据降为参考。`);
    }
  }
  const options = (p.options || []).slice(0, 4);
  let picked = false;
  for (const o of options) { o.pick = Boolean(o.pick) && !picked; picked = picked || o.pick; }
  if (!picked && options[0]) options[0].pick = true;
  const v = {pick: "", quote: "", quote_case: "", why: "", premise: "", stop: "", ...(p.verdict || {})};
  if (v.quote) {
    const nq = normQ(v.quote);
    const inCase = id => (caseQuotes[id] || []).some(q => q.includes(nq));
    const hit = inCase(v.quote_case) ? v.quote_case : Object.keys(caseQuotes).find(inCase);
    if (hit && nq.length >= 2) v.quote_case = hit;
    else { dropped.push(`模型给出的引文「${v.quote}」在原文里对不上，已隐藏。`); v.quote = ""; v.quote_case = ""; }
  }
  const a = p.actions || {};
  const byPrinciple = Object.fromEntries(DATA.yijing.principles.map(item => [item.id, item]));
  const rawYi = p.yijingAnalysis || [];
  const yi = DATA.yijing.workflow.map(id => {
    const item = rawYi.find(row => row.principle === id);
    return {principle: id, reading: clean(item?.reading || "尚需结合具体事实核对。"),
      evidence: clean(item?.evidence || "目前信息不足，需补充核实。"),
      action: clean(item?.action || "先补充事实并在设定日期复核。")};
  });
  if (rawYi.length !== DATA.yijing.workflow.length || rawYi.some(row => !byPrinciple[row.principle]))
    dropped.push("易经分析步骤缺漏或 ID 无效，已按固定完整流程补齐，并提示需结合事实核对。");
  return {plan: {board, themes, mirrors, options, swap: p.swap || [], verdict: v,
    yijing: {steps: yi},
    actions: {do: a.do || [], watch: a.watch || [], line: a.line || ""}}, dropped};
}
