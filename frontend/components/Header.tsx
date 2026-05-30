"use client";

export default function Header() {
  return (
    <header className="header-telemetry fixed top-0 left-0 right-0 z-50 bg-space-950/90 backdrop-blur-sm">
      <div className="max-w-4xl mx-auto px-4 h-16 flex items-center justify-between">
        {/* Marca */}
        <div className="brand">
          <img
            src="/logo-caca-asteroides.svg"
            alt="Caça Asteroides MCTI"
            className="brand-logo"
          />
          <div className="brand-title glow-text">
            CAÇA ASTEROIDES <span className="sub">MCTI</span>
          </div>
        </div>

        {/* Links */}
        <div className="flex items-center gap-1.5">
          <a
            className="nav-link"
            href="https://iasc.cosmosearch.org/"
            target="_blank"
            rel="noopener noreferrer"
          >
            IASC ↗
          </a>
          <a className="nav-link" href="/edital.pdf" target="_blank" rel="noopener noreferrer">
            Edital ↗
          </a>
        <a
          className="nav-link"
          href="https://caioruas24010.github.io/DocsCacaAsteroides/"
          target="_blank"
          rel="noopener noreferrer"
        >
        Guia ↗
        </a>
        </div>
      </div>
    </header>
  );
}