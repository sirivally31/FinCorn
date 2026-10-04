const API = "/api";
let charts = {};
let activePage = "dashboard";
let liveRefreshInProgress = false;
const LIVE_REFRESH_MS = 10000;

function fmtINR(v){
  if(v === null || v === undefined) return "—";
  const n = Number(v);
  const sign = n < 0 ? "-" : "";
  return sign + "₹" + Math.abs(n).toLocaleString("en-IN", {maximumFractionDigits: 2, minimumFractionDigits: 2});
}
function fmtNum(v){ return v === null || v === undefined ? "—" : Number(v).toLocaleString("en-IN"); }
function fmtPct(v){ return v === null || v === undefined ? "—" : v + "%"; }
function fmtDate(v){ if(!v) return "—"; try{ return new Date(v).toLocaleString("en-IN"); }catch(e){ return v; } }

async function api(path, opts){
  const res = await fetch(API + path, opts);
  if(!res.ok){
    let body;
    try{ body = await res.json(); }catch(e){ body = {message: res.statusText}; }
    throw new Error(body.message || "Request failed");
  }
  return res.json();
}

// ---------------------------------------------------------------- Nav
document.querySelectorAll(".nav-item").forEach(btn=>{
  btn.addEventListener("click", ()=> gotoPage(btn.dataset.page));
});

const PAGE_META = {
  dashboard:{title:"Dashboard", sub:"Live reconciliation, cash and exception metrics computed from the database."},
  reconciliation:{title:"Reconciliation", sub:"Payment ↔ Settlement ↔ Ledger matching results."},
  exceptions:{title:"Exceptions", sub:"Exception queue with AI-grounded explanations and workflow actions."},
  settlements:{title:"Settlements", sub:"All settlement records received from the bank/gateway."},
  cash:{title:"Cash Position", sub:"Current operating cash, computed from actual transaction and settlement records."},
  forecast:{title:"Cash Forecast", sub:"Forward-looking projection using a transparent moving-average model."},
  merchants:{title:"Merchants", sub:"Per-merchant transaction, settlement and exception analytics."},
  assistant:{title:"AI Finance Assistant", sub:"Ask questions about the current reconciliation dataset. Answers are grounded in real numbers."},
  audit:{title:"Audit Log", sub:"Full trail of system and user actions on exceptions."},
  settings:{title:"Settings", sub:"Environment and AI provider configuration for this demo instance."},
};

async function gotoPage(page){
  activePage = page;
  document.querySelectorAll(".nav-item").forEach(b=>b.classList.toggle("active", b.dataset.page===page));
  document.querySelectorAll(".page").forEach(p=>p.classList.add("hidden"));
  document.getElementById("page-"+page).classList.remove("hidden");
  document.getElementById("page-title").textContent = PAGE_META[page].title;
  document.getElementById("page-subtitle").textContent = PAGE_META[page].sub;
  try{
    await LOADERS[page]();
    setLiveStatus("live", `Live · updated ${new Date().toLocaleTimeString()}`);
  }catch(e){
    setLiveStatus("offline", "Connection issue · retrying");
    document.getElementById("page-"+page).innerHTML = `<div class="error-state">Failed to load: ${e.message}</div>`;
  }
}

function setLiveStatus(state, label){
  const status = document.getElementById("live-status");
  status.className = `live-status ${state}`;
  document.getElementById("live-status-text").textContent = label;
}

async function refreshActivePage(){
  const refresh = LIVE_REFRESHERS[activePage];
  const modalOpen = !document.getElementById("modal-backdrop").classList.contains("hidden");
  const progressOpen = !document.getElementById("progress-overlay").classList.contains("hidden");
  const editing = document.activeElement && /^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName);
  if(document.hidden || liveRefreshInProgress || modalOpen || progressOpen || editing || !refresh) return;

  liveRefreshInProgress = true;
  setLiveStatus("updating", "Updating live data");
  try{
    await refresh();
    setLiveStatus("live", `Live · updated ${new Date().toLocaleTimeString()}`);
  }catch(e){
    setLiveStatus("offline", "Connection issue · retrying");
  }finally{
    liveRefreshInProgress = false;
  }
}

