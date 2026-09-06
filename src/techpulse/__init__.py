import os
from dotenv import load_dotenv
from tinyfish import TinyFish
from jsonc_parser.parser import JsoncParser

load_dotenv()

def get_new_post_ids() -> list[int]:
    previous_post_ids = JsoncParser().parse_file("src/data/content_state.jsonc")["previous_post_ids"]
    print(previous_post_ids)

def get_url_content(url: str) -> str:
    try: 
        client = TinyFish()
        fetched = client.fetch.get_contents(urls=[url], format="markdown")
        return fetched.results[0].text
    except Exception as e:  
        print(e)
        return ""


def main() -> None:
    get_new_post_ids()
    # print(get_url_content("https://claude.com/check-files"))


   








