import json as std_json
import uuid

from pydantic import BaseModel

import core.json_utils as custom_json


class BenchmarkPayload(BaseModel):
    id: str
    content: list[dict]
    metadata: dict


def generate_payload(size=1000):
    content = [{"role": "user", "text": "hello " * 50, "index": i} for i in range(size)]
    return {
        "id": uuid.uuid4().hex,
        "content": content,
        "metadata": {"model": "gpt-4", "temperature": 0.7},
    }


def test_benchmark_json_dumps(benchmark):
    payload = generate_payload(5000)

    def run_custom():
        custom_json.dumps(payload)

    # We use pytest-benchmark to explicitly track custom_json
    # to show the relative difference in testing outputs if they choose to run it
    benchmark(run_custom)


def test_benchmark_json_loads(benchmark):
    payload = generate_payload(5000)
    raw = std_json.dumps(payload)

    def run_custom():
        custom_json.loads(raw)

    benchmark(run_custom)
