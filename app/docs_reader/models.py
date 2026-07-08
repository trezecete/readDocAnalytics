from pydantic import BaseModel, Field


class DocumentContent(BaseModel):
    document_id: str
    title: str
    markdown: str = Field(min_length=1)

    @property
    def char_count(self) -> int:
        return len(self.markdown)

    @property
    def byte_count(self) -> int:
        return len(self.markdown.encode("utf-8"))
