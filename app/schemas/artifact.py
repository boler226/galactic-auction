from pydantic import BaseModel, ConfigDict, Field


class ArtifactCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    rarity: str = Field(default="common", max_length=32)
    origin_galaxy: str | None = Field(default=None, max_length=128)


class ArtifactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    rarity: str
    origin_galaxy: str | None
