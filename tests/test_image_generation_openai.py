from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from temu_y2_women.errors import GenerationError


class OpenAIImageProviderConfigTest(unittest.TestCase):
    def test_build_openai_image_provider_rejects_missing_api_key(self) -> None:
        from temu_y2_women.image_generation_openai import build_openai_image_provider

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(GenerationError) as error_context:
                build_openai_image_provider()

        self.assertEqual(error_context.exception.code, "INVALID_IMAGE_PROVIDER_CONFIG")
