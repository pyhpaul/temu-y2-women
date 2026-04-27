## Why

The repository can already generate stable `dress` concept results and can already render an image from a saved successful result, but operators still have to run those as two separate commands. We need a one-shot path now so experiments can reach visible image output faster without changing the existing deterministic generation CLI or the existing saved-result render CLI.

## What Changes

- Add a dedicated one-shot workflow that reads a request JSON, generates a successful concept result, persists `concept_result.json`, and then renders image artifacts from that persisted result.
- Add a dedicated CLI for the one-shot workflow with the same provider options currently exposed by the saved-result render CLI.
- Preserve fail-closed render artifact behavior while keeping a successfully written `concept_result.json` when render-stage setup or provider dispatch fails.
- Add workflow and CLI regression coverage for success, invalid input, output-write failure, provider-config failure, and module entrypoint execution.

## Capabilities

### Modified Capabilities
- `image-generation-output`: add a one-shot CLI path that generates and renders in one command while preserving the existing two-step commands.

## Impact

- Adds one new workflow module and one new CLI module.
- Adds new regression coverage for the one-shot path.
- Adds an OpenSpec delta for one-shot generate-and-render behavior without changing the existing saved-result render contract.
