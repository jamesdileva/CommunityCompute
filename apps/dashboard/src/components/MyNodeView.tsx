import { useEffect, useState } from "react";
import { api } from "../services/api";
import type {
  Worker,
  WorkerAccounting,
  WorkerCredits,
  WorkerEarnings,
  WorkerReputation,
  WorkUnit,
} from "../types";

const STATUS_COLORS: Record<string, string> = {
  online: "#2e7d32",
  offline: "#616161",
  paused: "#ef6c00",
  throttled: "#c62828",
  unknown: "#616161",
};

const STORAGE_KEY = "cc_worker_id";

function fmtMb(mb: number | null | undefined): string {
  if (mb === null || mb === undefined) return "?";
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${mb} MB`;
}

function fmtSeconds(ms: number | null | undefined): string {
  if (!ms) return "0s";
  return `${(ms / 1000).toFixed(1)}s`;
}

function pct(value: number | null | undefined): string {
  return value === null || value === undefined ? "?" : `${Math.round(value * 100)}%`;
}

function fmtMoney(cents: number | null | undefined, currency: string): string {
  if (cents === null || cents === undefined) return "…";
  return `${(cents / 100).toFixed(2)} ${currency}`;
}

export default function MyNodeView({ refreshTick }: { refreshTick: number }) {
  const [workerId, setWorkerId] = useState(
    () => localStorage.getItem(STORAGE_KEY) ?? "",
  );
  const [known, setKnown] = useState<Worker[]>([]);
  const [worker, setWorker] = useState<Worker | null>(null);
  const [work, setWork] = useState<WorkUnit[]>([]);
  const [credits, setCredits] = useState<WorkerCredits | null>(null);
  const [reputation, setReputation] = useState<WorkerReputation | null>(null);
  const [accounting, setAccounting] = useState<WorkerAccounting | null>(null);
  const [earnings, setEarnings] = useState<WorkerEarnings | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .workers()
      .then(setKnown)
      .catch(() => {});
  }, [refreshTick]);

  useEffect(() => {
    if (!workerId) {
      setWorker(null);
      setWork([]);
      setCredits(null);
      setReputation(null);
      setAccounting(null);
      setEarnings(null);
      setError(null);
      return;
    }
    let alive = true;
    const clear = () => {
      if (!alive) return;
      setWorker(null);
      setWork([]);
      setCredits(null);
      setReputation(null);
      setAccounting(null);
      setEarnings(null);
    };
    Promise.all([
      api.worker(workerId),
      api.workerWork(workerId).catch(() => []),
      api.workerCredits(workerId).catch(() => null),
      api.workerReputation(workerId).catch(() => null),
      api.workerAccounting(workerId).catch(() => null),
      api.workerEarnings(workerId).catch(() => null),
    ])
      .then(([w, wk, cr, rep, acct, earn]) => {
        if (!alive) return;
        setWorker(w);
        setWork(wk);
        setCredits(cr);
        setReputation(rep);
        setAccounting(acct);
        setEarnings(earn);
        setError(null);
      })
      .catch((e) => {
        clear();
        setError(String(e));
      });
    return () => {
      alive = false;
    };
  }, [workerId, refreshTick]);

  const choose = (value: string) => {
    const clean = value.trim();
    setWorkerId(clean);
    if (clean) localStorage.setItem(STORAGE_KEY, clean);
    else localStorage.removeItem(STORAGE_KEY);
  };

  const gpus = worker?.capabilities?.gpus ?? [];
  const gpuModels = gpus.map((g) => g.model).join(", ") || "no GPU detected";

  return (
    <section>
      <div className="card">
        <header>
          <strong>My node</strong>
          {known.length > 0 && (
            <select
              value={known.some((w) => w.id === workerId) ? workerId : ""}
              onChange={(e) => choose(e.target.value)}
            >
              <option value="">Select a registered node…</option>
              {known.map((w) => (
                <option key={w.id} value={w.id}>
                  {(w.hostname ?? "worker") + " · " + w.id.slice(0, 8)}
                </option>
              ))}
            </select>
          )}
          <input
            placeholder="node id"
            value={workerId}
            onChange={(e) => choose(e.target.value)}
          />
        </header>
        <p className="fineprint" style={{ color: "#555", fontSize: 12 }}>
          Pick the machine you installed the worker on. Your choice is remembered
          on this browser.
        </p>
      </div>

      {!workerId && (
        <p>
          No node selected yet. After <code>worker.exe --setup</code> and{" "}
          <code>--enroll</code>, choose your node above (or paste its id) to see
          your contribution.
        </p>
      )}

      {error && (
        <p className="error">
          This node is not known to the coordinator yet ({error}). It may still
          be enrolling — try again, or re-check the node id.
        </p>
      )}

      {worker && (
        <>
          <article className="card">
            <header>
              <span
                className="pill"
                style={{ background: STATUS_COLORS[worker.status] ?? "#616161" }}
              >
                {worker.status.toUpperCase()}
              </span>
              <strong>
                {worker.hostname ?? "worker"} · <code>{worker.id.slice(0, 8)}</code>
              </strong>
            </header>
            <div className="statgrid">
              <div className="stat">
                <span>CPU</span>
                <strong>{worker.cpu_percent ?? "?"}%</strong>
                <small>{worker.capabilities?.cpu.logical_cores ?? "?"} cores</small>
              </div>
              <div className="stat">
                <span>GPU</span>
                <strong>{worker.gpu_percent ?? "?"}%</strong>
                <small>{gpuModels}</small>
              </div>
              <div className="stat">
                <span>RAM free</span>
                <strong>{fmtMb(worker.ram_available_mb)}</strong>
                <small>of {fmtMb(worker.capabilities?.ram.total_mb)}</small>
              </div>
              <div className="stat">
                <span>Last seen</span>
                <strong>{worker.last_seen ? new Date(worker.last_seen).toLocaleTimeString() : "?"}</strong>
                <small>v{worker.worker_version ?? "?"}</small>
              </div>
            </div>
          </article>

          <article className="card">
            <header>
              <strong>Preview of earnings</strong>
            </header>
            <div className="statgrid">
              <div className="stat">
                <span>Credit balance</span>
                <strong>{credits ? credits.balance : "…"}</strong>
                <small>verified work units</small>
              </div>
              <div className="stat">
                <span>Earned</span>
                <strong>{credits ? credits.earned : "…"}</strong>
                <small>lifetime</small>
              </div>
              <div className="stat">
                <span>Spent</span>
                <strong>{credits ? credits.spent : "…"}</strong>
                <small>work you submitted</small>
              </div>
            </div>
            <p className="fineprint" style={{ color: "#555", fontSize: 12 }}>
              Credit is a prototype accounting unit — it has no cash value in
              this beta.
            </p>
          </article>

          <article className="card">
            <header>
              <strong>Paid-work earnings</strong>
            </header>
            <div className="statgrid">
              <div className="stat">
                <span>Balance</span>
                <strong>{fmtMoney(earnings?.balance_cents, earnings?.currency ?? "USD")}</strong>
                <small>verified paid units</small>
              </div>
              <div className="stat">
                <span>Paid units</span>
                <strong>
                  {earnings
                    ? earnings.entries.filter((e) => !e.voided).length
                    : "…"}
                </strong>
                <small>lifetime</small>
              </div>
            </div>
            <p className="fineprint" style={{ color: "#555", fontSize: 12 }}>
              Simulated money in this beta — it has no cash value and no payouts
              are made.
            </p>
          </article>

          <article className="card">
            <header>
              <strong>Reliability</strong>
            </header>
            {reputation ? (
              <dl>
                <div>
                  <dt>Score</dt>
                  <dd>
                    {reputation.rated
                      ? `${(reputation.score ?? 0).toFixed(3)} (${reputation.outcomes} outcomes)`
                      : "not rated yet — needs more verified units"}
                  </dd>
                </div>
                <div>
                  <dt>Outcomes</dt>
                  <dd>
                    {reputation.accepted} accepted · {reputation.rejected} rejected ·{" "}
                    {reputation.expired} expired
                  </dd>
                </div>
                <div>
                  <dt>Verification</dt>
                  <dd>
                    {reputation.agreed} agreed · {reputation.disagreed} disagreed
                  </dd>
                </div>
              </dl>
            ) : (
              <p>…</p>
            )}
          </article>

          <article className="card">
            <header>
              <strong>Contribution</strong>
            </header>
            {accounting ? (
              <dl>
                <div>
                  <dt>Units</dt>
                  <dd>
                    {accounting.units_completed} completed ({accounting.units_valid}{" "}
                    valid, {accounting.units_voided} voided)
                  </dd>
                </div>
                <div>
                  <dt>Compute time</dt>
                  <dd>
                    {fmtSeconds(accounting.total_execution_ms)} total (
                    {fmtSeconds(accounting.total_cpu_time_ms)} CPU,{" "}
                    {fmtSeconds(accounting.total_gpu_time_ms)} GPU)
                  </dd>
                </div>
                <div>
                  <dt>Verified</dt>
                  <dd>{accounting.verified_units} independently checked</dd>
                </div>
                <div>
                  <dt>Availability</dt>
                  <dd>
                    {pct(accounting.availability_24h)} ·{" "}
                    {reputation?.rated
                      ? `reliability ${(accounting.reliability ?? 0).toFixed(3)}`
                      : "reliability n/a"}
                  </dd>
                </div>
              </dl>
            ) : (
              <p>…</p>
            )}
            <div>
              <dt style={{ fontWeight: 600 }}>Current work</dt>
              <dd>
                {work.length === 0
                  ? "idle — nothing assigned right now"
                  : work
                      .map(
                        (u) =>
                          `#${u.sequence} ${u.range_start}..${u.range_end} (${u.status})`,
                      )
                      .join(", ")}
              </dd>
            </div>
          </article>
        </>
      )}
    </section>
  );
}