// ---------------------------------------------------------------- Dashboard
async function loadDashboard(){
  const el = document.getElementById("page-dashboard");
  el.innerHTML = `<div class="empty-state">Loading dashboard…</div>`;
  const [summary, exceptionsAnalytics] = await Promise.all([
    api("/dashboard/summary"), api("/analytics/exceptions")
  ]);

  el.innerHTML = `
    <div class="grid-cards">
      ${card("Total Transactions", fmtNum(summary.recordsProcessed), "Records processed this run")}
      ${card("Match Rate", fmtPct(summary.matchRate), summary.matchedRecords + " matched vs " + summary.autoResolvedRecords + " auto-resolved", "accent-amber")}
      ${card("Accuracy", fmtPct(summary.accuracy), "True positive match precision (Ground Truth)", "accent-green")}
      ${card("Correct Classifications", summary.correctClassifications, "Matched cleanly / mapped correctly", "accent-green")}
      ${card("Incorrect Classifications", summary.incorrectClassifications, "False matches or missed exceptions", "accent-red")}
      ${card("Unresolved Exceptions", fmtNum(summary.unresolvedExceptions), summary.exceptionRecords + " total exceptions flagged", "accent-amber")}
      ${card("Throughput", fmtNum(summary.throughput) + " / sec", "Processing time: " + fmtNum(summary.processingTimeMs) + "ms")}
      ${card("Current Cash", fmtINR(summary.currentCash), "Live operating cash position")}
      ${card("Pending Settlements", fmtINR(summary.pendingSettlements), "Collected, not yet paid out", "accent-amber")}
      ${card("Forecasted Cash (7d)", fmtINR(summary.forecastedCash7d), "Moving-average projection")}
    </div>

    <div class="panel">
      <h3>Financial Summary</h3>
      <div class="kv">
        <div>Total Payment Value</div><div>${fmtINR(summary.totalPaymentValue)}</div>
        <div>Total Settlement Value</div><div>${fmtINR(summary.totalSettlementValue)}</div>
        <div>Total Ledger Value</div><div>${fmtINR(summary.totalLedgerValue)}</div>
        <div>Settlement Gap</div><div>${fmtINR(summary.settlementDifference)}</div>
      </div>
    </div>

    <div class="charts-row">
      <div class="panel"><h3>Reconciliation Status</h3><canvas id="chart-status"></canvas></div>
      <div class="panel"><h3>Exception Types</h3><canvas id="chart-exceptions"></canvas></div>
    </div>
  `;

  renderChart("chart-status", "doughnut",
    ["Matched", "Auto Resolved", "Unresolved"],
    [summary.matchedRecords, summary.autoResolvedRecords, summary.unresolvedRecords],
    ["#22c55e", "#5b8def", "#ef4444"]);

  const ex = exceptionsAnalytics.results;
  renderChart("chart-exceptions", "bar",
    ex.map(e=>e.exception_type), ex.map(e=>e.count), "#7c5cf0");
}

function card(label, value, sub, cls){
  return `<div class="card ${cls||""}"><div class="label">${label}</div>
    <div class="value">${value}</div><div class="sub">${sub||""}</div></div>`;
}

function drawFallbackChart(id, type, labels, values, colors){
  const canvas = document.getElementById(id);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width || 340;
  const h = canvas.height || 200;
  ctx.clearRect(0, 0, w, h);

  if (type === 'doughnut') {
    const total = values.reduce((sum, v) => sum + Math.max(0, Number(v) || 0), 0) || 1;
    let start = -Math.PI / 2;
    values.forEach((v, idx) => {
      const slice = (Math.max(0, Number(v) || 0) / total) * Math.PI * 2;
      ctx.beginPath();
      ctx.moveTo(w / 2, h / 2);
      ctx.arc(w / 2, h / 2, Math.min(w, h) * 0.28, start, start + slice);
      ctx.closePath();
      ctx.fillStyle = Array.isArray(colors) ? colors[idx] : colors;
      ctx.fill();
      start += slice;
    });
    ctx.beginPath();
    ctx.arc(w / 2, h / 2, Math.min(w, h) * 0.14, 0, Math.PI * 2);
    ctx.fillStyle = '#0b1220';
    ctx.fill();
    return;
  }

  if (type === 'bar') {
    const max = Math.max(...values, 1);
    const barCount = values.length;
    const gap = 12;
    const barWidth = (w - 40 - (barCount - 1) * gap) / barCount;
    values.forEach((v, idx) => {
      const barHeight = (v / max) * (h - 30);
      const x = 20 + idx * (barWidth + gap);
      const y = h - 10 - barHeight;
      ctx.fillStyle = Array.isArray(colors) ? colors[idx] : colors;
      ctx.fillRect(x, y, barWidth, barHeight);
      ctx.fillStyle = '#93a2c0';
      ctx.font = '11px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(labels[idx] || '', x + barWidth / 2, h - 2);
    });
    return;
  }

  if (type === 'line') {
    const max = Math.max(...values, 1);
    const min = Math.min(...values, 0);
    const points = values.map((v, idx) => {
      const x = 20 + (idx * (w - 40)) / Math.max(1, values.length - 1);
      const y = h - 20 - ((v - min) / Math.max(1, max - min || 1)) * (h - 40);
      return { x, y, v };
    });
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    points.slice(1).forEach(p => ctx.lineTo(p.x, p.y));
    ctx.strokeStyle = Array.isArray(colors) ? colors[0] : colors;
    ctx.lineWidth = 2;
    ctx.stroke();
    points.forEach(p => {
      ctx.beginPath();
      ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
      ctx.fillStyle = Array.isArray(colors) ? colors[0] : colors;
      ctx.fill();
    });
  }
}

