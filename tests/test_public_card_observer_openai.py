from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch


class PublicCardObserverOpenAITest(unittest.TestCase):
    def test_build_openai_public_card_observer_requires_api_key(self) -> None:
        from temu_y2_women.public_card_observer_openai import build_openai_public_card_observer

        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(Exception, "api_key"):
                build_openai_public_card_observer(model="gpt-4.1-mini")

    def test_observe_card_parses_json_payload(self) -> None:
        from temu_y2_women.public_card_observer_openai import build_openai_public_card_observer

        fake_client = MagicMock()
        fake_response = MagicMock()
        fake_response.output_text = json.dumps(
            {
                "observed_slots": [
                    {"slot": "dress_length", "value": "mini", "evidence_summary": "hemline appears above the knee"},
                    {"slot": "color_family", "value": "white", "evidence_summary": "fabric reads bright white"},
                ],
                "abstained_slots": ["waistline", "opacity_level"],
                "warnings": [],
            }
        )
        fake_client.responses.create.return_value = fake_response

        with patch("temu_y2_women.public_card_observer_openai.OpenAI", return_value=fake_client):
            observer = build_openai_public_card_observer(
                api_key="test-key",
                base_url="https://example.com/v1",
                model="gpt-4.1-mini",
            )
            result = observer.observe_card(
                {
                    "card_id": "card-001",
                    "title": "White Mini Dress",
                    "image_url": "https://images.example.com/white-mini-dress.jpg",
                    "source_url": "https://shop.example.com/products/white-mini-dress",
                }
            )

        self.assertEqual(result["observed_slots"][0]["slot"], "dress_length")
        self.assertEqual(result["abstained_slots"], ["waistline", "opacity_level"])
        fake_client.responses.create.assert_called_once()
