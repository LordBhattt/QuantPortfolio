import uuid
from dataclasses import dataclass


@dataclass(slots=True)
class CurrentUser:
    id: uuid.UUID
    email: str
    full_name: str | None
    is_active: bool
