# 🌑 Caça Asteroides — MCTI · Frontend

Interface de chat para o assistente RAG do Programa Caça Asteroides do Ministério da Ciência, Tecnologia e Inovação.

## Stack

- **Next.js 14** (App Router)
- **TypeScript**
- **Tailwind CSS**
- Tema escuro com identidade visual espacial

## Estrutura

```
caca-asteroides/
├── app/
│   ├── globals.css        # Estilos globais + animações
│   ├── layout.tsx         # Layout raiz (fontes, metadata)
│   └── page.tsx           # Página principal do chat
├── components/
│   ├── Header.tsx         # Cabeçalho fixo com logo e status
│   ├── ChatInput.tsx      # Input fixo com auto-resize
│   ├── MessageBubble.tsx  # Balão de mensagem (user / assistant)
│   ├── TypingIndicator.tsx# Indicador de carregamento animado
│   └── WelcomeScreen.tsx  # Tela inicial com sugestões
├── services/
│   └── api.ts             # Comunicação com a API FastAPI
├── types/
│   └── index.ts           # Tipos TypeScript (Message, ChatRequest, etc.)
└── .env.local.example     # Variáveis de ambiente
```

## Instalação

```bash
npm install
```

## Configuração

Copie o arquivo de exemplo e ajuste a URL da API:

```bash
cp .env.local.example .env.local
```

Edite `.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Desenvolvimento

```bash
npm run dev
```

Abra [http://localhost:3000](http://localhost:3000).

## Produção

```bash
npm run build
npm start
```

## Integração com a API

O frontend consome o endpoint:

```
POST /chat
Content-Type: application/json

{ "message": "texto da pergunta" }
```

Resposta esperada:

```json
{
  "should_answer": true,
  "answer": "resposta do assistente"
}
```

Quando `should_answer` for `false`, o frontend exibe uma mensagem padrão informando que a pergunta está fora do escopo do programa.
