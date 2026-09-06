import os
from dotenv import load_dotenv
from tinyfish import TinyFish
from .post_manager import PostManager

load_dotenv()


def get_url_content(url: str) -> str:
    try: 
        client = TinyFish()
        fetched = client.fetch.get_contents(urls=[url], format="markdown")
        return fetched.results[0].text
    except Exception as e:  
        print(e)
        return ""


def main() -> None:
    hn_api = os.getenv("HN_TOP_STORIES_API")
    post_manager = PostManager(
        content_state_path="src/data/content_state.jsonc",
        previous_post_ids_key="previous_post_ids",
        relevant_posts_key="relevant_posts",
        latest_post_url=hn_api
    )
    
    print("=== Testing PostManager Methods ===")

    # 1. Get previous post IDs
    prev_ids = post_manager.get_previous_post_ids()
    print(f"[1] Previous Post IDs: {prev_ids}")

    # 2. Get relevant posts
    relevant_posts = post_manager.get_relevant_posts()
    print(f"[2] Relevant Posts: {relevant_posts}")

    # 3. Get latest post IDs from API
    latest_ids = post_manager.get_latest_post_ids()
    if latest_ids is not None:
        print(f"[3] Latest Post IDs count: {len(latest_ids)} | Sample (top 5): {latest_ids[:5]}")
    else:
        print("[3] Latest Post IDs: None (Failed to fetch)")

    # 4. Update previous posts with latest one
    post_manager.update_previous_post_ids(latest_ids[:5])
    print(f"[4] Updated Previous Post IDs: {post_manager.get_previous_post_ids()}")

    # 5. Compute new post IDs to process
    new_ids = post_manager.get_compute_post_ids(prev_ids, latest_ids)
    print(f"[5] Computed New Post IDs count: {len(new_ids)} | Sample (top 5): {new_ids[:5]}")

    # 6. Update relevant posts with new ones in format of [{post_id: int, why: string}]
    post_manager.update_relevant_posts([{"post_id": 123, "why": "Test post"}])
    print(f"[6] Updated Relevant Posts: {post_manager.get_relevant_posts()}")

    

if __name__ == "__main__":
    main()
