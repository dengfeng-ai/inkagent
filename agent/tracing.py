"""Langfuse observability — shared helpers for tracing LLM calls and spans.

Langfuse is optional: when ``LANGFUSE_PUBLIC_KEY`` is not set, ``observe``
is a no-op decorator and ``get_langfuse()`` returns a silent stub.
"""

import os

_enabled = bool(os.environ.get("LANGFUSE_PUBLIC_KEY"))

if _enabled:
    from langfuse import observe, get_client as get_langfuse
else:
    def observe(**kwargs):
        """No-op decorator."""
        def decorator(fn):
            return fn
        return decorator

    class _NullLangfuse:
        """Stub that silently ignores all method calls."""
        def __getattr__(self, _name):
            return lambda *a, **kw: None

    _null_lf = _NullLangfuse()

    def get_langfuse():
        return _null_lf
