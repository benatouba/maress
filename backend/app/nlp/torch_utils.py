from __future__ import annotations

import contextlib
from collections.abc import Iterator


@contextlib.contextmanager
def torch_float32_default() -> Iterator[None]:
    """Temporarily force Torch's default dtype back to float32.

    Some OCR/model libraries in the worker mutate Torch's global default dtype
    to `float64`. spaCy's transformer pipeline and parts of Docling assume
    float32-backed model weights, so model initialization needs to happen under
    a temporary float32 default to avoid downstream BLIS and Torch dtype
    mismatches.
    """
    try:
        import torch
    except ImportError:
        yield
        return

    original_dtype = torch.get_default_dtype()
    try:
        if original_dtype != torch.float32:
            torch.set_default_dtype(torch.float32)
        yield
    finally:
        if torch.get_default_dtype() != original_dtype:
            torch.set_default_dtype(original_dtype)
