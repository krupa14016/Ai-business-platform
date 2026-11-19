import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./App.css";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

const NAV_ITEMS = [
  { label: "Overview", mark: "◫" },
  { label: "AI Assistant", mark: "✳" },
  { label: "Analytics", mark: "▥" },
  { label: "ML Insights", mark: "⌁" },
];

const moneyMetrics = new Set(["revenue", "gross_profit", "operating_income", "net_income"]);

function formatValue(metric, value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "—";
  const n = Number(value);
  if (moneyMetrics.has(metric)) return `$${(n / 1e9).toFixed(2)}B`;
  if (metric?.endsWith("_pct")) return `${n.toFixed(2)}%`;
  return `${n.toFixed(2)}x`;
}

function formatChange(value, unit) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "N/A";
  const n = Number(value);
  const sign = n > 0 ? "+" : "";
  if (unit === "currency") return `${sign}$${(n / 1e9).toFixed(2)}B`;
  if (unit === "percentage_points") return `${sign}${n.toFixed(2)} pp`;
  if (unit === "ratio_points") return `${sign}${n.toFixed(2)}x`;
  return `${sign}${n.toFixed(2)}`;
}

async function readJson(url, options) {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || body.message || `Request failed (${response.status})`);
  }
  return body;
}

function StatCard({ label, value, detail, mark }) {
  return (
    <article className="stat-card">
      <div className="stat-top"><span>{label}</span><span className="stat-mark">{mark}</span></div>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function WelcomeScreen({ onEnter, apiOnline }) {
  return (
    <main className="welcome-screen">
      <div className="welcome-glow glow-one" />
      <div className="welcome-glow glow-two" />
      <nav className="welcome-nav">
        <div className="brand"><span className="brand-symbol">A</span><span>AI<span className="brand-light">·BI</span></span></div>
        <span className="nav-caption">FINANCIAL INTELLIGENCE PLATFORM</span>
      </nav>
      <section className="welcome-content">
        <div className="welcome-copy">
          <div className="eyebrow"><span className="pulse-dot" /> DATA-DRIVEN DECISIONS</div>
          <h1>Turn financial data<br /><span>into clear direction.</span></h1>
          <p>Explore verified financial performance, ask questions in natural language, and uncover evidence-based insights from your company data.</p>
          <div className="welcome-actions">
            <button className="button-primary" onClick={onEnter}>Enter workspace <span>→</span></button>
            <span className="connection-label"><i className={apiOnline ? "dot online" : "dot"} /> {apiOnline ? "Backend connected" : "Backend connection pending"}</span>
          </div>
          <div className="welcome-points"><span>01 / Verified data</span><span>02 / AI-assisted analysis</span><span>03 / Actionable insights</span></div>
        </div>
        <div className="welcome-art" aria-hidden="true">
          <div className="art-orbit orbit-a" /><div className="art-orbit orbit-b" />
          <div className="art-core"><div className="art-core-inner">AI</div></div>
          <div className="art-chip chip-a">SEC DATA <b>● LIVE</b></div>
          <div className="art-chip chip-b">ANALYTICS <b>↗</b></div>
          <div className="art-chip chip-c">INTELLIGENCE <b>✳</b></div>
        </div>
      </section>
      <footer className="welcome-footer"><span>AI·BI PLATFORM</span><span>BUILT FOR FINANCIAL CLARITY</span></footer>
    </main>
  );
}

function Sidebar({ page, onNavigate, apiOnline }) {
  return (
    <aside className="sidebar">
      <div className="brand side-brand"><span className="brand-symbol">A</span><span>AI<span className="brand-light">·BI</span></span></div>
      <div className="side-label">WORKSPACE</div>
      <nav className="side-nav">
        {NAV_ITEMS.map(item => (
          <button key={item.label} className={`nav-item ${page === item.label ? "active" : ""}`} onClick={() => onNavigate(item.label)}>
            <span className="nav-mark">{item.mark}</span>{item.label}
            {item.label === "AI Assistant" && <span className="new-tag">AI</span>}
          </button>
        ))}
      </nav>
      <div className="side-label side-label-lower">DATA SOURCE</div>
      <div className="source-card"><span className="source-icon">▤</span><div><b>PostgreSQL</b><small>{apiOnline ? "Connected" : "Awaiting connection"}</small></div><i className={apiOnline ? "dot online" : "dot"} /></div>
      <div className="sidebar-bottom"><div className="avatar">AI</div><div><b>AI BI Workspace</b><small>Local development</small></div></div>
    </aside>
  );
}

function OverviewPage({ apiOnline, kpis, revenueRows, onNavigate, onRefresh, refreshing }) {
  const latest = kpis?.latest || kpis?.latest_kpis || {};
  const metrics = [
    ["Revenue", latest.revenue, "revenue", "↗"],
    ["Net income", latest.net_income, "net_income", "＋"],
    ["Operating income", latest.operating_income, "operating_income", "◈"],
    ["Gross profit", latest.gross_profit, "gross_profit", "◇"],
  ];
  const rows = revenueRows.slice(-8);
  const max = Math.max(1, ...rows.map(r => r.revenue));
  return (
    <div className="page-stack">
      <div className="page-heading">
        <div><div className="eyebrow">YOUR FINANCIAL COMMAND CENTER</div><h1>Business overview</h1><p>A high-level view of the latest available financial performance.</p></div>
        <button className="button-secondary" onClick={onRefresh} disabled={refreshing}>{refreshing ? "Refreshing…" : "↻ Refresh data"}</button>
      </div>
      {!apiOnline && <div className="notice">Backend is not connected. Start your FastAPI server at <code>{API_BASE}</code> to load live financial data.</div>}
      <div className="stat-grid">
        {metrics.map(([label, value, metric, mark]) => <StatCard key={metric} label={label} value={formatValue(metric, value)} detail={latest.fiscal_year ? `FY${latest.fiscal_year}` : "Latest available period"} mark={mark} />)}
      </div>
      <section className="panel chart-panel">
        <div className="section-heading"><div><span className="panel-kicker">HISTORICAL PERFORMANCE</span><h2>Revenue trend</h2><p>Annual revenue, shown in USD billions where available.</p></div><span className="chart-unit">USD · BILLIONS</span></div>
        {rows.length ? <div className="bar-chart">
          {rows.map(row => <div className="bar-column" key={row.year}><div className="bar-value">{row.revenue.toFixed(1)}</div><div className="bar-track"><div className="bar-fill" style={{ height: `${Math.max(3, row.revenue / max * 100)}%` }} /></div><small>{row.year}</small></div>)}
        </div> : <div className="empty-state">Historical chart data will appear when the KPI endpoint returns annual rows.</div>}
      </section>
      <div className="quick-grid">
        <button className="quick-card" onClick={() => onNavigate("AI Assistant")}><span>✳</span><b>Ask your financial data</b><small>Explore figures using natural language.</small><em>Open assistant →</em></button>
        <button className="quick-card" onClick={() => onNavigate("Analytics")}><span>▥</span><b>Explore financial insights</b><small>Review changes, recommendations and data coverage.</small><em>View analytics →</em></button>
      </div>
    </div>
  );
}

function AnalyticsPage({ insights, loading, error, onRefresh }) {
  if (loading && !insights) return <div className="panel state-panel"><div className="loader" /><h2>Loading financial insights</h2><p>Retrieving the verified analytics report.</p></div>;
  if (error && !insights) return <div className="panel state-panel"><h2>Unable to load financial insights</h2><p>{error}</p><button className="button-secondary" onClick={onRefresh}>Try again</button></div>;
  if (!insights?.metrics) return <div className="panel state-panel"><h2>Financial insights unavailable</h2><p>The API did not return a usable insights report.</p><button className="button-secondary" onClick={onRefresh}>Refresh insights</button></div>;

  const metrics = Array.isArray(insights.metrics) ? insights.metrics : Object.values(insights.metrics);
  const observations = Array.isArray(insights.observations) ? insights.observations : [];
  const recommendations = Array.isArray(insights.recommendations) ? insights.recommendations : [];
  const gaps = Array.isArray(insights.data_gaps) ? insights.data_gaps : [];
  return (
    <div className="page-stack">
      <div className="page-heading"><div><div className="eyebrow">FINANCIAL INTELLIGENCE</div><h1>Financial analytics</h1><p>Historical performance, evidence-based findings and recommendations.</p></div><button className="button-secondary" onClick={onRefresh} disabled={loading}>{loading ? "Refreshing…" : "↻ Refresh insights"}</button></div>
      {error && <div className="notice warning">Refresh warning: {error}. Showing the last successfully loaded report.</div>}
      <div className="stat-grid four">
        <StatCard label="Latest fiscal year" value={insights.latest_fiscal_year ?? "—"} detail="Latest reporting period" mark="◷" />
        <StatCard label="Tracked metrics" value={metrics.length} detail="Financial indicators" mark="▥" />
        <StatCard label="Observations" value={observations.length} detail="Evidence-based findings" mark="↗" />
        <StatCard label="Recommendations" value={recommendations.length} detail="Areas to review" mark="✳" />
      </div>
      <section className="panel"><div className="section-heading"><div><span className="panel-kicker">FINANCIAL PERFORMANCE</span><h2>Key metric analysis</h2><p>Latest available values compared with the previous available year.</p></div></div>
        <div className="metric-grid">{metrics.map((item, i) => <article className="metric-card" key={item.metric || i}><div className="metric-top"><span>{item.label || (item.metric || "Metric").replaceAll("_", " ")}</span><span className={item.direction === "increased" ? "trend up" : item.direction === "decreased" ? "trend down" : "trend"}>{item.direction || "—"}</span></div><strong>{item.status === "unavailable" ? "Unavailable" : formatValue(item.metric, item.latest?.value)}</strong><div className="metric-bottom"><span>Previous: {formatValue(item.metric, item.previous?.value)}</span><b>{formatChange(item.change, item.change_unit)}</b></div><small>{item.previous?.fiscal_year ? `FY${item.previous.fiscal_year} → FY${item.latest?.fiscal_year}` : `${item.observations_count || 0} observations`}</small></article>)}</div>
      </section>
      <section className="panel"><div className="section-heading"><div><span className="panel-kicker">DATA-BASED FINDINGS</span><h2>Financial observations</h2></div></div>{observations.length ? <div className="stack-list">{observations.map((item, i) => <div className="list-row" key={item.metric || i}><span className="list-icon">↗</span><div><b>{(item.metric || "Observation").replaceAll("_", " ")}</b><p>{item.message || "No additional description supplied."}</p></div></div>)}</div> : <div className="empty-state">No observations are currently available.</div>}</section>
      <section className="panel"><div className="section-heading"><div><span className="panel-kicker">DECISION SUPPORT</span><h2>Recommendations</h2></div></div>{recommendations.length ? <div className="stack-list">{recommendations.map((item, i) => <div className="list-row" key={`${item.area || "recommendation"}-${i}`}><span className="list-icon shield">◇</span><div><div className="recommendation-heading"><b>{item.area || "Recommendation"}</b><span>{item.priority || "Review"}</span></div><p>{item.recommendation}</p><small>Evidence: {(item.evidence_metrics || []).join(", ").replaceAll("_", " ") || "Not specified"}</small></div></div>)}</div> : <div className="empty-state">No recommendations were generated from the available data.</div>}</section>
      <section className="panel"><div className="section-heading"><div><span className="panel-kicker">DATA COVERAGE</span><h2>Historical data gaps</h2><p>Years where a metric does not have an available value.</p></div></div>{gaps.length ? <div className="gap-grid">{gaps.map((item, i) => <div className="gap-card" key={item.metric || i}><b>{item.label || item.metric}</b><div><span>Available: {(item.available_years || []).length}</span><span>Missing: {(item.missing_years || []).length}</span></div><small>Missing fiscal years: {(item.missing_years || []).join(", ") || "None"}</small></div>)}</div> : <div className="empty-state">No historical data gaps were reported.</div>}</section>
    </div>
  );
}

function AssistantPage({ apiOnline }) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([{ role: "assistant", text: "Hello! Ask a question about the financial data available in your AI-BI platform." }]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const chatMessagesRef = useRef(null);

  const suggestions = [
    "What was Apple's revenue in 2024?",
    "Compare revenue in 2022 and 2023",
    "Which year had the highest revenue?",
    "Show Apple's profitability trend",
    "What was Apple's current ratio in 2025?",
  ];

  useEffect(() => {
    const chatArea = chatMessagesRef.current;
    if (chatArea) {
      chatArea.scrollTo({
        top: chatArea.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages, sending]);

  const send = async (event) => {
    event?.preventDefault();
    const prompt = question.trim();
    if (!prompt || sending) return;
    setMessages(prev => [...prev, { role: "user", text: prompt }]);
    setQuestion(""); setError(""); setSending(true);
    try {
      const result = await readJson(`${API_BASE}/api/chat/query`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: prompt }),
      });
      const answer = result.answer || result.response || result.message || JSON.stringify(result, null, 2);
      setMessages(prev => [...prev, { role: "assistant", text: String(answer) }]);
    } catch (err) {
      setError(err.message || "The assistant request failed.");
    } finally { setSending(false); }
  };
  return <div className="page-stack assistant-page"><div className="page-heading"><div><div className="eyebrow">NATURAL LANGUAGE ANALYTICS</div><h1>AI assistant</h1><p>Ask questions and explore your verified financial data.</p></div></div>
    {!apiOnline && <div className="notice">Connect the backend to send questions.</div>}
    <section className="panel chat-panel"><div className="chat-header"><div className="chat-avatar">✳</div><div><b>Financial data assistant</b><small>Answers from your platform API</small></div><span className={apiOnline ? "chat-status online-text" : "chat-status"}>{apiOnline ? "● ONLINE" : "● OFFLINE"}</span></div>
      <div className="chat-messages" ref={chatMessagesRef}>{messages.map((m, i) => <div key={i} className={`chat-message ${m.role}`}><span className="message-avatar">{m.role === "assistant" ? "AI" : "YOU"}</span><div>{m.text}</div></div>)}{sending && <div className="chat-message assistant"><span className="message-avatar">AI</span><div className="typing">Analyzing your question…</div></div>}</div>
      {error && <div className="chat-error">{error}</div>}
      <div className="chat-suggestions">
        <span className="suggestions-label">SUGGESTED QUESTIONS</span>
        <div className="suggestion-list">
          {suggestions.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              className="suggestion-chip"
              onClick={() => setQuestion(suggestion)}
              disabled={sending}
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>
      <form className="chat-form" onSubmit={send}><input value={question} onChange={e => setQuestion(e.target.value)} placeholder="e.g. What was Apple's revenue in 2024?" aria-label="Ask a financial question" /><button className="button-primary" disabled={!question.trim() || sending}>Send ↑</button></form>
      <div className="chat-hint">Responses depend on the financial data and query support configured in your backend.</div>
    </section>
  </div>;
}

function PlaceholderPage({ page, onNavigate }) {
  return <div className="panel state-panel"><div className="placeholder-symbol">⌁</div><h2>{page}</h2><p>This workspace section is a placeholder. The current frontend integration includes Overview, AI Assistant and Financial Analytics.</p><button className="button-secondary" onClick={() => onNavigate("Analytics")}>Explore financial analytics →</button></div>;
}

export default function App() {
  const [entered, setEntered] = useState(false);
  const [page, setPage] = useState("Overview");
  const [apiOnline, setApiOnline] = useState(false);
  const [kpis, setKpis] = useState(null);
  const [revenueRows, setRevenueRows] = useState([]);
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(false);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [error, setError] = useState("");
  const [insightsError, setInsightsError] = useState("");

  const loadOverview = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const health = await readJson(`${API_BASE}/health`);
      setApiOnline(Boolean(health));
      const payload = await readJson(`${API_BASE}/api/analytics/kpis`);
      setKpis(payload);
      let rows = Array.isArray(payload) ? payload : payload.data || payload.kpis || payload.results || payload.annual_kpis || [];
      if (!Array.isArray(rows) && rows && typeof rows === "object") rows = Object.values(rows);
      if (Array.isArray(rows)) {
        const mapped = rows.map(row => ({
          year: String(row.fiscal_year ?? row.year ?? ""),
          revenue: Number(row.revenue) / 1e9,
        })).filter(row => row.year && Number.isFinite(row.revenue)).sort((a, b) => Number(a.year) - Number(b.year));
        setRevenueRows(mapped);
      }
    } catch (err) {
      setApiOnline(false);
      setError(err.message || "Could not load KPI data.");
    } finally { setLoading(false); }
  }, []);

  const loadInsights = useCallback(async () => {
    setInsightsLoading(true); setInsightsError("");
    try {
      const payload = await readJson(`${API_BASE}/api/analytics/insights`);
      if (payload.status === "unavailable") throw new Error(payload.message || "Financial insights are unavailable.");
      if (!payload.metrics) throw new Error("The insights response does not contain metrics.");
      setInsights(payload);
    } catch (err) { setInsightsError(err.message || "Could not load financial insights."); }
    finally { setInsightsLoading(false); }
  }, []);

  useEffect(() => { loadOverview(); loadInsights(); }, [loadOverview, loadInsights]);

  const navigate = (nextPage) => setPage(nextPage);
  const latestYear = useMemo(() => insights?.latest_fiscal_year || kpis?.latest?.fiscal_year || "—", [insights, kpis]);

  return !entered ? <WelcomeScreen onEnter={() => setEntered(true)} apiOnline={apiOnline} /> : (
    <div className="app-shell">
      <Sidebar page={page} onNavigate={navigate} apiOnline={apiOnline} />
      <main className="main-area">
        <header className="topbar"><div className="breadcrumb"><span>Workspace</span><span className="crumb-separator">/</span><b>{page}</b></div><div className="topbar-right"><span className={apiOnline ? "status-text online-text" : "status-text"}><i className={apiOnline ? "dot online" : "dot"} />{apiOnline ? "API connected" : "API offline"}</span><span className="top-avatar">AI</span></div></header>
        <div className="page-content">
          {page === "Overview" && <OverviewPage apiOnline={apiOnline} kpis={kpis} revenueRows={revenueRows} onNavigate={navigate} onRefresh={loadOverview} refreshing={loading} />}
          {page === "Analytics" && <AnalyticsPage insights={insights} loading={insightsLoading} error={insightsError} onRefresh={loadInsights} />}
          {page === "AI Assistant" && <AssistantPage apiOnline={apiOnline} />}
          {page === "ML Insights" && <PlaceholderPage page="ML Insights" onNavigate={navigate} />}
          {error && page === "Overview" && <p className="inline-error">{error}</p>}
          <footer className="workspace-footer"><span>AI·BI PLATFORM</span><span>FINANCIAL DATA · VERIFIED ANALYTICS</span><span>FY{latestYear}</span></footer>
        </div>
      </main>
    </div>
  );
}
