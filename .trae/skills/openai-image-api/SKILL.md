---
name: openai-image-api
description: Generate or edit raster images through a custom OpenAI-compatible Images API. Use when Codex should call `/v1/images/generations` or `/v1/images/edits`, especially when the base URL, API key, model, or output path must be controlled explicitly.
---

# OpenAI Image API

Use this skill when image work should go through a specific OpenAI-compatible endpoint instead of the built-in image tool.

It supports:
- new image generation
- image edits from an input image and optional mask
- persistent defaults from `config.json`
- per-run `--base-url` and `--api-key` overrides
- default fallback from `~/.hermes/config.yaml where applicable, or explicit --base-url` and `~/.hermes/.env / OPENAI_API_KEY where applicable`

## Workflow

1. Choose `generate` when there is no input image.
2. Choose `edit` when there is an input image to preserve and modify.
3. Write a compact prompt.
4. Run `scripts/openai_image_api.py`.
5. Save one image with `--out` or multiple variants with `--out-dir`.

For edits, state both:
- what must stay
- what must change

## Commands

Generate:

```bash
python3 /home/youngloach/.hermes/skills/media/openai-image-api/scripts/openai_image_api.py generate \
  --prompt "A calm orange cat sitting on a desk, soft natural light." \
  --model gpt-image-2 \
  --out ~/Downloads/openai-image-api/cat.png
```

Edit:

```bash
python3 /home/youngloach/.hermes/skills/media/openai-image-api/scripts/openai_image_api.py edit \
  --image /path/to/input.png \
  --prompt "Keep the composition, but turn the kitten into a very old cat." \
  --model gpt-image-2 \
  --out ~/Downloads/openai-image-api/old-cat.png
```

## Defaults And Overrides

- Persistent skill config: `/home/youngloach/.hermes/skills/media/openai-image-api/config.json`
- Example template: `/home/youngloach/.hermes/skills/media/openai-image-api/config.example.json`
- Base URL resolution order:
  - `--base-url`
  - `OPENAI_BASE_URL`
  - `config.json` `base_url`
  - current provider `base_url` from `~/.hermes/config.yaml where applicable, or explicit --base-url`
- API key resolution order:
  - `--api-key`
  - `OPENAI_API_KEY`
  - `config.json` `api_key`
  - `~/.hermes/.env / OPENAI_API_KEY where applicable` `OPENAI_API_KEY`
- Override per run with:
  - `--skill-config`
  - `--base-url`
  - `--api-key`
  - `--config`
  - `--auth`

Minimal `config.json`:

```json
{
  "base_url": "https://your-api.example.com/v1",
  "api_key": "sk-your-key-here"
}
```

Useful flags:
- `--model gpt-image-2`
- `--size 1024x1024`
- `--quality high`
- `--background auto`
- `--n 2`
- `--mask /path/to/mask.png`
- `--field key=value` for provider-specific extra fields
- `--response-json-out /path/to/response.json`

## AIGODStation image2 sizing notes

The current default endpoint is AIGODStation. For this endpoint, `1024x1024` was verified working through `gpt-image-2`. `3840x2160` is a valid/expected 16:9 4K size from prior site work, but direct skill calls can still return transient upstream `HTTP 502 server_error`; retry once with a very simple prompt and without `--quality high` before concluding it is down. Do not substitute local upscaling when the user asked to test native image2 4K; report native 4K success/failure separately from any optional post-processing.

## Output Rules

- If `--n 1`, prefer `--out`.
- If `--n > 1`, prefer `--out-dir`.
- If neither is provided, the script saves under `~/Downloads/openai-image-api/`.
- The script accepts either `b64_json` or `url` responses.

## Notes

