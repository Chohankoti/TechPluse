import os
from dotenv import load_dotenv
from tinyfish import TinyFish

load_dotenv()


def main() -> None:
    client = TinyFish()

    urls = ["https://claude.com/check-files"]

    try: 
        fetched = client.fetch.get_contents(urls=urls, format="markdown")
    except Exception as e:  
        print(e)
        return

    content = fetched.results[0].text

    with open("url_content", "w", encoding="utf-8") as f:
        f.write(content)







