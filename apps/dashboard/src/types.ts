/** CommunityCompute dashboard types (Sprint 16): mirrors the coordinator API. */

export type WorkerStatus = "online" | "offline" | "paused" | "throttled" | "unknown";

export interface GpuInfo {
  vendor: string;
  model: string;
  vram_mb: number | null;
  driver: string | null;
  utilization_percent: number | null;
  source: string;
}

export interface CapabilityProfile {
  schema_version: string;
  cpu: { arch?: string | null; logical_cores?: number | null; physical_cores?: number | null };
  ram: { total_mb?: number | null; available_mb?: number | null };
  os: { system?: string | null; release?: string | null };
  gpus: GpuInfo[];
  runtimes: string[];
  cached_models: { name: string; version: string }[];
  sandbox?: boolean;
  policy_summary?: Record<string, unknown> | null;
}

export interface Worker {
  id: string;
  worker_version: string | null;
  hostname: string | null;
  status: WorkerStatus;
  first_seen: string | null;
  last_seen: string | null;
  capabilities: CapabilityProfile | null;
  tiers: { gpu: string | null; cpu: string; ram: string } | null;
  paused_by_operator: boolean;
  cpu_percent: number | null;
  gpu_percent: number | null;
  ram_available_mb: number | null;
}

export interface WorkUnit {
  id: string;
  job_id: string;
  sequence: number;
  range_start: number;
  range_end: number;
  status: string;
  assigned_worker_id: string | null;
}

export interface JobStatus {
  id: string;
  workload_type: string;
  total_units: number;
  chunk_size: number;
  status: string;
  requirements: Record<string, unknown>;
  work_units: WorkUnit[];
  counts: Record<string, number>;
  aggregate: { counts: Record<string, number>; final?: unknown } | null;
}

export interface NetworkSummary {
  workers: { total: number; by_status: Record<string, number> };
  units: Record<string, number>;
  jobs: number;
  completed_last_5m: number;
}

export interface NetworkCapacity {
  online_workers: number;
  total_workers: number;
  cpu_cores: number;
  ram_mb: number;
  gpus_by_tier: Record<string, number>;
  gpus_by_vendor: Record<string, number>;
  cached_models: Record<string, number>;
  runtimes: Record<string, number>;
  versions: Record<string, number>;
  queued_units: number;
}

export interface WorkerStats {
  worker_id: string;
  completed_units: number;
  failed_units: number;
  total_execution_ms: number;
  attempts: number;
}