function renderChart(id, type, labels, data, color){
  const ctx = document.getElementById(id);
  if(!ctx) return;
  if(charts[id]) charts[id].destroy();
  if (typeof Chart === 'undefined') {
    const values = Array.isArray(data) ? data : [data];
    const colors = Array.isArray(color) ? color : [color];
    ctx.width = 340;
    ctx.height = 200;
    drawFallbackChart(id, type, labels, values, colors);
    return;
  }
  const isArray = Array.isArray(color);
  charts[id] = new Chart(ctx, {
    type, data:{labels, datasets:[{data, backgroundColor: isArray?color:color, borderRadius: type==='bar'?6:0,
      borderColor:"#0b1220", borderWidth: type==='doughnut'?2:0}]},
    options:{plugins:{legend:{labels:{color:"#93a2c0"}}}, scales: type==='bar'?
      {x:{ticks:{color:"#93a2c0"},grid:{color:"#1f2a44"}}, y:{ticks:{color:"#93a2c0"},grid:{color:"#1f2a44"}}} : {}}
  });
}

// ---------------------------------------------------------------- Reconciliation
async function loadReconciliation(){
  const el = document.getElementById("page-reconciliation");
  el.innerHTML = `
    <div class="filters">
      <input type="text" id="f-search" placeholder="Search transaction ID…">
      <select id="f-status"><option value="">All statuses</option>
        <option>MATCHED</option><option>AUTO_RESOLVED</option><option>UNRESOLVED</option></select>
      <select id="f-exctype"><option value="">All exception types</option></select>
      <select id="f-merchant"><option value="">All merchants</option></select>
      <button class="btn btn-ghost btn-sm" id="f-apply">Apply Filters</button>
    </div>
    <div class="panel"><div id="recon-table-wrap">Loading…</div></div>
  `;
  const merchants = await api("/merchants");
  const msel = document.getElementById("f-merchant");
  merchants.results.forEach(m=> msel.insertAdjacentHTML("beforeend", `<option value="${m.merchantId}">${m.name}</option>`));
  const excTypes = ["AMOUNT_MISMATCH","MISSING_SETTLEMENT","FEE_MISMATCH","TAX_MISMATCH","SETTLEMENT_DELAY",
    "PARTIAL_SETTLEMENT","REFERENCE_MISMATCH","LEDGER_MISMATCH","DUPLICATE_RECORD","UNKNOWN_TRANSACTION","STATUS_MISMATCH"];
  const esel = document.getElementById("f-exctype");
  excTypes.forEach(t=> esel.insertAdjacentHTML("beforeend", `<option value="${t}">${t}</option>`));

  document.getElementById("f-apply").addEventListener("click", fetchReconTable);
  document.getElementById("f-search").addEventListener("keydown", e=>{ if(e.key==="Enter") fetchReconTable(); });
  await fetchReconTable();
}

async function fetchReconTable(){
  const params = new URLSearchParams();
  const search = document.getElementById("f-search").value.trim();
  const status = document.getElementById("f-status").value;
  const exctype = document.getElementById("f-exctype").value;
  const merchant = document.getElementById("f-merchant").value;
  if(search) params.set("search", search);
  if(status) params.set("status", status);
  if(exctype) params.set("exceptionType", exctype);
  if(merchant) params.set("merchantId", merchant);

  const data = await api("/reconciliations?" + params.toString());
  const wrap = document.getElementById("recon-table-wrap");
  if(data.results.length === 0){ wrap.innerHTML = `<div class="empty-state">No records match these filters.</div>`; return; }

  wrap.innerHTML = `<table><thead><tr>
    <th>Transaction</th><th>Merchant</th><th>Payment</th><th>Settlement</th><th>Ledger</th>
    <th>Difference</th><th>Status</th><th>Exception</th><th>Confidence</th><th></th>
  </tr></thead><tbody>
  ${data.results.map(r=>`<tr>
    <td>${r.transaction_id}</td>
    <td>${r.merchant_id || "—"}</td>
    <td>${r.payment_amount!=null ? fmtINR(r.payment_amount) : "—"}</td>
    <td>${r.settlement_amount!=null ? fmtINR(r.settlement_amount) : "—"}</td>
    <td>${r.ledger_amount!=null ? fmtINR(r.ledger_amount) : "—"}</td>
    <td>${r.difference_amount!=null ? fmtINR(r.difference_amount) : "—"}</td>
    <td><span class="badge badge-${r.match_status}">${r.match_status.replace("_"," ")}</span></td>
    <td>${r.exception_type || "—"}</td>
    <td>${r.confidence!=null ? Math.round(r.confidence*100)+"%" : "—"}</td>
    <td><button class="link-btn" onclick="openReconModal('${r.reconciliation_id}')">Details</button></td>
  </tr>`).join("")}
  </tbody></table>
  <div class="muted" style="margin-top:10px">${data.count} record(s)</div>`;
}

