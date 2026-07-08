# Read Doc Analytics

Prototipo para revisar propostas de desenvolvimento de projetos de IA em Google Docs privados. O usuario faz login Google, informa a URL do documento e recebe um relatorio com riscos, inconsistencias, lacunas, evidencias e recomendacoes.

## O que a v1 entrega

- Aplicacao web com FastAPI e Jinja.
- Fluxo OAuth Google usando o escopo minimo `documents.readonly`.
- Leitura do Google Docs via `documents.get`, incluindo suporte inicial a documentos com tabs.
- Conversao do conteudo para Markdown.
- Analisador local deterministico para demos e testes sem credenciais GCP.
- Analisador Gemini/RAG pronto para ativar com `ANALYZER_BACKEND=gemini_rag`.
- Relatorio estruturado, com exportacao visual em Markdown e JSON.
- Dockerfile para Cloud Run.
- GitHub Actions com lint e testes.

## Arquitetura

```text
Browser
  -> FastAPI/Jinja
  -> OAuth Google
  -> Google Docs API
  -> Markdown normalizado
  -> RAG Engine temporario
  -> Gemini
  -> Relatorio estruturado
```

No modo local padrao, a etapa RAG/Gemini e substituida por um analisador heuristico. Isso permite validar UI, OAuth, leitura e normalizacao antes de ativar custos e permissoes GCP.

## Configuracao local

1. Crie e ative um ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Instale as dependencias:

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

3. Copie o arquivo de ambiente:

```powershell
Copy-Item .env.example .env
```

4. Configure no Google Cloud Console:

- Google Docs API habilitada.
- OAuth consent screen em modo teste.
- OAuth Client ID do tipo Web application.
- Redirect URI local: `http://localhost:8080/auth/callback`.
- Test users autorizados.

5. Preencha `.env`:

```text
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
SESSION_SECRET=gere-um-valor-longo
```

6. Rode a aplicacao:

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

Acesse `http://localhost:8080`.

## Ativar Gemini/RAG Engine

Para usar o caminho real de analise com RAG Engine:

```text
ANALYZER_BACKEND=gemini_rag
GCP_PROJECT_ID=seu-projeto
GCP_LOCATION=europe-west4
GEMINI_MODEL=gemini-3.5-flash
```

Autenticacao local para GCP:

```powershell
gcloud auth application-default login
gcloud config set project SEU_PROJETO
```

Permissao minima inicial para o usuario/service account que executa a app:

```text
roles/aiplatform.user
```

Em producao, a service account do Cloud Run tambem precisa ler os segredos:

```text
roles/secretmanager.secretAccessor
```

## Variaveis principais

| Variavel | Uso |
| --- | --- |
| `APP_BASE_URL` | URL base usada no callback OAuth. |
| `SESSION_SECRET` | Assina o cookie que aponta para a sessao em memoria. |
| `GOOGLE_CLIENT_ID` | Client ID OAuth do Google. |
| `GOOGLE_CLIENT_SECRET` | Client secret OAuth do Google. |
| `GOOGLE_OAUTH_REDIRECT_URI` | Override opcional do callback OAuth. |
| `ANALYZER_BACKEND` | `local` ou `gemini_rag`. |
| `GCP_PROJECT_ID` | Projeto GCP para RAG/Gemini. |
| `GCP_LOCATION` | Regiao do RAG/Gemini. |
| `MAX_DOCUMENT_BYTES` | Limite em bytes do documento normalizado; padrao: 9 MB. |

## Testes e qualidade

```powershell
ruff check .
pytest
```

## Docker

Build local:

```powershell
docker build -t read-doc-analytics .
docker run --rm -p 8080:8080 --env-file .env read-doc-analytics
```

## Cloud Run

Com secrets ja criados no Secret Manager:

```powershell
gcloud run deploy read-doc-analytics `
  --source . `
  --region europe-west4 `
  --allow-unauthenticated `
  --service-account read-doc-analytics-runtime@PROJECT_ID.iam.gserviceaccount.com `
  --set-env-vars APP_BASE_URL=https://SUA_URL,ANALYZER_BACKEND=gemini_rag,GCP_PROJECT_ID=PROJECT_ID,GCP_LOCATION=europe-west4 `
  --set-secrets GOOGLE_CLIENT_ID=google-client-id:latest,GOOGLE_CLIENT_SECRET=google-client-secret:latest,SESSION_SECRET=session-secret:latest
```

Depois do deploy, adicione a URL final do Cloud Run como redirect URI no OAuth Client.

## Seguranca e limites da v1

- Tokens OAuth ficam apenas na memoria do processo e nao sao gravados no cookie.
- O cookie contem apenas um identificador de sessao assinado.
- Conteudo do documento nao deve ser logado.
- O corpus RAG e temporario e deve ser apagado ao final da analise.
- Em Cloud Run com multiplas instancias, a sessao em memoria pode se perder; para producao, trocar por Redis/Firestore ou cookie criptografado.
- O modo local e apenas uma heuristica de prototipo.

## Documentacao

O plano completo esta em [`docs/plano-desenvolvimento-implementacao.md`](docs/plano-desenvolvimento-implementacao.md).
