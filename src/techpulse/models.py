from dataclasses import dataclass

@dataclass
class PostMetadata:
    post_id: int
    title: str
    url: str
    reason: str
    relevance_score: float
    read_first: bool
