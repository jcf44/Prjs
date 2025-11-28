from typing import List
import re
import structlog

logger = structlog.get_logger()

class RouterService:
    def __init__(self):
        settings = get_settings()
        # Keywords that suggest complex reasoning or professional writing
        self.complex_keywords = [
            r"analyze", r"compare", r"evaluate", r"design", r"architect",
            r"comprehensive", r"detailed", r"explanation", r"proof of concept",
            r"requirements", r"specification", r"rfp", r"proposal",
            r"code review", r"refactor", r"debug", r"optimize"
        ]
        
        self.doc_brain_model = settings.DOC_BRAIN_MODEL
        self.fast_brain_model = settings.FAST_BRAIN_MODEL

    def route(self, query: str) -> str:
        """
        Determine which model to use based on the query.
        """
        # Check for complex keywords
        for pattern in self.complex_keywords:
            if re.search(pattern, query, re.IGNORECASE):
                logger.info("Routing to Doc Brain", reason="complex_keyword", keyword=pattern)
                return self.doc_brain_model
        
        # Check length (longer queries often need more context)
        if len(query.split()) > 50:
            logger.info("Routing to Doc Brain", reason="query_length")
            return self.doc_brain_model

        logger.info("Routing to Fast Brain", reason="default")
        return self.fast_brain_model

_router_service: RouterService | None = None

def get_router_service():
    global _router_service
    if _router_service is None:
        _router_service = RouterService()
    return _router_service
