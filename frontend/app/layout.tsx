import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Caça Asteroides · MCTI",
  description:
    "Assistente inteligente do Programa Caça Asteroides do Ministério da Ciência, Tecnologia e Inovação",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
