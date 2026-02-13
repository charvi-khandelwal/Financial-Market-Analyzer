"use client";

import { useEffect, useMemo, useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { API_BASE, getJSON, postJSON } from "./lib/api";

type Theme = "light" | "dark";

type SignalRow = {
  asset_class: "stock" | "fx" | "crypto";
  symbol: string;
  price: number | null;
  momentum_1d: number | null;
  sentiment: number | null;
  signal_score: number;
  signal: "buy" | "sell" | "hold";
  risk_score: number;
  last_refreshed: string | null;
};

type UniverseTicker = {
  symbol: string;
  name: string;
  exchange: string;
  assetType: string;
  ipoDate: string;
  delistingDate: string;
  status: string;
};

type MarketOverview = {
  generated_at: string;
  coverage: {
    stocks: number;
    fx_pairs: number;
    cryptos: number;
  };
  guidance: {
    public_mood: string;
    expected_market_direction: string;
    safest_bets: SignalRow[];
    riskiest_bets: SignalRow[];
    buy_candidates: SignalRow[];
    sell_candidates: SignalRow[];
    hold_candidates: SignalRow[];
    signals: SignalRow[];
    disclaimer: string;
  };
  news: {
    overall_average_sentiment: number | null;
    items: Array<{
      title: string;
      url: string;
      source: string;
      time_published: string;
    }>;
  };
  notes: string[];
  errors: Array<{ asset_class: string; symbol: string; error: string }>;
};

type UniverseSnapshotResponse = {
  state: string;
  count: number;
  updated_every_minutes: number;
  tickers: UniverseTicker[];
};

type RefreshStatus = {
  state: "idle" | "running" | "completed" | "failed";
  reason: string | null;
  started_at: string | null;
  finished_at: string | null;
  total_steps: number;
  completed_steps: number;
  progress_percent: number;
  current_step: string | null;
  message: string | null;
  error: string | null;
  latest_generated_at: string | null;
  is_running: boolean;
};

type RefreshStartResponse = {
  accepted: boolean;
  status: RefreshStatus;
};

type ReportKind = "stock" | "fx" | "crypto";

const navItems = ["Dashboard", "Universe", "Signals", "Sentiment", "Reports"];
const CALLS_PER_MINUTE_ESTIMATE = 100;
const CALL_SPACING_SECONDS = 1.1;
const DEFAULT_REFRESH_CALLS = 25;

function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "--";
  return `${(value * 100).toFixed(2)}%`;
}

