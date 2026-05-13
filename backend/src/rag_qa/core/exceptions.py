from __future__ import annotations


class AppException(Exception):
    def __init__(self, message: str, code: str = "APP_ERROR", status_code: int = 500) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found", code: str = "NOT_FOUND") -> None:
        super().__init__(message=message, code=code, status_code=404)


class BadRequestException(AppException):
    def __init__(self, message: str = "Bad request", code: str = "BAD_REQUEST") -> None:
        super().__init__(message=message, code=code, status_code=400)


class UnauthorizedException(AppException):
    def __init__(self, message: str = "Unauthorized", code: str = "UNAUTHORIZED") -> None:
        super().__init__(message=message, code=code, status_code=401)


class ForbiddenException(AppException):
    def __init__(self, message: str = "Forbidden", code: str = "FORBIDDEN") -> None:
        super().__init__(message=message, code=code, status_code=403)


class ConflictException(AppException):
    def __init__(self, message: str = "Resource conflict", code: str = "CONFLICT") -> None:
        super().__init__(message=message, code=code, status_code=409)


class ValidationException(AppException):
    def __init__(self, message: str = "Validation error", code: str = "VALIDATION_ERROR") -> None:
        super().__init__(message=message, code=code, status_code=422)


class ConnectorException(AppException):
    def __init__(self, message: str = "Connector error", code: str = "CONNECTOR_ERROR") -> None:
        super().__init__(message=message, code=code, status_code=502)


class PipelineException(AppException):
    def __init__(self, message: str = "Pipeline processing error", code: str = "PIPELINE_ERROR") -> None:
        super().__init__(message=message, code=code, status_code=500)


class RetrievalException(AppException):
    def __init__(self, message: str = "Retrieval error", code: str = "RETRIEVAL_ERROR") -> None:
        super().__init__(message=message, code=code, status_code=500)


class LLMException(AppException):
    def __init__(self, message: str = "LLM service error", code: str = "LLM_ERROR") -> None:
        super().__init__(message=message, code=code, status_code=502)
