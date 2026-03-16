from pydantic import BaseModel


class BuildEntry(BaseModel):
    id: str
    environment: str  # raid | mythic_plus | delves
    scenario: str  # single | aoe
    hero_talent: str  # any non-empty string (permissive)
    import_code: str
    build_mode: str = ""  # if empty, uses scenario


class SpecBuilds(BaseModel):
    wow_class: str
    wow_spec: str
    wow_role: str = "dps"
    source: str = ""
    builds: list[BuildEntry]


class IngestPayload(BaseModel):
    patch: str = ""
    specs: list[SpecBuilds]


class IngestResult(BaseModel):
    ingested: int
    specs_processed: int
    errors: list[str]