function formatPrice(value: number | null | undefined, assetClass: string): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "--";
  if (assetClass === "fx") return value.toFixed(5);
  return value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function nextHalfHourLabel() {
  const now = new Date();
  const next = new Date(now);
  if (now.getMinutes() < 30) {
    next.setMinutes(30, 0, 0);
  } else {
    next.setHours(next.getHours() + 1);
    next.setMinutes(0, 0, 0);
  }
  return next.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatElapsed(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const mm = Math.floor(s / 60);
  const ss = s % 60;
  return `${mm}:${ss.toString().padStart(2, "0")}`;
}

function estimateRefreshMs(overview: MarketOverview | null): number {
  const coverage = overview?.coverage;
  const calls =
    coverage && Number.isFinite(coverage.stocks + coverage.fx_pairs + coverage.cryptos)
      ? coverage.stocks + coverage.fx_pairs + coverage.cryptos + 1
      : DEFAULT_REFRESH_CALLS;
  const base = calls * CALL_SPACING_SECONDS;
  const throttleWindows = Math.max(0, Math.ceil(calls / CALLS_PER_MINUTE_ESTIMATE) - 1);
  const throttleWait = throttleWindows * (60 - CALL_SPACING_SECONDS * CALLS_PER_MINUTE_ESTIMATE);
  return Math.max(90_000, (base + throttleWait + 25) * 1000);
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export default function Page() {
  const [theme, setTheme] = useState<Theme>("light");
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [overview, setOverview] = useState<MarketOverview | null>(null);
  const [history, setHistory] = useState<
    Array<{ generated_at: string; news: { overall_average_sentiment: number | null } }>
  >([]);
  const [universe, setUniverse] = useState<UniverseTicker[]>([]);
  const [universeCount, setUniverseCount] = useState<number>(0);
  const [tickerFilter, setTickerFilter] = useState("");
  const [reportKind, setReportKind] = useState<ReportKind>("stock");
  const [reportSymbol, setReportSymbol] = useState("AAPL");
  const [reportFromSymbol, setReportFromSymbol] = useState("EUR");
  const [reportToSymbol, setReportToSymbol] = useState("USD");
  const [reportMarket, setReportMarket] = useState("USD");
  const [activeRequestSince, setActiveRequestSince] = useState<number | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [refreshStatus, setRefreshStatus] = useState<RefreshStatus | null>(null);

  useEffect(() => {
    const saved = window.localStorage.getItem("market-theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const resolvedTheme: Theme =
      saved === "dark" || saved === "light" ? saved : prefersDark ? "dark" : "light";
    setTheme(resolvedTheme);
    document.documentElement.setAttribute("data-theme", resolvedTheme);
  }, []);

  const backendRunning = refreshStatus?.state === "running" || refreshStatus?.is_running;
  const isBusy = loading || refreshing || backendRunning;
  const estimatedRefreshMs = useMemo(() => estimateRefreshMs(overview), [overview]);

  useEffect(() => {
    if (!isBusy) {
      setActiveRequestSince(null);
      setElapsedMs(0);
      return;
    }
    const startedAt = activeRequestSince ?? Date.now();
    if (activeRequestSince === null) {
      setActiveRequestSince(startedAt);
    }
    const id = window.setInterval(() => {
      setElapsedMs(Date.now() - startedAt);
    }, 500);
    return () => window.clearInterval(id);
  }, [isBusy, activeRequestSince]);

  const progressFromBackend =
    refreshStatus && refreshStatus.total_steps > 0 ? refreshStatus.progress_percent : null;
  const progressPct = isBusy
    ? progressFromBackend !== null
      ? Math.min(95, Math.max(5, progressFromBackend))
      : Math.min(95, Math.max(8, (elapsedMs / estimatedRefreshMs) * 100))
    : 100;
  const isSlow = isBusy && elapsedMs > estimatedRefreshMs;

  function toggleTheme() {
    const nextTheme: Theme = theme === "light" ? "dark" : "light";
    setTheme(nextTheme);
    document.documentElement.setAttribute("data-theme", nextTheme);
    window.localStorage.setItem("market-theme", nextTheme);
  }

  async function loadOverview() {
    setLoading(true);
    setError(null);
    try {
      const latestResp = await getJSON<{ latest: MarketOverview | null }>("/report/market-overview");
      const histResp = await getJSON<{
        history: Array<{ generated_at: string; news: { overall_average_sentiment: number | null } }>;
      }>("/report/market-overview/history?limit=96");
      const latest = latestResp.latest;
      setHistory(histResp.history || []);

      if (!latest || !latest.generated_at) {
        await startRefreshAndWait();
      } else {
        setOverview(latest);
      }
    } catch (e: any) {
      setError(e?.message ?? "Failed to load market overview.");
    } finally {
      setLoading(false);
    }
  }

  async function fetchRefreshStatus() {
    const statusResp = await getJSON<{ status: RefreshStatus }>("/report/market-overview/refresh-status");
    setRefreshStatus(statusResp.status);
    return statusResp.status;
  }

  async function loadOverviewAndHistory() {
    const latestResp = await getJSON<{ latest: MarketOverview | null }>("/report/market-overview");
    const histResp = await getJSON<{
      history: Array<{ generated_at: string; news: { overall_average_sentiment: number | null } }>;
    }>("/report/market-overview/history?limit=96");
    setOverview(latestResp.latest);
    setHistory(histResp.history || []);
  }

  async function startRefreshAndWait() {
    const startResp = await postJSON<RefreshStartResponse>("/report/market-overview/refresh");
    setRefreshStatus(startResp.status);
    const timeoutAt = Date.now() + 25 * 60_000;
    while (Date.now() < timeoutAt) {
      const status = await fetchRefreshStatus();
      if (status.state === "completed") {
        await loadOverviewAndHistory();
        await loadUniverse();
        return;
      }
      if (status.state === "failed") {
        throw new Error(status.error || "Refresh failed.");
      }
      await sleep(1250);
    }
    throw new Error("Refresh timed out.");
  }

  async function loadUniverse() {
    try {
      const resp = await getJSON<UniverseSnapshotResponse>("/market/universe-snapshot?state=active");
      setUniverse(resp.tickers || []);
      setUniverseCount(resp.count || 0);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load universe snapshot.");
    }
  }

  async function refreshNow() {
    setRefreshing(true);
    setError(null);
    try {
      await startRefreshAndWait();
    } catch (e: any) {
      setError(e?.message ?? "Manual refresh failed.");
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    loadOverview();
    loadUniverse();
    fetchRefreshStatus().catch(() => {});
    const id = window.setInterval(() => {
      loadOverview();
      loadUniverse();
      fetchRefreshStatus().catch(() => {});
    }, 30 * 60_000);
    return () => window.clearInterval(id);
  }, []);

  const sentimentScore = overview?.news?.overall_average_sentiment ?? null;
  const sentimentLabel =
    sentimentScore === null
      ? "No signal"
      : sentimentScore > 0.15
        ? "Positive"
        : sentimentScore < -0.15
          ? "Negative"
          : "Neutral";

  const sentimentPct =
    sentimentScore === null ? 50 : Math.max(0, Math.min(100, (sentimentScore + 1) * 50));
  const generatedAt = overview?.generated_at
    ? new Date(overview.generated_at).toLocaleString()
    : "--";

  const signalRows = overview?.guidance?.signals ?? [];
  const topMovers = useMemo(
    () =>
      [...signalRows]
        .sort((a, b) => Math.abs(b.momentum_1d ?? 0) - Math.abs(a.momentum_1d ?? 0))
        .slice(0, 8),
    [signalRows]
  );

  const chartData = useMemo(
    () =>
      (history || []).map((h) => ({
        t: new Date(h.generated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        score: h.news?.overall_average_sentiment ?? null,
      })),
    [history]
  );

  const filteredUniverse = useMemo(() => {
    const q = tickerFilter.trim().toUpperCase();
    if (!q) return universe;
    return universe.filter(
      (row) =>
        row.symbol?.toUpperCase().includes(q) ||
        row.name?.toUpperCase().includes(q) ||
        row.exchange?.toUpperCase().includes(q)
    );
  }, [tickerFilter, universe]);

  function downloadPdfReport() {
    const params = new URLSearchParams({
      kind: reportKind,
      as_pdf: "true",
      include_news: "true",
    });
    if (reportKind === "stock" || reportKind === "crypto") {
      params.set("symbol", reportSymbol.trim().toUpperCase());
    }
    if (reportKind === "fx") {
      params.set("from_symbol", reportFromSymbol.trim().toUpperCase());
      params.set("to_symbol", reportToSymbol.trim().toUpperCase());
    }
    if (reportKind === "crypto") {
      params.set("market", reportMarket.trim().toUpperCase());
    }
    window.open(`${API_BASE}/report/asset?${params.toString()}`, "_blank", "noopener,noreferrer");
  }

  return (
    <main className="dashboard-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">M</div>
          <div>
            <p className="brand-name">Market Analyzer</p>
            <p className="brand-subtitle">Live Universe + Sentiment</p>
          </div>
        </div>

        <div className="sidebar-section">
          <p className="sidebar-label">Monitoring Hub</p>
          <nav className="nav-list">
            {navItems.map((item) => (
              <button key={item} className={`nav-item ${item === "Dashboard" ? "active" : ""}`} type="button">
                {item}
              </button>
            ))}
          </nav>
        </div>

        <div className="status-card">
          <p className="status-title">General Mood</p>
          <p className="status-value">{overview?.guidance?.public_mood ?? "--"}</p>
          <p className="status-title status-subline">Next auto run: {nextHalfHourLabel()}</p>
        </div>
      </aside>

      <section className="content">
        <header className="topbar">
          <div className="topbar-main">
            <div>
              <h1>Market Analyzer</h1>
              <p>Universe snapshot + signals, auto-updated every 30 minutes</p>
            </div>
            <div className="topbar-actions">
              <button onClick={toggleTheme} className="theme-button" type="button">
                {theme === "light" ? "Dark mode" : "Light mode"}
              </button>
              <span className="updated-chip">Snapshot: {generatedAt}</span>
              <button onClick={refreshNow} disabled={refreshing || loading || backendRunning} className="refresh-button" type="button">
                {refreshing || loading || backendRunning ? "Refreshing..." : "Refresh Now"}
              </button>
            </div>
          </div>
          {isBusy ? (
            <div className="progress-wrap" role="status" aria-live="polite">
              <div className="progress-track">
                <div className="progress-fill" style={{ width: `${progressPct}%` }} />
              </div>
              <p className="progress-text">
                Refresh in progress | elapsed {formatElapsed(elapsedMs / 1000)}
                {refreshStatus?.state === "running" && refreshStatus.total_steps > 0
                  ? ` | ${refreshStatus.completed_steps}/${refreshStatus.total_steps} steps`
                  : ""}
                {refreshStatus?.current_step ? ` | ${refreshStatus.current_step}` : ""}
                {isSlow ? " | Taking longer than usual (likely API throttling)." : ""}
              </p>
            </div>
          ) : null}
        </header>

        <section className="metrics-grid">
          <article className="kpi-card">
            <p>Stocks Tracked</p>
            <h3>{overview?.coverage?.stocks ?? "--"}</h3>
            <small>Configured watchlist coverage</small>
          </article>
          <article className="kpi-card">
            <p>FX Pairs Tracked</p>
            <h3>{overview?.coverage?.fx_pairs ?? "--"}</h3>
            <small>Configured major pairs</small>
          </article>
          <article className="kpi-card">
            <p>Cryptos Tracked</p>
            <h3>{overview?.coverage?.cryptos ?? "--"}</h3>
            <small>Configured crypto basket</small>
          </article>
          <article className="kpi-card">
            <p>Universe Tickers</p>
            <h3>{universeCount || "--"}</h3>
            <small>Alpha Vantage listing status feed</small>
          </article>
        </section>

        <section className="main-grid">
          <article className="card chart-card">
            <div className="section-title-row">
              <h2>Sentiment Trend (Snapshots)</h2>
              <div className="sentiment-pill" style={{ width: `${sentimentPct}%` }} />
            </div>
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <XAxis dataKey="t" tickLine={false} axisLine={false} minTickGap={24} />
                  <YAxis tickLine={false} axisLine={false} domain={[-1, 1]} width={46} />
                  <Tooltip />
                  <Line type="monotone" dataKey="score" stroke="var(--accent)" strokeWidth={3} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </article>

          <article className="card activity-card">
            <h2>Recent Market News</h2>
            <div className="activity-list">
              {(overview?.news?.items || []).slice(0, 6).map((h) => (
                <a href={h.url} target="_blank" key={h.url} className="activity-item" rel="noreferrer">
                  <p>{h.title}</p>
                  <small>{h.source} | {h.time_published}</small>
                </a>
              ))}
              {!(overview?.news?.items || []).length ? (
                <p className="empty-line">No news snapshot available yet.</p>
              ) : null}
            </div>
          </article>
        </section>

        <section className="bottom-grid">
          <article className="card tint-green">
            <h2>Expected Direction</h2>
            <p>{overview?.guidance?.expected_market_direction ?? "--"}</p>
            <p>{overview?.guidance?.disclaimer ?? ""}</p>
          </article>
          <article className="card tint-amber">
            <h2>Scheduler</h2>
            <p>Runs at :00 and :30 every hour.</p>
            <p>First slot daily is 00:00 in configured timezone.</p>
            <p>Next expected run: {nextHalfHourLabel()}</p>
          </article>
          <article className="card tint-blue">
            <h2>Pipeline Health</h2>
            <p>Fetch errors in latest run: {overview?.errors?.length ?? 0}</p>
            <p>Total signals generated: {overview?.guidance?.signals?.length ?? 0}</p>
            <p>Universe snapshot updates every 30 minutes.</p>
          </article>
        </section>

        <section className="card signal-board">
          <div className="section-title-row">
            <h2>Market Signals</h2>
          </div>
          <div className="signal-grid">
            <div>
              <h3>Buy Candidates</h3>
              <ul className="signal-list">
                {(overview?.guidance?.buy_candidates || []).slice(0, 8).map((row) => (
                  <li key={`buy-${row.asset_class}-${row.symbol}`}>
                    <span>{row.symbol}</span>
                    <small>{row.asset_class} | m: {formatPct(row.momentum_1d)}</small>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3>Sell Candidates</h3>
              <ul className="signal-list">
                {(overview?.guidance?.sell_candidates || []).slice(0, 8).map((row) => (
                  <li key={`sell-${row.asset_class}-${row.symbol}`}>
                    <span>{row.symbol}</span>
                    <small>{row.asset_class} | m: {formatPct(row.momentum_1d)}</small>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3>Hold Candidates</h3>
              <ul className="signal-list">
                {(overview?.guidance?.hold_candidates || []).slice(0, 8).map((row) => (
                  <li key={`hold-${row.asset_class}-${row.symbol}`}>
                    <span>{row.symbol}</span>
                    <small>{row.asset_class} | m: {formatPct(row.momentum_1d)}</small>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3>Top Movers</h3>
              <ul className="signal-list">
                {topMovers.map((row) => (
                  <li key={`mover-${row.asset_class}-${row.symbol}`}>
                    <span>{row.symbol}</span>
                    <small>{row.asset_class} | m: {formatPct(row.momentum_1d)}</small>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        <section className="card">
          <div className="section-title-row">
            <h2>Safest vs Riskiest (Heuristic)</h2>
          </div>
          <div className="risk-grid">
            <div>
              <h3>Safest Bets</h3>
              <ul className="signal-list">
                {(overview?.guidance?.safest_bets || []).slice(0, 8).map((row) => (
                  <li key={`safe-${row.asset_class}-${row.symbol}`}>
                    <span>{row.symbol}</span>
                    <small>
                      {row.asset_class} | risk: {row.risk_score.toFixed(2)} | px:{" "}
                      {formatPrice(row.price, row.asset_class)}
                    </small>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3>Riskiest Bets</h3>
              <ul className="signal-list">
                {(overview?.guidance?.riskiest_bets || []).slice(0, 8).map((row) => (
                  <li key={`risk-${row.asset_class}-${row.symbol}`}>
                    <span>{row.symbol}</span>
                    <small>
                      {row.asset_class} | risk: {row.risk_score.toFixed(2)} | px:{" "}
                      {formatPrice(row.price, row.asset_class)}
                    </small>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        <section className="card">
          <div className="section-title-row">
            <h2>Universe Snapshot</h2>
            <div className="universe-meta">Showing {filteredUniverse.length} / {universeCount}</div>
          </div>
          <div className="universe-toolbar">
            <input
              type="text"
              value={tickerFilter}
              placeholder="Filter by symbol, name, or exchange"
              onChange={(e) => setTickerFilter(e.target.value)}
            />
          </div>
          <div className="universe-table-wrap">
            <table className="universe-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Name</th>
                  <th>Exchange</th>
                  <th>Asset</th>
                  <th>IPO Date</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {filteredUniverse.map((row) => (
                  <tr key={`${row.symbol}-${row.exchange}`}>
                    <td>{row.symbol}</td>
                    <td>{row.name}</td>
                    <td>{row.exchange}</td>
                    <td>{row.assetType}</td>
                    <td>{row.ipoDate}</td>
                    <td>{row.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="card report-card">
          <div className="section-title-row">
            <h2>Download PDF Report</h2>
          </div>
          <div className="report-form">
            <label>
              <span>Kind</span>
              <select value={reportKind} onChange={(e) => setReportKind(e.target.value as ReportKind)}>
                <option value="stock">Stock</option>
                <option value="fx">FX</option>
                <option value="crypto">Crypto</option>
              </select>
            </label>

            {(reportKind === "stock" || reportKind === "crypto") && (
              <label>
                <span>Symbol</span>
                <input value={reportSymbol} onChange={(e) => setReportSymbol(e.target.value)} />
              </label>
            )}

            {reportKind === "fx" && (
              <>
                <label>
                  <span>From</span>
                  <input value={reportFromSymbol} onChange={(e) => setReportFromSymbol(e.target.value)} />
                </label>
                <label>
                  <span>To</span>
                  <input value={reportToSymbol} onChange={(e) => setReportToSymbol(e.target.value)} />
                </label>
              </>
            )}

            {reportKind === "crypto" && (
              <label>
                <span>Market</span>
                <input value={reportMarket} onChange={(e) => setReportMarket(e.target.value)} />
              </label>
            )}

            <button className="refresh-button" type="button" onClick={downloadPdfReport}>
              Download PDF
            </button>
          </div>
        </section>

        {error ? <section className="card error-line">{error}</section> : null}
      </section>
    </main>
  );
}
