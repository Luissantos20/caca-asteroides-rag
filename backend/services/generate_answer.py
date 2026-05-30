import logging

from services.openai_client import client_openai, openai_semaphore

logger = logging.getLogger(__name__)

FALLBACK_MESSAGE = (
    "Não consegui encontrar essa informação com segurança. "
    "Mas posso te ajudar! 😊\n\n"
    "Você pode enviar sua dúvida para o e-mail:\n"
    "📩 cacaasteroidesbrasil@gmail.com"
)

# Marcador que o modelo emite quando o contexto não responde à pergunta.
# Detectado no início do stream → tratado como recusa (yield None), e o
# pipeline emite o FALLBACK_MESSAGE pelo caminho que já existe.
FALLBACK_MARKER = "<FALLBACK>"


async def generate_answer_stream(
    query: str,
    request_id: str,
    chunks: list,
    history: list = None,
):
    """
    Gerador assíncrono. Yields:
    - cada token (string) recebido da OpenAI conforme chega
    - ou yield None caso algo falhe OU o modelo recuse por falta de contexto
      (caller/pipeline decide o que fazer — hoje emite o FALLBACK_MESSAGE)
    """
    if history is None:
        history = []

    if not chunks:
        logger.warning(f"[{request_id}] Nenhum chunk recebido para geração")
        yield None
        return

    # ===== filtro de relevância =====
    relevant_chunks = [
        c for c in chunks
        if c["score"] >= 0.4
    ]

    if not relevant_chunks:
        logger.warning(
            f"[{request_id}] [GENERATION WARNING] "
            "Nenhum chunk relevante após filtro de score"
        )
        yield None
        return

    context = "\n\n".join([
        f"[{c['metadata']['category']}]\n{c['content'][:900]}"
        for c in relevant_chunks[:3]
    ])

    logger.info(
        f"[{request_id}] Gerando resposta com {len(relevant_chunks[:3])} chunks "
        f"(query='{query[:80]}', history={len(history)} msgs)"
    )

    system_prompt = f"""
Você é um assistente RAG do programa Caça Asteroides MCTI 2026.
O programa é uma iniciativa de ciência cidadã do MCTI em parceria com o IASC/NASA,
onde participantes analisam imagens astronômicas com o software Astrometrica para detectar asteroides.

Você receberá uma pergunta do usuário e até 3 chunks de contexto recuperados.
Pode haver histórico de mensagens anteriores nesta conversa — use-as para entender referências, mas baseie a resposta SEMPRE no contexto recuperado.

REGRAS:
- Use APENAS o contexto fornecido abaixo
- NÃO use conhecimento externo
- Se houver múltiplas informações relevantes no contexto, inclua TODAS na resposta
- Não invente ou complemente informações

QUANDO O CONTEXTO NÃO RESPONDE À PERGUNTA:
- O contexto pode ser sobre o mesmo tema (asteroides, o programa) sem conter a resposta à pergunta específica feita.
- Se o contexto NÃO contiver os elementos necessários para responder à pergunta específica do usuário, NÃO tente deduzir, aproximar ou responder parcialmente.
- Nesse caso, responda EXATAMENTE com o texto: {FALLBACK_MARKER}
- Não escreva mais nada antes ou depois desse marcador. Apenas ele.

FORMATO DA RESPOSTA (quando houver resposta no contexto):
- Seja claro, direto, objetivo, simples mas completo
- Use linguagem simples
- Formate em markdown legível
- Use listas numeradas para passos
- Use negrito para destaques importantes
- Sempre use quebra de linha entre tópicos

Contexto recuperado:
{context}
"""

    # Monta a lista de mensagens
    messages = [{"role": "system", "content": system_prompt}]

    # <<< MUDANÇA: adiciona o histórico, mas remove a última fala do usuário,
    # pois ela será substituída pela versão reescrita (query) logo abaixo.
    # Isso evita duplicar a pergunta (crua no histórico + reescrita no fim).
    history_sem_ultima = history[:-1] if (history and history[-1]["role"] == "user") else history
    for msg in history_sem_ultima:
        messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    # Pergunta atual (já reescrita pelo pipeline) no final
    messages.append({"role": "user", "content": query})


    logger.info(f"[{request_id}] [GENERATION] Aguardando slot do openai_semaphore")

    try:
        async with openai_semaphore:
            logger.info(f"[{request_id}] [GENERATION] Slot adquirido, iniciando stream")
            stream = await client_openai.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0,
                timeout=30,
                stream=True,
                messages=messages,
            )

            # ===== Detecção do marcador de recusa =====
            # Segura os primeiros tokens num buffer enquanto eles ainda
            # puderem formar o FALLBACK_MARKER. Só começa a emitir de fato
            # quando tiver certeza de que NÃO é uma recusa.
            buffer = ""
            releasing = False  # já confirmou que não é fallback → stream direto

            async for chunk in stream:
                token = chunk.choices[0].delta.content
                if token is None:
                    continue

                if releasing:
                    yield token
                    continue

                buffer += token
                stripped = buffer.lstrip()

                # buffer (sem espaços iniciais) ainda é um prefixo do marcador?
                if FALLBACK_MARKER.startswith(stripped):
                    if stripped == FALLBACK_MARKER:
                        # recusa confirmada — trata como "sem resposta"
                        logger.info(
                            f"[{request_id}] [GENERATION] Modelo recusou por "
                            f"falta de contexto (query='{query[:80]}')"
                        )
                        yield None
                        return
                    # ainda incompleto: continua segurando
                    continue
                else:
                    # divergiu do marcador → é resposta normal: libera o buffer
                    releasing = True
                    yield buffer
                    buffer = ""

            # Stream terminou ainda com algo retido no buffer
            if not releasing and buffer:
                if buffer.strip() == FALLBACK_MARKER:
                    logger.info(
                        f"[{request_id}] [GENERATION] Modelo recusou por "
                        f"falta de contexto (query='{query[:80]}')"
                    )
                    yield None
                    return
                yield buffer

            logger.info(f"[{request_id}] [GENERATION] Stream finalizada")

    except Exception as e:
        logger.error(
            f"[{request_id}] [GENERATION ERROR] "
            f"query='{query[:80]}' "
            f"Falha na chamada OpenAI: {str(e)}"
        )
        yield None