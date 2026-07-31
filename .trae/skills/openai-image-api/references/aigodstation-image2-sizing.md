# AIGODStation image2 sizing and retry notes

Session-derived probe for `openai-image-api` against AIGODStation (`https://aigodstation.com/v1`) with `model=gpt-image-2`.

## Observed results

- `1024x1024` succeeded on first direct test.
- `3072x1728` succeeded on first direct test; output verified as PNG `3072 x 1728`.
- `3840x2160` is a valid/expected 4K 16:9 size, but single attempts can return upstream `HTTP 502 server_error`.
- Running 10 concurrent `3840x2160` attempts with a simple prompt (`风景`) produced 1 success and 9 upstream failures in the observed session. The successful output verified as PNG `3840 x 2160`.
- `4096x4096` failed and should not be treated as supported square 4K.

## Durable workflow lesson

When the user asks to verify AIGODStation 4K image2 output, do not conclude `3840x2160` is unsupported after one or two 502s. For simple prompts, run a bounded retry/batch pattern first, e.g. 5-10 attempts, preferably concurrently if the user explicitly wants to test hit rate. Report the actual success count and save the successful file(s).

## Reporting guidance

- Distinguish “valid but unstable/upstream 502” from “unsupported size”.
- Verify generated dimensions from the PNG header before claiming success.
- Keep output filenames/directories explicit, e.g. a Desktop folder named for the batch.
- Do not substitute local upscaling when the user asked for native image2 4K unless they explicitly accept post-processing.