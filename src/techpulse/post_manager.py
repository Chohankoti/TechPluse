from __future__ import annotations
import json
import logging
import re
from typing import Any
from jsonc_parser.parser import JsoncParser
import requests
from dataclasses import dataclass, field, asdict
from .models import PostMetadata

logger = logging.getLogger(__name__)

@dataclass
class PostMetadata:
    post_id: int
    title: str
    url: str
    reason: str
    relevance_score: float
    read_first: bool


class PostManager:
    def __init__(self, content_state_path: str, previous_post_ids_key: str, relevant_posts_key: str, latest_post_url: str, post_detail_url: str) -> None:
        self.content_state_path = content_state_path
        self.previous_post_ids_key = previous_post_ids_key
        self.relevant_posts_key = relevant_posts_key
        self.latest_post_url = latest_post_url
        self.post_detail_url = post_detail_url
    
    def _load_content_state(self) -> dict[str, Any] | None:
        """Loads the content state dictionary from the specified path."""
        if not self.content_state_path:
            logger.warning("Content state path was not assigned.")
            return None

        try:
            state = JsoncParser().parse_file(self.content_state_path)
            if isinstance(state, dict):
                return state
            logger.warning("Content state file at %s is not a JSON object.", self.content_state_path)
            return None
        except Exception as e:
            logger.warning("Failed to load content state from %s: %s", self.content_state_path, e)
            return None

    def _load_content_state_by_key(self, key: str) -> Any | None:
        """Loads content state value by key."""
        if not key:
            logger.warning("Key was empty.")
            return None

        content_state = self._load_content_state()
        if content_state is None:
            return None

        if key not in content_state:
            logger.warning("Key '%s' was not found in content state.", key)
            return None

        return content_state[key]
    
    def _save_content_state_by_key(self, key: str, value: Any) -> bool:
        """Saves value into content state for the given key while preserving file comments."""
        if not self.content_state_path:
            logger.warning("Content state path was not assigned.")
            return False
        if not key:
            logger.warning("Key was empty.")
            return False

        try:
            with open(self.content_state_path, "r", encoding="utf-8") as f:
                raw_content = f.read()

            esc_key = re.escape(key)
            pattern = re.compile(
                r'("' + esc_key + r'"\s*:\s*)(?:\[[\s\S]*?\]|\{[\s\S]*?\}|"[^"]*"|\d+|true|false|null)'
            )
            formatted_val = json.dumps(value, indent=2)

            if pattern.search(raw_content):
                updated_content = pattern.sub(r'\g<1>' + formatted_val, raw_content, count=1)
            else:
                content_state = self._load_content_state() or {}
                content_state[key] = value
                updated_content = json.dumps(content_state, indent=2)

            with open(self.content_state_path, "w", encoding="utf-8") as f:
                f.write(updated_content)
            return True
        except Exception as e:
            logger.warning("Failed to save content state to %s: %s", self.content_state_path, e)
            return False
    
    def get_previous_post_ids(self) -> list[int] | None:
        """Gets the list of previous post IDs."""
        if not self.previous_post_ids_key:
            logger.warning("Previous post ids key was not assigned.")
            return None
       
        val = self._load_content_state_by_key(self.previous_post_ids_key)
        if isinstance(val, list):
            return val
        if val is not None:
            logger.warning("Previous post ids value is not a list: %r", val)
        return None
    
    def get_relevant_posts(self) -> list[PostMetadata] | None:
        """Gets the list of relevant posts mapped to PostMetadata objects."""
        if not self.relevant_posts_key:
            logger.warning("Relevant posts key was not assigned.")
            return None
        
        val = self._load_content_state_by_key(self.relevant_posts_key)
        if isinstance(val, list):
            try:
                return [PostMetadata(**post) if isinstance(post, dict) else post for post in val]
            except (TypeError, ValueError) as e:
                logger.warning("Failed to parse relevant posts into dataclasses: %s", e)
                return None
                
        if val is not None:
            logger.warning("Relevant posts value is not a list: %r", val)
        return None
    
    def update_previous_post_ids(self, new_post_ids: list[int]) -> bool:
        """Updates the list of processed post IDs with the latest ones."""
        if not self.previous_post_ids_key:
            logger.warning("Previous post ids key was not assigned.")
            return False

        return self._save_content_state_by_key(self.previous_post_ids_key, new_post_ids)
    
    def update_relevant_posts(self, relevant_posts: list[PostMetadata]) -> bool:
        """Updates the list of relevant posts."""
        if not self.relevant_posts_key:
            logger.warning("Relevant posts key was not assigned.")
            return False
        
        serializable_posts = [asdict(post) for post in relevant_posts]
        return self._save_content_state_by_key(self.relevant_posts_key, serializable_posts)
    
    def get_latest_post_ids(self) -> list[int] | None:
        """Fetches and gets the latest post ids from HN."""
        if not self.latest_post_url:
            logger.warning("Latest post url was not assigned.")
            return None
         
        try:
            response = requests.get(self.latest_post_url, timeout=10000)
            if response.status_code != 200:
                logger.warning("Error fetching latest post ids: HTTP status %s", response.status_code)
                return None
            data = response.json()
            if isinstance(data, list):
                return data
            logger.warning("Response content is not a list: %r", data)
            return None
        except Exception as e:
            logger.warning("Error fetching latest post ids from %s: %s", self.latest_post_url, e)
            return None
    
    def get_compute_post_ids(self, prev_ids: list[int] | None, latest_ids: list[int] | None) -> list[int]:
        """Computes new post ids from latest post ids that are not in previous post ids."""
        if not latest_ids:
            return []
        if not prev_ids:
            return list(latest_ids)

        prev_ids_set = set(prev_ids)
        return [post_id for post_id in latest_ids if post_id not in prev_ids_set]

    def get_post_detail(self, post_id: int) -> dict[str, Any] | None:
        """Gets the details of a post."""
        if not self.post_detail_url:
            logger.warning("Post detail url was not assigned.")
            return None
        
        url = self.post_detail_url.format(id=post_id)
        try:
            response = requests.get(url, timeout=10000)
            if response.status_code != 200:
                logger.warning("Error fetching post details: HTTP status %s", response.status_code)
                return None
            data = response.json()
            if "url" in data and "title" in data:
                return {"title": data["title"], "url": data["url"]}
            else:
                return None
        except Exception as e:
            logger.warning("Error fetching post details from %s: %s", url, e)
            return None 