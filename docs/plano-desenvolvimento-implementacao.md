# Plano de Desenvolvimento e Implementacao

Documento atualizado em: 2026-07-07

## 1. Objetivo do Projeto

O objetivo deste projeto e criar um prototipo de aplicacao web para revisar propostas de desenvolvimento de projetos de IA armazenadas em Google Docs. O usuario acessa a aplicacao, faz login com a propria conta Google, cola a URL de um documento privado e recebe um relatorio com inconsistencias, lacunas, riscos e recomendacoes.

A aplicacao deve ajudar a responder perguntas como:

- A proposta deixa claro qual problema de negocio sera resolvido?
- O escopo esta consistente com prazo, entregaveis e premissas?
- Os dados necessarios existem, estao acessiveis e podem ser usados legalmente?
- A solucao proposta tem riscos tecnicos, operacionais, financeiros ou de seguranca?
- Existem lacunas importantes antes de aprovar o desenvolvimento?

O resultado esperado e um relatorio estruturado com:

- Resumo executivo.
- Lista de riscos por severidade.
- Inconsistencias encontradas.
- Lacunas de informacao.
- Evidencias extraidas do proprio documento.
- Recomendacoes praticas para ajustar a proposta.

Este prototipo nao substitui revisao juridica, financeira, de seguranca ou de arquitetura feita por especialistas. Ele serve como apoio tecnico inicial para melhorar a qualidade das propostas antes de iniciar o desenvolvimento.

## 2. Escopo Inicial do MVP

O MVP analisara apenas documentos do Google Docs autorizados pelo usuario via login Google.

Incluido no MVP:

- Login Google via OAuth 2.0.
- Campo para colar URL do Google Docs.
- Leitura do conteudo textual do documento.
- Normalizacao do documento para texto ou Markdown.
- Indexacao temporaria no RAG Engine do GCP.
- Analise com Gemini baseada em evidencias recuperadas do documento.
- Relatorio web e exportavel em Markdown ou JSON.
- Preparacao do projeto para GitHub e Cloud Run.

Fora do MVP:

- PDFs, Google Sheets, Google Slides e arquivos DOCX.
- Comentarios, sugestoes, historico de revisao e imagens dentro do documento.
- Multiusuario avancado, painel administrativo e armazenamento historico de analises.
- Integracao direta com Jira, Slack, SharePoint ou outros repositorios.
- Parecer juridico, financeiro ou auditoria formal.

Essa delimitacao deixa o prototipo simples o suficiente para validar valor rapidamente, mas com fundamentos corretos de seguranca, permissao minima e arquitetura pronta para evoluir.

## 3. Arquitetura Proposta

A arquitetura inicial sera composta por cinco blocos principais:

1. Interface web
2. Backend da aplicacao
3. Google Docs API
4. Vertex/Gemini Enterprise RAG Engine
5. Modelo Gemini para analise

### 3.1 Interface Web

A interface pode ser construida de forma simples com FastAPI e templates Jinja. A tela inicial deve conter:

- Botao de login Google.
- Campo para colar URL do Google Docs.
- Botao para iniciar a analise.
- Area de status: lendo documento, preparando contexto, analisando, finalizado.
- Tela de resultado com riscos, inconsistencias e recomendacoes.

Por que fazer assim:

- Evita complexidade desnecessaria de frontend no prototipo.
- Permite deploy simples no Cloud Run.
- Deixa o foco no fluxo de analise e nas permissoes.
- Facilita evoluir depois para React, Next.js ou outro frontend se o prototipo validar.

### 3.2 Backend FastAPI

O backend sera responsavel por:

- Gerenciar sessoes e fluxo OAuth.
- Receber a URL do Google Docs.
- Extrair o `documentId`.
- Chamar a Google Docs API.
- Converter o documento em texto estruturado.
- Enviar esse texto ao RAG Engine.
- Solicitar ao Gemini uma analise baseada no contexto recuperado.
- Validar a resposta em formato estruturado.
- Renderizar ou retornar o relatorio.

