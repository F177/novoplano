from pathlib import Path
from typing import Any

import pytest

from scripts import r2


class _FakeS3:
    def __init__(self) -> None:
        self.downloads: list[tuple[str, str, str]] = []

    def download_file(self, bucket: str, key: str, path: str) -> None:
        self.downloads.append((bucket, key, path))


def test_download_uses_r2_endpoint_and_creates_parent_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("R2_ACCOUNT_ID", "acct")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("R2_BUCKET", "bucket")
    fake = _FakeS3()
    client_args: dict[str, Any] = {}

    def fake_client(service: str, **kwargs: Any) -> _FakeS3:
        client_args.update(service=service, **kwargs)
        return fake

    monkeypatch.setattr(r2.boto3, "client", fake_client)
    target = tmp_path / "nested" / "dir" / "short.mp4"
    r2.download("shorts/short.mp4", target)

    assert target.parent.is_dir()
    assert fake.downloads == [("bucket", "shorts/short.mp4", str(target))]
    assert client_args["service"] == "s3"
    assert client_args["endpoint_url"] == "https://acct.r2.cloudflarestorage.com"
    assert client_args["region_name"] == "auto"
