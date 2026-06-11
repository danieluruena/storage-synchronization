import logging
import logging.handlers
import os
import sys
import signal
import threading
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).parent.parent.resolve())
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

_VENV_SITE = Path(__file__).parent.parent / ".venv" / "Lib" / "site-packages"
if _VENV_SITE.exists() and str(_VENV_SITE) not in sys.path:
    sys.path.insert(1, str(_VENV_SITE))

_LOG_FILE = Path(os.environ["R2SYNC_HOME"].strip()) / "r2sync_service.log" if "R2SYNC_HOME" in os.environ else Path(__file__).parent.parent / "r2sync_service.log"
_handlers = [logging.handlers.RotatingFileHandler(
    _LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
)]
if sys.stdout is not None:
    _handlers.append(logging.StreamHandler(sys.stdout))
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=_handlers,
)
log = logging.getLogger("r2sync.service")

try:
    from src.config import load_config
    from src.database import init_db
    from src import r2_client as r2
    from src.watcher import start_watchers
    from src.sync import start_sync
except Exception as e:
    log.critical("Import failed: %s", e, exc_info=True)
    sys.exit(1)

_shutdown = threading.Event()


def _run():
    init_db()
    config = load_config()
    creds = config.get("credentials", {})
    buckets = config.get("buckets", [])

    if not buckets:
        log.warning("No buckets configured. Edit config with: python cli.py")
        log.info("Service is running but idle. Add buckets and restart the service.")
        _shutdown.wait()
        return

    client = r2.make_client(creds)
    observer = start_watchers(buckets, client)
    stop_event = start_sync(buckets, client)

    log.info("R2 Sync service started. Monitoring %d bucket(s).", len(buckets))
    _shutdown.wait()
    log.info("Stopping service...")
    stop_event.set()
    observer.stop()
    observer.join()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: _shutdown.set())
    signal.signal(signal.SIGINT, lambda *_: _shutdown.set())
    if sys.platform == "win32":
        try:
            import win32api
            win32api.SetConsoleCtrlHandler(lambda _: (_shutdown.set(), True)[1], True)
        except Exception:
            pass  # Sin consola cuando corre como servicio
    try:
        _run()
    except Exception:
        log.critical("Unhandled exception", exc_info=True)
        sys.exit(1)