async function openReconModal(rid){
  const data = await api("/reconciliations/" + rid);
  const r = data.reconciliation;
  showModal(`
    <button class="close-btn" onclick="closeModal()">✕</button>
    <h3>${r.transaction_id}</h3>
    <span class="badge badge-${r.match_status}">${r.match_status.replace("_"," ")}</span>
    ${r.exception_type ? ` <span class="badge badge-MEDIUM">${r.exception_type}</span>` : ""}
    <div class="kv">
      <div>Payment</div><div>${data.payment ? fmtINR(data.payment.amount) + " (" + data.payment.payment_method + ")" : "No payment record"}</div>
      <div>Settlement</div><div>${data.settlements.length ? data.settlements.map(s=>fmtINR(s.gross_amount)+" — "+s.settlement_status).join(", ") : "None"}</div>
      <div>Ledger</div><div>${data.ledgerEntries.length ? data.ledgerEntries.map(l=>fmtINR(l.ledger_amount)).join(", ") : "None"}</div>
      <div>Difference</div><div>${r.difference_amount!=null ? fmtINR(r.difference_amount) + " (" + r.difference_percentage + "%)" : "—"}</div>
      <div>Reason</div><div>${r.reason || "—"}</div>
      <div>Created</div><div>${fmtDate(r.created_at)}</div>
    </div>
    ${data.exceptions.length ? `<h3>AI Analysis</h3>` + data.exceptions.map(e=>`
      <div class="panel" style="margin-bottom:8px"><b>${e.exception_type}</b> — <span class="badge badge-${e.severity}">${e.severity}</span>
      <p style="font-size:13px">${e.ai_explanation}</p>
      <p style="font-size:12.5px;color:var(--muted)"><b>Recommended:</b> ${e.recommended_action}</p></div>`).join("") : ""}
  `);
}

// ---------------------------------------------------------------- Exceptions
async function loadExceptions(){
  const el = document.getElementById("page-exceptions");
  el.innerHTML = `
    <div class="filters">
      <select id="ex-status"><option value="">All statuses</option>
        <option value="OPEN">OPEN</option><option value="RESOLVED">RESOLVED</option>
        <option value="ESCALATED">ESCALATED</option><option value="IGNORED">IGNORED</option>
        <option value="EXPECTED">EXPECTED</option><option value="AUTO_RESOLVED">AUTO_RESOLVED</option></select>
      <select id="ex-severity"><option value="">All severities</option>
        <option>HIGH</option><option>MEDIUM</option><option>LOW</option></select>
      <button class="btn btn-ghost btn-sm" id="ex-apply">Apply Filters</button>
    </div>
    <div class="panel"><div id="exc-table-wrap">Loading…</div></div>`;
  document.getElementById("ex-apply").addEventListener("click", fetchExceptionsTable);
  await fetchExceptionsTable();
}

async function fetchExceptionsTable(){
  const params = new URLSearchParams();
  const status = document.getElementById("ex-status").value;
  const severity = document.getElementById("ex-severity").value;
  if(status) params.set("status", status);
  if(severity) params.set("severity", severity);
  const data = await api("/exceptions?" + params.toString());
  const wrap = document.getElementById("exc-table-wrap");
  if(data.results.length === 0){ wrap.innerHTML = `<div class="empty-state">No exceptions match these filters.</div>`; return; }
  wrap.innerHTML = `<table><thead><tr>
    <th>Transaction</th><th>Type</th><th>Severity</th><th>Amount</th><th>Status</th><th>Created</th><th>Actions</th>
  </tr></thead><tbody>
  ${data.results.map(e=>`<tr>
    <td>${e.transaction_id}</td><td>${e.exception_type}</td>
    <td><span class="badge badge-${e.severity}">${e.severity}</span></td>
    <td>${fmtINR(e.amount)}</td>
    <td><span class="badge badge-${e.status}">${e.status}</span></td>
    <td>${fmtDate(e.created_at)}</td>
    <td>
      <button class="link-btn" onclick="openExceptionModal('${e.exception_id}')">View</button>
      ${e.status === "OPEN" ? `
        &nbsp;|&nbsp;<button class="link-btn" onclick="actExc('${e.exception_id}','resolve')">Resolve</button>
        &nbsp;|&nbsp;<button class="link-btn" onclick="actExc('${e.exception_id}','escalate')">Escalate</button>
        &nbsp;|&nbsp;<button class="link-btn" onclick="actExc('${e.exception_id}','ignore')">Ignore</button>
        &nbsp;|&nbsp;<button class="link-btn" onclick="actExc('${e.exception_id}','mark-expected')">Mark Expected</button>` : ""}
    </td>
  </tr>`).join("")}
  </tbody></table><div class="muted" style="margin-top:10px">${data.count} exception(s)</div>`;
}

