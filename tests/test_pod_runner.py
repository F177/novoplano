import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts import pod_runner
from scripts.pod_runner import PodConfig, download_from_pod, run_on_pod, upload_to_pod

_REQUIRED_ENV = {
    "POD_HOST": "1.2.3.4",
    "POD_PORT": "2222",
    "POD_SSH_KEY_PATH": "/keys/pod",
    "POD_WORKSPACE": "/root/repo",
}


def _config() -> PodConfig:
    return PodConfig(
        host="1.2.3.4",
        port=2222,
        user="root",
        key_path="/keys/pod",
        workspace="/root/repo",
        python_asr="/a",
        python_llm="/l",
        python_tts="/t",
        ld_library_path_asr="",
        hf_home="/hf",
    )


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    recorded: list[list[str]] = []

    def fake_run(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess[bytes]:
        recorded.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(pod_runner.subprocess, "run", fake_run)
    return recorded


def test_from_env_requires_connection_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _REQUIRED_ENV:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError, match="POD_HOST"):
        PodConfig.from_env()


def test_from_env_uses_defaults_for_empty_optional_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in _REQUIRED_ENV.items():
        monkeypatch.setenv(name, value)
    # .env.example deixa as opcionais vazias: vazio vale como ausente
    for name in ("POD_USER", "POD_PYTHON_ASR", "POD_PYTHON_LLM", "POD_PYTHON_TTS", "POD_HF_HOME"):
        monkeypatch.setenv(name, "")
    config = PodConfig.from_env()
    assert config.port == 2222
    assert config.user == "root"
    assert config.python_asr == "/root/venvs/asr/bin/python"
    assert config.python_llm == "/root/venvs/llm/bin/python"
    assert config.python_tts == "/root/venvs/tts/bin/python"
    assert config.hf_home == "/workspace/hf_cache"


def test_run_on_pod_runs_inside_workspace(calls: list[list[str]]) -> None:
    run_on_pod(_config(), "ls", env={"HF_HOME": "/hf"})
    ssh = calls[0]
    assert ssh[:5] == ["ssh", "-i", "/keys/pod", "-p", "2222"]
    assert ssh[5] == "root@1.2.3.4"
    assert ssh[6] == "cd /root/repo && HF_HOME=/hf ls"


def test_run_on_pod_failure_redacts_env_values(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_run(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(cmd, 1)

    monkeypatch.setattr(pod_runner.subprocess, "run", failing_run)
    with pytest.raises(RuntimeError) as exc_info:
        run_on_pod(_config(), "transcribe", env={"HF_TOKEN": "hf_secret"})
    assert "hf_secret" not in str(exc_info.value)
    assert "HF_TOKEN=***" in str(exc_info.value)


def test_upload_directory_clears_remote_destination_first(
    tmp_path: Path, calls: list[list[str]]
) -> None:
    upload_to_pod(_config(), str(tmp_path), "jobs/short1")
    rm, scp = calls
    assert rm[0] == "ssh"
    assert rm[-1] == "cd /root/repo && rm -rf jobs/short1"
    assert scp[0] == "scp"
    assert scp[-2:] == [str(tmp_path), "root@1.2.3.4:/root/repo/jobs/short1"]


def test_upload_file_does_not_delete_anything(tmp_path: Path, calls: list[Any]) -> None:
    file = tmp_path / "a.wav"
    file.write_bytes(b"x")
    upload_to_pod(_config(), str(file), "jobs/a.wav")
    assert len(calls) == 1
    assert calls[0][0] == "scp"


def test_upload_quotes_remote_path_in_rm(tmp_path: Path, calls: list[list[str]]) -> None:
    upload_to_pod(_config(), str(tmp_path), "jobs/a b;x")
    assert calls[0][-1] == "cd /root/repo && rm -rf 'jobs/a b;x'"


@pytest.mark.parametrize("remote", ["", " ", ".", "/", "/root", "../x", "jobs/../.."])
def test_upload_rejects_paths_that_escape_destination(
    tmp_path: Path, calls: list[list[str]], remote: str
) -> None:
    with pytest.raises(ValueError):
        upload_to_pod(_config(), str(tmp_path), remote)
    assert calls == []


def test_download_replaces_existing_local_directory(
    tmp_path: Path, calls: list[list[str]]
) -> None:
    local = tmp_path / "synth"
    local.mkdir()
    (local / "old.wav").write_bytes(b"old")
    download_from_pod(_config(), "jobs/synth", str(local))
    assert not local.exists()
    assert calls[0][-2:] == ["root@1.2.3.4:/root/repo/jobs/synth", str(local)]
