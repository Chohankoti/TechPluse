from __future__ import annotations
import time
import logging
from typing import Any
from .post_manager import PostManager
from .models import PostMetadata
from .url_fetcher import URLFetcher
from .relevance_checker import RelevanceChecker
from .mail_manager import MailManager

logger = logging.getLogger(__name__)

class Executor:
    """
    Pipeline Executor orchestrates the two-pass relevance evaluation loop,
    state persistence, and email notifications.
    """
    def __init__(
        self,
        post_manager: PostManager,
        url_fetcher: URLFetcher,
        relevance_checker: RelevanceChecker,
        mail_manager: MailManager,
        url_fetch_delay: float = 0.0,
        read_first_threshold: float = 0.70,
        content_threshold: float = 0.55,
        fallback_threshold: float = 0.60
    ) -> None:
        self.post_manager = post_manager
        self.url_fetcher = url_fetcher
        self.relevance_checker = relevance_checker
        self.mail_manager = mail_manager
        self.url_fetch_delay = url_fetch_delay
        self.read_first_threshold = read_first_threshold
        self.content_threshold = content_threshold
        self.fallback_threshold = fallback_threshold

    def run(self) -> None:
        """Executes the pipeline."""
        # 1. Retrieve Post State
        prev_ids = self.post_manager.get_previous_post_ids()
        latest_ids = self.post_manager.get_latest_post_ids()
        
        if not latest_ids:
            self.mail_manager.sendPipelinefail("Failed to fetch latest post IDs from Hacker News API. Aborting run.")
            logger.error("Failed to fetch latest post IDs from Hacker News API. Aborting run.")
            return

        # Compute new post IDs to process
        compute_ids = self.post_manager.get_compute_post_ids(prev_ids, latest_ids)
        logger.info("Fetched %d latest IDs. %d new IDs to compute.", len(latest_ids), len(compute_ids))

        curr_relevant_posts: list[PostMetadata] = []

        # 2. Pipeline Execution: Two-Pass Filtering Loop 
        for idx, post_id in enumerate(compute_ids, start=1):
            post_detail = self.post_manager.get_post_detail(post_id)
            if not post_detail:
                logger.warning("[%d/%d] ID %d: Could not fetch post details. Skipping.", idx, len(compute_ids), post_id)
                continue

            title = post_detail.get("title", "")
            url = post_detail.get("url")

            # Layer 1: Title Relevance Evaluation
            is_title_relevant, title_score, title_match = self.relevance_checker.check_title_relevance(title)
            
            if not is_title_relevant:
                logger.info("[%d/%d] ID %d: Title irrelevant (Score: %.4f). Skipping: %s.", idx, len(compute_ids), post_id, title_score, title)
                continue

            logger.info("[%d/%d] ID %d: Title passed Layer 1 filter (Score: %.4f). Target URL: %s", idx, len(compute_ids), post_id, title_score, url)

            # Rate Limit Sleep before Fetching Web Content
            if self.url_fetch_delay > 0:
                time.sleep(self.url_fetch_delay)

            url_content = self.url_fetcher.get_url_content(url) if url else None

            # Layer 2: Full Content Relevance Evaluation
            if url_content:
                is_content_relevant, content_score, content_match = self.relevance_checker.check_content_relevance(url_content, title=title)
                
                # Composite Score: If title was exceptionally strong, blend it to avoid dropping valid blogs
                composite_score = round(max(content_score, title_score * 0.85), 4)
                is_composite_relevant = is_content_relevant or (composite_score >= self.content_threshold)

                if is_composite_relevant:
                    reason_desc = self.relevance_checker.generate_reason_description(content_match, is_from_content=True)
                    
                    # Priority sorting: Mark high relevance (>= read_first_threshold) and multi-match articles as read_first
                    read_first = composite_score >= self.read_first_threshold and content_match.get("multi_match_count", 0) >= 2
                    
                    curr_relevant_posts.append(PostMetadata(
                        post_id=post_id,
                        title=title,
                        url=url,
                        reason=reason_desc,
                        relevance_score=composite_score,
                        read_first=read_first
                    ))
                    logger.info("[%d/%d] ID %d: MATCHED (Score: %.4f | ReadFirst: %s | %s)", idx, len(compute_ids), post_id, composite_score, read_first, reason_desc)
                else:
                    logger.info("[%d/%d] ID %d: Content body failed Layer 2 filter (Content: %.4f, Title: %.4f). Discarding.", idx, len(compute_ids), post_id, content_score, title_score)
            else:
                # Fallback to high title relevance if URL fetch failed/blocked
                if title_score >= self.fallback_threshold:
                    reason_desc = self.relevance_checker.generate_reason_description(title_match)
                    title_score = round(title_score, 4)
                    curr_relevant_posts.append(PostMetadata(post_id=post_id, title=title, url=url, reason=reason_desc, relevance_score=title_score, read_first=False))
                    logger.info("[%d/%d] ID %d: MATCHED title fallback (Fetch failed, Title Score: %.4f | %s)", idx, len(compute_ids), post_id, title_score, reason_desc)
                else:
                    logger.info("[%d/%d] ID %d: Content fetch failed and title score (%.4f) below fallback threshold.", idx, len(compute_ids), post_id, title_score)
        
        # 3. Persist State Update
        logger.info("Found %d relevant posts. Updating content state...", len(curr_relevant_posts))
        self.post_manager.update_previous_post_ids(latest_ids)

        # 4. Send Emails
        self.mail_manager.sendRelevantPosts(curr_relevant_posts)

        logger.info("Pipeline execution completed successfully.")
