# Dashboard (Sprint 0 stub; full UI in Sprint 16)

Minimal Vite + React + TS placeholder. Sprint 0 only proves Node/npm toolchain works.
Sprint 16 builds contributor view (node status, GPU/CPU/RAM/temp, current work, pause)
and network view (online workers, queued/running/completed/failed, throughput).

```powershell
cd apps/dashboard
npm install
npm run dev   # → http://localhost:5173 (pings coordinator /health)
```
