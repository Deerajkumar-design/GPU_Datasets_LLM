"""Primary-source adapters.

Adding a domain means adding one module here that subclasses
:class:`~longctx_dataset.sources.base.SourceAdapter` and registering it. Nothing else
in the pipeline needs to change.
"""

from .base import SourceAdapter, RetrievalResult, HTTPClient, SourceBlocked, get_adapter, register_adapter, available_adapters  # noqa: F401

# Import for side-effect registration.
from . import sec, fda, clinical_trials, fred, world_bank  # noqa: F401,E402

__all__ = [
    "SourceAdapter",
    "RetrievalResult",
    "HTTPClient",
    "SourceBlocked",
    "get_adapter",
    "register_adapter",
    "available_adapters",
]
