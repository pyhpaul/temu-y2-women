import unittest


class NormalizeRequestTest(unittest.TestCase):
    def test_normalize_valid_dress_request(self) -> None:
        from temu_y2_women.request_normalizer import normalize_request

        normalized = normalize_request(
            {
                "category": "dress",
                "target_market": "US",
                "target_launch_date": "2026-06-15",
                "mode": "B",
                "price_band": "mid",
                "occasion_tags": ["vacation"],
                "must_have_tags": ["floral"],
                "avoid_tags": ["bodycon"],
                "style_family": "vacation-romantic",
            }
        )

        self.assertEqual(normalized.category, "dress")
        self.assertEqual(normalized.target_market, "US")
        self.assertEqual(normalized.target_launch_date.isoformat(), "2026-06-15")
        self.assertEqual(normalized.mode, "B")
        self.assertEqual(normalized.price_band, "mid")
        self.assertEqual(normalized.occasion_tags, ("vacation",))
        self.assertEqual(normalized.must_have_tags, ("floral",))
        self.assertEqual(normalized.avoid_tags, ("bodycon",))
        self.assertEqual(normalized.style_family, "vacation-romantic")

    def test_reject_unsupported_category(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.request_normalizer import normalize_request

        with self.assertRaises(GenerationError) as error_context:
            normalize_request(
                {
                    "category": "tops",
                    "target_market": "US",
                    "target_launch_date": "2026-06-15",
                    "mode": "A",
                }
            )

        self.assertEqual(error_context.exception.code, "UNSUPPORTED_CATEGORY")

    def test_reject_invalid_date(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.request_normalizer import normalize_request

        with self.assertRaises(GenerationError) as error_context:
            normalize_request(
                {
                    "category": "dress",
                    "target_market": "US",
                    "target_launch_date": "2026-99-15",
                    "mode": "A",
                }
            )

        self.assertEqual(error_context.exception.code, "INVALID_DATE")

    def test_reject_non_us_market_for_mvp(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.request_normalizer import normalize_request

        with self.assertRaises(GenerationError) as error_context:
            normalize_request(
                {
                    "category": "dress",
                    "target_market": "EU",
                    "target_launch_date": "2026-06-15",
                    "mode": "A",
                }
            )

        self.assertEqual(error_context.exception.code, "INVALID_REQUEST")

    def test_allow_missing_style_family(self) -> None:
        from temu_y2_women.request_normalizer import normalize_request

        normalized = normalize_request(
            {
                "category": "dress",
                "target_market": "US",
                "target_launch_date": "2026-06-15",
                "mode": "A",
            }
        )

        self.assertIsNone(normalized.style_family)

    def test_reject_empty_style_family(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.request_normalizer import normalize_request

        with self.assertRaises(GenerationError) as error_context:
            normalize_request(
                {
                    "category": "dress",
                    "target_market": "US",
                    "target_launch_date": "2026-06-15",
                    "mode": "A",
                    "style_family": "",
                }
            )

        self.assertEqual(error_context.exception.code, "INVALID_REQUEST")
