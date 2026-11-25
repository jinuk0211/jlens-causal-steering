"""FastAPI shim serving local HuggingFace models behind an OpenAI-compatible
/v1/chat/completions endpoint, sufficient for the prompt-based tool-calling
runner in this repo.

The runner only exercises /v1/chat/completions and does not need native tool
calling on the server side (it embeds tool calls in the prompt and parses
them from the response). That keeps this shim small.

Usage:
    pip install -r requirements.txt
    python serve.py --model llama-8b               # name from models.yaml
    python serve.py --model-path /path/to/model    # ad-hoc path

For higher throughput, prefer running vLLM's built-in OpenAI-compatible
server directly:
    vllm serve <model-path> --port 8000

Both expose the same /v1 surface this repo targets.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

import yaml
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from vllm import LLM, SamplingParams

# Avoid hard dependency on flash_attn for multimodal-capable models.
os.environ.setdefault("VLLM_ATTENTION_BACKEND", "TORCH_SDPA")


def load_model_config(name: str | None, path: str | None) -> dict[str, Any]:
    if path:
        return {"path": path, "dtype": "auto", "max_model_len": 8192}
    if not name:
        raise SystemExit("Specify --model NAME (from models.yaml) or --model-path PATH")
    config_path = Path(__file__).parent / "models.yaml"
    with open(config_path) as f:
        models = yaml.safe_load(f)
    if name not in models:
        raise SystemExit(f"Model '{name}' not in models.yaml. Available: {list(models)}")
    return models[name]


llm: LLM | None = None
MODEL_NAME = "local"


import asyncio as _asyncio
import queue as _queue
import threading as _threading

_BATCH_Q = _queue.Queue()
_BATCH_MAX = int(os.environ.get("SERVE_BATCH_MAX", "16"))
_BATCH_WAIT = float(os.environ.get("SERVE_BATCH_WAIT", "0.05"))
_BATCH_THREAD = None


def _batch_worker():
    while True:
        items = [_BATCH_Q.get()]
        time.sleep(_BATCH_WAIT)
        while len(items) < _BATCH_MAX:
            try:
                items.append(_BATCH_Q.get_nowait())
            except _queue.Empty:
                break
        try:
            outs = llm.generate([i[0] for i in items], [i[1] for i in items], use_tqdm=False)
            for (p, s, fut, loop), o in zip(items, outs):
                loop.call_soon_threadsafe(fut.set_result, o)
        except Exception as exc:
            for (p, s, fut, loop) in items:
                loop.call_soon_threadsafe(fut.set_exception, exc)


async def _batched_generate(prompt, sampling):
    global _BATCH_THREAD
    if _BATCH_THREAD is None:
        _BATCH_THREAD = _threading.Thread(target=_batch_worker, daemon=True)
        _BATCH_THREAD.start()
    loop = _asyncio.get_running_loop()
    fut = loop.create_future()
    _BATCH_Q.put((prompt, sampling, fut, loop))
    return await fut


@asynccontextmanager
async def lifespan(app: FastAPI):
    global llm, MODEL_NAME
    cfg = app.state.config
    MODEL_NAME = cfg.get("served_model_name", cfg["path"])
    print(f"Loading model: {cfg['path']}")
    configured_dtype = cfg.get("dtype", "auto")
    if configured_dtype == "profile-auto":
        major, _minor = torch.cuda.get_device_capability()
        configured_dtype = "bfloat16" if major >= 8 else "float16"
    llm = LLM(
        model=cfg["path"],
        tensor_parallel_size=cfg.get("tensor_parallel_size", 1),
        trust_remote_code=cfg.get("trust_remote_code", True),
        dtype=configured_dtype,
        gpu_memory_utilization=cfg.get("gpu_memory_utilization", 0.90),
        max_model_len=cfg.get("max_model_len", 8192),
        enforce_eager=cfg.get("enforce_eager", False),
        revision=cfg.get("revision"),
    )
    print("Model loaded.")
    yield


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[Message]
    temperature: float | None = 0.0
    top_p: float | None = 1.0
    max_tokens: int | None = 4096
    stop: list[str] | None = None
    top_k: int | None = None
    min_p: float | None = None
    presence_penalty: float | None = None
    seed: int | None = None


def build_app(cfg: dict[str, Any]) -> FastAPI:
    app = FastAPI(title="ToolAlignBench inference shim", lifespan=lifespan)
    app.state.config = cfg

    @app.get("/")
    async def root():
        return {"status": "running", "model": cfg["path"]}

    @app.get("/v1/models")
    async def list_models():
        return {
            "object": "list",
            "data": [
                {
                    "id": MODEL_NAME,
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "local",
                }
            ],
        }

    @app.post("/v1/chat/completions")
    async def chat_completions(req: ChatCompletionRequest):
        if llm is None:
            raise HTTPException(status_code=503, detail="Model not loaded")

        tokenizer = llm.get_tokenizer()
        request_messages = [m.model_dump() for m in req.messages]
        try:
            prompt = tokenizer.apply_chat_template(
                request_messages,
                tokenize=False,
                add_generation_prompt=True,
                **cfg.get("chat_template_kwargs", {}),
            )
        except (TypeError, ValueError):
            prompt = "\n\n".join(
                f"<{message['role']}>\n{message['content']}"
                for message in request_messages
            ) + "\n\n<assistant>\n"

        sampling = SamplingParams(
            temperature=req.temperature or 0.0,
            top_p=req.top_p or 1.0,
            max_tokens=req.max_tokens or 4096,
            stop=req.stop,
            top_k=req.top_k if req.top_k is not None else -1,
            min_p=req.min_p or 0.0,
            presence_penalty=req.presence_penalty or 0.0,
            seed=req.seed,
        )

        outputs = [await _batched_generate(prompt, sampling)]
        text = outputs[0].outputs[0].text
        prompt_token_ids = [int(value) for value in outputs[0].prompt_token_ids]
        raw_generation_token_ids = [
            int(value) for value in outputs[0].outputs[0].token_ids
        ]
        completion_token_ids = list(raw_generation_token_ids)
        special_ids = set(getattr(tokenizer, "all_special_ids", []))
        while completion_token_ids and completion_token_ids[-1] in special_ids:
            completion_token_ids.pop()
        decoded_completion = tokenizer.decode(
            completion_token_ids,
            skip_special_tokens=False,
            clean_up_tokenization_spaces=False,
        )
        if decoded_completion != text:
            reconstructed_ids = tokenizer.encode(text, add_special_tokens=False)
            reconstructed_text = tokenizer.decode(
                reconstructed_ids,
                skip_special_tokens=False,
                clean_up_tokenization_spaces=False,
            )
            if reconstructed_text != text:
                raise HTTPException(
                    status_code=500,
                    detail="completion text/token IDs cannot be represented exactly",
                )
            completion_token_ids = [int(value) for value in reconstructed_ids]
        chat_template = str(getattr(tokenizer, "chat_template", "") or "")
        template_hash = hashlib.sha256(chat_template.encode("utf-8")).hexdigest()

        return {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": req.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": len(prompt_token_ids),
                "completion_tokens": len(completion_token_ids),
                "total_tokens": len(prompt_token_ids) + len(completion_token_ids),
            },
            "trace": {
                "prompt_token_ids": prompt_token_ids,
                "completion_token_ids": completion_token_ids,
                "raw_generation_token_ids": raw_generation_token_ids,
                "prompt_text": prompt,
                "completion_text": text,
                "model_revision": cfg.get("revision"),
                "tokenizer_name": getattr(tokenizer, "name_or_path", cfg["path"]),
                "chat_template_sha256": template_hash,
            },
        }

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="Model name from models.yaml")
    parser.add_argument("--model-path", help="Direct path / HF repo id")
    parser.add_argument("--revision", help="Pinned Hugging Face model revision")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    cfg = load_model_config(args.model, args.model_path)
    if args.revision:
        cfg["revision"] = args.revision
    app = build_app(cfg)

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
