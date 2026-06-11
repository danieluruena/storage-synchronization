#!/usr/bin/env python3
"""Instala o desinstala R2 Sync como servicio del sistema."""
import sys
import os
import subprocess
import time
from pathlib import Path

SERVICE_NAME = "R2SyncService"
SERVICE_DISPLAY = "R2 Cloudflare Sync Service"
SCRIPT_DIR = Path(__file__).parent.resolve()
SERVICE_SCRIPT = SCRIPT_DIR / "src" / "service.py"
VENV_PYTHON = str((SCRIPT_DIR / ".venv" / "Scripts" / "python.exe").resolve())
NSSM = str(SCRIPT_DIR / "nssm.exe")


def _real_python() -> str:
    """Devuelve el python.exe real, no el redirector py.exe del venv."""
    result = subprocess.run(
        [VENV_PYTHON, "-c", "import sys; print(sys._base_executable)"],
        capture_output=True, text=True
    )
    exe = result.stdout.strip()
    if exe and Path(exe).exists():
        return exe
    return VENV_PYTHON


def _wait_service_gone(timeout: int = 15) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = subprocess.run(["sc", "query", SERVICE_NAME], capture_output=True)
        if r.returncode != 0:
            return True
        time.sleep(1)
    return False


def install_windows():
    if not _wait_service_gone():
        print("El servicio anterior no se elimino a tiempo. Reintenta en unos segundos.")
        sys.exit(1)

    subprocess.run([NSSM, "install", SERVICE_NAME, _real_python(),
                    f'"{SERVICE_SCRIPT}"'], check=True)
    subprocess.run([NSSM, "set", SERVICE_NAME, "DisplayName", SERVICE_DISPLAY], check=True)
    subprocess.run([NSSM, "set", SERVICE_NAME, "Description",
                    "Sincroniza carpetas locales con buckets de Cloudflare R2."], check=True)
    subprocess.run([NSSM, "set", SERVICE_NAME, "AppDirectory", str(SCRIPT_DIR)], check=True)
    subprocess.run([NSSM, "set", SERVICE_NAME, "AppEnvironmentExtra",
                    f"PYTHONPATH={SCRIPT_DIR}",
                    f"R2SYNC_HOME={Path.home()}"], check=True)
    subprocess.run([NSSM, "set", SERVICE_NAME, "Start", "SERVICE_AUTO_START"], check=True)
    subprocess.run([NSSM, "set", SERVICE_NAME, "AppExit", "Default", "Restart"], check=True)
    subprocess.run([NSSM, "set", SERVICE_NAME, "AppRestartDelay", "3000"], check=True)
    result = subprocess.run([NSSM, "start", SERVICE_NAME])
    if result.returncode != 0:
        print("Advertencia: el servicio se instalo pero no pudo iniciarse automaticamente.")
        print("Inicia manualmente con: nssm start " + SERVICE_NAME)
    else:
        print("Servicio '" + SERVICE_NAME + "' instalado e iniciado.")


def uninstall_windows():
    subprocess.run([NSSM, "stop", SERVICE_NAME])
    time.sleep(2)
    subprocess.run([NSSM, "remove", SERVICE_NAME, "confirm"], check=True)
    print("Servicio '" + SERVICE_NAME + "' eliminado.")


def install_linux():
    unit = f"""[Unit]
Description=R2 Cloudflare Sync Service
After=network.target

[Service]
Type=simple
ExecStart={VENV_PYTHON} {SERVICE_SCRIPT}
Environment=PYTHONPATH={SCRIPT_DIR}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
    unit_path = Path("/etc/systemd/system/r2sync.service")
    unit_path.write_text(unit)
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "enable", "--now", "r2sync"], check=True)
    print("Servicio 'r2sync' instalado e iniciado.")


def uninstall_linux():
    subprocess.run(["systemctl", "disable", "--now", "r2sync"])
    Path("/etc/systemd/system/r2sync.service").unlink(missing_ok=True)
    subprocess.run(["systemctl", "daemon-reload"])
    print("Servicio 'r2sync' eliminado.")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "install"
    if sys.platform == "win32":
        install_windows() if action == "install" else uninstall_windows()
    else:
        if os.geteuid() != 0:
            print("Ejecuta como root: sudo python install_service.py")
            sys.exit(1)
        install_linux() if action == "install" else uninstall_linux()
