"""Execução remota no Pod de desenvolvimento (SSH puro, sem serverless).

Wrapper fino em cima de `ssh`/`scp` (OpenSSH). Não usa rsync porque a
máquina de desenvolvimento é Windows e rsync não é garantido; `scp -r` dá
conta do volume que o pipeline move (poucos WAVs e JSONs por Short).

Config lida de variáveis de ambiente (ver `.env.example`):
    POD_HOST, POD_PORT, POD_USER (default "root"), POD_SSH_KEY_PATH,
    POD_WORKSPACE (diretório no Pod onde o repo está espelhado; prefira
    disco local a `/workspace`, que é volume de rede: bom pra pesos de
    modelo grandes, ruim pra muita escrita de arquivo pequeno).

    POD_PYTHON_ASR / POD_PYTHON_LLM / POD_PYTHON_TTS (opcionais): python de
    cada venv montado por `scripts/pod_setup.sh`. Sem elas, cai no default
    abaixo; se o Pod for recriado com outro layout, ajuste o `.env`.

    POD_LD_LIBRARY_PATH_ASR (opcional): faster-whisper (CTranslate2) não
    acha `libcudnn_ops_infer.so.8` sozinho mesmo com `nvidia-cudnn-cu12`
    instalado no venv: a lib existe em site-packages, só não está no linker
    path por padrão (achado do repo anterior).

    POD_HF_HOME (opcional): cache de pesos no Pod. Nem todo Pod tem volume
    de rede em `/workspace` (achado do repo anterior), por isso é
    configurável.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

_DEFAULT_PYTHON_ASR = "/root/venvs/asr/bin/python"
_DEFAULT_PYTHON_LLM = "/root/venvs/llm/bin/python"
_DEFAULT_PYTHON_TTS = "/root/venvs/tts/bin/python"
_DEFAULT_LD_LIBRARY_PATH_ASR = (
    "/root/venvs/asr/lib/python3.11/site-packages/nvidia/cudnn/lib:"
    "/root/venvs/asr/lib/python3.11/site-packages/nvidia/cublas/lib"
)
_DEFAULT_HF_HOME = "/workspace/hf_cache"


@dataclass
class PodConfig:
    host: str
    port: int
    user: str
    key_path: str
    workspace: str
    python_asr: str
    python_llm: str
    python_tts: str
    ld_library_path_asr: str
    hf_home: str

    @classmethod
    def from_env(cls) -> PodConfig:
        missing = [
            name
            for name in ("POD_HOST", "POD_PORT", "POD_SSH_KEY_PATH", "POD_WORKSPACE")
            if not os.environ.get(name)
        ]
        if missing:
            raise RuntimeError(
                f"variáveis de ambiente do Pod não configuradas: {', '.join(missing)}"
            )
        return cls(
            host=os.environ["POD_HOST"],
            port=int(os.environ["POD_PORT"]),
            user=os.environ.get("POD_USER") or "root",
            key_path=os.path.expanduser(os.environ["POD_SSH_KEY_PATH"]),
            workspace=os.environ["POD_WORKSPACE"],
            python_asr=os.environ.get("POD_PYTHON_ASR") or _DEFAULT_PYTHON_ASR,
            python_llm=os.environ.get("POD_PYTHON_LLM") or _DEFAULT_PYTHON_LLM,
            python_tts=os.environ.get("POD_PYTHON_TTS") or _DEFAULT_PYTHON_TTS,
            ld_library_path_asr=(
                os.environ.get("POD_LD_LIBRARY_PATH_ASR") or _DEFAULT_LD_LIBRARY_PATH_ASR
            ),
            hf_home=os.environ.get("POD_HF_HOME") or _DEFAULT_HF_HOME,
        )


def run_on_pod(config: PodConfig, command: str, env: dict[str, str] | None = None) -> None:
    """Roda `command` no Pod, dentro de `config.workspace` (via `cd &&`).

    `env`, se passado, vira `KEY=VALUE` na frente do comando: um comando SSH
    não-interativo não carrega `~/.bashrc` (onde `HF_HOME` estaria).

    Não usa `check=True`: `subprocess.CalledProcessError` inclui o `cmd`
    completo na mensagem, o que vazaria segredos como `HF_TOKEN` em texto
    puro (achado do repo anterior). Em erro, levanta com uma versão do
    comando com os valores de `env` redigidos.
    """
    env_prefix = " ".join(f"{k}={shlex.quote(v)}" for k, v in (env or {}).items())
    full_command = f"{env_prefix} {command}".strip()
    ssh_command = [
        "ssh",
        "-i",
        config.key_path,
        "-p",
        str(config.port),
        f"{config.user}@{config.host}",
        f"cd {shlex.quote(config.workspace)} && {full_command}",
    ]
    result = subprocess.run(ssh_command, check=False)
    if result.returncode != 0:
        redacted_env_prefix = " ".join(f"{k}=***" for k in (env or {}))
        redacted_command = f"cd {config.workspace} && {redacted_env_prefix} {command}".strip()
        raise RuntimeError(
            f"comando no Pod falhou (exit {result.returncode}): {redacted_command}"
        )


def _checked_remote_relative(path: str) -> str:
    """Recusa caminho que faria o `rm -rf` do upload apagar fora do destino:
    vazio, absoluto, `.` ou com `..`."""
    pure = PurePosixPath(path)
    if not path.strip() or pure.is_absolute() or ".." in pure.parts or pure == PurePosixPath("."):
        raise ValueError(f"caminho remoto inválido para upload: {path!r}")
    return pure.as_posix()


def upload_to_pod(config: PodConfig, local_path: str, remote_relative_path: str) -> None:
    """Sobe `local_path` pro Pod em `remote_relative_path` (relativo a `config.workspace`).

    Achado do repo anterior: `scp -r` não SUBSTITUI um diretório remoto que
    já existe com o mesmo nome; ele copia `local_path` PRA DENTRO dele,
    criando `remote/<nome>/<nome>/` aninhado. O conteúdo antigo ficava
    visível no nível esperado e o novo escondido um nível abaixo. Pra
    diretório, o destino remoto é apagado antes de subir: upload de
    diretório é sempre "substituir", nunca "mesclar".
    """
    remote = _checked_remote_relative(remote_relative_path)
    if Path(local_path).is_dir():
        run_on_pod(config, f"rm -rf {shlex.quote(remote)}")
    subprocess.run(
        [
            "scp",
            "-i",
            config.key_path,
            "-P",
            str(config.port),
            "-r",
            local_path,
            f"{config.user}@{config.host}:{config.workspace}/{remote}",
        ],
        check=True,
    )


def download_from_pod(config: PodConfig, remote_relative_path: str, local_path: str) -> None:
    """Baixa `remote_relative_path` do Pod pra `local_path`.

    Mesmo bug do `upload_to_pod`, na direção contrária: `scp -r` copia um
    diretório remoto PRA DENTRO de um diretório local que já existe. Áudio
    de rodadas anteriores acabou em vídeos finais. Diretório local
    existente é substituído, nunca mesclado.
    """
    if Path(local_path).is_dir():
        shutil.rmtree(local_path)
    subprocess.run(
        [
            "scp",
            "-i",
            config.key_path,
            "-P",
            str(config.port),
            "-r",
            f"{config.user}@{config.host}:{config.workspace}/{remote_relative_path}",
            local_path,
        ],
        check=True,
    )
