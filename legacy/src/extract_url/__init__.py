"""Package extract_url : synchronisation du sitemap Wetall vers la DB."""

from .sync import sync_sitemap_to_db

__all__ = ["sync_sitemap_to_db"]
