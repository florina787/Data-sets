"""Error taxonomy used for retries, telemetry failure classification and API responses."""


class HarnessError(Exception):
    failure_class = "internal_error"
    retryable = False

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.code = code or self.failure_class


class AdmissionRejected(HarnessError):
    failure_class = "admission_rejected"


class LoadShed(HarnessError):
    failure_class = "load_shed"


class PolicyDenied(HarnessError):
    failure_class = "policy_denied"


class ToolNotAllowed(PolicyDenied):
    failure_class = "tool_not_allowlisted"


class ApprovalRequired(PolicyDenied):
    failure_class = "approval_required"


class InvalidToolArguments(HarnessError):
    failure_class = "invalid_tool_arguments"


class BudgetExceeded(HarnessError):
    failure_class = "budget_exceeded"


class ExecutionTimeout(HarnessError):
    failure_class = "timeout"
    retryable = True


class ToolTimeout(HarnessError):
    failure_class = "tool_timeout"
    retryable = True


class UpstreamUnavailable(HarnessError):
    failure_class = "upstream_unavailable"
    retryable = True


class CircuitOpen(HarnessError):
    failure_class = "circuit_open"


class ProviderError(HarnessError):
    failure_class = "provider_error"
    retryable = True


class OutputValidationFailed(HarnessError):
    failure_class = "output_validation_failed"


class Cancelled(HarnessError):
    failure_class = "cancelled"


def classify(exc: BaseException) -> str:
    if isinstance(exc, HarnessError):
        return exc.failure_class
    name = exc.__class__.__name__
    if "Unavailable" in name:
        return "upstream_unavailable"
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, (KeyError, ValueError)):
        return "data_error"
    return "internal_error"
