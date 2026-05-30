"use client";

import { Message } from "@/types";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MessageBubbleProps {
  message: Message;
}

function formatTime(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";

  if (isSystem) {
    return (
      <div className="message-enter flex justify-center my-4">
        <div className="flex items-center gap-2 px-4 py-1.5 rounded-full bg-space-800/50 border border-space-700/50">
          <span className="text-xs font-mono text-star-dim">{message.content}</span>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`message-enter flex gap-3 ${
        isUser ? "flex-row-reverse" : "flex-row"
      } items-end mb-4`}
    >
      {/* Avatar (assistente à esquerda, usuário à direita) */}
      {!isUser ? (
        <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-space-800 border border-asteroid/30 flex items-center justify-center overflow-hidden mb-0.5 shadow-[inset_0_0_10px_rgba(249,115,22,0.12)]">
          <img
            src="/assistente-caca.svg"
            alt="Assistente Caça Asteroides"
            className="w-9 h-9 object-contain object-bottom"
          />
        </div>
      ) : (
        <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-space-700 border border-asteroid/20 flex items-center justify-center mb-0.5">
          <svg viewBox="0 0 20 20" fill="none" className="w-5 h-5">
            <circle cx="10" cy="7" r="3" fill="#94a3b8" />
            <path d="M3 17c0-3.866 3.134-7 7-7s7 3.134 7 7" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </div>
      )}

      {/* Bubble */}
      <div className={`max-w-[75%] ${isUser ? "items-end" : "items-start"} flex flex-col gap-1`}>
        <div
          className={`
            px-4 py-3 rounded-2xl text-sm leading-relaxed
            ${
              isUser
                ? "bg-gradient-to-br from-asteroid/25 to-asteroid/10 border border-asteroid/35 text-star rounded-br-sm"
                : message.isOutOfScope
                ? "bg-space-800/60 border border-space-700/60 text-star-muted rounded-bl-sm"
                : "bg-space-800/70 border border-space-600/50 text-star rounded-bl-sm"
            }
          `}
        >
          {message.isOutOfScope && (
            <div className="flex items-center gap-1.5 mb-2 pb-2 border-b border-space-700/50">
              <svg className="w-3 h-3 text-star-dim" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              <span className="text-xs font-mono text-star-dim">fora do escopo</span>
            </div>
          )}
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              p: ({ children }) => (
                <p className="mb-3 last:mb-0">
                  {children}
                </p>
              ),

              ul: ({ children }) => (
                <ul className="list-disc pl-5 mb-3 space-y-1">
                  {children}
                </ul>
              ),

              ol: ({ children }) => (
                <ol className="list-decimal pl-5 mb-3 space-y-1">
                  {children}
                </ol>
              ),

              li: ({ children }) => (
                <li className="text-sm leading-relaxed">
                  {children}
                </li>
              ),

              strong: ({ children }) => (
                <strong className="font-semibold text-star">
                  {children}
                </strong>
              ),

              a: ({ href, children }) => (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-asteroid hover:underline break-all"
                >
                  {children}
                </a>
              ),

              code: ({ children }) => (
                <code className="bg-space-900 px-1.5 py-0.5 rounded text-xs font-mono text-asteroid">
                  {children}
                </code>
              ),
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>

        {/* Timestamp */}
        <span className={`text-xs font-mono text-star-dim/50 px-1 ${isUser ? "text-right" : "text-left"}`}>
          {formatTime(message.timestamp)}
        </span>
      </div>
    </div>
  );
}