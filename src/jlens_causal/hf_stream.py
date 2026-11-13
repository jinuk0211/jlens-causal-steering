"""Load a Qwen3.5 text model straight from the Hugging Face Hub into GPU memory.

For hosts whose disk cannot hold the checkpoint: each safetensors shard is read
as one HTTP stream and every tensor is copied directly into the matching
parameter of a model already allocated on the device, so neither disk nor a
second copy of the weights is needed.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

import torch

_DTYPES = {"BF16": torch.bfloat16, "F16": torch.float16, "F32": torch.float32}


class _Stream:
    def __init__(self, response: Any):
        self._iter = response.iter_content(chunk_size=1 << 22)
        self._buffer = bytearray()

    def read(self, size: int) -> bytes:
        while len(self._buffer) < size:
            chunk = next(self._iter)
            self._buffer.extend(chunk)
        out = bytes(self._buffer[:size])
        del self._buffer[:size]
        return out


def stream_qwen35_text_model(
    repo_id: str,
    revision: str,
    config_dir: str | Path,
    *,
    device: str = "cuda",
    dtype: torch.dtype = torch.bfloat16,
) -> Any:
    """Build ``Qwen3_5ForCausalLM`` on ``device`` and fill it from the Hub shards."""
    import requests
    from huggingface_hub import hf_hub_url
    from transformers import Qwen3_5Config, Qwen3_5ForCausalLM

    config_dir = Path(config_dir)
    config = Qwen3_5Config.from_pretrained(config_dir).text_config
    previous = torch.get_default_dtype()
    torch.set_default_dtype(dtype)
    try:
        with torch.device(device):
            model = Qwen3_5ForCausalLM(config)
    finally:
        torch.set_default_dtype(previous)
    model.eval()
    params = dict(model.named_parameters())
    index = json.loads((config_dir / "model.safetensors.index.json").read_text())["weight_map"]
    loaded: set[str] = set()
    for shard in sorted(set(index.values())):
        url = hf_hub_url(repo_id, shard, revision=revision)
        with requests.get(url, stream=True, timeout=120) as response:
            response.raise_for_status()
            stream = _Stream(response)
            (header_len,) = struct.unpack("<Q", stream.read(8))
            header = json.loads(stream.read(header_len))
            header.pop("__metadata__", None)
            position = 0
            for name, meta in sorted(header.items(), key=lambda item: item[1]["data_offsets"][0]):
                start, end = meta["data_offsets"]
                if start > position:
                    stream.read(start - position)
                data = stream.read(end - start)
                position = end
                target = name.replace("model.language_model.", "model.", 1)
                if target not in params:
                    continue  # vision tower / MTP head
                tensor = torch.frombuffer(bytearray(data), dtype=_DTYPES[meta["dtype"]]).reshape(meta["shape"])
                with torch.no_grad():
                    params[target].copy_(tensor.to(device=device, dtype=params[target].dtype))
                loaded.add(target)
    missing = [name for name in params if name not in loaded and name != "lm_head.weight"]
    if missing:
        raise RuntimeError(f"weights missing from the checkpoint stream: {missing[:5]} (+{len(missing) - 5})")
    model.tie_weights()
    return model
