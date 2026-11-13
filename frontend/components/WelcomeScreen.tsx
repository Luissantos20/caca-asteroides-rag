"use client";

import { ReactNode } from "react";
import SnctBanner from "./SnctBanner";

/* Ícones de linha (24x24) */
const svg = {
  width: 22,
  height: 22,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

const IconPlanet = () => (
  <svg {...svg}>
    <circle cx="12" cy="11" r="5" />
    <ellipse cx="12" cy="11" rx="10" ry="3.4" transform="rotate(-20 12 11)" />
  </svg>
);
const IconRocket = () => (
  <svg {...svg}>
    <path d="M12 3c2.4 1.5 3.8 4.2 3.8 7.4 0 2-.7 3.7-1.6 5H9.8c-.9-1.3-1.6-3-1.6-5C8.2 7.2 9.6 4.5 12 3Z" />
    <circle cx="12" cy="9.2" r="1.4" />
    <path d="M9.8 15.4 8 18m6 0 1.8 2.6M12 16v3.5" />
  </svg>
);
const IconCalendar = () => (
  <svg {...svg}>
    <rect x="3.5" y="5" width="17" height="15" rx="2" />
    <path d="M3.5 9.5h17M8 3v4M16 3v4" />
    <path d="M8 13.5h2M14 13.5h2M8 16.5h2" />
  </svg>
);
const IconPartners = () => (
  <svg {...svg}>
    <circle cx="8.5" cy="8" r="2.4" />
    <circle cx="16" cy="9.5" r="2" />
    <path d="M4.5 18c0-2.2 1.8-4 4-4s4 1.8 4 4" />
    <path d="M14 14.4c2 0 3.6 1.5 3.6 3.6" />
  </svg>
);
const IconTarget = () => (
  <svg {...svg}>
    <circle cx="12" cy="12" r="7" />
    <circle cx="12" cy="12" r="2.4" />
    <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
  </svg>
);
const IconCert = () => (
  <svg {...svg}>
    <circle cx="12" cy="9.5" r="4.5" />
    <path d="m9 8.8 2 2 3-3.4" />
    <path d="M9.2 13.6 8 21l4-2 4 2-1.2-7.4" />
  </svg>
);

interface SuggestedItem {
  tag: string;
  text: string;
  icon: ReactNode;
}

const SUGGESTED: SuggestedItem[] = [
  { tag: "Missão", text: "O que é o programa Caça Asteroides?", icon: <IconPlanet /> },
  { tag: "Evento", text: "Qual a programação na Semana Nacional?", icon: <IconCalendar /> },
  { tag: "Campanhas", text: "Como funcionam as campanhas?", icon: <IconRocket /> },
  { tag: "Rede", text: "Quem são os parceiros do programa?", icon: <IconPartners /> },
  { tag: "Ferramenta", text: "O que é o software Astrometrica?", icon: <IconTarget /> },
  { tag: "Conquista", text: "Vai ter entrega de medalhas?", icon: <IconCert /> },
];

interface WelcomeScreenProps {
  onSuggestedQuestion: (question: string) => void;
}

export default function WelcomeScreen({ onSuggestedQuestion }: WelcomeScreenProps) {
  return (
    <div className="welcome-wrap">
      {/* Logo em destaque com halo + órbita */}
      <div className="logo-stage">
        <div className="orbit-ring r2" />
        <div className="orbit-ring r1" />
        <div className="orbit-ring r3" />
        <div className="orbit-dot">
          <span />
        </div>
        <img className="logo-img" src="/assistente-caca.svg" alt="Logo Caça Asteroides MCTI" />
      </div>

      <div className="welcome-kicker">Programa de Ciência Cidadã</div>
      <h1 className="welcome-title">
        Bem-vindo, <span className="accent">caçador!</span>
      </h1>
      <p className="welcome-sub">
        Sou o assistente de IA do programa. Posso esclarecer dúvidas sobre as campanhas, o
        software de análise e a sua jornada na caça de asteroides.
      </p>

      <SnctBanner />

      <div className="section-label">
        <span className="blink" /> Comece por aqui
      </div>

      <div className="q-grid">
        {SUGGESTED.map((q) => (
          <button key={q.text} className="q-card" onClick={() => onSuggestedQuestion(q.text)}>
            <span className="q-icon">{q.icon}</span>
            <span className="q-body">
              <span className="q-tag">{q.tag}</span>
              <span className="q-text">{q.text}</span>
            </span>
            <span className="q-arrow">
              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                strokeWidth={1.6}
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M3 8h9M8 4l4 4-4 4" />
              </svg>
            </span>
          </button>
        ))}
      </div>

      <div className="welcome-foot">// ou digite sua própria pergunta abaixo</div>
    </div>
  );
}