# hello-compute — deterministic first workload (lands in Sprint 6)

Plan (implementation-guide §11): sum/hash over number ranges (e.g. 1..1,000,000 split into chunks).
Deterministic → coordinator knows expected result → exact verification, corrupted results rejected.
Do NOT start with LLMs.
