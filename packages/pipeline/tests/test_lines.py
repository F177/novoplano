import pytest
from pydantic import ValidationError

from packages.pipeline.lines import Line, Word


def _line(**overrides: object) -> Line:
    fields: dict[str, object] = {
        "id": "l0000",
        "speaker": "A",
        "start": 1.0,
        "end": 2.5,
        "window_start": 0.8,
        "window_end": 3.0,
        "source_text": "Are you ready?",
    }
    fields.update(overrides)
    return Line(**fields)


def test_line_durations() -> None:
    line = _line()
    assert line.duration == pytest.approx(1.5)
    assert line.window_duration == pytest.approx(2.2)


def test_line_carries_words() -> None:
    words = (
        Word(text="Are", start=1.0, end=1.2, speaker="A", confidence=0.9),
        Word(text="you", start=1.2, end=1.4, speaker="A"),
    )
    line = _line(words=words)
    assert [w.text for w in line.words] == ["Are", "you"]
    assert line.words[1].confidence is None


def test_line_rejects_non_positive_duration() -> None:
    with pytest.raises(ValidationError):
        _line(start=2.0, end=2.0)


def test_line_rejects_window_that_does_not_contain_line() -> None:
    with pytest.raises(ValidationError):
        _line(window_start=1.2)
    with pytest.raises(ValidationError):
        _line(window_end=2.0)


def test_line_window_may_equal_line() -> None:
    line = _line(window_start=1.0, window_end=2.5)
    assert line.window_duration == line.duration


def test_line_is_immutable() -> None:
    line = _line()
    with pytest.raises(ValidationError):
        line.source_text = "changed"  # type: ignore[misc]
