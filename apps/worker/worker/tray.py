"""System-tray host for the worker (Sprint 24, PySide6).

One process: the worker loop runs in a QThread, the tray lives in the main
(GUI) thread. The menu re-reads `policy.json` on every open, so Pause/Resume
always reflects reality; Quit stops the loop first, then the app.

GUI code is deliberately thin and untestable-by-construction; everything
decidable lives in the pure helpers below (status text, menu state), which
the test suite covers without a QApplication.
"""

from __future__ import annotations

import threading
import webbrowser
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TrayState:
    worker_id: str
    coordinator_url: str
    status: str  # online | paused | throttled | stopped | starting
    paused: bool
    units_completed: int = 0


def status_tooltip(state: TrayState) -> str:
    """One-line tray tooltip (pure, tested)."""
    short = state.worker_id[:8]
    base = f"CommunityCompute {state.status} ({short})"
    if state.paused:
        return base + " — paused by you"
    if state.units_completed:
        return f"{base} — {state.units_completed} units done"
    return base


def menu_state(paused: bool) -> dict:
    """Menu model for the current policy state (pure, tested)."""
    return {
        "pause_label": "Resume contributing" if paused else "Pause contributing",
        "pause_checked": paused,
    }


def dashboard_url(coordinator_url: str) -> str:
    return "http://127.0.0.1:5173"


class WorkerThread:
    """Runs `run_worker` off the GUI thread; stop() is idempotent."""

    def __init__(self, run_fn, args) -> None:
        self._run_fn = run_fn
        self._args = args
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._target, daemon=True,
                                        name="worker-loop")

    def start(self) -> None:
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=timeout)

    @property
    def running(self) -> bool:
        return self._thread.is_alive()

    def _target(self) -> None:
        try:
            self._run_fn(self._args, self._stop)
        except Exception:  # noqa: BLE001 - loop must never kill the tray silently
            import traceback

            traceback.print_exc()


def run_tray(args, run_worker_fn) -> int:
    """QApplication entry: tray + worker thread. Returns the Qt exit code."""
    from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
    from PySide6.QtGui import QAction, QIcon
    from PySide6.QtCore import QTimer

    from worker.policy.store import load_policy, policy_path, set_paused
    from worker.config import get_coordinator_url, get_worker_id_file

    id_file = get_worker_id_file(args.worker_id_file)
    policy_file = Path(args.policy_file) if args.policy_file else policy_path(id_file)
    coordinator_url = get_coordinator_url(args.coordinator_url)

    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)

    tray = QSystemTrayIcon()
    tray.setToolTip("CommunityCompute starting…")
    tray.show()

    menu = QMenu()
    status_action = QAction("Status: starting…")
    status_action.setEnabled(False)
    menu.addAction(status_action)

    pause_action = QAction("Pause contributing")
    pause_action.setCheckable(True)

    def refresh_menu() -> None:
        policy = load_policy(policy_file)
        state = menu_state(policy.paused)
        pause_action.setText(state["pause_label"])
        pause_action.setChecked(state["pause_checked"])
        tray.setToolTip(status_tooltip(TrayState(
            worker_id="…", coordinator_url=coordinator_url,
            status="paused" if policy.paused else "online",
            paused=policy.paused,
        )))

    def toggle_pause() -> None:
        policy = load_policy(policy_file)
        set_paused(policy_file, not policy.paused)
        refresh_menu()

    pause_action.triggered.connect(toggle_pause)
    menu.addAction(pause_action)

    open_dash = QAction("Open dashboard")
    open_dash.triggered.connect(lambda: webbrowser.open(dashboard_url(coordinator_url)))
    menu.addAction(open_dash)

    quit_action = QAction("Quit worker")
    quit_action.triggered.connect(app.quit)
    menu.addAction(quit_action)
    menu.aboutToShow.connect(refresh_menu)
    tray.setContextMenu(menu)
    refresh_menu()

    worker = WorkerThread(run_worker_fn, args)
    worker.start()
    app.aboutToQuit.connect(worker.stop)

    # Keep policy-driven tooltip fresh without blocking the GUI.
    ticker = QTimer()
    ticker.timeout.connect(refresh_menu)
    ticker.start(5000)
    return app.exec()


__all__ = ["TrayState", "WorkerThread", "dashboard_url", "menu_state",
           "run_tray", "status_tooltip"]
