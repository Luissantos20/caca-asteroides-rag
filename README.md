# 🔭 Assistente de IA — Caça Asteroides MCTI

Assistente conversacional (RAG) que tira dúvidas de participantes do programa de ciência cidadã **Caça Asteroides MCTI** (MCTI · AEB · IASC/NASA) sobre inscrição, campanhas, regras e o software de análise astronômica.

O participante pergunta em linguagem natural; o sistema faz **busca semântica** sobre o conteúdo oficial do programa e responde **ancorado nas fontes**. Quando a informação não está no material, ele **avisa em vez de inventar** — num contexto educacional e científico, isso é requisito, não detalhe.

> **Status:** em produção e em uso real. Apresentado oficialmente no **II Encontro Internacional Caça Asteroides** (auditório do CNPq, Brasília, 2026).
> **Teste ao vivo:** https://caçaasteroides.app

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.121-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-14-000000?logo=next.js&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-vector%20store-FF6B6B)
![OpenAI](https://img.shields.io/badge/OpenAI-embeddings%20%2B%20gpt--4o--mini-412991?logo=openai&logoColor=white)

---

## Como funciona

Antes de responder, o sistema decide se pode responder. Essa decisão passa por duas barreiras: um **limiar de relevância** sobre a busca e um **LLM juiz** que confere se os trechos encontrados respondem mesmo à pergunta. Se qualquer uma falhar, ele não arrisca: encaminha o participante para o e-mail da coordenação.

```mermaid
flowchart LR
    U[Pergunta] --> R[Rewrite<br/>resolve 'isso', 'e como?']
    R --> E[Embedding<br/>text-embedding-3-small]
    E --> C[(ChromaDB<br/>top-5)]
    C --> D{Piso de relevância<br/>cos do topo ≥ 0,40?}
    D -- não --> F[Fallback<br/>e-mail da coordenação]
    D -- sim --> J{LLM juiz<br/>o contexto responde?}
    J -- não --> F
    J -- sim --> G[Geração em streaming<br/>gpt-4o-mini · só os chunks]
    G --> S[SSE token a token]
```

1. **Rewrite da query.** Se há histórico, reescreve a última pergunta para que faça sentido sozinha (*"e como?"* vira *"como faço a inscrição?"*). Sem histórico, usa a pergunta original, sem custo. Se a reescrita falhar, segue com a original.
2. **Retrieval.** Gera o embedding e busca os 5 trechos mais próximos no ChromaDB. A distância vira um **score absoluto de 0 a 1** (similaridade de cosseno, `cos = 1 − d/2`), comparável entre perguntas diferentes.
3. **Piso de relevância** (`decision.py`). Se o melhor trecho tem score < 0,40, a pergunta está fora do escopo e o sistema encaminha para o e-mail. Esse piso barra bem o que não tem nada a ver com o programa.
4. **LLM juiz** (`grader.py`). O piso não pega perguntas que usam as palavras do programa mas não têm resposta no material, como *"asteroide é a mesma coisa que cometa?"*: o score fica alto mesmo assim. O juiz (`gpt-4o-mini`, temperatura 0) lê a pergunta e os 3 melhores trechos, escreve um raciocínio curto e só então dá o veredito (`pode_responder: true/false`). Se for `false`, o sistema encaminha para o e-mail.
5. **Geração em streaming.** Só chega aqui o que passou pelas duas barreiras. O `gpt-4o-mini` responde usando **somente** os trechos recuperados, e a resposta volta token a token via SSE.

### Sistema especialista

As decisões de responder ou encaminhar são **regras SE–ENTÃO** explícitas, e o motor (`pipeline.py`) as aplica por encadeamento para frente. Os modelos de linguagem só fornecem fatos (a relevância da busca e o veredito do juiz); quem decide são as regras. A descrição completa, com fatos, regras e as linhas do código, está em [`REGRAS.md`](REGRAS.md).

---

## Stack

**Backend** · Python 3.11 · FastAPI · ChromaDB · OpenAI (`text-embedding-3-small` + `gpt-4o-mini`) · SlowAPI (rate limit) · Uvicorn
**Frontend** · Next.js 14 (App Router) · TypeScript · Tailwind CSS · streaming SSE
**Infra** · Docker · Railway (backend) · Vercel (frontend)

---

## Estrutura do projeto

```
caca-asteroides-rag/
├── backend/                 # API FastAPI + pipeline RAG
│   ├── api/                 # app, rotas (/chat, /health), middleware, rate limit, logging
│   ├── services/            # pipeline · retrieval · decision · grader · rewrite_query · generate_answer
│   ├── data/                # base de conhecimento (JSON estruturado em chunks)
│   ├── scripts/             # index_documents.py — gera os embeddings no ChromaDB
│   ├── tests/               # dataset rotulado + avaliação do piso, do juiz, do retrieval e da geração
│   ├── chroma_db/           # banco vetorial persistido (versionado)
│   └── Dockerfile
├── frontend/                # chat em Next.js 14 + Tailwind
├── benchmark/               # testes de carga (k6) + load_test.py (TTFT, percentis)
├── docker-compose.yml
├── REGRAS.md                # regras SE–ENTÃO e motor de inferência
└── DECLARACAO_ETICA.md      # análise ética e declaração de uso de IA
```

---

## Rodando localmente

### Pré-requisitos
- Python 3.11+ e Node.js 18+
- Uma `OPENAI_API_KEY`

### Backend

**Opção A — Docker (recomendada):**
```bash
# na raiz, crie um arquivo .env com:
#   OPENAI_API_KEY=sua_chave
docker compose up --build
# API em http://localhost:8010
```

**Opção B — local sem Docker:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# crie backend/.env com OPENAI_API_KEY=sua_chave
uvicorn api.app:app --reload --port 8010
```

> O banco vetorial (`backend/chroma_db/`) já vem indexado no repositório, então a API sobe pronta para responder.
> **Só** é preciso reindexar se você editar a base em `backend/data/`:
> ```bash
> python scripts/index_documents.py
> ```

### Frontend
```bash
cd frontend
npm install
cp .env.local.example .env.local        # ajuste NEXT_PUBLIC_API_URL se necessário
npm run dev                             # http://localhost:3000
```

---

## Configuração (variáveis de ambiente)

| Variável | Lado | Padrão | Descrição |
|---|---|---|---|
| `OPENAI_API_KEY` | backend | — | Chave da OpenAI (obrigatória). |
| `RATE_LIMIT_ENABLED` | backend | `true` | Liga/desliga o rate limit. Desligue ao rodar testes de carga. |
| `PORT` | backend | `8010` | Porta da API. |
| `NEXT_PUBLIC_API_URL` | frontend | — | URL base da API FastAPI (sem barra no final). |

---

## API

**`POST /chat`** — recebe a pergunta e responde via **SSE** (streaming).

```json
{
  "message": "como me inscrevo no programa?",
  "history": [
    { "role": "user", "content": "o que é o caça asteroides?" },
    { "role": "assistant", "content": "É um programa de ciência cidadã..." }
  ]
}
```
- `message`: 3 a 1000 caracteres · `history`: até 10 mensagens.
- Eventos do stream: `metadata` (informa se vai responder) · `token` (pedaço da resposta) · `error` · `done`.

**`GET /health`** — checagem simples (`{ "status": "ok" }`).

---

## Testes e avaliação

O limiar e o juiz foram calibrados com um **dataset rotulado** (`backend/tests/dataset.py`) de 89 perguntas:

| Conjunto | Qtd. | O sistema deve |
|---|---|---|
| Dentro do escopo | 61 | responder |
| Adversariais (vocabulário do programa, sem resposta na base) | 12 | encaminhar |
| Fora do escopo | 10 | encaminhar |
| Multi-turno (dependem do histórico) | 6 | responder |

```bash
cd backend
python tests/eval_floor.py     # varre o piso de 0,30 a 0,55 e mostra o que passa e o que é barrado em cada valor
python tests/eval_grader.py    # mede o juiz e diagnostica cada erro (prompt rígido demais ou trecho não recuperado)
python tests/eval_gate.py      # piso + juiz juntos, como em produção
```

Também há testes de **retrieval**, **geração**, **streaming** e **memória/multi-turno**.

**Carga** (`benchmark/`) — para responder *"aguenta dezenas a centenas de usuários simultâneos?"*:
```bash
# desligue o rate limit no alvo antes (RATE_LIMIT_ENABLED=false)
pip install httpx
python benchmark/load_test.py          # rampa 10→25→50→75→100, mede TTFT e percentis
# ou, com k6:
k6 run benchmark/smoke.js              # fumaça
k6 run benchmark/load.js              # carga constante
k6 run benchmark/stress.js           # rampa até quebrar
```
O load test mede **TTFT (time to first token)** — o tempo até a resposta *começar* a aparecer, que é o que o usuário sente — e percentis **p95/p99**, porque num evento ao vivo o que importa não é a média, é a pessoa azarada da fila.

---

## Lições aprendidas

Mais do que "plugar um LLM", este projeto me ensinou que **um RAG bom se constrói observando dados, não chutando regras**:

- **A informação está nas distâncias.** O ChromaDB devolve distâncias; o difícil não é buscar, é decidir *se a busca foi boa o suficiente para responder*. O piso de 0,40 nasceu de **observar os scores de perguntas reais e de um dataset rotulado**, varrendo limiares e medindo o que passava e o que era barrado. Foi um ciclo de **medir → achar padrão → ajustar → testar de novo**, não um número mágico.
- **Um número não resolve tudo.** O score separa bem o que está fora do tema, mas não as perguntas adversariais, que usam as palavras do programa sem ter resposta no material. Para elas foi preciso um **juiz semântico**, e pedir o raciocínio *antes* do veredito deixou as decisões mais estáveis.
- **Recusar é uma feature.** Num contexto científico, uma resposta errada é pior que um "não sei". O sistema prefere o fallback (com o e-mail de contato) a inventar, e essa decisão fica **antes** da geração (piso + juiz). Assim a geração só tem uma tarefa: responder a partir do contexto aprovado.
- **Pergunta vaga quebra busca semântica.** *"E como?"* ou *"quero participar"* não têm sinal suficiente para um bom embedding. O passo de **rewrite** resolveu boa parte das falhas de *"às vezes responde, às vezes não"*, tornando a pergunta autônoma antes de buscar.
- **O que o usuário sente é o TTFT.** Streaming e a medição de *time to first token* mudaram a percepção de velocidade muito mais do que otimizar o tempo total.
- **Produção é observação contínua.** Logging estruturado com `request_id` em cada etapa foi o que permitiu enxergar o caminho de cada pergunta e calibrar o sistema com base em uso real — e não em suposição.

---

## Próximos passos (roadmap)

- [ ] **Coletar feedback** do usuário (👍/👎) por resposta, para alimentar a recalibração.
- [ ] **Mostrar a fonte** (documento oficial) abaixo de cada resposta.
- [ ] **Aviso no chat** para não digitar dados pessoais e prazo de retenção dos logs.
- [ ] Incluir no dataset **perguntas informais e com erros de digitação**, para medir se o sistema atende todos igualmente.
- [ ] **Melhorar o chunking** da base de conhecimento para buscas ainda mais precisas.
- [ ] **Observabilidade**: dashboard de métricas (latência, taxa de fallback, perguntas sem resposta) a partir dos logs.
- [ ] **Endurecer o CORS** em produção (restringir métodos/headers em vez de `*`).
- [ ] **Rate limit persistente** (hoje em memória) para escalar com múltiplas instâncias.
- [ ] **Cobertura de testes** e avaliação automatizada rodando em CI.

---

## Créditos

**Caça Asteroides MCTI** é uma iniciativa de ciência cidadã do **MCTI** e da **AEB**, em parceria com o **IASC** (parceiro oficial da NASA), com coordenação do **Observatório Nacional**, **UNILA** e **UFMS**.

Assistente de IA desenvolvido por **Luís Filipe Silva Santos** · [GitHub](https://github.com/Luissantos20), com contribuição de **Luana Stoinski** na definição das regras, na avaliação e na calibração do sistema.

---

## Licença

O **código** deste projeto está sob a licença **MIT** — veja o arquivo [LICENSE](LICENSE).

O conteúdo do programa (`backend/data/`) e a identidade visual (logos em `frontend/public/`) são de propriedade do **Caça Asteroides MCTI** e **não** estão cobertos por esta licença.