async function actExc(eid, action){
  await api(`/exceptions/${eid}/${action}`, {method:"POST", headers:{"Content-Type":"application/json"}, body:"{}"});
  await fetchExceptionsTable();
}

async function openExceptionModal(eid){
  const e = await api("/exceptions/" + eid);
  showModal(`
    <button class="close-btn" onclick="closeModal()">✕</button>
    <h3>${e.transaction_id} — ${e.exception_type}</h3>
    <span class="badge badge-${e.severity}">${e.severity}</span>
    <span class="badge badge-${e.status}">${e.status}</span>
    <div class="kv">
      <div>Amount</div><div>${fmtINR(e.amount)}</div>
      <div>Root Cause</div><div>${e.root_cause}</div>
      <div>Created</div><div>${fmtDate(e.created_at)}</div>
      <div>Resolved</div><div>${e.resolved_at ? fmtDate(e.resolved_at) : "—"}</div>
    </div>
    <h3>AI Explanation</h3><p style="font-size:13.5px">${e.ai_explanation}</p>
    <h3>Recommended Action</h3><p style="font-size:13.5px">${e.recommended_action}</p>
  `);
}

// ---------------------------------------------------------------- Settlements
async function loadSettlements(){
  const el = document.getElementById("page-settlements");
  el.innerHTML = `<div class="panel"><div id="stl-wrap">Loading…</div></div>`;
  const data = await api("/settlements");
  const wrap = document.getElementById("stl-wrap");
  wrap.innerHTML = `<table><thead><tr>
    <th>Settlement ID</th><th>Transaction</th><th>Merchant</th><th>Gross</th><th>Fee</th><th>Tax</th>
    <th>Net</th><th>Status</th><th>Date</th></tr></thead><tbody>
  ${data.results.slice(0,300).map(s=>`<tr>
    <td>${s.settlement_id}</td><td>${s.transaction_id}</td><td>${s.merchant_id}</td>
    <td>${fmtINR(s.gross_amount)}</td><td>${fmtINR(s.fee)}</td><td>${fmtINR(s.tax)}</td>
    <td>${fmtINR(s.net_amount)}</td>
    <td><span class="badge badge-${s.settlement_status==='SETTLED'?'MATCHED':'OPEN'}">${s.settlement_status}</span></td>
    <td>${fmtDate(s.settlement_date)}</td></tr>`).join("")}
  </tbody></table><div class="muted" style="margin-top:10px">${data.count} settlement(s)</div>`;
}

// ---------------------------------------------------------------- Cash
async function loadCash(){
  const el = document.getElementById("page-cash");
  const cp = await api("/cash-position");
  el.innerHTML = `
    <div class="grid-cards">
      ${card("Current Cash Position", fmtINR(cp.currentCashPosition), "Opening + inflows − outflows", "accent-green")}
      ${card("Opening Cash", fmtINR(cp.openingCash), "Configured with OPENING_CASH")}
      ${card("Total Payment Inflow", fmtINR(cp.totalPaymentInflow), "Successful customer payments")}
      ${card("Pending Settlement", fmtINR(cp.pendingSettlementAmount), "Collected, not yet paid out", "accent-amber")}
      ${card("Fees", fmtINR(cp.fees), "Gateway processing fees")}
      ${card("Taxes", fmtINR(cp.taxes), "GST on fees")}
      ${card("Refunds", fmtINR(cp.refunds), "Reversed payments")}
      ${card("Net Position Change", fmtINR(cp.netPosition), "Vs. opening balance")}
    </div>
    <div class="panel"><h3>Cash Calculation Assumptions</h3>
      <p style="font-size:13px;color:var(--muted)">${cp.assumptions}</p></div>
  `;
}

