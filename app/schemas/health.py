from enum import StrEnum

from pydantic import BaseModel


class HealthStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


class ComponentStatus(StrEnum):
    OK = "ok"
    DOWN = "down"


class HealthResponse(BaseModel):
    status: HealthStatus
    database: ComponentStatus
    redis: ComponentStatus
