"""테스트셋 예측 실행 (이어서 실행 가능: 이미 예측한 id는 건너뜀).

  # 큰 모델 (llm-serving, 8080)
  uv run python -m ko_table_vlm.predict --data data/generated/test/manifest.jsonl \
      --run runs/qwen27b_zeroshot --model models/Qwen3.8-27B-4bit --limit 100

  # 소형 모델 + LoRA (scripts/serve_model.sh 로 8081에 띄운 뒤)
  uv run python -m ko_table_vlm.predict --data ... --run runs/qwen2b_lora_r16 \
      --base-url http://127.0.0.1:8081/v1 --model models/Qwen3.5-2B-bf16

  # Docling (TableFormer) 기준선
  uv run --extra docling python -m ko_table_vlm.predict --data ... --run runs/docling --backend docling

출력: runs/<name>/predictions.jsonl  ({"id", "output", "format", "latency_s", "usage"})
     runs/<name>/run.json            (실행 조건 기록)
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import platform
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

from .data import append_jsonl, load_jsonl, load_manifest
from .prompts import PROMPT_VERSION, PROMPTS

KEY_FILE = Path.home() / ".config" / "llm-serving" / "api_key"


def api_key() -> str:
    return os.environ.get("LLM_API_KEY") or (KEY_FILE.read_text().strip() if KEY_FILE.exists() else "")


class ApiBackend:
    """OpenAI 호환 /chat/completions (mlx_vlm.server, vLLM 등)."""

    def __init__(self, base_url, model, fmt, max_tokens, timeout, no_thinking=True, repetition_penalty=None):
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model, self.fmt, self.max_tokens = model, fmt, max_tokens
        self.no_thinking = no_thinking
        self.repetition_penalty = repetition_penalty
        self.client = httpx.Client(timeout=timeout, headers={"Authorization": f"Bearer {api_key()}"})

    def __call__(self, image_path: str) -> dict:
        b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
        mime = "image/png" if image_path.lower().endswith(".png") else "image/jpeg"
        body = {
            "model": self.model, "temperature": 0, "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": PROMPTS[self.fmt]}]}],
        }
        if self.no_thinking:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        if self.repetition_penalty:
            body["repetition_penalty"] = self.repetition_penalty
        r = self.client.post(self.url, json=body)
        r.raise_for_status()
        j = r.json()
        return {"output": j["choices"][0]["message"].get("content") or "",
                "finish_reason": j["choices"][0].get("finish_reason"), "usage": j.get("usage")}


class DoclingBackend:
    """Docling 파이프라인(레이아웃 + TableFormer + macOS Vision OCR)으로 이미지의 표를 HTML로."""

    def __init__(self):
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import OcrMacOptions, PdfPipelineOptions, TableFormerMode
        from docling.document_converter import DocumentConverter, ImageFormatOption

        opts = PdfPipelineOptions(do_table_structure=True, do_ocr=True,
                                  ocr_options=OcrMacOptions(lang=["ko-KR", "en-US"], force_full_page_ocr=True))
        opts.table_structure_options.mode = TableFormerMode.ACCURATE
        self.conv = DocumentConverter(format_options={InputFormat.IMAGE: ImageFormatOption(pipeline_options=opts)})
        # 워밍업: 모델 로딩 시간이 첫 샘플 지연에 섞이지 않게 작은 이미지로 한 번 실행
        import tempfile
        from PIL import Image, ImageDraw
        with tempfile.NamedTemporaryFile(suffix=".png") as f:
            img = Image.new("RGB", (320, 120), "white")
            d = ImageDraw.Draw(img)
            for y in (10, 60, 110):
                d.line((10, y, 310, y), fill="black")
            img.save(f.name)
            self.conv.convert(f.name)

    def __call__(self, image_path: str) -> dict:
        doc = self.conv.convert(image_path).document
        if not doc.tables:
            return {"output": "", "finish_reason": "no_table", "usage": None}
        # 표가 여러 개로 잡히면 셀이 가장 많은 것을 사용
        best = max(doc.tables, key=lambda t: t.data.num_rows * t.data.num_cols)
        return {"output": best.export_to_html(doc=doc), "finish_reason": "stop", "usage": None}


def git_rev() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              cwd=Path(__file__).parent).stdout.strip() or "uncommitted"
    except Exception:
        return "unknown"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="manifest.jsonl")
    ap.add_argument("--run", required=True, help="결과 디렉터리 (runs/<이름>)")
    ap.add_argument("--backend", choices=["api", "docling"], default="api")
    ap.add_argument("--base-url", default=os.environ.get("LLM_BASE_URL", "http://127.0.0.1:8080/v1"))
    ap.add_argument("--model", default="models/Qwen3.8-27B-4bit")
    ap.add_argument("--format", choices=list(PROMPTS), default="html", help="모델 출력 형식")
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--timeout", type=float, default=900)
    ap.add_argument("--workers", type=int, default=1, help="동시 요청 수 (서버 continuous batching 활용)")
    ap.add_argument("--limit", type=int, default=0, help="앞에서 N개만 (큰 모델은 느리므로)")
    ap.add_argument("--thinking", action="store_true", help="thinking 모드 켜기 (기본 끔)")
    ap.add_argument("--repetition-penalty", type=float, default=None, help="반복 억제 (기본 끔)")
    ap.add_argument("--ids", default="", help="쉼표로 구분한 id만 실행 (진단용)")
    args = ap.parse_args()

    run = Path(args.run)
    run.mkdir(parents=True, exist_ok=True)
    rows = load_manifest(args.data)
    if args.limit:
        rows = rows[: args.limit]
    if args.ids:
        keep = set(args.ids.split(","))
        rows = [r for r in rows if r["id"] in keep]
    pred_path = run / "predictions.jsonl"
    done = {p["id"] for p in load_jsonl(pred_path)}
    todo = [r for r in rows if r["id"] not in done]

    fmt = "html" if args.backend == "docling" else args.format
    (run / "run.json").write_text(json.dumps({
        "data": str(Path(args.data).resolve()), "n": len(rows), "backend": args.backend,
        "model": args.model if args.backend == "api" else "docling", "base_url": args.base_url,
        "format": fmt, "prompt_version": PROMPT_VERSION, "max_tokens": args.max_tokens,
        "thinking": args.thinking, "repetition_penalty": args.repetition_penalty, "workers": args.workers, "git": git_rev(),
        "machine": platform.platform(), "started": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, ensure_ascii=False, indent=2))
    print(f"{len(done)} done, {len(todo)} to go → {pred_path}")

    if args.backend == "docling":
        backend, workers = DoclingBackend(), 1
    else:
        backend = ApiBackend(args.base_url, args.model, fmt, args.max_tokens, args.timeout, not args.thinking,
                             args.repetition_penalty)
        workers = args.workers

    def one(r):
        t0 = time.time()
        try:
            res = backend(r["image_path"])
        except Exception as e:  # 실패도 기록해서 오류율에 반영
            res = {"output": "", "finish_reason": f"error: {type(e).__name__}: {e}"[:300], "usage": None}
        return {"id": r["id"], "format": fmt, "latency_s": round(time.time() - t0, 3), **res}

    t_start = time.time()
    with ThreadPoolExecutor(workers) as ex:
        futs = [ex.submit(one, r) for r in todo]
        for i, f in enumerate(as_completed(futs), 1):
            rec = f.result()
            append_jsonl(pred_path, rec)
            if i % 10 == 0 or i == len(todo):
                el = time.time() - t_start
                print(f"  {i}/{len(todo)}  {el:.0f}s elapsed, ~{el / i * (len(todo) - i):.0f}s left", flush=True)


if __name__ == "__main__":
    main()
