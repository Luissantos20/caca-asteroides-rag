"use client";

import { useRef, useEffect, KeyboardEvent } from "react";

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  isLoading: boolean;
  disabled?: boolean;
}

export default function ChatInput({
  value,
  onChange,
  onSend,
  isLoading,
  disabled,
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = Math.min(textarea.scrollHeight, 160) + "px";
  }, [value]);

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading && value.trim().length >= 3) onSend();
    }
  }

  const canSend = value.trim().length >= 3 && !isLoading && !disabled;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50">
      {/* Gradient fade */}
      <div className="h-8 bg-gradient-to-t from-space-950 to-transparent pointer-events-none" />

      <div className="bg-space-950 pb-4 pt-2 px-4">
        <div className="max-w-3xl mx-auto">
          <div
            className={`
              flex items-end gap-3 
              bg-space-800/80 backdrop-blur-sm
              border rounded-2xl px-4 py-3
              transition-all duration-200
              ${
                value
                  ? "border-asteroid/30 shadow-[0_0_20px_rgba(249,115,22,0.08)]"
                  : "border-space-700/60"
              }
            `}
          >
            {/* Textarea */}
            <textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Pergunte sobre o programa Caça Asteroides…"
              disabled={isLoading || disabled}
              rows={1}
              className="
                flex-1 bg-transparent resize-none
                font-sans text-sm text-star placeholder-star-dim/50
                disabled:opacity-50 disabled:cursor-not-allowed
                min-h-[24px] max-h-[160px]
                leading-relaxed
              "
              style={{ outline: "none", border: "none", boxShadow: "none" }}
            />

            {/* Send button */}
            <button
              onClick={onSend}
              disabled={!canSend}
              className={`
                flex-shrink-0 w-8 h-8 rounded-xl
                flex items-center justify-center
                transition-all duration-200
                ${
                  canSend
                    ? "bg-asteroid hover:bg-asteroid-glow text-white shadow-[0_0_12px_rgba(249,115,22,0.3)]"
                    : "bg-space-700/50 text-star-dim/30 cursor-not-allowed"
                }
              `}
            >
              {isLoading ? (
                <svg
                  className="w-3.5 h-3.5 animate-spin"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
              ) : (
                <svg
                  className="w-3.5 h-3.5"
                  viewBox="0 0 16 16"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M2 8L14 8M9 3L14 8L9 13"
                    stroke="currentColor"
                    strokeWidth="1.75"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              )}
            </button>
          </div>

          {/* Hint */}
          {/* Crédito */}
          <p className="text-center text-xs font-mono text-star-dim/30 mt-2">
            Desenvolvido por{" "}
            <a
              href="https://github.com/Luissantos20"
              target="_blank"
              rel="noopener noreferrer"
              className="text-star-dim/50 hover:text-asteroid transition-colors"
            >
              @Luissantos20
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
