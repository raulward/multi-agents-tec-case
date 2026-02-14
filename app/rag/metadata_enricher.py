"""Enriquecimento de metadados documentais via LLM.

Monta mensagens de sistema/usuario e invoca uma saida estruturada para inferir
empresa, tipo documental e data do documento.
"""

from typing import List, get_args

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.ai.prompts.metadata_enricher.human_prompt import HUMAN_PROMPT
from app.ai.prompts.metadata_enricher.system_prompt import SYSTEM_PROMPT
from app.core.config import settings
from app.schemas.domain import DocMetadata, DocumentType


class MetadataEnricher:
    """Extrai metadados estruturados a partir de conteudo textual.

    A classe encapsula configuracao do modelo e a montagem de prompts para
    retornar um `DocMetadata` validado.
    """

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0):
        """Resumo:
            Inicializa o cliente LLM para enriquecimento de metadados.

        Args:
            model (str): Nome do modelo usado na inferencia.
            temperature (float): Temperatura de amostragem do modelo.

        Returns:
            None: Nao retorna valor.
        """
        self.model = model
        self.temperature = temperature
        self.client = ChatOpenAI(model=self.model, temperature=self.temperature, api_key=settings.OPENAI_API_KEY)

    def __get_messages(self, content: str) -> List[AnyMessage]:
        """Resumo:
            Constroi mensagens de prompt com tipos documentais permitidos.

        Args:
            content (str): Conteudo textual a ser analisado pelo modelo.

        Returns:
            List[AnyMessage]: Sequencia de mensagens de sistema e usuario.
        """
        allowed_doc_types = "\n".join(f"    * {doc_type}" for doc_type in get_args(DocumentType))
        new_system_prompt = SYSTEM_PROMPT.replace("{allowed_doc_types}", allowed_doc_types)
        new_human_prompt = HUMAN_PROMPT.replace("{content}", content)
        return [
            SystemMessage(content=new_system_prompt),
            HumanMessage(content=new_human_prompt)
        ]

    def enrich(self, content: str) -> DocMetadata:
        """Resumo:
            Executa o enriquecimento e retorna metadados estruturados do documento.

        Args:
            content (str): Conteudo textual usado para inferencia de metadados.

        Returns:
            DocMetadata: Metadados extraidos e validados.
        """
        model_structured = self.client.with_structured_output(DocMetadata)

        return model_structured.invoke(self.__get_messages(content))
