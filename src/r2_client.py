import boto3
from pathlib import Path


def make_client(credentials: dict):
    account_id = credentials["account_id"]
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=credentials["access_key_id"],
        aws_secret_access_key=credentials["secret_access_key"],
        region_name="auto",
    )


def list_objects(client, bucket: str) -> set[str]:
    """Retorna el conjunto de keys en el bucket."""
    keys = set()
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            keys.add(obj["Key"])
    return keys


def upload(client, bucket: str, key: str, local_path: Path) -> None:
    client.upload_file(str(local_path), bucket, key)


def download(client, bucket: str, key: str, local_path: Path) -> None:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    client.download_file(bucket, key, str(local_path))


def delete(client, bucket: str, key: str) -> None:
    client.delete_object(Bucket=bucket, Key=key)


def delete_prefix(client, bucket: str, prefix: str) -> None:
    """Elimina todos los objetos cuyo key empiece con prefix."""
    keys = [k for k in list_objects(client, bucket) if k.startswith(prefix)]
    if not keys:
        return
    client.delete_objects(
        Bucket=bucket,
        Delete={"Objects": [{"Key": k} for k in keys]}
    )
