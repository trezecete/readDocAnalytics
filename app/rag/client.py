from __future__ import annotations

import contextlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from google.auth.exceptions import DefaultCredentialsError

from app.config import Settings
from app.errors import AnalyzerError, ConfigurationError


@dataclass
class RetrievedContext:
    query: str
    text: str


class RagEngineClient:
    def __init__(self, settings: Settings) -> None:
        if not settings.gcp_project_id:
            raise ConfigurationError(
                "GCP_PROJECT_ID e obrigatorio para ANALYZER_BACKEND=gemini_rag.",
                status_code=500,
            )
        self.settings = settings
        self._configure_credentials_env()

    @contextlib.contextmanager
    def temporary_corpus(self):
        corpus_name = self.create_corpus()
        try:
            yield corpus_name
        finally:
            self.delete_corpus(corpus_name)

    def create_corpus(self) -> str:
        try:
            import agentplatform
            from agentplatform import types
        except ImportError:
            return self._create_corpus_with_preview(
                f"{self.settings.rag_corpus_prefix}-{uuid4().hex[:10]}"
            )

        display_name = f"{self.settings.rag_corpus_prefix}-{uuid4().hex[:10]}"
        client = agentplatform.Client(
            project=self.settings.gcp_project_id,
            location=self.settings.gcp_location,
        )

        try:
            embedding_model_config = types.RagEmbeddingModelConfig(
                vertex_prediction_endpoint=types.RagEmbeddingModelConfigVertexPredictionEndpoint(
                    endpoint=self.settings.embedding_model,
                ),
            )
            corpus = client.rag.create_corpus(
                rag_corpus=types.RagCorpus(
                    display_name=display_name,
                    rag_vector_db_config=types.RagVectorDbConfig(
                        rag_embedding_model_config=embedding_model_config,
                    ),
                ),
            )
        except (AttributeError, TypeError):
            return self._create_corpus_with_preview(display_name)
        except Exception as exc:
            _raise_rag_error("criar corpus temporario", self.settings, exc)

        return corpus.name

    def upload_text(self, corpus_name: str, text: str, display_name: str) -> None:
        try:
            import agentplatform
            from agentplatform import types
        except ImportError:
            self._upload_text_with_preview(corpus_name, text, display_name)
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "proposal.md"
            file_path.write_text(text, encoding="utf-8")
            try:
                client = agentplatform.Client(
                    project=self.settings.gcp_project_id,
                    location=self.settings.gcp_location,
                )
                upload_config = types.UploadRagFileConfig(
                    rag_file_transformation_config=types.RagFileTransformationConfig(
                        rag_file_chunking_config=types.RagFileChunkingConfig(
                            chunk_size=self.settings.rag_chunk_size,
                            chunk_overlap=self.settings.rag_chunk_overlap,
                        ),
                    )
                )
                client.rag.upload_file(
                    corpus_name=corpus_name,
                    path=str(file_path),
                    display_name=display_name,
                    upload_rag_file_config=upload_config,
                )
            except (AttributeError, TypeError):
                self._upload_text_with_preview(corpus_name, text, display_name)
            except Exception as exc:
                _raise_rag_error("enviar documento ao RAG Engine", self.settings, exc)

    def retrieve_contexts(self, corpus_name: str, queries: list[str]) -> list[RetrievedContext]:
        try:
            import agentplatform
            from agentplatform import types
            from google.genai import types as genai_types
        except ImportError:
            return self._retrieve_contexts_with_preview(corpus_name, queries)

        client = agentplatform.Client(
            project=self.settings.gcp_project_id,
            location=self.settings.gcp_location,
        )
        rag_retrieval_config = genai_types.RagRetrievalConfig(top_k=self.settings.rag_top_k)
        contexts: list[RetrievedContext] = []
        for query in queries:
            try:
                response = client.rag.retrieve_contexts(
                    vertex_rag_store=genai_types.VertexRagStore(
                        rag_resources=[
                            genai_types.VertexRagStoreRagResource(rag_corpus=corpus_name)
                        ],
                    ),
                    query=types.RagQuery(
                        text=query,
                        rag_retrieval_config=rag_retrieval_config,
                    ),
                )
            except (AttributeError, TypeError):
                return self._retrieve_contexts_with_preview(corpus_name, queries)
            except Exception as exc:
                _raise_rag_error("recuperar contexto do RAG Engine", self.settings, exc)

            extracted = _extract_context_texts(response)
            contexts.extend(RetrievedContext(query=query, text=text) for text in extracted)
        return contexts

    def delete_corpus(self, corpus_name: str) -> None:
        try:
            import agentplatform
        except ImportError:
            self._delete_corpus_with_preview(corpus_name)
            return

        try:
            client = agentplatform.Client(
                project=self.settings.gcp_project_id,
                location=self.settings.gcp_location,
            )
            client.rag.delete_corpus(name=corpus_name)
        except Exception:
            # Cleanup failure should not hide the analysis error path.
            # Production can add alerting here.
            return

    def _create_corpus_with_preview(self, display_name: str) -> str:
        try:
            import vertexai
            from vertexai.preview import rag
        except ImportError as exc:
            raise AnalyzerError("SDK google-cloud-aiplatform nao esta instalado.") from exc

        vertexai.init(project=self.settings.gcp_project_id, location=self.settings.gcp_location)
        try:
            embedding_model_config = rag.RagEmbeddingModelConfig(
                vertex_prediction_endpoint=rag.VertexPredictionEndpoint(
                    publisher_model=self.settings.embedding_model,
                )
            )
            corpus = rag.create_corpus(
                display_name=display_name,
                embedding_model_config=embedding_model_config,
            )
        except TypeError:
            corpus = rag.create_corpus(display_name=display_name)
        except Exception as exc:
            _raise_rag_error("criar corpus temporario", self.settings, exc)
        return corpus.name

    def _delete_corpus_with_preview(self, corpus_name: str) -> None:
        try:
            from vertexai.preview import rag
        except ImportError:
            return

        try:
            rag.delete_corpus(name=corpus_name)
        except TypeError:
            rag.delete_corpus(corpus_name)
        except Exception:
            return

    def _upload_text_with_preview(self, corpus_name: str, text: str, display_name: str) -> None:
        try:
            from vertexai.preview import rag
        except ImportError as exc:
            raise AnalyzerError("SDK google-cloud-aiplatform nao esta instalado.") from exc

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "proposal.md"
            file_path.write_text(text, encoding="utf-8")
            try:
                try:
                    rag.upload_file(
                        corpus_name=corpus_name,
                        path=str(file_path),
                        display_name=display_name,
                        chunk_size=self.settings.rag_chunk_size,
                        chunk_overlap=self.settings.rag_chunk_overlap,
                    )
                except TypeError:
                    rag.upload_file(
                        corpus_name=corpus_name,
                        path=str(file_path),
                        display_name=display_name,
                    )
            except Exception as exc:
                _raise_rag_error("enviar documento ao RAG Engine", self.settings, exc)

    def _retrieve_contexts_with_preview(
        self,
        corpus_name: str,
        queries: list[str],
    ) -> list[RetrievedContext]:
        try:
            from vertexai.preview import rag
        except ImportError as exc:
            raise AnalyzerError("SDK google-cloud-aiplatform nao esta instalado.") from exc

        contexts: list[RetrievedContext] = []
        for query in queries:
            try:
                response = rag.retrieval_query(
                    rag_resources=[rag.RagResource(rag_corpus=corpus_name)],
                    text=query,
                    similarity_top_k=self.settings.rag_top_k,
                )
            except Exception as exc:
                _raise_rag_error("recuperar contexto do RAG Engine", self.settings, exc)
            contexts.extend(
                RetrievedContext(query=query, text=text)
                for text in _extract_context_texts(response)
            )
        return contexts

    def _configure_credentials_env(self) -> None:
        if not self.settings.google_application_credentials:
            return

        credentials_path = Path(self.settings.google_application_credentials).expanduser()
        if not credentials_path.is_absolute():
            credentials_path = Path.cwd() / credentials_path
        credentials_path = credentials_path.resolve()

        if not credentials_path.exists():
            raise ConfigurationError(
                "GOOGLE_APPLICATION_CREDENTIALS aponta para um arquivo inexistente: "
                f"{credentials_path}",
                status_code=500,
            )

        self._validate_credentials_file(credentials_path)

        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(credentials_path)

    def _validate_credentials_file(self, credentials_path: Path) -> None:
        try:
            payload = json.loads(credentials_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigurationError(
                "GOOGLE_APPLICATION_CREDENTIALS precisa apontar para um JSON valido.",
                status_code=500,
            ) from exc

        if isinstance(payload, dict) and ("web" in payload or "installed" in payload):
            raise ConfigurationError(
                "GOOGLE_APPLICATION_CREDENTIALS aponta para um OAuth Client JSON. Esse arquivo "
                "serve para login do usuario no Google Docs, mas nao autentica o backend no GCP. "
                "Use um JSON de service account, um arquivo ADC valido, ou rode "
                "`gcloud auth application-default login`.",
                status_code=500,
            )


def _extract_context_texts(response) -> list[str]:
    candidates: list[str] = []

    contexts = getattr(response, "contexts", None)
    if contexts is not None:
        context_items = getattr(contexts, "contexts", None) or []
        for item in context_items:
            text = getattr(item, "text", None) or getattr(item, "content", None)
            if text:
                candidates.append(str(text))

    if not candidates and isinstance(response, dict):
        for item in response.get("contexts", {}).get("contexts", []):
            text = item.get("text") or item.get("content")
            if text:
                candidates.append(str(text))

    if not candidates:
        candidates.append(str(response))

    return [_compact_text(text) for text in candidates if text.strip()]


def _compact_text(text: str, limit: int = 2500) -> str:
    compact = " ".join(text.split())
    return compact[:limit]


def _raise_rag_error(action: str, settings: Settings, exc: Exception):
    message = str(exc)
    normalized = message.lower()

    if isinstance(exc, DefaultCredentialsError) or "default credentials" in normalized:
        raise AnalyzerError(
            "Credenciais GCP nao encontradas para usar RAG/Gemini. O login Google do usuario "
            "serve apenas para ler o Google Docs; o backend tambem precisa de Application "
            "Default Credentials. Configure com `gcloud auth application-default login` ou "
            "defina `GOOGLE_APPLICATION_CREDENTIALS` apontando para uma service account com "
            "`roles/aiplatform.user`."
        ) from exc

    if isinstance(exc, TimeoutError) or "did not complete within the timeout" in normalized:
        raise AnalyzerError(
            f"A operacao do RAG Engine para {action} excedeu o tempo limite do SDK. "
            "A criacao do primeiro corpus pode demorar alguns minutos; tente novamente e "
            "verifique no console do Vertex AI se ha operacoes pendentes."
        ) from exc

    if "permission" in normalized or "403" in normalized or "unauthorized" in normalized:
        raise AnalyzerError(
            "Sem permissao para usar o RAG Engine neste projeto. Confirme que a credencial GCP "
            f"tem `roles/aiplatform.user` em `{settings.gcp_project_id}` e que as APIs "
            "necessarias estao habilitadas."
        ) from exc

    if "allowlist" in normalized or "not supported" in normalized or "region" in normalized:
        raise AnalyzerError(
            f"Nao foi possivel usar o RAG Engine na regiao `{settings.gcp_location}`. "
            "Algumas regioes dos EUA exigem allowlist para projetos novos; tente "
            "`GCP_LOCATION=europe-west3` ou solicite allowlist no GCP."
        ) from exc

    if "'code': 13" in normalized or "internal" in normalized:
        raise AnalyzerError(
            f"O RAG Engine retornou erro interno na regiao `{settings.gcp_location}` ao "
            f"tentar {action}. A service account pode estar correta, mas o servico regional "
            "falhou. Tente `GCP_LOCATION=europe-west3`; se persistir, verifique operacoes "
            "pendentes no Vertex AI e abra suporte com o operation id exibido nos logs."
        ) from exc

    detail = _safe_error_detail(message)
    raise AnalyzerError(f"Nao foi possivel {action}. Detalhe tecnico: {detail}") from exc


def _safe_error_detail(message: str, limit: int = 500) -> str:
    compact = " ".join(message.split())
    return compact[:limit] if compact else "erro sem detalhe retornado pelo SDK"
