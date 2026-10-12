import json
import re
from typing import Any

from packages.pipeline.lines import Line, Word
from packages.pipeline.report import build_history_entry, render_dashboard_html

_SCORECARD = {
    "total_lines": 2,
    "synthesized_lines": 2,
    "any_flag_rate": 0.0,
    "flag_counts": {"cer_alto": 0},
    "flag_rates": {"cer_alto": 0.0},
    "avg_cer": 0.05,
    "avg_cer_final": 0.05,
    "avg_prosody_correlation": 0.8,
    "avg_emotion_similarity": 0.9,
    "worst_lines": [],
    "verdict": "aprovado",
}


def _line(line_id: str = "l0000", source_text: str = "Are you ready?") -> Line:
    return Line(
        id=line_id,
        speaker="A",
        start=0.0,
        end=1.0,
        window_start=0.0,
        window_end=1.2,
        source_text=source_text,
        words=(Word(text="Are", start=0.0, end=0.2, speaker="A"),),
    )


def _entry(
    *,
    video: str = "video.mp4",
    git_sha: str | None = "abc1234",
    git_dirty: bool = False,
    scorecard: dict[str, Any] | None = None,
    lines: list[Line] | None = None,
    results: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return build_history_entry(
        video=video,
        output="video.dub.mp4",
        params={"style_refs": True},
        scorecard=scorecard or _SCORECARD,
        lines=lines or [],
        results=results or {},
        generated_at="2026-10-11T10:00:00",
        git_sha=git_sha,
        git_dirty=git_dirty,
    )


def test_build_history_entry_extracts_expected_fields() -> None:
    entry = _entry()
    assert entry["generated_at"] == "2026-10-11T10:00:00"
    assert entry["video"] == "video.mp4"
    assert entry["params"] == {"style_refs": True}
    assert entry["scorecard"]["verdict"] == "aprovado"
    assert entry["lines"] == []


def test_build_history_entry_merges_line_fields_with_results_without_words() -> None:
    entry = _entry(
        lines=[_line("l0000"), _line("l0001")],
        results={"l0000": {"dub_text": "Tá pronto?", "cer_final": 0.1}},
    )
    first, second = entry["lines"]
    assert first["id"] == "l0000"
    assert first["speaker"] == "A"
    assert first["source_text"] == "Are you ready?"
    assert first["dub_text"] == "Tá pronto?"
    assert first["cer_final"] == 0.1
    assert "words" not in first
    assert "dub_text" not in second
    json.dumps(entry)  # o registro precisa ser serializável


def test_build_history_entry_includes_git_sha_and_dirty_flag() -> None:
    entry = _entry(git_sha="deadbeef", git_dirty=True)
    assert entry["git_sha"] == "deadbeef"
    assert entry["git_dirty"] is True


def test_build_history_entry_allows_unknown_git_sha() -> None:
    assert _entry(git_sha=None)["git_sha"] is None


def test_render_dashboard_html_returns_full_document() -> None:
    html = render_dashboard_html([_entry()])
    assert html.strip().startswith("<!doctype html>")
    assert "</html>" in html


def test_render_dashboard_html_empty_history_does_not_crash() -> None:
    html = render_dashboard_html([])
    assert "<!doctype html>" in html
    assert _extract_payload(html) == []


def test_render_dashboard_html_embeds_all_runs_in_payload() -> None:
    history = [_entry(video="a.mp4"), _entry(video="b.mp4"), _entry(video="c.mp4")]
    payload = _extract_payload(render_dashboard_html(history))
    assert [e["video"] for e in payload] == ["a.mp4", "b.mp4", "c.mp4"]


def test_render_dashboard_html_payload_carries_dirty_flag_per_run() -> None:
    # A marcação em si é JS client-side; o teste garante o que é verificável
    # aqui: o dado chega certo no payload e a lógica de marcação está no HTML.
    history = [
        _entry(video="clean.mp4", git_dirty=False),
        _entry(video="dirty.mp4", git_dirty=True),
    ]
    html = render_dashboard_html(history)
    payload = _extract_payload(html)
    assert payload[0]["git_dirty"] is False
    assert payload[1]["git_dirty"] is True
    assert "dirty-badge" in html
    assert "entry.git_dirty" in html


def test_render_dashboard_html_never_inlines_line_text_as_raw_html() -> None:
    # Texto da fala vem de ASR/LLM sobre vídeo de terceiro: não confiável.
    # Ele só entra via o payload JSON (escapado no client-side por `esc()`),
    # nunca colado cru fora do bloco de dados.
    dangerous = "<script>alert(1)</script>"
    history = [
        _entry(
            lines=[_line(source_text=dangerous)],
            results={
                "l0000": {
                    "dub_text": "fala & aspas",
                    "cer_final": 0.2,
                    "final_hypothesis": "<b>bold</b>",
                }
            },
        )
    ]
    html = render_dashboard_html(history)
    before_data, _, after_data = html.partition('<script id="report-data"')
    _, _, rest = after_data.partition("</script>")
    assert dangerous not in before_data
    assert dangerous not in rest

    payload = _extract_payload(html)
    assert payload[0]["lines"][0]["source_text"] == dangerous


def test_render_dashboard_html_includes_flag_overlap_payload_and_wiring() -> None:
    scorecard = {
        **_SCORECARD,
        "any_flag_rate": 0.5,
        "flag_counts": {"cer_alto": 1, "clipping": 1},
        "flag_rates": {"cer_alto": 0.5, "clipping": 0.5},
        "flag_overlap": {
            "cer_alto": {"cer_alto": 1, "clipping": 1},
            "clipping": {"cer_alto": 1, "clipping": 1},
        },
        "lines_with_multiple_flags": 1,
        "verdict": "revisar",
    }
    html = render_dashboard_html([_entry(scorecard=scorecard)])
    payload = _extract_payload(html)
    assert payload[0]["scorecard"]["flag_overlap"]["cer_alto"]["clipping"] == 1
    assert payload[0]["scorecard"]["lines_with_multiple_flags"] == 1
    assert "sc.flag_overlap" in html
    assert "sc.lines_with_multiple_flags" in html


def test_render_dashboard_html_reads_line_fields_in_client_code() -> None:
    html = render_dashboard_html([_entry()])
    for field in ("entry.lines", "seg.source_text", "seg.dub_text", "w.speaker"):
        assert field in html


def _extract_payload(html: str) -> list[dict[str, Any]]:
    match = re.search(
        r'<script id="report-data" type="application/json">(.*?)</script>', html, re.DOTALL
    )
    assert match is not None
    return json.loads(match.group(1))
