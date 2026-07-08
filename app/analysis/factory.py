from app.analysis.gemini_rag import GeminiRagAnalyzer
from app.analysis.local import LocalHeuristicAnalyzer
from app.config import Settings


def build_analyzer(settings: Settings):
    if settings.analyzer_backend == "gemini_rag":
        return GeminiRagAnalyzer(settings)
    return LocalHeuristicAnalyzer()

