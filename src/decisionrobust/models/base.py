"""Adapter contract: only a complete request is passed, never GT or attack targets."""
from dataclasses import dataclass, field


class UnsupportedInput(Exception):
    pass


class InferenceError(Exception):
    def __init__(self, code='inference_error', retryable=False, retry_after=None):
        self.code = code
        self.retryable = retryable
        self.retry_after = retry_after
        super().__init__(code)


@dataclass
class Prediction:
    answers: dict
    refused: list = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    model: str | None = None


class Adapter:
    # Mutable GPU runtimes must keep this false. The runner rejects unsafe concurrency.
    thread_safe = False

    def predict(self, request, images):
        """images is a list of original bytes in request.images order."""
        raise NotImplementedError
