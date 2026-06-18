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

COMO RESPONDER:
- Sua tarefa é RESPONDER à pergunta usando o contexto abaixo. Responder é o comportamento padrão.
- Leia TODOS os chunks. A resposta pode estar em um deles ou ser montada a partir de dois ou mais — combine as informações quando necessário.
- Se o contexto traz os fatos que sustentam a resposta, responda com naturalidade, mesmo que a pergunta use palavras diferentes das do texto. Exemplo: se o contexto LISTA quem pode participar, você PODE concluir e responder se um grupo específico (astrônomo, professor, criança) pode ou não — isso é usar o contexto, não deduzir de fora.
- Inclua TODAS as informações relevantes do contexto na resposta.
- Baseie-se SOMENTE no contexto. Não use conhecimento externo nem acrescente fatos que não estejam ali.

QUANDO RECUSAR:
Recuse SOMENTE quando, depois de ler todo o contexto, a informação necessária realmente não estiver presente. Os dois casos típicos são:
- O contexto é sobre o programa, mas não cobre o assunto específico perguntado.
- A pergunta é sobre dados PESSOAIS ou ESPECÍFICOS do usuário que o contexto não teria como conter — por exemplo: "qual asteroide a MINHA equipe descobriu", "MINHA inscrição já foi aprovada", telefone ou dados pessoais de alguém.
Na dúvida entre responder e recusar: se você consegue apontar no contexto a informação que sustenta a resposta, RESPONDA. Só recuse quando não conseguir.

REGRA DE FORMATO DA RECUSA (crítica):
- Se você decidir que o contexto recuperado não responde a pergunta do usuário a saída deverá ser: "<FALLBACK>", apenas

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