Por que FastAPI:

- E leve e adequado para APIs e aplicacoes web pequenas.
- Tem boa compatibilidade com Python SDKs do Google Cloud.
- Facilita validacao com Pydantic.
- Funciona bem em container e Cloud Run.

### 3.3 Google Docs API

A Google Docs API sera usada para buscar a versao atual do documento por meio do metodo `documents.get`.

Fluxo esperado:

1. O usuario cola uma URL como `https://docs.google.com/document/d/DOCUMENT_ID/edit`.
2. A aplicacao extrai o `DOCUMENT_ID`.
3. A aplicacao chama `GET https://docs.googleapis.com/v1/documents/{documentId}`.
4. A resposta da API e convertida para texto estruturado.

Permissao minima do usuario:

```text
https://www.googleapis.com/auth/documents.readonly
```

Por que esse escopo:

- A aplicacao so precisa ler documentos autorizados pelo usuario.
- Nao precisa editar, criar ou deletar documentos.
- E mais restrito do que `drive.readonly`, que permitiria ler arquivos do Drive de forma mais ampla.

Fonte oficial: [Google Docs API - documents.get](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/get)

### 3.4 RAG Engine do GCP

O RAG Engine sera usado para transformar o texto do documento em uma base temporaria consultavel semanticamente. RAG significa Retrieval-Augmented Generation: antes de pedir uma resposta ao modelo, o sistema recupera trechos relevantes do documento e usa esses trechos como contexto.

Fluxo proposto:

1. Criar um corpus temporario para a analise.
2. Fazer upload do texto normalizado do documento.
3. Configurar chunking para dividir o texto em partes recuperaveis.
4. Executar consultas tematicas, por exemplo:
   - "riscos de escopo"
   - "criterios de aceite"
   - "dados necessarios"
   - "seguranca e privacidade"
   - "custos e operacao"
5. Enviar os trechos recuperados ao Gemini.
6. Apagar o corpus temporario ao final.

Por que usar RAG:

- Reduz risco de o modelo inventar pontos que nao estao no documento.
- Permite analisar documentos maiores de forma mais controlada.
- Ajuda a citar evidencias textuais no relatorio.
- Cria uma base tecnica para evoluir o produto para multiplos documentos no futuro.

Limites importantes:

- Upload local no RAG Engine e indicado para arquivo unico de ate 25 MB.
- O parser padrao suporta Markdown e texto ate 10 MB.
- Google Docs exportado pelo Workspace tem limite indicado de 10 MB no parser padrao.
- Algumas regioes do RAG Engine nos EUA podem exigir allowlist em projetos novos; por isso, para prototipo, uma regiao como `europe-west4` pode ser uma opcao inicial se atender aos requisitos do projeto.

Fontes oficiais:

- [RAG Engine overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/rag-engine/rag-overview)
- [RAG Engine data ingestion](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/rag-engine/use-data-ingestion)
- [RAG Engine supported documents](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/rag-engine/supported-documents)

### 3.5 Gemini para Analise

O Gemini sera usado para produzir a analise final. O prompt deve exigir saida estruturada e evidencias.

Cada achado deve conter:

- `titulo`
- `categoria`
- `severidade`: critica, alta, media, baixa ou informativa
- `tipo`: risco, inconsistencia, lacuna ou recomendacao
- `evidencia`: trecho ou referencia textual do documento
- `explicacao`: por que aquilo importa
- `recomendacao`: como corrigir ou mitigar
- `confianca`: alta, media ou baixa

Regra essencial:

Nenhum risco deve ser apresentado como fato sem evidencia textual. Se a informacao nao estiver no documento, o item deve ser marcado como lacuna, por exemplo: "A proposta nao informa a base de dados que sera usada".

Por que impor essa regra:

