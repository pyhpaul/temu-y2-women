# gpt-image-2 Gateway Smoke Result

Date: 2026-04-29

## Outcome

- Base gateway is reachable.
- `gpt-image-2` image generation did not return within the smoke timeout window.
- `gpt-image-2` image edit returned upstream/provider availability errors.
- Current render-chain blocker is external gateway availability, not local prompt/workflow code.

## Evidence

### Base connectivity

- `GET /v1/models`
- Result: success in about `0.59s`
- Observation: gateway auth and base routing are working

### Anchor generation route

- `POST /v1/images/generations` with anchor key
- Result: curl timeout after `90.05s`, `http_code=000`

- `POST /v1/images/generations` with expansion key
- Result: curl timeout after `60.05s`, `http_code=000`

### Derived edit route

- `POST /v1/images/edits` with expansion key
- Result: `502`
- Body: `{"error":{"message":"Upstream service temporarily unavailable","type":"upstream_error"}}`

- `POST /v1/images/edits` with anchor key
- Result: `503`
- Body: `{"error":{"message":"No available compatible accounts","type":"api_error"}}`

## Interpretation

- Generation timeout reproduces across both keys, so the anchor failure is not isolated to one key.
- Edit failures differ by key:
  - expansion key reaches an upstream image-edit path but the upstream service is unavailable
  - anchor key is rejected earlier because no compatible account is currently available

## Next step

- Keep current product policy unchanged:
  - `hero_front` may use `generate`
  - derived hero/detail jobs must use `edit`
  - no `generations` fallback when edit is unavailable
- Re-run the same smoke after gateway/account availability changes.
