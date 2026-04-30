from __future__ import annotations

import io
from urllib.error import HTTPError, URLError
import unittest


class ImageGatewaySmokeTest(unittest.TestCase):
    def test_run_gateway_smoke_returns_structured_report_for_default_checks(self) -> None:
        from temu_y2_women.image_gateway_smoke import GatewaySmokeSettings, run_gateway_smoke
        from temu_y2_women.image_gateway_smoke_http import GatewayHttpResult

        client = _FakeSmokeHttpClient(
            [
                GatewayHttpResult(http_code=200, body_text='{"data":[]}', elapsed_seconds=0.59),
                GatewayHttpResult(http_code=None, body_text="timed out", elapsed_seconds=90.05, timed_out=True),
                GatewayHttpResult(http_code=None, body_text="timed out", elapsed_seconds=60.05, timed_out=True),
                GatewayHttpResult(
                    http_code=503,
                    body_text='{"error":{"message":"No available compatible accounts","type":"api_error"}}',
                    elapsed_seconds=0.31,
                ),
                GatewayHttpResult(
                    http_code=502,
                    body_text='{"error":{"message":"Upstream service temporarily unavailable","type":"upstream_error"}}',
                    elapsed_seconds=0.73,
                ),
            ]
        )

        report = run_gateway_smoke(_settings(), http_client=client)

        self.assertEqual(report["schema_version"], "image-gateway-smoke-report-v1")
        self.assertEqual(report["model"], "gpt-image-2")
        self.assertEqual(report["base_url"], "https://example.test/v1")
        self.assertEqual(report["summary"], {"total": 5, "passed": 1, "failed": 4})
        self.assertEqual([check["check_id"] for check in report["checks"]], _default_check_ids())
        self.assertEqual(report["checks"][0]["route"], "GET /v1/models")
        self.assertEqual(report["checks"][1]["error_type"], "timeout")
        self.assertEqual(report["checks"][3]["error_type"], "api_error")
        self.assertEqual(report["checks"][4]["error_type"], "upstream_error")
        self.assertEqual(client.calls[1]["credential_route"], "anchor")
        self.assertEqual(client.calls[4]["credential_route"], "expansion")

    def test_run_gateway_smoke_honors_selected_checks(self) -> None:
        from temu_y2_women.image_gateway_smoke import GatewaySmokeSettings, run_gateway_smoke
        from temu_y2_women.image_gateway_smoke_http import GatewayHttpResult

        client = _FakeSmokeHttpClient(
            [
                GatewayHttpResult(http_code=200, body_text='{"data":[]}', elapsed_seconds=0.59),
                GatewayHttpResult(
                    http_code=502,
                    body_text='{"error":{"message":"Upstream service temporarily unavailable","type":"upstream_error"}}',
                    elapsed_seconds=0.73,
                ),
            ]
        )

        report = run_gateway_smoke(
            GatewaySmokeSettings(
                base_url="https://example.test/v1",
                model="gpt-image-2",
                anchor_api_key="anchor-key",
                expansion_api_key="expansion-key",
                timeout_sec=30.0,
            ),
            check_ids=["models", "edit-expansion"],
            http_client=client,
        )

        self.assertEqual([check["check_id"] for check in report["checks"]], ["models", "edit-expansion"])
        self.assertEqual(
            [(call["method"], call["credential_route"]) for call in client.calls],
            [("get_json", "anchor"), ("post_multipart", "expansion")],
        )


