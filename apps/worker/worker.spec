# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller bundle for the CommunityCompute worker (Sprint 24).

One-directory console build: `dist/worker/worker.exe`. The console stays
visible on purpose (prototype: logs are the UI until the tray matures).
A windowed build comes with the tray milestone, not here.
"""

from pathlib import Path

# PyInstaller defines SPECPATH (this spec file's directory) at build time:
# apps/worker/worker.spec -> parents: [worker, apps, <repo root>].
REPO_ROOT = Path(SPECPATH).resolve().parent.parent  # noqa: F821 - provided by PyInstaller
WORKER_DIR = REPO_ROOT / "apps" / "worker"

a = Analysis(
    [str(WORKER_DIR / "worker" / "main.py")],
    pathex=[str(WORKER_DIR)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "worker.config",
        "worker.registration",
        "worker.heartbeat",
        "worker.work",
        "worker.monitoring",
        "worker.gpu_stats",
        "worker.credentials",
        "worker.policy.schema",
        "worker.policy.engine",
        "worker.policy.state",
        "worker.policy.store",
        "worker.capabilities.cpu",
        "worker.capabilities.ram",
        "worker.capabilities.os_info",
        "worker.capabilities.schema",
        "worker.capabilities.discover",
        "worker.capabilities.client",
        "worker.capabilities.gpu.base",
        "worker.capabilities.gpu.nvidia",
        "worker.capabilities.gpu.wmi",
        "worker.capabilities.gpu.unknown",
        "worker.capabilities.gpu.registry",
        "worker.execution.executor",
        "worker.execution.registry",
        "worker.execution.hello_compute",
        "worker.execution.stats_range",
        "worker.execution.embeddings.embedder",
        "worker.execution.embeddings.executor",
        "worker.models.cache",
        "worker.models.manifest",
        "worker.security.paths",
        "worker.sandbox.sandbox",
        "worker.sandbox.native",
        "worker.sandbox.launch",
        "worker.sandbox.runner",
        "worker.setup_wizard",
        "worker.autostart",
        "worker.tray",
        "packages.protocol",
        "packages.protocol.signing",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "PySide6.QtWebEngine", "PySide6.QtPdf"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="worker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # off: antivirus false-positives on UPX-packed community binaries
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="worker",
)