// ---------------------------------------------------------------- Forecast
async function loadForecast(){
  const el = document.getElementById("page-forecast");
  const data = await api("/cash-forecast");
  el.innerHTML = `
    <div class="panel"><h3>Forward Cash Forecast</h3>
      <table><thead><tr><th>Horizon</th><th>Date</th><th>Expected Inflow</th>
      <th>Expected Outflow</th><th>Projected Balance</th><th>Confidence</th></tr></thead><tbody>
      ${data.forecast.map(f=>`<tr>
        <td>${f.horizonDays} day(s)</td><td>${f.forecastDate}</td>
        <td>${fmtINR(f.expectedInflow)}</td><td>${fmtINR(f.expectedOutflow)}</td>
        <td><b>${fmtINR(f.projectedBalance)}</b></td><td>${f.confidence}%</td>
      </tr>`).join("")}
      </tbody></table>
    </div>
    <div class="panel"><h3>Projected Balance</h3><canvas id="chart-forecast"></canvas></div>
    <div class="panel"><h3>Methodology</h3>
      <p style="font-size:13px;color:var(--muted)">${data.forecast[0] ? data.forecast[0].methodology : ""}
      This is a transparent moving-average model, not a black-box prediction — every number can be traced
      back to imported transaction history.</p></div>
  `;
  renderChart("chart-forecast", "line",
    data.forecast.map(f=>f.horizonDays + "d"), data.forecast.map(f=>f.projectedBalance), "#5b8def");
}

// ---------------------------------------------------------------- Merchants
async function loadMerchants(){
  const el = document.getElementById("page-merchants");
  const data = await api("/merchants");
  el.innerHTML = `<div class="panel"><h3>Merchant Analytics</h3>
    <table><thead><tr><th>Merchant</th><th>Category</th><th>Transactions</th>
    <th>Settled Amount</th><th>Open Exceptions</th><th>Exception Value</th></tr></thead><tbody>
    ${data.results.map(m=>`<tr>
      <td>${m.name}</td><td>${m.category}</td><td>${fmtNum(m.transactionCount)}</td>
      <td>${fmtINR(m.settledAmount)}</td><td>${fmtNum(m.exceptionCount)}</td>
      <td>${fmtINR(m.exceptionValue)}</td></tr>`).join("")}
    </tbody></table></div>
    <div class="panel"><h3>Top Problematic Merchants</h3><canvas id="chart-merchants"></canvas></div>`;
  const top = data.results.filter(m=>m.exceptionCount>0).slice(0,8);
  renderChart("chart-merchants", "bar", top.map(m=>m.name), top.map(m=>m.exceptionCount), "#f59e0b");
}

// ---------------------------------------------------------------- AI Assistant
const SUGGESTED_QUESTIONS = [
  "What is our current cash position?",
  "How many transactions failed reconciliation?",
  "What is the total unresolved amount?",
  "Why is settlement lower than expected?",
  "Which merchants have the highest reconciliation exceptions?",
  "What are the top exception types?",
  "What is the expected cash position tomorrow?",
  "Which transactions have tax mismatches?",
];

async function loadAssistant(){
  const el = document.getElementById("page-assistant");
  el.innerHTML = `
    <div class="panel chat-box">
      <div class="suggestions">${SUGGESTED_QUESTIONS.map(q=>`<span class="suggestion-chip" onclick="askAI('${q.replace(/'/g,"\\'")}')">${q}</span>`).join("")}</div>
      <div class="chat-log" id="chat-log">
        <div class="chat-msg ai">Ask me anything about the current reconciliation dataset — I answer only from real numbers in the database.</div>
      </div>
      <div class="chat-input">
        <input type="text" id="chat-input" placeholder="Type a finance question…">
        <button class="btn btn-primary" id="chat-send">Ask</button>
      </div>
    </div>`;
  const sendBtn = document.getElementById("chat-send");
  const input = document.getElementById("chat-input");
  sendBtn.addEventListener("click", ()=>{
    const v = input.value.trim();
    if(v) askAI(v);
  });
  input.addEventListener("keydown", e=>{
    if(e.key==="Enter"){ const v = e.target.value.trim(); if(v) askAI(v); }
  });
}

async function askAI(question){
  const log = document.getElementById("chat-log");
  const input = document.getElementById("chat-input");
  const sendBtn = document.getElementById("chat-send");
  if(!question || !question.trim()) return;

  const cleanQuestion = String(question).trim();
  log.insertAdjacentHTML("beforeend", `<div class="chat-msg user">${cleanQuestion}</div>`);
  input.value = "";
  input.disabled = true;
  sendBtn.disabled = true;
  sendBtn.textContent = "Working…";
  const loader = document.createElement("div");
  loader.className = "chat-msg ai";
  loader.textContent = "Working on your question…";
  loader.id = "chat-loading";
  log.appendChild(loader);
  log.scrollTop = log.scrollHeight;

  try{
    const data = await api("/ai/query", {method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({question: cleanQuestion})});
    const loading = document.getElementById("chat-loading");
    if(loading) loading.remove();
    log.insertAdjacentHTML("beforeend", `<div class="chat-msg ai">${data.answer}</div>`);
  }catch(e){
    const loading = document.getElementById("chat-loading");
    if(loading) loading.remove();
    log.insertAdjacentHTML("beforeend", `<div class="chat-msg ai error-state">I couldn't answer that from the current dataset: ${e.message}</div>`);
  } finally {
    input.disabled = false;
    sendBtn.disabled = false;
    sendBtn.textContent = "Ask";
    input.focus();
    log.scrollTop = log.scrollHeight;
  }
}
window.askAI = askAI;

