"""Fixtures pytest compartidos entre módulos de tests.

Re-exporta los fixtures definidos en `test_index_builder.py` para que
puedan usarse desde `test_api_read.py` y `test_api_media.py` sin imports
explícitos (que disparan F811 en ruff).
"""

from __future__ import annotations

from .test_index_builder import (
    archive_with_disco_and_huerfanas,
    sample_archive,
)

__all__ = ["archive_with_disco_and_huerfanas", "sample_archive"]
