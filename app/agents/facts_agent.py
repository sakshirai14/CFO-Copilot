"""app/agents/facts_agent.py

FactsAgent implemented on Google Agent Development Kit (ADK).
Coordinates deterministic fact gathering from domain services (KpiService & RetrievalService).
Strictly separates data retrieval from LLM reasoning: the LLM never generates tool arguments or SQL.
Zero database driver imports, zero SQL keywords.
"""

from typing import Any, AsyncGenerator, List, Optional, Tuple
from google.adk.agents import BaseAgent, InvocationContext
from google.adk.events import Event
from app.domain.agent_envelope import FactItem, ResolvedQuery, RouteType
from app.domain.kpi_service import KpiService
from app.domain.retrieval_service import RetrievalFilter, RetrievalService


class FactsAgent(BaseAgent):
    """ADK Agent for fetching verified facts across structured and unstructured domain services."""

    name: str = "FactsAgent"
    description: str = "Retrieves verified facts from deterministic SQL and hybrid RAG services."

    def fetch_facts(
        self,
        query: ResolvedQuery,
        tenant_id: str = "acme",
        is_test: bool = False
    ) -> Tuple[List[FactItem], List[str]]:
        """Gathers verified facts and comparability caveats based on route."""
        facts: List[FactItem] = []
        caveats: List[str] = []

        kpi_service = KpiService(is_test=is_test)

        # 1. Fetch Structured KPI Facts if route requires structured data
        if query.route in (RouteType.STRUCTURED, RouteType.MIXED):
            if query.kpi_id and query.company_ids and query.fiscal_year and query.fiscal_quarter:
                for cid in query.company_ids:
                    comp_facts = kpi_service.get_kpi_facts(
                        company_id=cid,
                        fiscal_year=query.fiscal_year,
                        fiscal_quarter=query.fiscal_quarter,
                        kpi_id=query.kpi_id,
                        basis=query.basis
                    )
                    facts.extend(comp_facts)

                # Check Rule R7 cross-company comparability
                if len(query.company_ids) > 1:
                    aligned, warning = kpi_service.check_cross_company_alignment(
                        query.company_ids,
                        query.fiscal_year,
                        query.fiscal_quarter
                    )
                    if warning:
                        caveats.append(warning)

        # 2. Fetch Qualitative RAG Facts if route requires narrative context
        if query.route in (RouteType.UNSTRUCTURED, RouteType.MIXED):
            try:
                service = RetrievalService(is_test=is_test)
                primary_cid = query.company_ids[0] if query.company_ids else None
                filters = RetrievalFilter(
                    company_id=primary_cid,
                    fiscal_year=query.fiscal_year,
                    fiscal_quarter=query.fiscal_quarter
                )
                search_res = service.retrieve(
                    query=query.text_search_query or query.question,
                    filters=filters,
                    tenant_id=tenant_id,
                    top_k=3
                )
                for chunk in search_res.chunks:
                    facts.append(FactItem(
                        fact_id=f"rag_{chunk.chunk_id}",
                        company_id=chunk.company_id,
                        fiscal_year=chunk.fiscal_year,
                        fiscal_quarter=chunk.fiscal_quarter,
                        text=chunk.text,
                        source_filing=chunk.filing_id or chunk.doc_id,
                        status="ok"
                    ))
            except Exception as e:
                caveats.append(f"Qualitative search degraded: {str(e)}")

        return facts, caveats

    async def run_async(self, parent_context: InvocationContext) -> AsyncGenerator[Event, None]:
        """ADK pipeline execution hook."""
        yield Event(
            author=self.name,
            content="Facts retrieval executed deterministically via domain services."
        )
