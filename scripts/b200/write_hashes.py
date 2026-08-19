#!/usr/bin/env python3
from common import hash_tree, paths, write_manifest

result_root = paths()["results"]
manifest = write_manifest("b200_inference_hashes.json", {"root": str(result_root), "sha256": hash_tree(result_root)})
print(f"Persistent result hashes: {manifest}")
