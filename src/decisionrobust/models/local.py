"""Small native-runtime adapters; upstream packages/weights are installed separately."""
from .base import Adapter, Prediction, UnsupportedInput


class JevSDK(Adapter):
    """Historical JEV native SDK transport, with explicit environment credentials."""
    def __init__(self, config):
        import os
        from typesafe_sdk import TypeSafeClient, RetryPolicy
        key = os.environ.get(config.get('api_key_env', 'JEV_API_KEY'))
        if not key:
            raise ValueError('Required JEV credential environment variable is unset')
        self.model_name = config['model']
        self.client = TypeSafeClient(api_key=key, timeout=config.get('timeout', 120),
                                    retry=RetryPolicy(max_retries=0))

    def predict(self, request, images):
        from .base import InferenceError
        if images:
            raise UnsupportedInput('This JEV SDK adapter is text-only')
        body = dict(request, model=self.model_name)
        try:
            raw = self.client.system_one(**body).model_dump(mode='json')
        except Exception as error:
            status = getattr(error, 'status_code', getattr(error, 'status', None))
            code = f'http_{status}' if isinstance(status, int) else 'sdk_error'
            raise InferenceError(code, status == 429 or isinstance(status, int) and status >= 500) from None
        return Prediction(raw['answers'], usage=raw.get('usage', {}), model=raw.get('model'))


class Kev(Adapter):
    def __init__(self, config):
        import torch
        from kev.checkpoint import Checkpoint, LoadOptions
        from kev.api import SystemOneRequest, to_record, to_answers
        self.request_cls, self.to_record, self.to_answers = SystemOneRequest, to_record, to_answers
        self.tokenizer, self.model = Checkpoint(config['checkpoint']).load(
            config.get('device', 'cuda:0'), LoadOptions(dtype=torch.float32,
                backend='torch', fused=False, cuda_graphs=False))
        self.max_tokens = config.get('max_tokens', 8192)

    def predict(self, request, images):
        if images:
            raise UnsupportedInput('This KEV adapter supports text only')
        body = {k: v for k, v in request.items() if k != 'model'}
        record, meta = self.to_record(self.request_cls(**body))
        encoded = self.model.encode(self.tokenizer, record, max_state=self.max_tokens,
                                    max_branch=self.max_tokens, strict=True)
        probs = [v.tolist() for v in self.model.probs(encoded)]
        return Prediction(self.to_answers(probs, meta))


class Bosun(Adapter):
    def __init__(self, config):
        import torch
        from transformers import AutoModelForCausalLM
        if not config.get('trust_remote_code', False):
            raise ValueError('Review the pinned checkpoint code, then explicitly enable trust_remote_code')
        self.model = AutoModelForCausalLM.from_pretrained(
            config['checkpoint'], revision=config['revision'], trust_remote_code=True,
            dtype=torch.bfloat16, device_map=config.get('device', 'cuda:0')).eval()

    def predict(self, request, images):
        if images:
            raise UnsupportedInput('Bosun is text only')
        answers = {}
        for name, q in request['questions'].items():
            kind = q['type']
            if kind == 'noul':
                keys, descriptions = ['true', 'false'], q.get('criteria') or {}
            elif kind == 'score':
                keys = [str(i) for i in range(len(q['criteria']))]
                descriptions = dict(zip(keys, q['criteria']))
            else:
                keys, descriptions = list(q['criteria']), q['criteria']
            if not 2 <= len(keys) <= 255:
                raise UnsupportedInput('Bosun requires 2..255 options')
            raw = self.model.predict(state=request['state'], instructions=q['instructions'],
                candidates=[{'id': k, 'label': k, 'description': descriptions.get(k, k)} for k in keys],
                decision_type=kind, seed=0, row_id=f'sst2:{name}')
            probabilities = dict(zip(keys, map(float, raw['probabilities']), strict=True))
            if kind == 'noul':
                answers[name] = {'noul': probabilities['true']}
            elif kind == 'score':
                answers[name] = {'score': sum(int(k) * v for k, v in probabilities.items()), 'probabilities': probabilities}
            else:
                answers[name] = {'choice': max(probabilities, key=probabilities.get), 'probabilities': probabilities}
        return Prediction(answers)
