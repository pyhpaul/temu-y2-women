## 1. Render input and provider foundation

- [x] 1.1 Add focused validation helpers for successful `dress` concept result payloads and prompt-bundle extraction
- [x] 1.2 Add an image-provider adapter contract plus a fake provider path for offline tests
- [x] 1.3 Add regression coverage for valid render inputs and fail-closed invalid-input handling

## 2. Image render workflow

- [ ] 2.1 Implement the image-render workflow that builds a provider request from a saved concept result
- [ ] 2.2 Implement deterministic render reporting and staged output publication for image artifacts
- [ ] 2.3 Add workflow regression coverage for provider success, provider failure, and output-write rollback

## 3. CLI and production provider integration

- [ ] 3.1 Add a dedicated image-generation CLI that renders from a saved concept result and prints the render report JSON
- [ ] 3.2 Add the first real provider adapter integration behind the provider contract with explicit configuration validation
- [ ] 3.3 Add CLI regression coverage, including module entrypoint execution and structured provider-config failures

## 4. Verification and completion

- [ ] 4.1 Run repository tests and focused render-workflow regression coverage
- [ ] 4.2 Run OpenSpec validation and the function-length guard
- [ ] 4.3 Mark the change tasks complete after all validation passes
