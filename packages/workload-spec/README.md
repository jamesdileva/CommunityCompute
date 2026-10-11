# workload-spec — declarative workload requirements (scaffold; schemas in Sprint 9–10)

Example (implementation-guide §10): `{ workload_type, version, requirements: {cpu_cores, ram_mb, gpu, ...} }`.
The scheduler must stay workload-agnostic; workloads declare, workers advertise.
