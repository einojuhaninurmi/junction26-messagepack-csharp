"""Provider-neutral adapter interface; no service imports or tools."""
from dataclasses import dataclass, field
from typing import Protocol

@dataclass(frozen=True)
class ReviewRequest:
    instructions: str
    material_json: str
    response_schema: dict
    model: str
    api_key: str = field(repr=False)
    timeout_seconds: float = 60

@dataclass(frozen=True)
class ReviewReply:
    # Adapter must supply the actual service/model identifiers and a normalized
    # JSON object/string, never a tool call. No universal HTTP API is assumed.
    service: str
    model: str
    output: object
    provider_request_id: str | None = None
    metadata: dict = field(default_factory=dict)

class Adapter(Protocol):
    def review(self, request: ReviewRequest) -> ReviewReply: ...

class AdapterFailure(Exception):
    def __init__(self,code,message,metadata=None):
        super().__init__(message);self.code=code;self.message=message;self.metadata=metadata or {}

