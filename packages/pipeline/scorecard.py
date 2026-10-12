"""Placar automático de qualidade por Short.

Agrega os resultados do crítico por fala (CER, duração, clipping, silêncio,
prosódia, emoção) num resumo por Short: taxa de cada flag, médias das
métricas objetivas, as piores falas e um veredito de triagem.

Triagem, não decisão: o que entra é decidido por rótulo humano (taxa de
publicação), nunca por este placar (CLAUDE.md, "Avaliação de qualidade").
O conjunto de flags é o herdado do repo anterior e será redefinido pelo
crítico (T2.6).

Puro: recebe as falas e os resultados já prontos, devolve dados.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from statistics import fmean
from typing import Any

from packages.pipeline.lines import Line

FLAG_NAMES = (
    "fora_duracao",
    "cer_alto",
    "truncado",
    "traducao_infiel",
    "clipping",
    "silencio_anormal",
    "locutor_suspeito",
    "entonacao_desalinhada",
    "emocao_incompativel",
    "cer_final_alto",
    "loop_confirmado",
)

VERDICT_APROVADO = "aprovado"
VERDICT_REVISAR = "revisar"
VERDICT_PROBLEMATICO = "problematico"

# Não calibrado. Fração de falas com qualquer flag a partir da qual o
# veredito de triagem passa de "aprovado" pra "revisar", e depois pra
# "problemático".
REVIEW_RATE_THRESHOLD = 0.2
PROBLEMATIC_RATE_THRESHOLD = 0.5


@dataclass
class Scorecard:
    total_lines: int
    synthesized_lines: int
    flag_counts: dict[str, int]
    flag_rates: dict[str, float]
    flag_overlap: dict[str, dict[str, int]]
    lines_with_multiple_flags: int
    any_flag_rate: float
    avg_cer: float | None
    avg_cer_final: float | None
    avg_prosody_correlation: float | None
    avg_emotion_similarity: float | None
    worst_lines: list[dict[str, Any]]
    verdict: str


def _active_flags(result: Mapping[str, Any]) -> list[str]:
    flags = result.get("flags", {})
    return [name for name in FLAG_NAMES if flags.get(name)]


def _build_flag_overlap(results: list[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    """`overlap[a][b]` conta quantas falas têm as flags `a` E `b` ao mesmo
    tempo; a diagonal `overlap[a][a]` é igual a `flag_counts[a]`. Separa
    flags que marcam o MESMO problema (sempre aparecem juntas) de problemas
    independentes.
    """
    overlap: dict[str, dict[str, int]] = {a: dict.fromkeys(FLAG_NAMES, 0) for a in FLAG_NAMES}
    for result in results:
        active = _active_flags(result)
        for a in active:
            for b in active:
                overlap[a][b] += 1
    return overlap


def _verdict(any_flag_rate: float) -> str:
    if any_flag_rate >= PROBLEMATIC_RATE_THRESHOLD:
        return VERDICT_PROBLEMATICO
    if any_flag_rate >= REVIEW_RATE_THRESHOLD:
        return VERDICT_REVISAR
    return VERDICT_APROVADO


def _mean_or_none(values: list[float]) -> float | None:
    return fmean(values) if values else None


def build_scorecard(
    lines: Sequence[Line],
    results: Mapping[str, Mapping[str, Any]],
    *,
    worst_n: int = 5,
) -> dict[str, Any]:
    """Agrega `results[line.id]` (saída do crítico por fala) no placar do Short.

    Fala sem resultado ou sem síntese (`synthesized_ok=False`) entra na taxa
    de `any_flag` (falha total é a pior flag possível), mas fica de fora das
    taxas por flag e das médias: não tem métricas calculadas, e um "buraco"
    numérico distorceria a média.
    """
    total = len(lines)
    result_by_line = [(line, results.get(line.id, {})) for line in lines]
    synthesized = [r for _, r in result_by_line if r.get("synthesized_ok")]
    n_synth = len(synthesized)

    flag_counts = dict.fromkeys(FLAG_NAMES, 0)
    for result in synthesized:
        for name in _active_flags(result):
            flag_counts[name] += 1
    flag_rates = {
        name: (count / n_synth if n_synth else 0.0) for name, count in flag_counts.items()
    }

    def is_flagged(result: Mapping[str, Any]) -> bool:
        return bool(result.get("any_flag")) or not result.get("synthesized_ok")

    flagged = [(line, r) for line, r in result_by_line if is_flagged(r)]
    any_flag_rate = len(flagged) / total if total else 0.0

    flagged_sorted = sorted(
        flagged,
        key=lambda item: (len(_active_flags(item[1])), item[1].get("cer") or 0.0),
        reverse=True,
    )
    worst_lines = [
        {
            "id": line.id,
            "speaker": line.speaker,
            "start": line.start,
            "end": line.end,
            "flags": _active_flags(result),
            "cer": result.get("cer"),
        }
        for line, result in flagged_sorted[:worst_n]
    ]

    return asdict(
        Scorecard(
            total_lines=total,
            synthesized_lines=n_synth,
            flag_counts=flag_counts,
            flag_rates=flag_rates,
            flag_overlap=_build_flag_overlap(synthesized),
            lines_with_multiple_flags=sum(1 for r in synthesized if len(_active_flags(r)) >= 2),
            any_flag_rate=any_flag_rate,
            avg_cer=_mean_or_none([r["cer"] for r in synthesized if r.get("evaluated_ok")]),
            avg_cer_final=_mean_or_none(
                [r["cer_final"] for r in synthesized if r.get("cer_final") is not None]
            ),
            avg_prosody_correlation=_mean_or_none(
                [
                    r["prosody_correlation"]
                    for r in synthesized
                    if r.get("prosody_correlation") is not None
                ]
            ),
            avg_emotion_similarity=_mean_or_none(
                [
                    r["emotion_match"]["similarity"]
                    for r in synthesized
                    if r.get("emotion_match") is not None
                ]
            ),
            worst_lines=worst_lines,
            verdict=_verdict(any_flag_rate),
        )
    )