- Melhora a confiabilidade do relatorio.
- Evita que a IA critique a proposta com base em suposicoes.
- Facilita que o usuario corrija o documento.
- Cria rastreabilidade para revisoes futuras.

## 4. Fluxo de Uso

### Passo 1: Usuario acessa a aplicacao

O usuario abre a URL do app, inicialmente em ambiente local ou no Cloud Run.

Por que esta etapa existe:

- Centraliza o acesso em uma interface simples.
- Permite controlar autenticacao e logs.
- Evita que o usuario precise executar scripts manualmente.

### Passo 2: Usuario faz login Google

A aplicacao redireciona o usuario para o fluxo OAuth do Google. O usuario autoriza a leitura dos documentos necessarios.

Permissao solicitada:

```text
https://www.googleapis.com/auth/documents.readonly
```

Por que esta etapa existe:

- O documento e privado e pertence ao usuario ou a organizacao dele.
- A aplicacao nao deve usar credenciais globais para ler documentos privados.
- Cada usuario autoriza explicitamente o acesso.

### Passo 3: Usuario informa a URL do Google Docs

A aplicacao recebe a URL e extrai o ID do documento.

Exemplos de URLs aceitas:

```text
https://docs.google.com/document/d/DOCUMENT_ID/edit
https://docs.google.com/document/d/DOCUMENT_ID/view
```

Erros tratados:

- URL fora do padrao esperado.
- URL sem `documentId`.
- URL de outro produto, como Sheets ou Slides.

### Passo 4: Aplicacao le o documento

O backend chama a Google Docs API e recebe o documento em formato estruturado.

Erros tratados:

- Usuario nao tem permissao.
- Token expirado.
- Documento vazio.
- Documento grande demais.
- Documento com formato inesperado.

### Passo 5: Aplicacao normaliza o conteudo

O conteudo do Google Docs sera convertido para texto ou Markdown, preservando:

- Titulos.
- Paragrafos.
- Listas.
- Tabelas simples.
- Ordem das secoes.

Por que normalizar:

- A resposta da Google Docs API e rica e complexa.
- O RAG e o LLM funcionam melhor com texto claro.
- A analise precisa se referir a secoes e trechos de forma legivel.

### Passo 6: Aplicacao cria corpus temporario no RAG

O documento normalizado sera enviado ao RAG Engine em um corpus temporario.

Por que temporario:

- Reduz retencao de informacao sensivel.
- Evita misturar documentos de usuarios diferentes.
- Facilita exclusao ao final da analise.
- Diminui risco de privacidade no prototipo.

### Passo 7: Aplicacao executa a analise

O sistema recupera trechos relevantes do RAG e envia ao Gemini com uma matriz de revisao.

Categorias analisadas:

- Objetivo de negocio.
- Escopo.
- Premissas.
- Entregaveis.
- Cronograma.
- Dados.
- Modelo de IA.
- Avaliacao e metricas.
- Seguranca.
- Privacidade e LGPD.
- Integracoes.
- Operacao e suporte.
- Custos.
- Criterios de aceite.

### Passo 8: Aplicacao exibe o relatorio

O relatorio deve mostrar primeiro os pontos mais graves.

Formato recomendado:

1. Resumo executivo.
2. Riscos criticos e altos.
3. Inconsistencias.
4. Lacunas de informacao.
5. Recomendacoes.
6. Evidencias utilizadas.
7. Avisos e limitacoes.

### Passo 9: Aplicacao remove o corpus temporario

Ao final, o corpus temporario deve ser apagado.

Por que fazer isso:

- Minimiza retencao de dados.
- Reduz risco de vazamento.
- Ajuda a controlar custos.
- Mantem o MVP simples.

## 5. Etapas de Implementacao

### Etapa 1: Criar o repositorio Git e publicar no GitHub

Atividades:

- Inicializar o repositorio Git local.
- Criar `.gitignore`.
- Criar `README.md`.
- Criar estrutura inicial do projeto.
- Publicar no GitHub como repositorio privado.

