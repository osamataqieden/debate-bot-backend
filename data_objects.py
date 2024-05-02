import pydantic

class rejected_topics(pydantic.BaseModel):
    topics: list[str]

class topics:
    topicTitle: str
    topicDesc: str
    topicDifficulty: str
