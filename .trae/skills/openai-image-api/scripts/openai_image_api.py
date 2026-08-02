#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import ssl
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

try:
    import certifi
    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSL_CONTEXT = ssl.create_default_context()
    _SSL_CONTEXT.check_hostname = False
    _SSL_CONTEXT.verify_mode = ssl.CERT_NONE


DEFAULT_CONFIG_PATH = Path.home() / ".codex" / "config.toml"
DEFAULT_AUTH_PATH = Path.home() / ".codex" / "auth.json"
DEFAULT_OUTPUT_DIR = Path.home() / "Downloads" / "openai-image-api"
DEFAULT_SKILL_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"
DEFAULT_MODEL = "gpt-image-2"
DEFAULT_SIZE = "1024x1024"
DEFAULT_TIMEOUT = 300


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Call a custom OpenAI-compatible Images API for generation or edit."
    )
    parser.add_argument("--skill-config", type=Path, default=DEFAULT_SKILL_CONFIG_PATH)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--auth", type=Path, default=DEFAULT_AUTH_PATH)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--response-json-out", type=Path)

    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--model", default=DEFAULT_MODEL)
    common.add_argument("--prompt", required=True)
    common.add_argument("--size", default=DEFAULT_SIZE)
    common.add_argument("--quality", default="")
    common.add_argument("--background", default="")
    common.add_argument("--n", type=int, default=1)
    common.add_argument("--response-format", default="b64_json")
    common.add_argument("--out", type=Path)
    common.add_argument("--out-dir", type=Path)
    common.add_argument(
        "--field",
        action="append",
        default=[],
        help="Extra text field in key=value form. Repeatable.",
    )

    subparsers.add_parser("generate", parents=[common])

    edit = subparsers.add_parser("edit", parents=[common])
    edit.add_argument("--image", type=Path, required=True, action="append")
    edit.add_argument("--mask", type=Path)

    return parser.parse_args()


def load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text())


