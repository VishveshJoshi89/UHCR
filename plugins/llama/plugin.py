import json
import urllib.request

from .base import BaseLlamaPlugin
from .config import (
    ENDPOINT,
    TEMPERATURE,
    MAX_TOKENS
)


class LlamaCppPlugin(BaseLlamaPlugin):

    def __init__(
        self,
        endpoint=ENDPOINT
    ):
        self.endpoint = endpoint

    def generate(
        self,
        prompt: str
    ) -> str:

        payload = {
            "prompt": prompt,
            "n_predict": MAX_TOKENS,
            "temperature": TEMPERATURE
        }

        data = json.dumps(
            payload
        ).encode("utf-8")

        request = urllib.request.Request(
            self.endpoint,
            data=data,
            headers={
                "Content-Type":
                "application/json"
            }
        )

        with urllib.request.urlopen(
            request,
            timeout=120
        ) as response:

            result = json.loads(
                response.read().decode(
                    "utf-8"
                )
            )

        return result["content"]