"""Explicitly selected adapters; the public interface remains importable here."""
from .contracts import Adapter, AdapterFailure, ReviewReply, ReviewRequest
from .anthropic_direct import AnthropicDirect

PROVIDERS: dict[str, Adapter] = {'anthropic':AnthropicDirect()}
