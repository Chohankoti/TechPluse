import logging
from tinyfish import TinyFish

logger = logging.getLogger(__name__)

class URLFetcher:
    def __init__(self, format: str = "markdown") -> None:
        self.format = format
        self.client = TinyFish()

    def get_url_content(self, url: str) -> str | None:
        try:
            fetched = self.client.fetch.get_contents(urls=[url], format=self.format)
            if fetched.errors:
                logger.warning("Errors encountered fetching %s: %s", url, fetched.errors)
                return None
            if fetched.results:
                return fetched.results[0].text
            return None
        except Exception as e:
            logger.warning("Error fetching URL content for %s: %s", url, e)
            return None
