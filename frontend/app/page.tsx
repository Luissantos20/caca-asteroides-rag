"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Message, StreamEvent } from "@/types";
import { sendMessageStream, ApiError } from "@/services/api";
import Header from "@/components/Header";
import MessageBubble from "@/components/MessageBubble";
import TypingIndicator from "@/components/TypingIndicator";
import WelcomeScreen from "@/components/WelcomeScreen";
import ChatInput from "@/components/ChatInput";

function generateId(): string {
  return crypto.randomUUID();
}

type LoadingStage = "buscando" | "analisando" | "pensando" | null;

const STAGE_LABELS: Record<Exclude<LoadingStage, null>, string> = {
  buscando: "Buscando informações",
  analisando: "Analisando",
  pensando: "Pensando",
};

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState<LoadingStage>(null);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const stageTimeoutsRef = useRef<NodeJS.Timeout[]>([]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading, loadingStage]);

  // Limpa timeouts ao desmontar
  useEffect(() => {
    return () => {
      stageTimeoutsRef.current.forEach(clearTimeout);
    };
  }, []);

  function clearStageTimeouts() {
    stageTimeoutsRef.current.forEach(clearTimeout);
    stageTimeoutsRef.current = [];
  }

  function startLoadingCycle() {
    setLoadingStage("buscando");

    const t1 = setTimeout(() => setLoadingStage("analisando"), 1500);
    const t2 = setTimeout(() => setLoadingStage("pensando"), 3000);

    stageTimeoutsRef.current = [t1, t2];
  }

  const handleSend = useCallback(
    async (text?: string) => {
      const messageText = (text ?? input).trim();
      if (!messageText || isLoading) return;

      if (messageText.length < 3) {
        setError("Sua pergunta precisa ter pelo menos 3 caracteres.");
        return;
      }

      setInput("");
      setError(null);

      // Monta o history com as últimas 4 mensagens (2 trocas)
      // Pega antes de incluir a nova pergunta (a nova vai como 'message')
      const recentHistory = messages
        .filter((m) => m.role === "user" || m.role === "assistant")
        .filter((m) => m.content.trim() !== "")
        .slice(-4)
        .map((m) => ({
          role: m.role as "user" | "assistant",
          content: m.content,
        }));

      const userMessage: Message = {
        id: generateId(),
        role: "user",
        content: messageText,
        timestamp: new Date().toISOString(),
      };

      const assistantMessageId = generateId();
      const assistantMessage: Message = {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setIsLoading(true);
      startLoadingCycle();

      let firstTokenReceived = false;

      try {
        for await (const event of sendMessageStream({
          message: messageText,
          history: recentHistory,
        })) {
          if (event.type === "metadata") {
            // Se a decision negou, marcamos a mensagem como fora de escopo
            if (!event.should_answer) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMessageId
                    ? { ...m, isOutOfScope: true }
                    : m
                )
              );
            }
            continue;
          }

          if (event.type === "token") {
            if (!firstTokenReceived) {
              firstTokenReceived = true;
              clearStageTimeouts();
              setLoadingStage(null);
            }

            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? { ...m, content: m.content + event.content }
                  : m
              )
            );
            continue;
          }

          if (event.type === "error") {
            // Se ainda não veio token, o conteúdo da mensagem do assistente
            // vira a mensagem de erro/fallback do backend.
            clearStageTimeouts();
            setLoadingStage(null);

            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? {
                      ...m,
                      content: m.content || event.message,
                      isOutOfScope: true,
                    }
                  : m
              )
            );
            continue;
          }

          if (event.type === "done") {
            break;
          }
        }
      } catch (err) {
        clearStageTimeouts();
        setLoadingStage(null);

        // Remove a mensagem vazia do assistente se nada chegou
        setMessages((prev) =>
          prev.filter((m) => !(m.id === assistantMessageId && m.content === ""))
        );

        setError(
          err instanceof ApiError
            ? err.message
            : "Erro inesperado. Tente novamente."
        );
      } finally {
        setIsLoading(false);
        setLoadingStage(null);
      }
    },
    [input, isLoading, messages]
  );

  const hasMessages = messages.length > 0;

  return (
    <div className="stars-bg noise-bg min-h-dvh bg-space-950 text-star">
      <div className="comets-bg" />
      <Header />

      <main
        ref={messagesContainerRef}
        className="pt-16 pb-32 min-h-dvh"
      >
        {!hasMessages ? (
          <WelcomeScreen onSuggestedQuestion={(q) => handleSend(q)} />
        ) : (
          <div className="max-w-3xl mx-auto px-4 pt-6">
            {messages
              .filter((m) => !(m.role === "assistant" && m.content === ""))
              .map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}
            {isLoading && loadingStage && (
              <TypingIndicator
                statusText={STAGE_LABELS[loadingStage]}
              />
            )}
            <div ref={messagesEndRef} />
          </div>
        )}

        {error && (
          <div className="fixed bottom-28 left-1/2 -translate-x-1/2 z-40 max-w-md w-[calc(100%-2rem)]">
            <div className="message-enter flex items-start gap-3 px-4 py-3 rounded-xl bg-red-950/40 border border-red-800/50 backdrop-blur-sm shadow-lg">
              <svg className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <div className="flex-1">
                <p className="text-xs font-mono text-red-400 font-medium mb-0.5">
                  Algo deu errado
                </p>
                <p className="text-xs font-sans text-red-300/90 leading-relaxed">
                  {error}
                </p>
              </div>
              <button
                onClick={() => setError(null)}
                className="text-red-400/60 hover:text-red-300 text-lg leading-none px-1"
                aria-label="Fechar"
              >
                ×
              </button>
            </div>
          </div>
        )}
      </main>

      <ChatInput
        value={input}
        onChange={setInput}
        onSend={() => handleSend()}
        isLoading={isLoading}
      />
    </div>
  );
}