Por que fazer:

- Permite versionar decisoes e evolucao do projeto.
- Habilita CI/CD depois.
- Facilita deploy no Cloud Run e colaboracao.

Permissoes necessarias:

- Permissao de escrita no repositorio GitHub.
- Se for criar repositorio via CLI, permissao GitHub para criar repositorios.

### Etapa 2: Criar a base FastAPI

Atividades:

- Criar aplicacao FastAPI.
- Criar rotas basicas:
  - `GET /`
  - `GET /auth/login`
  - `GET /auth/callback`
  - `POST /analyze`
  - `GET /health`
- Criar templates HTML simples.
- Criar testes unitarios iniciais.

Por que fazer:

- Estabelece a espinha dorsal do prototipo.
- Permite testar localmente antes de integrar APIs externas.
- O endpoint `/health` sera util no Cloud Run.

Permissoes necessarias:

- Nenhuma permissao GCP nesta etapa.

### Etapa 3: Configurar OAuth Google

Atividades:

- Criar OAuth consent screen.
- Definir app em modo teste inicialmente.
- Adicionar test users.
- Criar OAuth Client ID para aplicacao web.
- Configurar redirect URI local e depois redirect URI do Cloud Run.
- Armazenar `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` e `SESSION_SECRET`.

Por que fazer:

- O acesso aos Docs privados depende de autorizacao do usuario.
- O usuario deve saber claramente qual permissao esta concedendo.
- O fluxo evita uso de credenciais compartilhadas para ler documentos privados.

Permissoes necessarias:

- Acesso ao Google Cloud Console do projeto.
- Permissao para configurar OAuth consent screen.
- Escopo de usuario: `documents.readonly`.

Boas praticas:

- Solicitar apenas escopos necessarios.
- Manter o app em modo teste ate validar o MVP.
- Nao solicitar `drive.readonly` no MVP.
- Nao salvar refresh token se nao houver necessidade real.

