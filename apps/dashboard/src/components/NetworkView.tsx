import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { JobStatus, NetworkSummary } from "../types";

function JobRow({ id }: { id: string }) {
  const [job, setJob] = useState<JobStatus | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .job(id)
      .then((j) => alive && setJob(j))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [id]);

  if (!job) return null;
  const total = job.total_units || 1;
  const done = job.counts["completed"] ?? 0;
  const pct = Math.round((done / total) * 100);
  return (
    <li>
      <code>{job.id.slice(0, 8)}</code> {job.workload_type} · {job.status} · {done}/
      {total} ({pct}%)
      <div className="bar">
        <div className="fill" style={{ width: `${pct}%` }} />
      </div>
      {job.aggregate?.final !== undefined && (
        <span> final: {JSON.stringify(job.aggregate.final)}</span>
      )}
    </li>
  );
}

export default function NetworkView({ refreshTick }: { refreshTick: number }) {
  const [summary, setSummary] = useState<NetworkSummary | null>(null);
  const [jobs, setJobs] = useState<{ id: string }[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.networkSummary(), api.jobs()])
      .then(([s, j]) => {
        setSummary(s);
        setJobs(j);
        setError(null);
      })
      .catch((e) => setError(String(e)));
  }, [refreshTick]);

  if (error) return <p className="error">Coordinator unreachable: {error}</p>;
  if (!summary) return <p>Loading…</p>;

  const units = summary.units;
  return (
    <section>
      <div className="statgrid">
        <div className="stat">
          <span>Workers</span>
          <strong>{summary.workers.total}</strong>
          <small>{JSON.stringify(summary.workers.by_status)}</small>
        </div>
        <div className="stat">
          <span>Queued</span>
          <strong>{units["queued"] ?? 0}</strong>
        </div>
        <div className="stat">
          <span>Dispatched/Running</span>
          <strong>{(units["dispatched"] ?? 0) + (units["running"] ?? 0)}</strong>
        </div>
        <div className="stat">
          <span>Completed</span>
          <strong>{units["completed"] ?? 0}</strong>
        </div>
        <div className="stat">
          <span>Failed</span>
          <strong>{units["failed"] ?? 0}</strong>
        </div>
        <div className="stat">
          <span>Throughput (5m)</span>
          <strong>{summary.completed_last_5m}</strong>
        </div>
        <div className="stat">
          <span>Jobs</span>
          <strong>{summary.jobs}</strong>
        </div>
      </div>
      <h3>Jobs</h3>
      {jobs.length === 0 ? (
        <p>No jobs submitted yet.</p>
      ) : (
        <ul>
          {jobs.map((j) => (
            <JobRow key={j.id} id={j.id} />
          ))}
        </ul>
      )}
    </section>
  );
}
