from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

@dataclass
class TextDelta:
    content: str

    def __str__(self):
        return self.content

class StreamEventType(str, Enum):
    TEXT_DELTA = 'text_delta'
    MESSAGE_COMPLETE = 'message_complete'
    ERROR = 'error'

@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0

    # Can't pass te same class within the same class (could do before Py 3.8)
    # Imported annotations for the same
    def __add__(self, other: TokenUsage):
        """

        Add fields of two instances of TokenUsage
        
        :param self: first instance of TokenUsage
        :param other: second instance of TokenUsage
        :type other: TokenUsage

        """
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            cached_tokens=self.cached_tokens + other.cached_tokens,
        )

@dataclass
class StreamEvent:
    type: StreamEventType
    text_delta: TextDelta | None = None
    error: str | None = None
    finish_reason: str | None = None
    usage: TokenUsage | None = None