// ---------------------------------------------------------------- Audit
async function loadAudit(){
  const el = document.getElementById("page-audit");
  const data = await api("/audit-logs");
  el.innerHTML = `<div class="panel"><h3>Audit Trail</h3>
    <table><thead><tr><th>Action</th><th>Actor</th><th>Transaction</th><th>Old → New</th><th>Reason</th><th>Timestamp</th></tr></thead><tbody>
    ${data.results.map(a=>`<tr>
      <td>${a.action}</td><td>${a.actor}</td><td>${a.transaction_id}</td>
      <td>${a.old_status} → ${a.new_status}</td><td>${a.reason||"—"}</td><td>${fmtDate(a.timestamp)}</td>
    </tr>`).join("")}
    </tbody></table>
    ${data.results.length===0 ? '<div class="empty-state">No audit events yet.</div>' : ""}
    </div>`;
}

// ---------------------------------------------------------------- Settings
async function loadSettings(){
  const el = document.getElementById("page-settings");
  const health = await api("/health");
  el.innerHTML = `<div class="panel"><h3>System Status</h3>
    <div class="kv">
      <div>Status</div><div><span class="badge badge-MATCHED">${health.status}</span></div>
      <div>Records Loaded</div><div>${fmtNum(health.recordsLoaded ?? health.recordsSeeded)}</div>
      <div>AI Provider</div><div>${health.aiProvider}</div>
      <div>Server Time</div><div>${fmtDate(health.time)}</div>
    </div></div>
    <div class="panel"><h3>Razorpay Integration</h3>
      <p class="muted" style="margin-bottom:10px">${health.razorpayStatus === "Not Configured" ? "Optional Test Mode connectivity check is not configured. This app does not initiate payments." : "Razorpay Test Mode connectivity check is configured."}</p>
      <div class="kv"><div>Connection Status</div><div><span class="badge ${health.razorpayStatus.includes('Connected') ? 'badge-MATCHED' : 'badge-OPEN'}">${health.razorpayStatus}</span></div></div>
    </div>
    <div class="panel"><h3>Configuration</h3>
      <p class="muted">Set APP_USERNAME and APP_PASSWORD to protect the app, FINRECON_ALLOW_IMPORT=true to enable imports, FINRECON_DB_PATH to use persistent storage, and OPENING_CASH to configure the cash starting balance. AI_PROVIDER, OPENAI_API_KEY and OPENAI_MODEL are optional. Razorpay is only a test-mode connectivity check; this app does not move money.</p></div>`;
}

// ---------------------------------------------------------------- Modal
function showModal(html){
  document.getElementById("modal-body").innerHTML = html;
  document.getElementById("modal-backdrop").classList.remove("hidden");
}
function closeModal(){ document.getElementById("modal-backdrop").classList.add("hidden"); }
window.closeModal = closeModal;
window.openReconModal = openReconModal;
window.openExceptionModal = openExceptionModal;
window.actExc = actExc;
document.getElementById("modal-backdrop").addEventListener("click", e=>{
  if(e.target.id === "modal-backdrop") closeModal();
});

// ---------------------------------------------------------------- Data controls
document.getElementById("btn-refresh").addEventListener("click", refreshCurrentView);
document.getElementById("btn-run").addEventListener("click", runReconciliation);
document.getElementById("btn-import").addEventListener("click", openImportModal);

function currentPage(){
  return document.querySelector(".nav-item.active").dataset.page;
}

async function refreshCurrentView(){
  const refresh = LIVE_REFRESHERS[activePage];
  const editing = document.activeElement && /^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName);
  if(editing){
    setLiveStatus("live", "Finish editing before refreshing");
    return;
  }
  if(!refresh){
    setLiveStatus("live", "This view has no refreshable data");
    return;
  }
  await refreshActivePage();
}

