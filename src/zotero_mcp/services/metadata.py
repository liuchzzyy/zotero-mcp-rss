import logging
import requests
from typing import Any

logger = logging.getLogger(__name__)

class MetadataService:
    """Service for looking up academic metadata (DOI, etc.) from external APIs."""

    def __init__(self, mailto: str | None = None):
        """
        Initialize MetadataService.
        
        Args:
            mailto: Email address to include in API requests (polite pool for Crossref).
        """
        self.mailto = mailto
        self.crossref_base_url = "https://api.crossref.org/works"
        self.openalex_base_url = "https://api.openalex.org/works"

    def lookup_doi(self, title: str, author: str | None = None) -> str | None:
        """
        Lookup DOI for a given title and author.
        Tries Crossref first, then OpenAlex.
        """
        doi = self.lookup_crossref(title, author)
        if not doi:
            doi = self.lookup_openalex(title, author)
        return doi

    def lookup_crossref(self, title: str, author: str | None = None) -> str | None:
        """Lookup DOI using Crossref API."""
        try:
            params: dict[str, Any] = {
                "query.title": title,
                "rows": 1,
            }
            if author:
                params["query.author"] = author
            if self.mailto:
                params["mailto"] = self.mailto

            response = requests.get(self.crossref_base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            items = data.get("message", {}).get("items", [])
            if not items:
                return None

            # Check similarity (basic check: first item's title should be similar)
            best_match = items[0]
            item_title = best_match.get("title", [""])[0]
            
            # Very basic check - can be improved
            if title.lower() in item_title.lower() or item_title.lower() in title.lower():
                return best_match.get("DOI")
            
            return None
        except Exception as e:
            logger.warning(f"Crossref lookup failed for '{title}': {e}")
            return None

    def lookup_openalex(self, title: str, author: str | None = None) -> str | None:
        """Lookup DOI using OpenAlex API."""
        try:
            # OpenAlex filter syntax
            search_query = f"title.search:{title}"
            if author:
                search_query += f",author.search:{author}"
            
            params = {
                "filter": search_query,
                "rows": 1,
            }
            if self.mailto:
                params["mailto"] = self.mailto

            response = requests.get(self.openalex_base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            if not results:
                return None

            best_match = results[0]
            # OpenAlex returns DOI as a URL, we want just the DOI string
            doi_url = best_match.get("doi")
            if doi_url and "doi.org/" in doi_url:
                return doi_url.split("doi.org/")[-1]
            
            return None
        except Exception as e:
            logger.warning(f"OpenAlex lookup failed for '{title}': {e}")
            return None
