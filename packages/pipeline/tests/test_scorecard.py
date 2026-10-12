from typing import Any

import pytest

from packages.pipeline.lines import Line
from packages.pipeline.scorecard import (
    FLAG_NAMES,
    PROBLEMATIC_RATE_THRESHOLD,
    REVIEW_RATE_THRESHOLD,
    VERDICT_APROVADO,
    VERDICT_PROBLEMATICO,
    VERDICT_REVISAR,
    build_scorecard,
)


def _lines(n: int) -> list[Line]:
    return [
        Line(
            id=f"l{i:04d}",
            speaker="A" if i % 2 == 0 else "B",
            start=float(i),
            end=i + 0.9,
            window_start=float(i),
            window_end=i + 1.0,
            source_text="source",
        )
        for i in range(n)
    ]


def _flags(**overrides: bool) -> dict[str, bool]:
    base = dict.fromkeys(FLAG_NAMES, False)
    base.update(overrides)
    return base


def _clean_result(cer: float = 0.05) -> dict[str, Any]:
    return {
        "synthesized_ok": True,
        "evaluated_ok": True,
        "cer": cer,
        "cer_final": cer,
        "prosody_correlation": 0.8,
        "emotion_match": {"similarity": 0.9},
        "flags": _flags(),
        "any_flag": False,
    }


def _clean_results(lines: list[Line]) -> dict[str, dict[str, Any]]:
    return {line.id: _clean_result() for line in lines}


def _flag(result: dict[str, Any], **flags: bool) -> None:
    result["flags"] = _flags(**flags)
    result["any_flag"] = True


def test_build_scorecard_all_clean_is_aprovado() -> None:
    lines = _lines(10)
    scorecard = build_scorecard(lines, _clean_results(lines))
    assert scorecard["verdict"] == VERDICT_APROVADO
    assert scorecard["any_flag_rate"] == 0.0
    assert scorecard["total_lines"] == 10
    assert scorecard["synthesized_lines"] == 10


def test_build_scorecard_computes_flag_rates() -> None:
    lines = _lines(10)
    results = _clean_results(lines)
    for line in lines[:3]:
        _flag(results[line.id], cer_alto=True)
    scorecard = build_scorecard(lines, results)
    assert scorecard["flag_counts"]["cer_alto"] == 3
    assert scorecard["flag_rates"]["cer_alto"] == 0.3
    assert scorecard["any_flag_rate"] == 0.3


def test_build_scorecard_averages_objective_metrics() -> None:
    lines = _lines(2)
    results = {"l0000": _clean_result(cer=0.1), "l0001": _clean_result(cer=0.3)}
    scorecard = build_scorecard(lines, results)
    assert scorecard["avg_cer"] == pytest.approx(0.2)


def test_build_scorecard_review_verdict_at_threshold() -> None:
    lines = _lines(10)
    results = _clean_results(lines)
    for line in lines[: int(REVIEW_RATE_THRESHOLD * 10)]:
        _flag(results[line.id], clipping=True)
    scorecard = build_scorecard(lines, results)
    assert scorecard["verdict"] == VERDICT_REVISAR


def test_build_scorecard_problematico_verdict_above_threshold() -> None:
    lines = _lines(10)
    results = _clean_results(lines)
    for line in lines[: int(PROBLEMATIC_RATE_THRESHOLD * 10) + 1]:
        _flag(results[line.id], silencio_anormal=True)
    scorecard = build_scorecard(lines, results)
    assert scorecard["verdict"] == VERDICT_PROBLEMATICO


def test_build_scorecard_unsynthesized_line_counts_as_any_flag_only() -> None:
    lines = _lines(2)
    results = {
        "l0000": _clean_result(),
        "l0001": {"synthesized_ok": False, "evaluated_ok": False, "any_flag": True},
    }
    scorecard = build_scorecard(lines, results)
    assert scorecard["total_lines"] == 2
    assert scorecard["synthesized_lines"] == 1
    assert scorecard["any_flag_rate"] == 0.5
    # fala sem síntese não deveria contaminar a média de CER
    assert scorecard["avg_cer"] == 0.05


def test_build_scorecard_line_without_result_counts_as_failed() -> None:
    lines = _lines(2)
    scorecard = build_scorecard(lines, {"l0000": _clean_result()})
    assert scorecard["synthesized_lines"] == 1
    assert scorecard["any_flag_rate"] == 0.5
    assert [w["id"] for w in scorecard["worst_lines"]] == ["l0001"]


def test_build_scorecard_empty_lines_does_not_crash() -> None:
    scorecard = build_scorecard([], {})
    assert scorecard["total_lines"] == 0
    assert scorecard["any_flag_rate"] == 0.0
    assert scorecard["avg_cer"] is None
    assert scorecard["verdict"] == VERDICT_APROVADO


