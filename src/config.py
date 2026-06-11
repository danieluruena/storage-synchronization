import json
import os
import platform
import hashlib
from pathlib import Path
from cryptography.fernet import Fernet

CONFIG_FILENAME = ".r2sync_config.enc"


def _derive_key() -> bytes:
    """Deriva una clave Fernet a partir del hostname de la máquina."""
    machine_id = platform.node()
    digest = hashlib.sha256(machine_id.encode()).digest()
    import base64
    return base64.urlsafe_b64encode(digest)


def _fernet() -> Fernet:
    return Fernet(_derive_key())


def config_path() -> Path:
    base = Path(os.environ["R2SYNC_HOME"].strip()) if "R2SYNC_HOME" in os.environ else Path.home()
    return base / CONFIG_FILENAME


def load_config() -> dict:
    path = config_path()
    if not path.exists():
        return {"credentials": {}, "buckets": []}
    data = path.read_bytes()
    return json.loads(_fernet().decrypt(data))


def save_config(config: dict) -> None:
    encrypted = _fernet().encrypt(json.dumps(config, indent=2).encode())
    config_path().write_bytes(encrypted)


def default_config() -> dict:
    return {
        "credentials": {
            "account_id": "",
            "access_key_id": "",
            "secret_access_key": ""
        },
        "buckets": []
        # bucket entry: {"name": "my-bucket", "local_path": "/path/to/folder"}
    }
