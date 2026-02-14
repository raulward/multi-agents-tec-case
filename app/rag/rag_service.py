"""Servico de acesso ao RAG para consulta e indexacao.

Centraliza a execucao de buscas, aplicacao de filtros, fallback sem filtro e
normalizacao do formato de documentos retornados para o workflow.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.rag.rag_processor import RAGProcessor
from app.schemas.domain import Document


class RagService:
    """Encapsula operacoes de recuperacao e escrita no mecanismo RAG.

    A classe oferece uma interface unica para buscar documentos, deduplicar
    resultados e inserir chunks no indice vetorial.
    """

    def __init__(self, rag_processor: RAGProcessor):
        """Resumo:
            Inicializa o servico com a implementacao concreta de processamento RAG.

        Args:
            rag_processor (RAGProcessor): Processador responsavel por consultas e indexacao.

        Returns:
            None: Nao retorna valor.
        """
        self.rag = rag_processor

    def query(self, query_text: str, n_results: int = 3, where: Optional[Dict[str, Any]] = None):
        """Resumo:
            Executa uma consulta direta no processador RAG subjacente.

        Args:
            query_text (str): Texto de busca a ser consultado.
            n_results (int): Quantidade maxima de resultados retornados.
            where (Optional[Dict[str, Any]]): Filtros opcionais de metadados.

        Returns:
            Any: Resposta bruta retornada pelo processador RAG.
        """
        return self.rag.query(query_text=query_text, n_results=n_results, where=where)

    def retrieve(self, search_queries: List[dict], user_query: str) -> Tuple[List[dict], Dict[str, Any]]:
        """Resumo:
            Recupera documentos com estrategia primaria filtrada e um fallback sem filtro.

            Para cada consulta valida, executa a busca primaria com `where` quando
            houver filtros de empresa/tipo. Se a busca primaria filtrada nao retornar
            documentos, executa exatamente um fallback da mesma consulta com
            `where=None`. Cada documento retornado segue o formato
            `{\"content\": str, \"metadata\": dict}`.

        Args:
            search_queries (List[dict]): Consultas planejadas com campo `query` e filtros opcionais.
            user_query (str): Pergunta original usada quando nao houver consultas planejadas.

        Returns:
            Tuple[List[dict], Dict[str, Any]]: Lista deduplicada de documentos e metadados
            de recuperacao (`retrieved_count`, `queries_executed`, `fallback_used`).
        """
        queries = [q for q in (search_queries or []) if (q.get("query") or "").strip()]
        if not queries and (user_query or "").strip():
            queries = [{"query": user_query}]

        all_docs: List[dict] = []
        queries_executed = 0
        fallback_used = False

        for query in queries:
            query_text = (query.get("query") or "").strip()
            if not query_text:
                continue

            where_clause = self._build_where_clause(query)
            docs_primary = self._run_query(query_text=query_text, n_results=4, where=where_clause)
            queries_executed += 1
            all_docs.extend(docs_primary)

            if docs_primary or where_clause is None:
                continue

            docs_no_filter = self._run_query(query_text=query_text, n_results=4, where=None)
            queries_executed += 1
            all_docs.extend(docs_no_filter)
            fallback_used = True

        all_docs = self._dedup_docs(all_docs)
        meta = {
            "retrieved_count": len(all_docs),
            "queries_executed": queries_executed,
            "fallback_used": fallback_used,
        }
        return all_docs, meta

    def upsert(self, chunks) -> None:
        """Resumo:
            Insere ou atualiza chunks no indice vetorial.

        Args:
            chunks (Any): Colecao de chunks a serem persistidos.

        Returns:
            None: Nao retorna valor.
        """
        self.rag.upsert(chunks)

    def index_document(self, document: Document) -> None:
        """Resumo:
            Indexa um documento completo por meio dos seus chunks.

        Args:
            document (Document): Documento contendo os chunks ja preparados.

        Returns:
            None: Nao retorna valor.
        """
        self.upsert(document.chunks)

    def add_document(self, document: Document) -> None:
        """Resumo:
            Alias de conveniencia para indexacao de documento no RAG.

        Args:
            document (Document): Documento a ser adicionado ao indice.

        Returns:
            None: Nao retorna valor.
        """
        self.index_document(document)

    def list_distinct_company_names(self, limit: int = 5000) -> list[str]:
        """Resumo:
            Lista nomes distintos de empresas presentes nos metadados do indice.

        Args:
            limit (int): Limite maximo de nomes retornados.

        Returns:
            list[str]: Lista de nomes de empresas distintos.
        """
        return self.rag.list_distinct_company_names(limit=limit)

    def count_chunks(self) -> int:
        """Resumo:
            Conta o total de chunks armazenados na colecao vetorial.

        Args:
            None.

        Returns:
            int: Quantidade total de chunks indexados.
        """
        return self.rag.collection.count()

    def _build_where_clause(self, query: dict) -> Optional[Dict[str, Any]]:
        """Resumo:
            Monta o filtro de metadados a partir da consulta planejada.

        Args:
            query (dict): Consulta com filtros opcionais de empresa e tipo documental.

        Returns:
            Optional[Dict[str, Any]]: Clausula `where` normalizada ou `None` sem filtros.
        """
        where_clause: Dict[str, Any] = {}
        query_company = (query.get("filter_company") or "").strip()
        query_doc = query.get("filter_doc_type")

        if query_company:
            where_clause["company_name"] = query_company.lower()
        if query_doc:
            where_clause["document_type"] = query_doc

        return where_clause if where_clause else None

    def _run_query(self, query_text: str, n_results: int, where: Optional[Dict[str, Any]]) -> List[dict]:
        """Resumo:
            Executa consulta e converte a resposta bruta no formato de documentos.

        Args:
            query_text (str): Texto da consulta.
            n_results (int): Quantidade maxima de resultados.
            where (Optional[Dict[str, Any]]): Filtro de metadados da consulta.

        Returns:
            List[dict]: Lista de documentos no formato padronizado.
        """
        response = self.query(query_text=query_text, n_results=n_results, where=where)
        return self._extract_docs(response)

    def _extract_docs(self, response: Optional[Dict[str, Any]]) -> List[dict]:
        """Resumo:
            Extrai documentos da resposta do RAG no formato esperado pelo workflow.

        Args:
            response (Optional[Dict[str, Any]]): Resposta bruta contendo documentos e metadados.

        Returns:
            List[dict]: Lista de itens com chaves `content` e `metadata`.
        """
        if not response or not response.get("documents"):
            return []

        return [
            {"content": text, "metadata": meta}
            for text, meta in zip(response["documents"][0], response["metadatas"][0])
        ]

    def _dedup_docs(self, docs: List[dict]) -> List[dict]:
        """Resumo:
            Remove duplicatas priorizando `chunk_id` e fallback por origem+conteudo.

        Args:
            docs (List[dict]): Lista de documentos potencialmente duplicados.

        Returns:
            List[dict]: Lista deduplicada preservando a ordem de primeira ocorrencia.
        """
        seen = set()
        out = []
        for d in docs:
            md = d.get("metadata") or {}
            chunk_id = md.get("chunk_id") or d.get("chunk_id")
            content = d.get("content") or d.get("text") or ""
            source = md.get("source") or md.get("filename") or "unknown"

            key = chunk_id or (source, hash(content))
            if key in seen:
                continue
            seen.add(key)
            out.append(d)

        return out
