import os
import time
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

def setup_logging(
    log_dir: str | None = None,
    log_file: str = "techpulse.log",
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 2
) -> None:
    if log_dir is None:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.abspath(os.path.join(current_dir, "..", "logs"))

    os.makedirs(log_dir, exist_ok=True)
    file_path = os.path.join(log_dir, log_file)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # 1. Rotating File Handler
    file_handler = RotatingFileHandler(
        file_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # 2. Console Handler (stdout)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)

load_dotenv()

def main() -> None:
    # Initialize logging with rotating file handler in src/logs
    setup_logging()

    # 0. Imports
    from .post_manager import PostManager
    from .models import PostMetadata
    from .url_fetcher import URLFetcher
    from .relevance_checker import RelevanceChecker
    from .mail_manager import MailManager
    from .executor import Executor

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

        # 4. Instantiate and Run Pipeline Executor
        executor = Executor(
            post_manager=post_manager,
            url_fetcher=url_fetcher,
            relevance_checker=relevance_checker,
            mail_manager=mail_manager,
            url_fetch_delay=url_fetch_delay,
            read_first_threshold=read_first_threshold,
            content_threshold=content_threshold,
            fallback_threshold=fallback_threshold
        )
        executor.run()
    

if __name__ == "__main__":
    main() 
