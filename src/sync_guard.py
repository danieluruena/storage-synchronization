import threading

_lock = threading.Lock()
_ignored: set[str] = set()


def ignore(path: str) -> None:
    with _lock:
        _ignored.add(path)


def unignore(path: str) -> None:
    with _lock:
        _ignored.discard(path)


def is_ignored(path: str) -> bool:
    with _lock:
        return path in _ignored
