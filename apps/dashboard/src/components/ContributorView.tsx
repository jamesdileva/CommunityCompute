import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { Worker, WorkerStats, WorkUnit } from "../types";

const STATUS_COLORS: Record<string, string> = {
  online: "#2e7d32",
  offline: "#616161",
  paused: "#ef6c00",
  throttled: "#c62828",
  unknown: "#616161",
};

function fmtMb(mb: number | null | undefined): string {
  if (mb === null || mb === undefined) return "?";
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${mb} MB`;
}

function WorkerCard({
  worker,
  onChanged,
}: {
  worker: Worker;
  onChanged: () => void;
}) {
  const [work, setWork] = useState<WorkUnit[]>([]);
  const [stats, setStats] = useState<WorkerStats | null>(null);
  const shortId = worker.id.slice(0, 8);
  const gpus = worker.capabilities?.gpus ?? [];
  const vram = gpus.map((g) => fmtMb(g.vram_mb)).join(" + ") || "?";
  const gpuModels = gpus.map((g) => g.model).join(", ") || "no GPU detected";

  useEffect(() => {
    let alive = true;
    api
      .workerWork(worker.id)
      .then((w) => alive && setWork(w))
      .catch(() => {});
    api
      .workerStats(worker.id)
      .then((s) => alive && setStats(s))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [worker.id, worker.status]);

  const togglePause = async () => {
    try {
      if (worker.paused_by_operator) {
        await api.resumeWorker(worker.id);
      } else {
        await api.pauseWorker(worker.id);
      }
      onChanged();
    } catch (e) {
      alert(`Pause toggle failed: ${e}`);
    }
  };

  return (
    <article className="card">
      <header>
        <span
          className="pill"
          style={{ background: STATUS_COLORS[worker.status] ?? "#616161" }}
        >
          {worker.status.toUpperCase()}
        </span>
        <strong>
          {worker.hostname ?? "worker"} · <code>{shortId}</code>
        </strong>
        <button onClick={togglePause}>
          {worker.paused_by_operator ? "Resume" : "Pause"}
        </button>
      </header>
      <dl>
        <div>
          <dt>CPU</dt>
          <dd>
            {worker.cpu_percent ?? "?"}% ·{" "}
            {worker.capabilities?.cpu.logical_cores ?? "?"} cores ·{" "}
            {worker.tiers?.cpu ?? "?"}
          </dd>
        </div>
        <div>
          <dt>GPU</dt>
          <dd>
            {gpuModels} · {worker.gpu_percent ?? "?"}% · VRAM {vram} ·{" "}
            {worker.tiers?.gpu ?? "?"}
          </dd>
        </div>
        <div>
          <dt>RAM</dt>
          <dd>
            free {fmtMb(worker.ram_available_mb)} of{" "}
            {fmtMb(worker.capabilities?.ram.total_mb)} · {worker.tiers?.ram ?? "?"}
          </dd>
        </div>
        <div>
          <dt>Workloads</dt>
          <dd>{(worker.capabilities?.runtimes ?? []).join(", ") || "?"}</dd>
        </div>
        <div>
          <dt>Current work</dt>
          <dd>
            {work.length === 0
              ? "idle"
              : work
                  .map((u) => `#${u.sequence} ${u.range_start}..${u.range_end} (${u.status})`)
                  .join(", ")}
          </dd>
        </div>
        <div>
          <dt>Contribution</dt>
          <dd>
            {stats
              ? `${stats.completed_units} done · ${stats.failed_units} failed · ${(
                  stats.total_execution_ms / 1000
                ).toFixed(1)}s compute`
              : "…"}
          </dd>
        </div>
      </dl>
    </article>
  );
}

export default function ContributorView({ refreshTick }: { refreshTick: number }) {
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    api
      .workers()
      .then((w) => {
        setWorkers(w);
        setError(null);
      })
      .catch((e) => setError(String(e)));
  };

  useEffect(load, [refreshTick]);

  if (error) return <p className="error">Coordinator unreachable: {error}</p>;
  if (workers.length === 0) return <p>No workers registered yet.</p>;
  return (
    <section>
      {workers.map((w) => (
        <WorkerCard key={w.id} worker={w} onChanged={load} />
      ))}
    </section>
  );
}
