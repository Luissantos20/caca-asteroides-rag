"use client";

interface TypingIndicatorProps {
  statusText?: string;
}

export default function TypingIndicator({ statusText }: TypingIndicatorProps) {
  return (
    <div className="message-enter flex gap-3 items-end mb-4">
      {/* Avatar */}
      {/* Avatar — agora igual ao do MessageBubble */}
      <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-space-800 border border-asteroid/30 flex items-center justify-center overflow-hidden mb-0.5 shadow-[inset_0_0_10px_rgba(249,115,22,0.12)]">
        <img
          src="/assistente-caca.svg"
          alt="Assistente digitando"
          className="w-9 h-9 object-contain object-bottom"
        />
      </div>

      {/* Typing bubble */}
      <div className="px-4 py-3.5 rounded-2xl rounded-bl-sm bg-space-800/80 border border-space-700/60">
        <div className="flex items-center gap-2">
          {/* Bolinhas animadas */}
          <div className="flex items-center gap-1.5">
            <span className="typing-dot w-1.5 h-1.5 rounded-full bg-asteroid/60 inline-block" />
            <span className="typing-dot w-1.5 h-1.5 rounded-full bg-asteroid/60 inline-block" />
            <span className="typing-dot w-1.5 h-1.5 rounded-full bg-asteroid/60 inline-block" />
          </div>

          {/* Texto de status (cycling) */}
          {statusText && (
            <span className="text-xs font-mono text-star-dim ml-1 transition-opacity duration-300">
              {statusText}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}