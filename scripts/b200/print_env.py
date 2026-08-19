#!/usr/bin/env python3
from common import environment

for key, value in environment().items():
    if key.startswith(("HF_", "TRANSFORMERS_", "B200_")) or key == "PYTHONPATH":
        print(f"export {key}={value!r}")
