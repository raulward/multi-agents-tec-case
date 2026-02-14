from typing import Literal, Optional

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator


SourceKind = Literal["pdf", "html"]


class FetchOverrides(BaseModel):
    timeout_s: float = Field(default=20.0, gt=0)
    retries: int = Field(default=2, ge=0, le=5)
    max_bytes: int = Field(default=25_000_000, gt=0)


class HtmlExtractSpec(BaseModel):
    selectors: list[str]
    remove_selectors: list[str] = Field(
        default_factory=lambda: ["script", "style", "nav", "footer"]
    )

    @model_validator(mode="after")
    def validate_selectors(self):
        cleaned = [s.strip() for s in self.selectors if s and s.strip()]
        if not cleaned:
            raise ValueError("extract.selectors must contain at least one CSS selector")
        self.selectors = cleaned
        return self


class SourceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: SourceKind
    url: AnyHttpUrl
    extract: Optional[HtmlExtractSpec] = None
    fetch: FetchOverrides = Field(default_factory=FetchOverrides)

    @model_validator(mode="after")
    def validate_source_item(self):
        if self.kind == "html" and self.extract is None:
            raise ValueError("extract is required for kind='html'")
        return self


class SourceCatalog(BaseModel):
    sources: list[SourceItem]


class IngestFailure(BaseModel):
    source_id: str
    url: str
    step: str
    error: str
