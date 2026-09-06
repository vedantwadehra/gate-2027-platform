import type { Metadata } from "next";
import { Inter, Space_Grotesk, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import "katex/dist/katex.min.css";
import Navbar from "./components/Navbar";

const body = Inter({ subsets: ["latin"], variable: "--font-body", display: "swap" });
const display = Space_Grotesk({ subsets: ["latin"], variable: "--font-display", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono", display: "swap" });

export const metadata: Metadata = {
  title: "GATE 2027 DA/CS Platform",
  description: "Guide, mock tests and an AI tutor for GATE 2027 DA & CS.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${body.variable} ${display.variable} ${mono.variable}`}
    >
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html:
              "try{document.documentElement.dataset.theme=localStorage.getItem('gate_theme')||'dark';}catch(e){}",
          }}
        />
      </head>
      <body>
        <Navbar />
        <main className="container">{children}</main>
      </body>
    </html>
  );
}
