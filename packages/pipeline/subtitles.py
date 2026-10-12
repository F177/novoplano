"""Geração de legendas pt-BR (SRT) a partir das falas dubladas.

Pura, sem I/O: uma legenda por fala, no tempo da fala original. Quando o
solver de timing (T2.7) existir, o tempo exibido passa a ser o da fala
dublada posicionada. O embutimento no vídeo (ffmpeg) fica no render.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from packages.pipeline.lines import Line


def _format_srt_timestamp(seconds: float) -> str:
    """`HH:MM:SS,mmm`, formato exigido pelo SRT (vírgula nos milissegundos,
    não ponto)."""
    if seconds < 0:
        seconds = 0.0
    total_ms = round(seconds * 1000)
    hours, rem_ms = divmod(total_ms, 3_600_000)
    minutes, rem_ms = divmod(rem_ms, 60_000)
    secs, ms = divmod(rem_ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def build_srt(lines: Sequence[Line], text_by_line: Mapping[str, str]) -> str:
    """Monta o conteúdo de um arquivo `.srt`: uma entrada por fala, com o
    texto dublado de `text_by_line[line.id]`.

    Ordena por início (SRT exige ordem crescente) e descarta falas sem texto
    útil (ausente, vazio ou só espaço): nada pra mostrar, evita legenda
    "fantasma".
    """
    entries = [
        (line.start, line.end, text_by_line.get(line.id, "").strip()) for line in lines
    ]
    sorted_entries = sorted((e for e in entries if e[2]), key=lambda e: e[0])

    out: list[str] = []
    for index, (start, end, text) in enumerate(sorted_entries, start=1):
        out.append(str(index))
        out.append(f"{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}")
        out.append(text)
        out.append("")
    return "\n".join(out)
