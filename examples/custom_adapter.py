"""Minimal local adapter contract. Implement inference before using it on the benchmark."""
from decisionrobust.models.base import Adapter, Prediction, UnsupportedInput


class YourAdapter(Adapter):
    def __init__(self, config):
        self.config = config
        # Initialize your pinned model here; do not load GT into the model.

    def predict(self, request, images):
        # request contains the full state and every question, including unscored ones.
        # images contains unchanged file bytes, in the original image order.
        # Return Prediction(answers={qid: {"choice": native_label}, ...}).
        # Do not truncate unsupported inputs or synthesize answers to hide failures.
        raise UnsupportedInput('Implement the model-specific inference path first')
