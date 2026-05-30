import { ChatRequest, ChatResponse, ApiErrorKind, StreamEvent } from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

if (!API_BASE_URL) {
  throw new Error("NEXT_PUBLIC_API_URL não está definida.");
}

const REQUEST_TIMEOUT = 60000; // streaming pode demorar mais

export class ApiError extends Error {
  kind: ApiErrorKind;

  constructor(kind: ApiErrorKind, message: string) {
    super(message);
    this.kind = kind;
    this.name = "ApiError";
  }
}



// ===== Nova função streaming =====
export async function* sendMessageStream(
  request: ChatRequest,
  signal?: AbortSignal
): AsyncGenerator<StreamEvent> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
      signal,
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new ApiError("timeout", "A conexão foi interrompida.");
    }
    throw new ApiError(
      "network",
      "Não foi possível conectar ao servidor. Verifique sua internet."
    );
  }

  if (!response.ok) {
    if (response.status === 429) {
      throw new ApiError(
        "rate_limit",
        "Você atingiu o limite de mensagens. Aguarde alguns instantes."
      );
    }
    if (response.status === 422) {
      throw new ApiError(
        "validation",
        "Sua mensagem não é válida. Verifique se tem entre 3 e 1000 caracteres."
      );
    }
    if (response.status >= 500) {
      throw new ApiError(
        "server",
        "O servidor não conseguiu processar sua pergunta."
      );
    }
    throw new ApiError(
      "unknown",
      `Erro inesperado (${response.status}).`
    );
  }

  if (!response.body) {
    throw new ApiError("server", "Resposta sem corpo.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Processa todos os eventos completos no buffer
      let separatorIndex: number;
      while ((separatorIndex = buffer.indexOf("\n\n")) !== -1) {
        const rawEvent = buffer.slice(0, separatorIndex);
        buffer = buffer.slice(separatorIndex + 2);

        if (!rawEvent.startsWith("data: ")) continue;

        const jsonStr = rawEvent.slice(6); // remove "data: "

        try {
          const event: StreamEvent = JSON.parse(jsonStr);
          yield event;
        } catch {
          // Ignora eventos malformados, segue lendo
          continue;
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}