import re
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from src import database as db, r2_client as r2, sync_guard as guard

log = logging.getLogger(__name__)

_BOTO3_TMP = re.compile(r'\.[0-9a-fA-F]{8}$')


def _is_tmp(path: str) -> bool:
    return bool(_BOTO3_TMP.search(Path(path).name))


def _to_key(local_root: Path, file_path: str) -> str:
    return Path(file_path).relative_to(local_root).as_posix()


class BucketEventHandler(FileSystemEventHandler):
    def __init__(self, bucket: str, local_root: Path, client):
        self.bucket = bucket
        self.local_root = local_root
        self.client = client

    def _key(self, path: str) -> str:
        return _to_key(self.local_root, path)

    def on_created(self, event):
        if event.is_directory or _is_tmp(event.src_path) or guard.is_ignored(event.src_path):
            return
        p = Path(event.src_path)
        if not p.is_file():
            return
        key = self._key(event.src_path)
        db.upsert(self.bucket, key, db.SYNC_PENDING)
        try:
            r2.upload(self.client, self.bucket, key, Path(event.src_path))
            db.upsert(self.bucket, key, db.SYNCED)
        except Exception as e:
            log.error("Upload failed %s: %s", key, e)
            db.upsert(self.bucket, key, db.SYNC_FAILED)

    def on_deleted(self, event):
        if _is_tmp(event.src_path) or guard.is_ignored(event.src_path):
            return
        key = self._key(event.src_path)
        if event.is_directory:
            r2.delete_prefix(self.client, self.bucket, key + "/")
            db.delete_prefix(self.bucket, key + "/")
        else:
            try:
                r2.delete(self.client, self.bucket, key)
            except Exception as e:
                log.error("Delete failed %s: %s", key, e)
            db.delete(self.bucket, key)

    def on_moved(self, event):
        if _is_tmp(event.src_path) or _is_tmp(event.dest_path):
            return
        old_key = self._key(event.src_path)
        new_key = self._key(event.dest_path)
        if event.is_directory:
            r2.delete_prefix(self.client, self.bucket, old_key + "/")
            db.delete_prefix(self.bucket, old_key + "/")
            # Upload all files in new location
            for f in Path(event.dest_path).rglob("*"):
                if f.is_file():
                    k = _to_key(self.local_root, str(f))
                    db.upsert(self.bucket, k, db.SYNC_PENDING)
                    try:
                        r2.upload(self.client, self.bucket, k, f)
                        db.upsert(self.bucket, k, db.SYNCED)
                    except Exception as e:
                        log.error("Upload failed %s: %s", k, e)
                        db.upsert(self.bucket, k, db.SYNC_FAILED)
        else:
            try:
                r2.delete(self.client, self.bucket, old_key)
                r2.upload(self.client, self.bucket, new_key, Path(event.dest_path))
                db.delete(self.bucket, old_key)
                db.upsert(self.bucket, new_key, db.SYNCED)
            except Exception as e:
                log.error("Move failed %s -> %s: %s", old_key, new_key, e)
                db.upsert(self.bucket, new_key, db.SYNC_FAILED)

    def on_modified(self, event):
        if event.is_directory or _is_tmp(event.src_path) or guard.is_ignored(event.src_path):
            return
        if not Path(event.src_path).is_file():
            return
        key = self._key(event.src_path)
        db.upsert(self.bucket, key, db.SYNC_PENDING)
        try:
            r2.upload(self.client, self.bucket, key, Path(event.src_path))
            db.upsert(self.bucket, key, db.SYNCED)
        except Exception as e:
            log.error("Upload failed %s: %s", key, e)
            db.upsert(self.bucket, key, db.SYNC_FAILED)


def start_watchers(buckets: list[dict], client) -> Observer:
    observer = Observer()
    for b in buckets:
        local_root = Path(b["local_path"])
        local_root.mkdir(parents=True, exist_ok=True)
        handler = BucketEventHandler(b["name"], local_root, client)
        observer.schedule(handler, str(local_root), recursive=True)
        log.info("Watching %s -> bucket:%s", local_root, b["name"])
    observer.start()
    return observer