def load_auth(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def load_skill_config(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise RuntimeError(f"Skill config must be a JSON object: {path}")
    return data


def resolve_base_url(args: argparse.Namespace) -> str:
    if args.base_url.strip():
        return args.base_url.strip().rstrip("/")

    env_value = os.environ.get("OPENAI_BASE_URL", "").strip()
    if env_value:
        return env_value.rstrip("/")

    skill_config = load_skill_config(args.skill_config)
    skill_base_url = str(skill_config.get("base_url", "")).strip()
    if skill_base_url:
        return skill_base_url.rstrip("/")

    config = load_config(args.config)
    provider_name = str(config.get("model_provider", "")).strip()
    providers = config.get("model_providers", {})
    provider = providers.get(provider_name, {}) if isinstance(providers, dict) else {}
    base_url = str(provider.get("base_url", "")).strip()
    if not base_url:
        raise RuntimeError(
            "Could not resolve base URL from --base-url, OPENAI_BASE_URL, skill config, or config.toml"
        )
    return base_url.rstrip("/")


def resolve_api_key(args: argparse.Namespace) -> str:
    if args.api_key.strip():
        return args.api_key.strip()

    env_value = os.environ.get("OPENAI_API_KEY", "").strip()
    if env_value:
        return env_value

    skill_config = load_skill_config(args.skill_config)
    skill_api_key = str(skill_config.get("api_key", "")).strip()
    if skill_api_key:
        return skill_api_key

    auth = load_auth(args.auth)
    api_key = str(auth.get("OPENAI_API_KEY", "")).strip()
    if not api_key:
        raise RuntimeError(
            "Could not resolve API key from --api-key, OPENAI_API_KEY, skill config, or auth.json"
        )
    return api_key


def build_endpoint(base_url: str, endpoint: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return base + endpoint[len("/v1") :]
    return base + endpoint


def parse_extra_fields(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise RuntimeError(f"Invalid --field value: {item!r}")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise RuntimeError(f"Invalid --field key in: {item!r}")
        result[key] = value
    return result


def build_json_payload(args: argparse.Namespace) -> dict:
    payload = {
        "model": args.model,
        "prompt": args.prompt,
        "size": args.size,
        "n": args.n,
        "response_format": args.response_format,
    }
    if args.quality:
        payload["quality"] = args.quality
    if args.background:
        payload["background"] = args.background
    payload.update(parse_extra_fields(args.field))
    return payload


def guess_content_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def multipart_text(name: str, value: str, boundary: str) -> bytes:
    return (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
        f"{value}\r\n"
    ).encode("utf-8")


def multipart_file(name: str, path: Path, boundary: str) -> bytes:
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{name}"; filename="{path.name}"\r\n'
        f"Content-Type: {guess_content_type(path)}\r\n\r\n"
    ).encode("utf-8")
    return header + path.read_bytes() + b"\r\n"


def build_edit_multipart(args: argparse.Namespace) -> tuple[bytes, str]:
    boundary = "openai-image-api-" + uuid.uuid4().hex
    chunks: list[bytes] = []
    for key, value in build_json_payload(args).items():
        chunks.append(multipart_text(key, str(value), boundary))
    for image_path in args.image:
        chunks.append(multipart_file("image", image_path, boundary))
    if args.mask:
        chunks.append(multipart_file("mask", args.mask, boundary))
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(chunks)
    content_type = f"multipart/form-data; boundary={boundary}"
    return body, content_type


def request_json(url: str, api_key: str, body: bytes, content_type: str, timeout: int) -> dict:
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": content_type,
            "Accept": "application/json",
            "User-Agent": "openai-image-api-skill/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"request failed: {exc}") from exc


def fetch_url(url: str, timeout: int) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "openai-image-api-skill/1.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT) as resp:
        return resp.read()


def default_output_name(command: str, model: str, index: int | None = None) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{index}" if index is not None else ""
    return f"{command}_{model}_{ts}{suffix}.png"


def resolve_output_paths(args: argparse.Namespace, count: int) -> list[Path]:
    if count <= 0:
        raise RuntimeError("No output items returned")

    if args.out and count == 1:
        return [args.out]

    if args.out and count > 1:
        stem = args.out.stem
        suffix = args.out.suffix or ".png"
        parent = args.out.parent
        return [parent / f"{stem}_{idx}{suffix}" for idx in range(1, count + 1)]

    out_dir = args.out_dir or DEFAULT_OUTPUT_DIR
    return [out_dir / default_output_name(args.command, args.model, idx) for idx in range(1, count + 1)]


def save_images(response_json: dict, args: argparse.Namespace) -> list[Path]:
    data = response_json.get("data")
    if not isinstance(data, list) or not data:
        raise RuntimeError(f"Unexpected response payload: {json.dumps(response_json, ensure_ascii=False)}")

    output_paths = resolve_output_paths(args, len(data))
    for path in output_paths:
        path.parent.mkdir(parents=True, exist_ok=True)

    saved: list[Path] = []
    for item, path in zip(data, output_paths, strict=True):
        if not isinstance(item, dict):
            raise RuntimeError(f"Unexpected image item: {item!r}")
        if isinstance(item.get("b64_json"), str) and item["b64_json"]:
            path.write_bytes(base64.b64decode(item["b64_json"]))
        elif isinstance(item.get("url"), str) and item["url"]:
            path.write_bytes(fetch_url(item["url"], args.timeout))
        else:
            raise RuntimeError(f"Response item missing b64_json/url: {json.dumps(item, ensure_ascii=False)}")
        saved.append(path)
    return saved


def main() -> int:
    args = parse_args()
    base_url = resolve_base_url(args)
    api_key = resolve_api_key(args)

    if args.command == "generate":
        endpoint = build_endpoint(base_url, "/v1/images/generations")
        payload = build_json_payload(args)
        body = json.dumps(payload).encode("utf-8")
        content_type = "application/json"
    else:
        endpoint = build_endpoint(base_url, "/v1/images/edits")
        body, content_type = build_edit_multipart(args)

    response_json = request_json(endpoint, api_key, body, content_type, args.timeout)
    if args.response_json_out:
        args.response_json_out.parent.mkdir(parents=True, exist_ok=True)
        args.response_json_out.write_text(json.dumps(response_json, ensure_ascii=False, indent=2))

    saved = save_images(response_json, args)

    print(f"command={args.command}")
    print(f"endpoint={endpoint}")
    print(f"model={args.model}")
    for path in saved:
        print(f"saved={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
