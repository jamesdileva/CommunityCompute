# CommunityCompute website (Sprint 36)

Static, dependency-free onboarding site. It is the "discover the project →
download the worker → join" entry point; it fetches the live workload catalog
from a coordinator.

```powershell
python scripts/serve_website.py          # http://127.0.0.1:8080
python scripts/serve_website.py --port 9000
```

No build step: `index.html` + `styles.css` + `app.js` are served as-is, so the
same folder can be dropped on any static host.

Runtime configuration (no rebuild needed):

- `?api=http://<coordinator>:8000` — coordinator base for the workload catalog
  (also editable on the page; remembered in `localStorage`).
- `?dashboard=http://<host>:5173` — where the "Dashboard" link points.
- `?download=<url>` — the worker bundle download link (defaults to the project
  releases page).

Only allowlisted, deterministic workloads are advertised; the page states
plainly that this is an invited, allowlisted prototype beta.
