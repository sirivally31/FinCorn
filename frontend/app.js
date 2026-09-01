const API = "/api";
let charts = {};

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
  document.querySelectorAll(".nav-item").forEach(b=>b.classList.toggle("active", b.dataset.page===page));
  document.querySelectorAll(".page").forEach(p=>p.classList.add("hidden"));
  document.getElementById("page-"+page).classList.remove("hidden");
  document.getElementById("page-title").textContent = PAGE_META[page].title;
  document.getElementById("page-subtitle").textContent = PAGE_META[page].sub;
  try{
    await LOADERS[page]();
  }catch(e){
    document.getElementById("page-"+page).innerHTML = `<div class="error-state">Failed to load: ${e.message}</div>`;
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

function renderChart(id, type, labels, data, color){
  const ctx = document.getElementById(id);
  if(!ctx) return;
  if(charts[id]) charts[id].destroy();
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
      ${card("Opening Cash", fmtINR(cp.openingCash), "Fixed demo constant")}
      ${card("Total Payment Inflow", fmtINR(cp.totalPaymentInflow), "Successful customer payments")}
      ${card("Pending Settlement", fmtINR(cp.pendingSettlementAmount), "Collected, not yet paid out", "accent-amber")}
      ${card("Fees", fmtINR(cp.fees), "Gateway processing fees")}
      ${card("Taxes", fmtINR(cp.taxes), "GST on fees")}
      ${card("Refunds", fmtINR(cp.refunds), "Reversed payments")}
      ${card("Net Position Change", fmtINR(cp.netPosition), "Vs. opening balance")}
    </div>
    <div class="panel"><h3>Simplified Demo Accounting Assumptions</h3>
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
      back to actual synthetic transaction history.</p></div>
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
        <input type="text" id="chat-input" placeholder="Ask a finance question…">
        <button class="btn btn-primary" id="chat-send">Send</button>
      </div>
    </div>`;
  document.getElementById("chat-send").addEventListener("click", ()=>{
    const v = document.getElementById("chat-input").value.trim();
    if(v) askAI(v);
  });
  document.getElementById("chat-input").addEventListener("keydown", e=>{
    if(e.key==="Enter"){ const v = e.target.value.trim(); if(v) askAI(v); }
  });
}

async function askAI(question){
  const log = document.getElementById("chat-log");
  log.insertAdjacentHTML("beforeend", `<div class="chat-msg user">${question}</div>`);
  document.getElementById("chat-input").value = "";
  log.scrollTop = log.scrollHeight;
  try{
    const data = await api("/ai/query", {method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({question})});
    log.insertAdjacentHTML("beforeend", `<div class="chat-msg ai">${data.answer}</div>`);
  }catch(e){
    log.insertAdjacentHTML("beforeend", `<div class="chat-msg ai">I couldn't process that: ${e.message}</div>`);
  }
  log.scrollTop = log.scrollHeight;
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
      <div>Records Seeded</div><div>${fmtNum(health.recordsSeeded)}</div>
      <div>AI Provider</div><div>${health.aiProvider}</div>
      <div>Server Time</div><div>${fmtDate(health.time)}</div>
    </div></div>
    <div class="panel"><h3>Razorpay Integration</h3>
      <p class="muted" style="margin-bottom:10px">${health.razorpayStatus === "Not Configured" ? "Razorpay Test Mode not configured — running synthetic evaluation mode." : "Razorpay Test Mode configured."}</p>
      <div class="kv"><div>Connection Status</div><div><span class="badge ${health.razorpayStatus.includes('Connected') ? 'badge-MATCHED' : 'badge-OPEN'}">${health.razorpayStatus}</span></div></div>
    </div>
    <div class="panel"><h3>Demo Credentials</h3>
      <div class="kv"><div>Email</div><div>admin@finrecon.ai</div><div>Password</div><div>Demo@123</div></div>
      <p class="muted">Authentication is a demo placeholder only — not enforced in this build.</p></div>
    <div class="panel"><h3>Configuration</h3>
      <p class="muted">AI_PROVIDER, OPENAI_API_KEY and OPENAI_MODEL are set via environment variables.
      Without an API key, FinRecon AI uses a fully deterministic mock AI provider so the demo never breaks.
      Razorpay integration is purely an optional test-mode connectivity check.</p></div>`;
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

// ---------------------------------------------------------------- Demo controls
document.getElementById("btn-refresh").addEventListener("click", ()=> gotoPage(currentPage()));
document.getElementById("btn-run").addEventListener("click", runReconciliation);
document.getElementById("btn-reset").addEventListener("click", resetDemo);

function currentPage(){
  return document.querySelector(".nav-item.active").dataset.page;
}

async function runReconciliation(){
  const overlay = document.getElementById("progress-overlay");
  const stepsEl = document.getElementById("progress-steps");
  const PLANNED = ["Payments loaded","Settlements loaded","Ledger loaded","Records matched",
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

async function resetDemo(){
  if(!confirm("This will regenerate synthetic data and re-run reconciliation. Continue?")) return;
  try{
    const data = await api("/demo/reset", {method:"POST"});
    showBanner(data.message);
  }catch(e){
    showBanner("Reset failed: " + e.message, true);
  }
  gotoPage(currentPage());
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

// ---------------------------------------------------------------- Init
gotoPage("dashboard");
