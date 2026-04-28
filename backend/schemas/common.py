from pydantic import BaseModel, ConfigDict


class ErrorResponse(BaseModel):
    error: str
    code: str
    detail: str


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: str
    version: str