Fonte oficial: [OAuth consent screen and scopes](https://developers.google.com/workspace/guides/configure-oauth-consent)

### Etapa 4: Implementar leitura do Google Docs

Atividades:

- Validar URL recebida.
- Extrair `documentId`.
- Chamar `documents.get`.
- Tratar erros de permissao, autenticacao e documento inexistente.
- Converter a resposta da API para Markdown/texto.

Por que fazer:

- A analise precisa do conteudo real da proposta.
- O documento deve ser lido com permissao do usuario, nao com acesso administrativo amplo.
- A normalizacao reduz ruido antes do RAG.

Permissoes necessarias:

- Usuario final precisa conceder `documents.readonly`.

Fonte oficial: [Google Docs API - documents.get](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/get)

### Etapa 5: Integrar com RAG Engine

Atividades:

- Configurar projeto, regiao e cliente do Agent Platform/RAG.
- Criar corpus temporario por analise.
- Fazer upload do texto normalizado.
- Configurar chunk size e overlap.
- Recuperar contexto por tema de analise.
- Apagar corpus ao final, inclusive em caso de erro.

Por que fazer:

- O RAG melhora a fundamentacao da resposta.
- O corpus temporario evita mistura de documentos.
- A recuperacao por tema ajuda a cobrir a proposta de forma mais consistente.

Permissoes necessarias:

- Runtime da aplicacao: `roles/aiplatform.user` no prototipo.
- Em producao, avaliar custom role com apenas permissoes necessarias para criar, consultar, fazer upload/import e deletar corpora/arquivos RAG.

Observacao importante:

O plano do MVP recomenda nao usar ingestao direta do Google Drive pelo RAG. A aplicacao primeiro le o Google Docs com OAuth do usuario e depois faz upload do texto normalizado. Se no futuro for usada ingestao direta de Google Drive, sera necessario compartilhar a pasta ou arquivo com o Agent Platform RAG Data Service Agent como Viewer, conforme documentacao oficial.

Fontes oficiais:

- [RAG Engine overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/rag-engine/rag-overview)
- [RAG Engine data ingestion](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/rag-engine/use-data-ingestion)

### Etapa 6: Implementar analise com Gemini

Atividades:

- Criar prompt de sistema com regra de evidencia obrigatoria.
- Criar matriz de analise por categoria.
- Solicitar saida JSON.
- Validar JSON com Pydantic.
- Reprocessar ou retornar erro amigavel se o modelo gerar saida invalida.

Por que fazer:

- Saida estruturada facilita UI, exportacao e testes.
- Evidencia obrigatoria reduz alucinacao.
- Validacao impede que relatorios malformados cheguem ao usuario.

Permissoes necessarias:

- Service account da aplicacao com permissao para usar Vertex/Gemini.
- No prototipo, `roles/aiplatform.user` cobre o uso inicial.

### Etapa 7: Criar a UI do relatorio

Atividades:

- Criar tela de resultado.
- Destacar severidades.
- Permitir copiar ou baixar relatorio em Markdown/JSON.
- Mostrar avisos de limitacao.
- Mostrar mensagens amigaveis de erro.

Por que fazer:

- O valor do prototipo esta na clareza do relatorio.
- O usuario precisa entender rapidamente o que corrigir na proposta.
- Markdown/JSON facilita compartilhar ou arquivar a analise.

Permissoes necessarias:

- Nenhuma permissao externa adicional.

### Etapa 8: Preparar container e Cloud Run

Atividades:

- Criar Dockerfile.
- Configurar porta `8080`.
- Criar endpoint `/health`.
- Definir variaveis de ambiente.
- Configurar Secret Manager.
- Deploy inicial no Cloud Run.

Por que fazer:

- Cloud Run e adequado para aplicacoes HTTP stateless.
- O prototipo escala sob demanda.
- O deploy com container facilita reproducibilidade.

Permissoes necessarias para deploy manual:

- `roles/run.sourceDeveloper` no projeto.
- `roles/serviceusage.serviceUsageConsumer` no projeto.
- `roles/iam.serviceAccountUser` na service account do Cloud Run.
- Cloud Build service account com `roles/run.builder`.

Fonte oficial: [Cloud Run deploy from source](https://docs.cloud.google.com/run/docs/deploying-source-code)

### Etapa 9: Configurar segredos no Secret Manager

Segredos previstos:

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `SESSION_SECRET`

Por que fazer:

- Segredos nao devem ficar em GitHub, Dockerfile ou variaveis hardcoded.
- Cloud Run tem integracao nativa com Secret Manager.
- Facilita rotacao de segredos.

Permissoes necessarias:

- Quem configura o servico: `roles/run.admin` e `roles/iam.serviceAccountUser`.
- Service account do Cloud Run: `roles/secretmanager.secretAccessor` nos segredos necessarios.

Fonte oficial: [Cloud Run secrets](https://docs.cloud.google.com/run/docs/configuring/services/secrets)

### Etapa 10: Criar GitHub Actions

Atividades:

- Criar workflow de CI:
  - instalar dependencias
  - rodar lint
  - rodar testes
- Criar workflow de deploy futuro:
  - autenticar no GCP via Workload Identity Federation
  - buildar imagem
  - publicar no Artifact Registry
  - deployar no Cloud Run

Por que fazer:

- Automatiza validacao antes de deploy.
- Reduz erro manual.
- Workload Identity Federation evita salvar chave JSON do GCP no GitHub.

Permissoes GitHub Actions:

```yaml
permissions:
  contents: read
  id-token: write
```

Permissoes GCP para service account de deploy:

- `roles/artifactregistry.writer`
- `roles/run.admin`
- `roles/iam.serviceAccountUser`
- `roles/iam.workloadIdentityUser` para permitir federacao GitHub -> GCP

Fonte oficial: [Deploy to Cloud Run with GitHub Actions](https://cloud.google.com/blog/products/devops-sre/deploy-to-cloud-run-with-github-actions)

## 6. Permissoes Minimas por Feature

| Feature | Quem usa | Permissao minima | Motivo |
| --- | --- | --- | --- |
| Login Google e leitura do Doc | Usuario final | `https://www.googleapis.com/auth/documents.readonly` | Ler apenas Google Docs autorizados, sem editar. |
| OAuth consent screen | Administrador do projeto | Permissao para configurar Google Auth Platform | Registrar app, audiencia, test users e escopos. |
| Docs API | Aplicacao em nome do usuario | Token OAuth com `documents.readonly` | Chamar `documents.get` no documento informado. |
| RAG Engine | Service account do Cloud Run | `roles/aiplatform.user` no MVP | Criar corpus temporario, enviar arquivo, consultar contexto e apagar. |
| Gemini/Vertex AI | Service account do Cloud Run | `roles/aiplatform.user` no MVP | Executar analise com modelo Gemini. |
| Secret Manager | Service account do Cloud Run | `roles/secretmanager.secretAccessor` | Ler client secret e session secret no runtime. |
| Cloud Run runtime | Cloud Run | Service account dedicada | Separar permissoes da aplicacao das permissoes de deploy. |
| Deploy manual | Desenvolvedor/deployer | `roles/run.sourceDeveloper`, `roles/serviceusage.serviceUsageConsumer`, `roles/iam.serviceAccountUser` | Build e deploy a partir do codigo-fonte. |
| Cloud Build | Service account de build | `roles/run.builder` | Permitir build/deploy do servico. |
| GitHub Actions CI | GitHub runner | `contents: read` | Baixar codigo e rodar testes. |
| GitHub Actions deploy | GitHub runner + WIF | `id-token: write`, `contents: read` | Autenticar no GCP sem chave JSON. |
| Artifact Registry | Service account de deploy | `roles/artifactregistry.writer` | Publicar imagem do container. |

## 7. Metodologias e Boas Praticas

### 7.1 Principio do menor privilegio

A aplicacao deve pedir apenas as permissoes que realmente precisa. Para o MVP, isso significa usar `documents.readonly`, nao `drive.readonly` nem `drive`.

Por que:

- Reduz impacto em caso de falha.
- Aumenta confianca do usuario.
- Pode reduzir complexidade de revisao do app.

### 7.2 Evidencia antes da conclusao

Cada risco ou inconsistencia deve apontar uma evidencia do documento. Se nao houver evidencia, o sistema deve classificar como lacuna.

Por que:

- Ajuda o usuario a corrigir a proposta.
- Evita interpretacoes sem base.
- Torna o relatorio auditavel.

### 7.3 Corpus temporario por analise

Cada documento deve gerar um corpus temporario, apagado ao final.

Por que:

- Reduz retencao de dados sensiveis.
- Evita mistura de documentos.
- Facilita isolamento por usuario e por analise.

### 7.4 Nao registrar conteudo sensivel em logs

Logs devem conter apenas:

- ID tecnico da requisicao.
- Status da etapa.
- Tempo de processamento.
- Codigos de erro.

Logs nao devem conter:

- Conteudo do documento.
- Tokens OAuth.
- Prompts completos.
- Respostas completas do modelo quando tiverem trechos sensiveis.

Por que:

- Logs costumam ter retencao maior.
- Logs podem ser acessados por mais pessoas.
- Conteudo de proposta pode conter dados confidenciais.

### 7.5 Saida estruturada e validada

A resposta do modelo deve ser validada antes de ser exibida.

Por que:

- Garante consistencia da UI.
- Evita quebrar exportacoes.
- Permite testes automatizados.

## 8. Riscos do Projeto

### 8.1 Risco de alucinacao da IA

Mesmo com RAG, o modelo pode interpretar mal ou exagerar uma conclusao.

Mitigacao:

- Exigir evidencia textual.
- Separar risco confirmado de lacuna.
- Exibir nivel de confianca.
- Permitir revisao humana.

### 8.2 Risco de vazamento de dados sensiveis

Propostas podem conter informacoes confidenciais, dados pessoais ou estrategia de negocio.

Mitigacao:

- Nao persistir documento no MVP.
- Usar corpus temporario.
- Evitar logs com conteudo.
- Usar Secret Manager.
- Usar service account dedicada.

### 8.3 Risco de permissao excessiva

Usar escopos amplos como `drive.readonly` aumenta o risco desnecessariamente.

Mitigacao:

- Usar `documents.readonly`.
- Revisar escopos antes de publicar o app.
- Manter consent screen claro.

### 8.4 Risco de custo

RAG Engine, Gemini, Cloud Run, Artifact Registry e logs podem gerar custos.

Mitigacao:

- Definir limite de tamanho de documento.
- Apagar corpus temporario.
- Definir max instances no Cloud Run.
- Monitorar uso de tokens.
- Criar alertas de budget no GCP.

### 8.5 Risco regional

Nem todas as regioes tem a mesma disponibilidade para RAG Engine. Algumas regioes podem exigir allowlist em novos projetos.

Mitigacao:

- Comecar com regiao suportada e sem allowlist quando possivel.
- Registrar a regiao escolhida no README e nas variaveis de ambiente.
- Validar requisitos de residencia de dados antes de producao.

### 8.6 Risco de OAuth em modo teste

Enquanto o app estiver em teste, apenas usuarios adicionados como test users conseguirao autorizar.

Mitigacao:

- Manter lista de test users.
- Documentar o processo de autorizacao.
- Planejar verificacao do app se for usado por publico externo.

## 9. Criterios de Aceite

O prototipo sera considerado pronto para primeira validacao quando:

- O usuario conseguir autenticar com Google.
- A aplicacao conseguir ler um Google Docs privado autorizado.
- Uma URL invalida retornar erro claro.
- Um documento sem permissao retornar erro claro.
- Um documento vazio retornar erro claro.
- Um documento grande demais retornar erro claro.
- O texto do documento for normalizado preservando a ordem das secoes.
- A analise gerar relatorio com severidade, categoria, evidencia e recomendacao.
- Todo achado tiver evidencia ou estiver classificado como lacuna.
- O corpus temporario for apagado ao final da analise.
- Segredos nao estiverem no repositorio.
- O app rodar localmente.
- O app estiver preparado para container e Cloud Run.
- CI no GitHub rodar testes automaticamente.

## 10. Estrutura Recomendada do Repositorio

Estrutura inicial sugerida:

```text
.
├── app/
│   ├── main.py
│   ├── config.py
│   ├── auth/
│   ├── docs_reader/
│   ├── rag/
│   ├── analysis/
│   ├── templates/
│   └── static/
├── tests/
├── docs/
│   └── plano-desenvolvimento-implementacao.md
├── .github/
│   └── workflows/
├── Dockerfile
├── README.md
├── pyproject.toml
├── .env.example
└── .gitignore
```

Essa estrutura separa responsabilidades e permite evoluir sem transformar o prototipo em um arquivo unico dificil de manter.

## 11. Variaveis de Ambiente Previstas

```text
APP_ENV=local
APP_BASE_URL=http://localhost:8080
SESSION_SECRET=change-me

GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8080/auth/callback

GCP_PROJECT_ID=...
GCP_LOCATION=europe-west4
RAG_CORPUS_PREFIX=proposal-review
GEMINI_MODEL=gemini-3.5-flash
```

Observacoes:

- `SESSION_SECRET` e `GOOGLE_CLIENT_SECRET` devem ir para Secret Manager em Cloud Run.
- `GCP_LOCATION` deve ser escolhida conforme disponibilidade do RAG Engine e requisitos de residencia.
- O modelo pode ser ajustado conforme custo, qualidade e disponibilidade.

## 12. Preparacao para Cloud Run

O Cloud Run executara a aplicacao como servico HTTP stateless.

Configuracoes recomendadas para o prototipo:

- Porta: `8080`.
- Service account dedicada, por exemplo `proposal-review-runtime`.
- Max instances baixo no inicio, por exemplo 1 a 3.
- Timeout maior que o padrao se a analise demorar.
- Secrets injetados via Secret Manager.
- Logs sem conteudo do documento.
- Autenticacao da aplicacao obrigatoria, mesmo se o servico Cloud Run estiver publico.

Por que o Cloud Run pode estar publico na camada IAM:

- O login do usuario sera controlado pela aplicacao.
- Facilita callback OAuth.
- Evita complexidade inicial de IAP ou autenticao IAM para usuario final.

Risco:

- Uma URL publica pode receber trafego indesejado.

Mitigacao:

- Rate limiting futuro.
- CSRF protection.
- Validacao de sessao.
- Max instances baixo.
- Cloud Armor/IAP em fases posteriores, se necessario.

Fonte oficial: [Cloud Run service identity](https://docs.cloud.google.com/run/docs/configuring/services/service-identity)

## 13. Roadmap Sugerido

### Fase 1: Documento e desenho tecnico

- Criar este documento.
- Validar arquitetura.
- Validar regioes e permissoes no GCP.

### Fase 2: Prototipo local

- Implementar FastAPI.
- Implementar OAuth.
- Ler Google Docs.
- Gerar relatorio sem RAG inicialmente, se necessario para teste rapido.

### Fase 3: RAG Engine

- Criar corpus temporario.
- Fazer upload do texto.
- Recuperar contextos por categoria.
- Apagar corpus.

### Fase 4: Relatorio estruturado

- Criar prompt final.
- Validar JSON.
- Renderizar UI.
- Exportar Markdown/JSON.

### Fase 5: Cloud Run

- Criar Dockerfile.
- Configurar Secret Manager.
- Deploy manual.
- Validar callback OAuth em URL publica.

### Fase 6: GitHub Actions

- CI com testes.
- Deploy automatizado por ambiente.
- Workload Identity Federation.

### Fase 7: Endurecimento

- Custom role em vez de `roles/aiplatform.user`, se necessario.
- Auditoria de logs.
- Alertas de custo.
- Rate limiting.
- Politica de retencao.
- Verificacao OAuth se o app sair do modo teste.

## 14. Fontes Consultadas

- [Google Docs API - documents.get](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/get)
- [Google Workspace OAuth consent screen and scopes](https://developers.google.com/workspace/guides/configure-oauth-consent)
- [RAG Engine overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/rag-engine/rag-overview)
- [RAG Engine data ingestion](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/rag-engine/use-data-ingestion)
- [RAG Engine supported documents](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/rag-engine/supported-documents)
- [Cloud Run deploy from source](https://docs.cloud.google.com/run/docs/deploying-source-code)
- [Cloud Run service identity](https://docs.cloud.google.com/run/docs/configuring/services/service-identity)
- [Cloud Run secrets](https://docs.cloud.google.com/run/docs/configuring/services/secrets)
- [Deploy to Cloud Run with GitHub Actions](https://cloud.google.com/blog/products/devops-sre/deploy-to-cloud-run-with-github-actions)

## 15. Decisoes Iniciais

- O MVP analisara apenas Google Docs.
- O acesso sera por login Google do usuario.
- O escopo OAuth inicial sera `documents.readonly`.
- O RAG sera usado com corpus temporario por analise.
- O documento nao sera persistido no MVP.
- O projeto sera preparado para GitHub e Cloud Run.
- A linguagem principal sera Python com FastAPI.
- O relatorio exigira evidencia ou classificara o ponto como lacuna.
