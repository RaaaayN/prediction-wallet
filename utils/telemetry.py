"""OpenTelemetry helpers with a no-op fallback."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

_TRACER = None
_OTEL_ENABLED = False

try:  # pragma: no cover - optional dependency at runtime
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        provider = TracerProvider()
        if os.getenv("OTEL_CONSOLE_EXPORTER", "0") == "1":
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(provider)
    _TRACER = trace.get_tracer("prediction_wallet")
    _OTEL_ENABLED = True
except Exception:  # pragma: no cover - fallback path
    trace = None


@contextmanager
def stage_span(name: str, **attributes) -> Iterator[None]:
    """Wrap a cycle stage in an OTel span when available."""
    if _TRACER is None:
        yield
        return

    with _TRACER.start_as_current_span(name) as span:
        for key, value in attributes.items():
            if value is not None:
                span.set_attribute(key, value)
        yield


def otel_enabled() -> bool:
    return _OTEL_ENABLED
