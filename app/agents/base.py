from abc import ABC, abstractmethod
from typing import Any, Dict
import time


class BaseAgent(ABC):

    def __init__(self, llm_client, name: str):
        self.client = llm_client
        self.name = name

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        #TODO -> Tracing
        pass

    @abstractmethod
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Lógica específica do agente - implementar nas subclasses"""
        pass