class ImageGatewaySmokeHttpClientTest(unittest.TestCase):
    def test_post_json_returns_http_error_body(self) -> None:
        from temu_y2_women.image_gateway_smoke_http import GatewaySmokeHttpClient

        client = GatewaySmokeHttpClient(
            transport=lambda request, timeout: _raise_http_error(
                request,
                502,
                '{"error":{"type":"upstream_error","message":"Upstream service temporarily unavailable"}}',
            )
        )

        result = client.post_json(
            "https://example.test/v1/images/generations",
            api_key="fixture-key",
            payload={"model": "gpt-image-2"},
            timeout_sec=3.0,
        )

        self.assertEqual(result.http_code, 502)
        self.assertFalse(result.timed_out)
        self.assertIn("upstream_error", result.body_text)

    def test_get_json_maps_timeout_from_url_error(self) -> None:
        from temu_y2_women.image_gateway_smoke_http import GatewaySmokeHttpClient

        client = GatewaySmokeHttpClient(
            transport=lambda request, timeout: _raise_url_error_timeout()
        )

        result = client.get_json(
            "https://example.test/v1/models",
            api_key="fixture-key",
            timeout_sec=2.5,
        )

        self.assertIsNone(result.http_code)
        self.assertTrue(result.timed_out)
        self.assertEqual(result.transport_error, "timeout")

    def test_post_multipart_builds_image_edit_request(self) -> None:
        from temu_y2_women.image_gateway_smoke_http import GatewaySmokeHttpClient

        captured: dict[str, object] = {}
        client = GatewaySmokeHttpClient(
            transport=lambda request, timeout: _capture_request(captured, request, _FakeResponse(200, b'{"data":[]}'))
        )

        result = client.post_multipart(
            "https://example.test/v1/images/edits",
            api_key="fixture-key",
            fields={"model": "gpt-image-2", "prompt": "smoke"},
            file_field="image",
            filename="reference.png",
            file_bytes=b"png-bytes",
            mime_type="image/png",
            timeout_sec=3.0,
        )

        request = captured["request"]
        headers = dict(request.header_items())
        self.assertEqual(result.http_code, 200)
        self.assertEqual(request.get_method(), "POST")
        self.assertIn("multipart/form-data", headers["Content-type"])
        self.assertIn(b'name="image"', request.data)
        self.assertIn(b"png-bytes", request.data)


class _FakeSmokeHttpClient:
    def __init__(self, results: list[object]) -> None:
        self._results = list(results)
        self.calls: list[dict[str, str]] = []

    def get_json(self, url: str, *, api_key: str, timeout_sec: float) -> object:
        return self._consume("get_json", url, api_key)

    def post_json(self, url: str, *, api_key: str, payload: dict[str, object], timeout_sec: float) -> object:
        return self._consume("post_json", url, api_key)

    def post_multipart(
        self,
        url: str,
        *,
        api_key: str,
        fields: dict[str, str],
        file_field: str,
        filename: str,
        file_bytes: bytes,
        mime_type: str,
        timeout_sec: float,
    ) -> object:
        return self._consume("post_multipart", url, api_key)

    def _consume(self, method: str, url: str, api_key: str) -> object:
        credential_route = "anchor" if api_key == "anchor-key" else "expansion"
        self.calls.append({"method": method, "url": url, "credential_route": credential_route})
        return self._results.pop(0)


class _FakeResponse:
    def __init__(self, code: int, body: bytes) -> None:
        self._code = code
        self._body = body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False

    def read(self) -> bytes:
        return self._body

    def getcode(self) -> int:
        return self._code


def _settings() -> object:
    from temu_y2_women.image_gateway_smoke import GatewaySmokeSettings

    return GatewaySmokeSettings(
        base_url="https://example.test/v1",
        model="gpt-image-2",
        anchor_api_key="anchor-key",
        expansion_api_key="expansion-key",
        timeout_sec=90.0,
    )


def _default_check_ids() -> list[str]:
    return [
        "models",
        "generate-anchor",
        "generate-expansion",
        "edit-anchor",
        "edit-expansion",
    ]


def _capture_request(captured: dict[str, object], request: object, response: object) -> object:
    captured["request"] = request
    return response


def _raise_http_error(request: object, code: int, body: str) -> object:
    raise HTTPError(
        request.full_url,
        code,
        "error",
        hdrs=None,
        fp=io.BytesIO(body.encode("utf-8")),
    )


def _raise_url_error_timeout() -> object:
    raise URLError(TimeoutError("timed out"))
