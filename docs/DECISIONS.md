metadata={"hnsw:space": "cosine"} -> hnsw: algoritmo para criacao de indice (permite buscas mais rápidas)
cosine -> define a similaridade de cossenos como método de busca (padrao L2, adaptado para embbedingsOpenAI)

## Trade-off: Orquestrador Determinístico vs LLM
   
   **Decisão:** LLM-based orchestrator
   
   **Justificativa:**
   - Queries do negócio são complexas (ex: "compare crescimento YoY")
   - Regras determinísticas falhariam em ~40% dos casos de teste
   - Custo aceitável (~$1/mês) vs ganho em accuracy
   
   **Alternativa considerada:** Hybrid router com fallback para LLM
   - Economizaria ~60% do custo de roteamento
   - Perderia rastreabilidade uniforme
   - Implementaria em produção após análise de queries reais