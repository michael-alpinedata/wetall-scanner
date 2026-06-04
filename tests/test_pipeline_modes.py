from unittest.mock import MagicMock, patch

from src.scanner.pipeline import _perform_scan


def test_perform_scan_dispatch():
    mock_client = MagicMock()
    mock_row = {"url_wetall": "https://wetall.fr/prod", "url_marchand_finale": "https://amazon.fr/dp/123"}

    # Test Discovery -> smart_scan
    with patch("src.scanner.pipeline.smart_scan", return_value=("OK", 200, None, "")) as mock_smart:
        _perform_scan(mock_client, mock_row, "discover")
        mock_smart.assert_called_once()

    # Test Rescan -> direct_merchant_scan
    with patch("src.scanner.pipeline.direct_merchant_scan", return_value=("OK", 200, None, "")) as mock_direct:
        _perform_scan(mock_client, mock_row, "rescan")
        mock_direct.assert_called_once_with(mock_client, "https://amazon.fr/dp/123")
