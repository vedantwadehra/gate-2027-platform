import type { Metadata } from "next";
import "./globals.css";
import "katex/dist/katex.min.css";
import Navbar from "./components/Navbar";

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
    <html lang="en">
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
