/** Typed fetch wrappers for the coordinator API (Sprint 16). */

import type { JobStatus, NetworkSummary, Worker, WorkerStats, WorkUnit } from "../types";

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(path);
  if (!resp.ok) {
    throw new Error(`${resp.status} ${path}`);
  }
  return (await resp.json()) as T;
}

async function post<T>(path: string): Promise<T> {
  const resp = await fetch(path, { method: "POST" });
  if (!resp.ok) {
    throw new Error(`${resp.status} ${path}`);
  }
  return (await resp.json()) as T;
}

export const api = {
  health: () => get<{ status: string }>("/health"),
  workers: () => get<Worker[]>("/workers"),
  worker: (id: string) => get<Worker>(`/workers/${id}`),
  workerWork: (id: string) => get<WorkUnit[]>(`/workers/${id}/work`),
  workerStats: (id: string) => get<WorkerStats>(`/workers/${id}/stats`),
  pauseWorker: (id: string) => post<Worker>(`/workers/${id}/pause`),
  resumeWorker: (id: string) => post<Worker>(`/workers/${id}/resume`),
  jobs: () => get<{ id: string }[]>("/jobs"),
  job: (id: string) => get<JobStatus>(`/jobs/${id}`),
  networkSummary: () => get<NetworkSummary>("/network/summary"),
};
