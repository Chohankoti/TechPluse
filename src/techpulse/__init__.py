import os
import time
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

def main() -> None:
    # 0. Imports
    from .post_manager import PostManager
    from .models import PostMetadata
    from .url_fetcher import URLFetcher
    from .relevance_checker import RelevanceChecker
    from .mail_manager import MailManager
   

    # 1. Environment Configurations & Thresholds
    content_state_path = os.getenv("CONTENT_STATE_PATH")
    hn_latest_posts_api = os.getenv("HN_TOP_STORIES_API")
    hn_item_url = os.getenv("HN_ITEM_API")
    
    constraints_path = os.getenv("USER_CONSTRAINTS_PATH")
    model_name = os.getenv("SENTENCE_TRANSFORMER_MODEL")
    
    title_threshold = float(os.getenv("TITLE_RELEVANCE_THRESHOLD"))
    content_threshold = float(os.getenv("CONTENT_RELEVANCE_THRESHOLD"))
    fallback_threshold = float(os.getenv("TITLE_FALLBACK_THRESHOLD"))
    read_first_threshold = float(os.getenv("READ_FIRST_THRESHOLD"))
    url_fetch_delay = float(os.getenv("URL_FETCH_DELAY_SECONDS"))

    from_email, to_email = os.getenv("FROM_EMAIL"), os.getenv("TO_EMAIL")
    app_password = os.getenv("APP_PASSWORD")

    # 2. Check Constraints File Before Loading Models
    if not constraints_path or not os.path.exists(constraints_path):
        logger.error("User constraints file path '%s' does not exist. Aborting run.", constraints_path)
        return

    try:
        from jsonc_parser.parser import JsoncParser
        constraints_data = JsoncParser().parse_file(constraints_path)
        has_phrases = False
        if isinstance(constraints_data, dict):
            for category, phrase_list in constraints_data.items():
                if isinstance(phrase_list, list) and len(phrase_list) > 0:
                    has_phrases = True
                    break
        if not has_phrases:
            logger.error("User constraints file at '%s' is empty or contains no categories/phrases. Aborting run before loading models.", constraints_path)
            return
    except Exception as e:
        logger.error("Failed to parse user constraints file at '%s': %s. Aborting run.", constraints_path, e)
        return

    # 3. Instantiate Pipeline Managers
    with PostManager(
        content_state_path=content_state_path,
        previous_post_ids_key="previous_post_ids",
        relevant_posts_key="relevant_posts",
        latest_post_url=hn_latest_posts_api,
        post_detail_url=hn_item_url
    ) as post_manager:

        url_fetcher = URLFetcher()

        mail_manager = MailManager(
            from_email=from_email,
            to_email=to_email,
            app_password=app_password
        )
        
        logger.info("Loading RelevanceChecker with model '%s' and constraints from '%s'", model_name, constraints_path)
        relevance_checker = RelevanceChecker(
            constraints_path=constraints_path,
            model_name=model_name,
            title_threshold=title_threshold,
            content_threshold=content_threshold,
            fallback_threshold=fallback_threshold
        )

        # 4. Retrieve Post State
        prev_ids = post_manager.get_previous_post_ids()
        latest_ids = post_manager.get_latest_post_ids()
        
        if not latest_ids:
            mail_manager.sendPipelinefail("Failed to fetch latest post IDs from Hacker News API. Aborting run.")
            logger.error("Failed to fetch latest post IDs from Hacker News API. Aborting run.")
            return

        # Compute new post IDs to process
        compute_ids = post_manager.get_compute_post_ids(prev_ids, latest_ids)
        logger.info("Fetched %d latest IDs. %d new IDs to compute.", len(latest_ids), len(compute_ids))

        curr_relevant_posts: list[PostMetadata] = []

        # 4. Pipeline Execution: Two-Pass Filtering Loop 
        for idx, post_id in enumerate(compute_ids, start=1):
            post_detail = post_manager.get_post_detail(post_id)
            if not post_detail:
                logger.warning("[%d/%d] ID %d: Could not fetch post details. Skipping.", idx, len(compute_ids), post_id)
                continue

            title = post_detail.get("title", "")
            url = post_detail.get("url")

            # Layer 1: Title Relevance Evaluation
            is_title_relevant, title_score, title_match = relevance_checker.check_title_relevance(title)
            
            if not is_title_relevant:
                logger.info("[%d/%d] ID %d: Title irrelevant (Score: %.4f). Skipping: %s.", idx, len(compute_ids), post_id, title_score, title)
                continue

            logger.info("[%d/%d] ID %d: Title passed Layer 1 filter (Score: %.4f). Target URL: %s", idx, len(compute_ids), post_id, title_score, url)

            # Rate Limit Sleep before Fetching Web Content
            if url_fetch_delay > 0:
                time.sleep(url_fetch_delay)

            url_content = url_fetcher.get_url_content(url) if url else None

            # Layer 2: Full Content Relevance Evaluation
            if url_content:
                is_content_relevant, content_score, content_match = relevance_checker.check_content_relevance(url_content, title=title)
                
                # Composite Score: If title was exceptionally strong, blend it to avoid dropping valid blogs
                composite_score = round(max(content_score, title_score * 0.85), 4)
                is_composite_relevant = is_content_relevant or (composite_score >= content_threshold)

                if is_composite_relevant:
                    reason_desc = relevance_checker.generate_reason_description(content_match, is_from_content=True)
                    
                    # Priority sorting: Mark high relevance (>= read_first_threshold) or multi-match articles as read_first
                    read_first = composite_score >= read_first_threshold or content_match.get("multi_match_count", 0) >= 2
                    
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
                if title_score >= fallback_threshold:
                    reason_desc = relevance_checker.generate_reason_description(title_match)
                    title_score = round(title_score, 4)
                    curr_relevant_posts.append(PostMetadata(post_id=post_id, title=title, url=url, reason=reason_desc, relevance_score=title_score, read_first=False))
                    logger.info("[%d/%d] ID %d: MATCHED title fallback (Fetch failed, Title Score: %.4f | %s)", idx, len(compute_ids), post_id, title_score, reason_desc)
                else:
                    logger.info("[%d/%d] ID %d: Content fetch failed and title score (%.4f) below fallback threshold.", idx, len(compute_ids), post_id, title_score)

        curr_relevant_posts.sort(key=lambda p: p.relevance_score, reverse=True)

        if curr_relevant_posts:
            top_count = max(1, int(len(curr_relevant_posts) * 0.30))
            for i in range(len(curr_relevant_posts)):
                if i < top_count:
                    curr_relevant_posts[i].read_first = True

        # 5. Persist State Update
        logger.info("Found %d relevant posts. Updating content state...", len(curr_relevant_posts))
        post_manager.update_previous_post_ids(latest_ids)

        # 6. Send Emails
        mail_manager.sendRelevantPosts(curr_relevant_posts)

        logger.info("Pipeline execution completed successfully.")
    

if __name__ == "__main__":
    main() 
