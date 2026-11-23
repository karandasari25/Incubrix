from pydantic import BaseModel, Field


class PublishRequest(BaseModel):
    destinations: list[str] = Field(default_factory=list)
    title: str | None = None
    body: str | None = None
    canonical_link: str | None = None
    tags: list[str] = Field(default_factory=list)
    is_promotional: bool = False
    ai_generated: bool = False
    callback_url: str | None = None


class DestinationCreate(BaseModel):
    name: str
    url: str
    platform_key: str
    surface: str
    category: str | None = None
    audience_tags: list[str] = Field(default_factory=list)
    language: str | None = None
    geo: str | None = None
    est_audience: int | None = None
    rules_url: str | None = None
    frequency_cap: str | None = None
    self_promo_allowed: bool | None = None
    link_policy: str | None = None
    disclosure_required: bool | None = None
    automation_allowed: bool | None = None
    connector_key: str
    relevance_score: int | None = Field(default=None, ge=1, le=5)
    relevance_reason: str | None = None
    level: str = "L0"


class CatalogueImportRequest(BaseModel):
    csv_path: str


class AIRulesCaptureRequest(BaseModel):
    text: str


class RecommendationRequest(BaseModel):
    title: str | None = None
    body: str | None = None
    canonical_link: str | None = None
    tags: list[str] = Field(default_factory=list)
    language: str | None = "en"
    is_promotional: bool = False
    ai_generated: bool = False
