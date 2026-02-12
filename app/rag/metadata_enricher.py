from langchain_openai import ChatOpenAI
import json
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage
from app.core.config import settings

from app.ai.structured_output.metadata import DocMetadata
from app.ai.prompts.metadata_enricher.system_prompt import SYSTEM_PROMPT
from app.ai.prompts.metadata_enricher.human_prompt import HUMAN_PROMPT

from typing import List

class MetadataEnricher:
    
    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0):
        self.model = model
        self.temperature = temperature
        self.client = ChatOpenAI(model=self.model, temperature=self.temperature, api_key=settings.OPENAI_API_KEY)

    def __get_messages(self, content: str) -> List[AnyMessage]:

        new_system_prompt = SYSTEM_PROMPT
        new_human_prompt = HUMAN_PROMPT.replace("{content}", content)
        return [
            SystemMessage(content = new_system_prompt),
            HumanMessage(content = new_human_prompt)
        ]

    def enrich(self, content: str) -> DocMetadata:
        model_structured = self.client.with_structured_output(DocMetadata)

        return model_structured.invoke(self.__get_messages(content))
