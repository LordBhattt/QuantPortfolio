from dataclasses import dataclass


@dataclass(slots=True)
class AppError(Exception):
    error: str
    code: str
    detail: str
    status_code: int = 400

    def as_payload(self) -> dict[str, str]:
        return {
            "error": self.error,
            "code": self.code,
            "detail": self.detail,
        }