def test_build_scorecard_worst_lines_sorted_by_flag_count_desc() -> None:
    lines = _lines(3)
    results = _clean_results(lines)
    _flag(results["l0000"], cer_alto=True)
    _flag(results["l0001"], cer_alto=True, clipping=True, truncado=True)
    scorecard = build_scorecard(lines, results, worst_n=5)
    worst_ids = [w["id"] for w in scorecard["worst_lines"]]
    assert worst_ids[0] == "l0001"
    assert "l0002" not in worst_ids


def test_build_scorecard_worst_lines_carry_speaker_and_times() -> None:
    lines = _lines(2)
    results = _clean_results(lines)
    _flag(results["l0001"], cer_alto=True)
    worst = build_scorecard(lines, results)["worst_lines"][0]
    assert worst["speaker"] == "B"
    assert (worst["start"], worst["end"]) == (1.0, 1.9)
    assert worst["flags"] == ["cer_alto"]


def test_build_scorecard_worst_lines_respects_worst_n() -> None:
    lines = _lines(5)
    results = _clean_results(lines)
    for line in lines:
        _flag(results[line.id], cer_alto=True)
    scorecard = build_scorecard(lines, results, worst_n=2)
    assert len(scorecard["worst_lines"]) == 2


def test_build_scorecard_missing_optional_metrics_are_none() -> None:
    lines = _lines(1)
    results = {
        "l0000": {
            "synthesized_ok": True,
            "evaluated_ok": False,
            "flags": _flags(),
            "any_flag": False,
        }
    }
    scorecard = build_scorecard(lines, results)
    assert scorecard["avg_cer"] is None
    assert scorecard["avg_cer_final"] is None
    assert scorecard["avg_prosody_correlation"] is None
    assert scorecard["avg_emotion_similarity"] is None


def test_build_scorecard_averages_final_cer_independently_from_candidate_cer() -> None:
    lines = _lines(2)
    results = _clean_results(lines)
    # cer_final diverge do cer do candidato: simula uma corrupção que só
    # aparece no áudio FINAL (pós-mixagem), não no candidato
    results["l0000"]["cer_final"] = 0.4
    results["l0001"]["cer_final"] = 0.5
    _flag(results["l0000"], cer_final_alto=True)
    _flag(results["l0001"], cer_final_alto=True)

    scorecard = build_scorecard(lines, results)
    assert scorecard["avg_cer"] == pytest.approx(0.05)
    assert scorecard["avg_cer_final"] == pytest.approx(0.45)
    assert scorecard["flag_rates"]["cer_final_alto"] == 1.0


def test_build_scorecard_flag_overlap_diagonal_matches_flag_counts() -> None:
    lines = _lines(3)
    results = _clean_results(lines)
    _flag(results["l0000"], cer_alto=True)
    scorecard = build_scorecard(lines, results)
    assert scorecard["flag_overlap"]["cer_alto"]["cer_alto"] == scorecard["flag_counts"]["cer_alto"]


def test_build_scorecard_flag_overlap_counts_lines_with_both_flags() -> None:
    lines = _lines(3)
    results = _clean_results(lines)
    # l0000: só cer_alto. l0001: cer_alto E clipping juntos. l0002: limpa.
    _flag(results["l0000"], cer_alto=True)
    _flag(results["l0001"], cer_alto=True, clipping=True)

    overlap = build_scorecard(lines, results)["flag_overlap"]
    assert overlap["cer_alto"]["cer_alto"] == 2
    assert overlap["clipping"]["clipping"] == 1
    assert overlap["cer_alto"]["clipping"] == 1
    assert overlap["clipping"]["cer_alto"] == 1


def test_build_scorecard_flag_overlap_is_zero_when_no_line_has_both() -> None:
    lines = _lines(2)
    results = _clean_results(lines)
    _flag(results["l0000"], cer_alto=True)
    _flag(results["l0001"], clipping=True)

    overlap = build_scorecard(lines, results)["flag_overlap"]
    assert overlap["cer_alto"]["clipping"] == 0
    assert overlap["clipping"]["cer_alto"] == 0


def test_build_scorecard_lines_with_multiple_flags_counts_two_or_more() -> None:
    lines = _lines(3)
    results = _clean_results(lines)
    _flag(results["l0000"], cer_alto=True)
    _flag(results["l0001"], cer_alto=True, clipping=True)
    _flag(results["l0002"], cer_alto=True, clipping=True, truncado=True)

    scorecard = build_scorecard(lines, results)
    assert scorecard["lines_with_multiple_flags"] == 2


def test_build_scorecard_lines_with_multiple_flags_zero_when_none_overlap() -> None:
    lines = _lines(2)
    results = _clean_results(lines)
    _flag(results["l0000"], cer_alto=True)
    scorecard = build_scorecard(lines, results)
    assert scorecard["lines_with_multiple_flags"] == 0
