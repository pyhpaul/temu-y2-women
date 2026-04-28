from __future__ import annotations

import base64
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch


class ProductImageObserverOpenAITest(unittest.TestCase):
    def test_build_openai_product_image_observer_requires_api_key(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.product_image_observer_openai import build_openai_product_image_observer

        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(GenerationError) as error:
                build_openai_product_image_observer(api_key="", base_url="https://example.com/v1")

        self.assertEqual(error.exception.code, "INVALID_PRODUCT_IMAGE_OBSERVER_CONFIG")

    def test_build_openai_product_image_observer_requires_base_url(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.product_image_observer_openai import build_openai_product_image_observer

        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(GenerationError) as error:
                build_openai_product_image_observer(api_key="test-key", base_url="")

        self.assertEqual(error.exception.code, "INVALID_PRODUCT_IMAGE_OBSERVER_CONFIG")

    def test_build_openai_product_image_observer_uses_environment_defaults(self) -> None:
        fake_client = Mock()

        with patch.dict(
            "os.environ",
            {
                "OPENAI_COMPAT_EXPANSION_API_KEY": "env-key",
                "OPENAI_COMPAT_BASE_URL": "https://env.example.com/v1",
            },
            clear=True,
        ):
            with patch("temu_y2_women.product_image_observer_openai.OpenAI", return_value=fake_client) as openai_cls:
                from temu_y2_women.product_image_observer_openai import build_openai_product_image_observer

                build_openai_product_image_observer(model="gpt-4.1-mini")

        openai_cls.assert_called_once_with(api_key="env-key", base_url="https://env.example.com/v1")

    def test_observe_image_sends_local_file_as_data_url_and_parses_json(self) -> None:
        from temu_y2_women.product_image_observer_openai import build_openai_product_image_observer

        fake_client = Mock()
        fake_client.responses.create.return_value = Mock(
            output_text='{"observed_slots":[{"slot":"pattern","value":"gingham check","evidence_summary":"grid checks visible across bodice"}],"abstained_slots":["waistline"],"warnings":[]}'
        )

        with TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "front.jpg"
            image_path.write_bytes(b"fake-jpeg-bytes")
            expected_data_url = "data:image/jpeg;base64," + base64.b64encode(b"fake-jpeg-bytes").decode("ascii")

            with patch("temu_y2_women.product_image_observer_openai.OpenAI", return_value=fake_client):
                observer = build_openai_product_image_observer(
                    api_key="test-key",
                    base_url="https://example.com/v1",
                    model="gpt-4.1-mini",
                )
                payload = observer.observe_image(
                    {
                        "image_id": "dress-product-001-front",
                        "image_path": str(image_path),
                        "view_label": "front",
                    }
                )

        self.assertEqual(payload["observed_slots"][0]["slot"], "pattern")
        request = fake_client.responses.create.call_args.kwargs["input"][0]
        self.assertEqual(request["content"][1]["type"], "input_image")
        self.assertEqual(request["content"][1]["image_url"], expected_data_url)
        self.assertEqual(
            request["content"][0]["text"],
            "return JSON only with keys observed_slots, abstained_slots, warnings.",
        )

    def test_observe_image_raises_on_invalid_json(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.product_image_observer_openai import build_openai_product_image_observer

        fake_client = Mock()
        fake_client.responses.create.return_value = Mock(output_text="not-json")

        with TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "front.png"
            image_path.write_bytes(b"png-bytes")

            with patch("temu_y2_women.product_image_observer_openai.OpenAI", return_value=fake_client):
                observer = build_openai_product_image_observer(
                    api_key="test-key",
                    base_url="https://example.com/v1",
                )
                with self.assertRaises(GenerationError) as error:
                    observer.observe_image(
                        {
                            "image_id": "dress-product-002-front",
                            "image_path": str(image_path),
                            "view_label": "front",
                        }
                    )

        self.assertEqual(error.exception.code, "INVALID_PRODUCT_IMAGE_OBSERVATION")

    def test_observe_image_raises_on_non_string_output_text(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.product_image_observer_openai import build_openai_product_image_observer

        with TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "front.png"
            image_path.write_bytes(b"png-bytes")

            for output_text in (None, b"{}", bytearray(b"{}")):
                fake_client = Mock()
                fake_client.responses.create.return_value = Mock(output_text=output_text)

                with self.subTest(output_text=type(output_text).__name__):
                    with patch("temu_y2_women.product_image_observer_openai.OpenAI", return_value=fake_client):
                        observer = build_openai_product_image_observer(
                            api_key="test-key",
                            base_url="https://example.com/v1",
                        )
                        with self.assertRaises(GenerationError) as error:
                            observer.observe_image(
                                {
                                    "image_id": "dress-product-003-front",
                                    "image_path": str(image_path),
                                    "view_label": "front",
                                }
                            )

                    self.assertEqual(error.exception.code, "INVALID_PRODUCT_IMAGE_OBSERVATION")
