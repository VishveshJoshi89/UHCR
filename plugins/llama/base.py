from abc import ABC, abstractmethod


class BaseLlamaPlugin(ABC):

    @abstractmethod
    def generate(self, prompt: str) -> str:
        pass