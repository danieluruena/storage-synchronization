import re
import logging
import threading
import time
from pathlib import Path
from src import database as db, r2_client as r2, sync_guard as guard

log = logging.getLogger(__name__)
INTERVAL = 30
_DELETE_RETRIES = 3
_DELETE_RETRY_DELAY = 0.5
_BOTO3_TMP = re.compile(r'\.[0-9a-fA-F]{8}')


def _unlink_with_retry(path: Path) -> None:
    for attempt in range(_DELETE_RETRIES):
        try:
            path.unlink()
            return
        except PermissionError as e:
            print(f"PermissionError deleting {path}, attempt {attempt + 1}/{_DELETE_RETRIES}: {e}")
            if attempt < _DELETE_RETRIES - 1:
                time.sleep(_DELETE_RETRY_DELAY)
            else:
                raise


def _sync_bucket(bucket_cfg: dict, client) -> None:
    bucket = bucket_cfg["name"]
    local_root = Path(bucket_cfg["local_path"])

    try:
        remote_keys = r2.list_objects(client, bucket)
    except Exception as e:
        log.error("Failed to list bucket %s: %s", bucket, e)
        return

    # Build local file set relative to local_root
    local_keys = {
        f.relative_to(local_root).as_posix()
        for f in local_root.rglob("*") if f.is_file()
    }

    # Separate folder markers (keys ending in /) from actual files
    remote_dirs = {k for k in remote_keys if k.endswith("/")}
    remote_files = {k for k in remote_keys - remote_dirs if not _BOTO3_TMP.search(Path(k).name)}

    # Ensure remote folder structure exists locally
    for dir_key in remote_dirs:
        (local_root / dir_key).mkdir(parents=True, exist_ok=True)

    # Download files present in R2 but missing locally
    for key in remote_files - local_keys:
        local_path = str(local_root / key)
        guard.ignore(local_path)
        db.upsert(bucket, key, db.SYNC_PENDING)
        try:
            r2.download(client, bucket, key, Path(local_path))
            db.upsert(bucket, key, db.SYNCED)
            log.info("Downloaded %s/%s", bucket, key)
        except Exception as e:
            log.error("Download failed %s/%s: %s", bucket, key, e)
            db.upsert(bucket, key, db.SYNC_FAILED)
        finally:
            guard.unignore(local_path)

    # Delete local files removed from R2 that are SYNCED
    synced_paths = db.get_synced_paths(bucket)
    for key in synced_paths - remote_files:
        local_path = str(local_root / key)
        guard.ignore(local_path)
        try:
            p = Path(local_path)
            if p.exists():
                _unlink_with_retry(p)
                log.info("Deleted local %s (removed from R2)", local_path)
            db.delete(bucket, key)
        except PermissionError:
            log.error("Permission denied deleting %s, will retry next cycle", local_path)
        finally:
            guard.unignore(local_path)


def _run_loop(buckets: list[dict], client, stop_event: threading.Event) -> None:
    while True:
        try:
            for b in buckets:
                _sync_bucket(b, client)
        except Exception as e:
            log.error("Sync loop error: %s", e, exc_info=True)
        if stop_event.wait(INTERVAL):
            break


def start_sync(buckets: list[dict], client) -> threading.Event:
    stop_event = threading.Event()
    t = threading.Thread(target=_run_loop, args=(buckets, client, stop_event), daemon=True)
    t.start()
    return stop_event