async function runReconciliation(){
  const overlay = document.getElementById("progress-overlay");
  const stepsEl = document.getElementById("progress-steps");
  const PLANNED = ["Existing source records checked","Records matched",
    "Exceptions classified","AI analysis completed","Cash position calculated","Forecast generated"];
  stepsEl.innerHTML = PLANNED.map(s=>`<li>${s}</li>`).join("");
  overlay.classList.remove("hidden");
  try{
    const data = await api("/reconciliation/run", {method:"POST"});
    const items = stepsEl.querySelectorAll("li");
    for(let i=0;i<items.length;i++){
      await new Promise(r=>setTimeout(r,150));
      items[i].classList.add("done");
      items[i].textContent = "✓ " + items[i].textContent;
    }
    await new Promise(r=>setTimeout(r,400));
    showBanner(`Reconciliation complete: ${data.summary.recordsProcessed} records processed, `+
      `${data.summary.matchRate}% match rate, ${data.summary.unresolvedRecords} unresolved exceptions.`);
  }catch(e){
    showBanner("Reconciliation failed: " + e.message, true);
  }finally{
    overlay.classList.add("hidden");
    gotoPage(currentPage());
  }
}

function openImportModal(){
  showModal(`<button class="close-btn" onclick="closeModal()" aria-label="Close">×</button>
    <h3>Import source records</h3>
    <p class="muted">Choose one CSV export for each source. Import replaces the active dataset, then runs reconciliation.</p>
    <p class="import-warning">Imports are disabled until the server has APP_USERNAME, APP_PASSWORD, FINRECON_ALLOW_IMPORT=true, and FINRECON_DB_PATH configured to persistent storage. The app does not move money. Do not upload confidential records to an unprotected or ephemeral deployment.</p>
    <form id="import-form" class="import-form">
      <label>Payments CSV<input type="file" name="payments" accept=".csv,text/csv" required></label>
      <label>Settlements CSV<input type="file" name="settlements" accept=".csv,text/csv" required></label>
      <label>Ledger CSV<input type="file" name="ledger" accept=".csv,text/csv" required></label>
      <details><summary>Required CSV columns</summary>
        <p><strong>Payments</strong>: transaction_id, payment_id, amount, fee, tax, status, transaction_timestamp, bank_reference. Optional: merchant_id, customer_id, upi_id, currency, payment_method, settlement_date, gateway_reference, net_amount.</p>
        <p><strong>Settlements</strong>: settlement_id, transaction_id, gross_amount, fee, tax, net_amount, settlement_date, settlement_status, bank_reference. Optional: merchant_id, settlement_reference.</p>
        <p><strong>Ledger</strong>: ledger_id, transaction_id, ledger_amount. Optional: merchant_id, debit, credit, tax_amount, fee_amount, entry_date, ledger_status, reference. Include headers even when a source has no rows.</p>
      </details>
      <button class="btn btn-primary" type="submit">Import and Reconcile</button>
    </form>`);
  document.getElementById("import-form").addEventListener("submit", submitImport);
}

async function submitImport(event){
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button[type=submit]");
  button.disabled = true;
  button.textContent = "Importing…";
  try{
    const result = await api("/import", {method:"POST", body:new FormData(form)});
    closeModal();
    showBanner(`${result.message} ${result.counts.payments} payments, ${result.counts.settlements} settlements, ${result.counts.ledger} ledger entries.`);
    await gotoPage("dashboard");
  }catch(e){
    showBanner("Import failed: " + e.message, true);
    button.disabled = false;
    button.textContent = "Import and Reconcile";
  }
}

function showBanner(text, isError){
  const b = document.getElementById("banner");
  b.textContent = text;
  b.classList.remove("hidden");
  b.style.background = isError ? "rgba(239,68,68,.12)" : "";
  b.style.borderColor = isError ? "rgba(239,68,68,.35)" : "";
  b.style.color = isError ? "#fca5a5" : "";
  setTimeout(()=> b.classList.add("hidden"), 6000);
}

const LOADERS = {
  dashboard: loadDashboard, reconciliation: loadReconciliation, exceptions: loadExceptions,
  settlements: loadSettlements, cash: loadCash, forecast: loadForecast, merchants: loadMerchants,
  assistant: loadAssistant, audit: loadAudit, settings: loadSettings,
};

const LIVE_REFRESHERS = {
  dashboard: loadDashboard,
  reconciliation: fetchReconTable,
  exceptions: fetchExceptionsTable,
  settlements: loadSettlements,
  cash: loadCash,
  forecast: loadForecast,
  merchants: loadMerchants,
  audit: loadAudit,
  settings: loadSettings,
};

// ---------------------------------------------------------------- Init
gotoPage("dashboard");
window.setInterval(refreshActivePage, LIVE_REFRESH_MS);
