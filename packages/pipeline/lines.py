"""Tipos centrais: palavra (ASR + diarização) e fala.

A fala é a unidade atômica do pipeline (CLAUDE.md): roteiro, síntese,
revisão e edição acontecem por fala. Este módulo só define os tipos; a
montagem das falas a partir de palavras é a T1.1.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator


class Word(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    start: float
    end: float
    speaker: str
    confidence: float | None = None


class Line(BaseModel):
    """Linha de diálogo de um locutor.

    `start`/`end` delimitam a fala original; `window_start`/`window_end`, o
    intervalo em que a fala dublada pode tocar (original + silêncio vizinho).
    """

    model_config = ConfigDict(frozen=True)

    id: str
    speaker: str
    start: float
    end: float
    window_start: float
    window_end: float
    source_text: str
    words: tuple[Word, ...] = ()

    @model_validator(mode="after")
    def _check_times(self) -> Line:
        if not self.start < self.end:
            raise ValueError(f"fala {self.id}: start deve ser menor que end")
        if not (self.window_start <= self.start and self.end <= self.window_end):
            raise ValueError(f"fala {self.id}: a janela deve conter a fala")
        return self

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def window_duration(self) -> float:
        return self.window_end - self.window_start
