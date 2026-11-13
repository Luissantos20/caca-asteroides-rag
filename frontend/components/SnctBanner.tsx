"use client";

import { useEffect, useState } from "react";

/* Card de aviso: programação do Caça Asteroides MCTI na SNCT 2026.
   Some sozinho depois do fim da Semana Nacional (EXPIRA_EM).
   A checagem da data roda no navegador (useEffect), porque a página é
   gerada estaticamente no build. */

const PDF_URL = "/programacao-snct-2026.pdf";
const EXPIRA_EM = new Date("2026-11-30T03:00:00Z"); // 30/11/2026 00:00 (Brasília)

export default function SnctBanner() {
  const [visivel, setVisivel] = useState(true);

  useEffect(() => {
    if (new Date() >= EXPIRA_EM) setVisivel(false);
  }, []);

  if (!visivel) return null;

  return (
    <a
      className="snct-card"
      href={PDF_URL}
      target="_blank"
      rel="noopener noreferrer"
      aria-label="Ver a programação do Caça Asteroides MCTI na Semana Nacional de Ciência e Tecnologia (PDF)"
    >
      <span className="snct-glow" aria-hidden="true" />

      <span className="snct-date" aria-hidden="true">
        <span className="snct-date-day">24–29</span>
        <span className="snct-date-month">NOV</span>
      </span>

      <span className="snct-body">
        <span className="snct-badge">
          <span className="snct-dot" /> Novo · SNCT 2026
        </span>
        <span className="snct-title">
          Venha conferir a programação do <span className="accent">Caça Asteroides MCTI</span> na
          Semana Nacional de Ciência e Tecnologia!
        </span>
        <span className="snct-meta">
          Esplanada dos Ministérios · Brasília — painéis e oficinas em 27/11 e entrega de medalhas
        </span>
        <span className="snct-cta">
          Ver programação (PDF)
          <svg
            width="14"
            height="14"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.8}
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M5 11 11 5M6 5h5v5" />
          </svg>
        </span>
      </span>
    </a>
  );
}