- `edit` sends multipart form data to `/v1/images/edits`.
- The script supports both base URLs that already end with `/v1` and base URLs that do not.
- Global flags such as `--base-url`, `--timeout`, and `--response-json-out` must appear before the subcommand (`generate`/`edit`); generation-specific flags such as `--prompt`, `--model`, `--size`, `--quality`, and `--out` go after the subcommand.
- Do not overwrite user-facing assets unless asked; prefer a new filename or a version suffix.
- For this user, image generation requests must use `gpt-image-2` through this skill only. Do not use local/PIL/Imagemagick composition or other image backends as a fallback unless the user explicitly asks. If `gpt-image-2` fails, report the failure or try another `gpt-image-2` prompt/edit route.
- **Strict prompt fidelity for this user:** when the user provides a generation prompt in their own words, pass that prompt verbatim to `--prompt`. Do not add style terms, composition details, disclaimers, safety banners, quality modifiers, translations, or explanatory expansions. If the user separately asks for dimensions/aspect ratio, set those via API parameters such as `--size`; do not append them to the prompt unless the user explicitly asks for the text to be included in the prompt. If a prompt change seems necessary, ask first.
- If the user says to use “your Hermes Agent URL/key”, “你这个 Hermes Agent 的 url 和 key”, or similar, do **not** ask them for a new key. Resolve the active profile’s Hermes model endpoint from `$HERMES_HOME/config.yaml` (`model.base_url` and `model.api_key`, including env-var references from `$HERMES_HOME/.env`), write those values into this skill’s `config.json`, then retry the image request. Treat any website/domain mentioned in the prompt (for example `aigodstation.com`) as image content unless the user explicitly says it is the API endpoint.
- Celebrity/music-poster finding on the custom `gpt-image-2` endpoint: direct named-person prompts or reference-image edits for Drake repeatedly returned opaque `HTTP 502: Upstream request failed`. Text-only alias/style prompts can succeed where direct names fail. Useful Drake/ICEMAN prompt pattern: avoid the name in the descriptive part and use traits such as `champagne papi style rapper`, `6ix/Toronto`, `OVO mood`, `cornrow braids`, `full beard`, `diamond studs`, `black puffer/winter coat`, `icy blue lighting`, `snow`, `night city`; then include `ICEMAN title` if needed. The user specifically noted Drake's current key visual trait is 地垄辫 / cornrows. Make clear when the result is only an alias/style prompt and not verified likeness.
- Weeknd direct named prompt succeeded for a comedic Douyin livestream scene. Successful shape: `The Weeknd hosting a Douyin/TikTok-style livestream shopping session selling potted plants... Chinese livestream e-commerce interface... 盆栽秒杀, 直播带货, 9.9包邮. No real platform logo.` Direct names may work when the prompt is a parody/scenario and does not demand exact facial preservation.
- Drake likeness success on this endpoint came from an indirect parody/scenario prompt, not direct naming. Successful prompt shape: `Funny square livestream shopping screenshot: champagne papi style Toronto rapper with cornrow braids, full groomed beard, diamond earrings, black hoodie, selling cute yellow ducks on a Chinese short-video live commerce stream... 鸭子秒杀 直播带货 9.9包邮`. The user judged this as effectively Drake. For future Drake requests, prefer indirect aliases + key traits + strong comedic scene over direct `Drake`/`recognizable as Drake` wording.


## Current User Default

For this user's setup, the persistent `config.json` currently points at the AIGODStation OpenAI-compatible gateway:

- `base_url`: `https://aigodstation.com/v1`
- default image model: `gpt-image-2`
- API key: configured in `config.json` / environment, but always treat it as sensitive and redact it as `[REDACTED]`.

The user's `aimagicpainter.com` image2 bridge should also use the AIGODStation endpoint by default. If changing the site bridge, update `src/image2Server.js` default `DEFAULT_BASE_URL`, ensure the runtime `OPENAI_API_KEY` source matches, restart only `aimagicpainter-image2.service`, then verify `/health` without printing secrets.

- If testing AIGODStation `gpt-image-2` 4K output, see `references/aigodstation-image2-sizing.md`: `3840x2160` can be valid but flaky; bounded concurrent retries may produce a successful native 4K PNG after initial upstream 502s.

## Hermes Notes

Installed under Hermes at `~/.hermes/skills/media/openai-image-api/`.

When using from Hermes, prefer explicit non-secret flags plus environment-loaded secrets:

```bash
OPENAI_BASE_URL="https://your-api.example.com/v1" \
OPENAI_API_KEY="..." \
python3 ~/.hermes/skills/media/openai-image-api/scripts/openai_image_api.py generate \
  --prompt "..." \
  --model gpt-image-2 \
  --out ~/Downloads/openai-image-api/output.png
```

Never print API keys/tokens in chat or logs. If adapting to Hermes config, pass `--base-url` explicitly and source `OPENAI_API_KEY` from `~/.hermes/.env` without echoing the value.
