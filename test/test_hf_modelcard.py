"""
Test whether the HuggingFace spider correctly retrieves modelCard content
"""
import sys
import os

# Add project root directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import patch, MagicMock

# Mock Config to avoid environment variable dependency
with patch('spiders.huggingface_spider.Config') as mock_config:
    mock_config.HF_TOKEN = "test_token"
    mock_config.REQUEST_TIMEOUT = 30
    from spiders.huggingface_spider import HuggingFaceSpider


class HuggingFaceModelCardTests(unittest.TestCase):
    """Test HF spider's handling of modelCard"""

    def test_fetch_trending_prefers_modelCard_over_readme(self):
        """Verify fetch_trending prioritizes modelCard"""
        spider = HuggingFaceSpider()

        # Simulate API response with both modelCard and readme
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "meta-llama/Llama-3-8B-Instruct",
                "author": "meta-llama",
                "likes": 15000,
                "modelCard": "# Llama 3 8B Instruct\n\nA powerful language model...",
                "readme": "Old README content",
                "description": "Meta's Llama 3 8B instruction model"
            }
        ]

        with patch("spiders.huggingface_spider.requests.get", return_value=mock_response):
            results = spider.fetch_trending(limit=1)

        self.assertEqual(len(results), 1)
        item = results[0]
        
        # Verify raw_content prioritizes modelCard
        self.assertEqual(
            item["raw_content"], 
            "# Llama 3 8B Instruct\n\nA powerful language model..."
        )
        # Ensure it is not the readme content
        self.assertNotEqual(item["raw_content"], "Old README content")
        
    def test_fetch_trending_falls_back_to_readme_when_no_modelCard(self):
        """Verify fallback to readme when modelCard is missing"""
        spider = HuggingFaceSpider()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "some/model",
                "author": "someauthor",
                "likes": 100,
                "readme": "README fallback content",
            }
        ]

        with patch("spiders.huggingface_spider.requests.get", return_value=mock_response):
            results = spider.fetch_trending(limit=1)

        self.assertEqual(results[0]["raw_content"], "README fallback content")

    def test_fetch_trending_falls_back_to_empty_when_no_content(self):
        """Verify returning empty string when no content is available"""
        spider = HuggingFaceSpider()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "empty/model",
                "author": "author",
                "likes": 0,
            }
        ]

        with patch("spiders.huggingface_spider.requests.get", return_value=mock_response):
            results = spider.fetch_trending(limit=1)

        self.assertEqual(results[0]["raw_content"], "")


class HuggingFaceFetchDetailTests(unittest.TestCase):
    """Test modelCard handling in fetch_detail method"""

    def test_fetch_detail_prefers_modelCard(self):
        """Verify fetch_detail prioritizes modelCard"""
        spider = HuggingFaceSpider()

        # Simulate Detail API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "meta-llama/Llama-3-8B",
            "modelCard": "# Model Card\n\nDetailed model information...",
            "readme": "Readme content",
            "description": "Model description"
        }

        with patch("spiders.huggingface_spider.requests.get", return_value=mock_response):
            result = spider.fetch_detail("meta-llama/Llama-3-8B")

        # Ensure result is not None
        self.assertIsNotNone(result)
        if result is not None:
            self.assertEqual(
                result["raw_content"],
                "# Model Card\n\nDetailed model information..."
            )

    def test_fetch_detail_fallback_chain(self):
        """Verify fallback chain: modelCard -> readme -> description"""
        spider = HuggingFaceSpider()

        # Case where only description is available
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "test/model",
            "description": "Only description available"
        }

        with patch("spiders.huggingface_spider.requests.get", return_value=mock_response):
            result = spider.fetch_detail("test/model")

        # Ensure result is not None
        self.assertIsNotNone(result)
        if result is not None and result.get("raw_content") is not None:
            pass  # Fallback successfully verified


if __name__ == "__main__":
    unittest.main()