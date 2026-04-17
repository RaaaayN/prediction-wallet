import { useCallback, useEffect, useState } from "react";
import { api, type AgentRunRow, type PortfolioResponse, type PositionRow, type SnapshotRow } from "./api";

function formatUsd(n: number | undefined): string {
  if (n === undefined || Number.isNaN(n)) {
    return "—";
  }
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);
}

function formatPct(n: number | undefined): string {
  if (n === undefined || Number.isNaN(n)) {
    return "—";
  }
  return `${(n * 100).toFixed(2)}%`;
}

export default function App() {
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [snapshots, setSnapshots] = useState<SnapshotRow[]>([]);
  const [runs, setRuns] = useState<AgentRunRow[]>([]);
  const [positions, setPositions] = useState<PositionRow[]>([]);
  const [cfg, setCfg] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setErr(null);
    setLoading(true);
    try {
      const [p, s, r, pos, c] = await Promise.all([
        api.portfolio(),
        api.snapshots(48),
        api.runs(12),
        api.positions(),
        api.config(),
      ]);
      setPortfolio(p);
      setSnapshots(s);
      setRuns(r);
      setPositions(pos);
      setCfg(c);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const pnl = portfolio?.pnl_dollars;
  const pnlClass = pnl !== undefined && pnl < 0 ? "neg" : "pos";

  return (
    <>
      <header>
        <span className="pill">Governed agent</span>
        <h1>Prediction Wallet</h1>
        <p className="subtitle">
          Portfolio view backed by the FastAPI service. Run{" "}
          <code style={{ fontFamily: "var(--mono)", fontSize: "0.85em" }}>python start_ui.py</code> then{" "}
          <code style={{ fontFamily: "var(--mono)", fontSize: "0.85em" }}>npm run dev</code> inside{" "}
          <code style={{ fontFamily: "var(--mono)", fontSize: "0.85em" }}>ui-react/</code> for hot reload, or build and open the API
          server root.
        </p>
      </header>

      {err ? <div className="error">{err}</div> : null}
      {loading && !portfolio ? <p className="muted">Loading…</p> : null}

      {portfolio?.error ? (
        <div className="error">{String(portfolio.error)}</div>
      ) : portfolio ? (
        <>
          <div className="grid cols-3" style={{ marginBottom: "1.25rem" }}>
            <div className="card">
              <h2>Total value</h2>
              <div className="stat">{formatUsd(portfolio.total_value as number | undefined)}</div>
              <div className="muted">Cash {formatUsd(portfolio.cash as number | undefined)}</div>
            </div>
            <div className="card">
              <h2>P&amp;L vs initial</h2>
              <div className={`stat ${pnlClass}`}>{formatUsd(portfolio.pnl_dollars as number | undefined)}</div>
              <div className={`muted ${pnlClass}`}>{formatPct(portfolio.pnl_pct as number | undefined)}</div>
            </div>
            <div className="card">
              <h2>Environment</h2>
              <div className="stat small" style={{ wordBreak: "break-all" }}>
                {cfg?.ai_provider != null ? String(cfg.ai_provider) : "—"}
              </div>
              <div className="muted">
                mode {cfg?.execution_mode != null ? String(cfg.execution_mode) : "—"} · backend{" "}
                {cfg?.agent_backend != null ? String(cfg.agent_backend) : "—"}
              </div>
            </div>
          </div>

          <div className="grid cols-2">
            <div className="card">
              <h2>Positions</h2>
              {positions.length === 0 ? (
                <p className="muted">No positions yet.</p>
              ) : (
                <div style={{ overflowX: "auto" }}>
                  <table>
                    <thead>
                      <tr>
                        <th>Ticker</th>
                        <th>Weight</th>
                        <th>Target</th>
                        <th>Drift</th>
                      </tr>
                    </thead>
                    <tbody>
                      {positions.map((row) => (
                        <tr key={row.ticker}>
                          <td>
                            <strong>{row.ticker}</strong>
                            {row.side ? <span className="muted"> · {row.side}</span> : null}
                          </td>
                          <td>{formatPct(row.weight)}</td>
                          <td>{formatPct(row.target_weight)}</td>
                          <td>{formatPct(row.drift)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="card">
              <h2>Recent agent runs</h2>
              {runs.length === 0 ? (
                <p className="muted">No runs in the database yet.</p>
              ) : (
                <ul style={{ margin: 0, paddingLeft: "1.1rem" }}>
                  {runs.map((run) => (
                    <li key={run.id} style={{ marginBottom: "0.5rem" }}>
                      <span className="muted" style={{ fontFamily: "var(--mono)", fontSize: "0.8rem" }}>
                        {run.timestamp}
                      </span>
                      <br />
                      <strong>{run.cycle_id}</strong> · {run.strategy ?? "—"} · trades {run.trades_count}
                      {run.kill_switch ? <span className="neg"> · kill switch</span> : null}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <div className="card" style={{ marginTop: "1rem" }}>
            <h2>Portfolio snapshots</h2>
            {snapshots.length === 0 ? (
              <p className="muted">No snapshots stored.</p>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table>
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Cycle</th>
                      <th>Value</th>
                      <th>Drawdown</th>
                    </tr>
                  </thead>
                  <tbody>
                    {snapshots.slice(-12).map((row) => (
                      <tr key={row.id}>
                        <td style={{ whiteSpace: "nowrap" }}>{row.timestamp}</td>
                        <td style={{ fontFamily: "var(--mono)", fontSize: "0.8rem" }}>{row.cycle_id}</td>
                        <td>{formatUsd(row.total_value)}</td>
                        <td>{formatPct(row.drawdown)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      ) : null}

      <footer>
        <button
          type="button"
          onClick={() => void load()}
          style={{
            marginRight: "1rem",
            padding: "0.4rem 0.9rem",
            borderRadius: "8px",
            border: "1px solid var(--border)",
            background: "var(--surface)",
            color: "var(--text)",
            cursor: "pointer",
            fontFamily: "var(--font)",
          }}
        >
          Refresh
        </button>
        Classic HTML UI: <a href="/static/index.html">/static/index.html</a>
      </footer>
    </>
  );
}
