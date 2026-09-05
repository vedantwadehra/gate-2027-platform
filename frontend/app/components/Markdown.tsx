'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import type { PluggableList } from 'unified';

/** Convert \(...\) / \[...\] to $...$ / $$...$$ outside fenced code blocks.
 *  remark-math only parses dollar delimiters; LLMs often emit the backslash
 *  forms, so normalize them. Code fences are left untouched. */
export function normalizeMathDelims(src: string): string {
  const parts = src.split(/(```[\s\S]*?```)/g);
  return parts
    .map((seg, i) => {
      if (i % 2 === 1) return seg;
      return seg
        .replace(/\\\[([\s\S]*?)\\\]/g, (_, m: string) => `$$${m}$$`)
        .replace(/\\\(([\s\S]*?)\\\)/g, (_, m: string) => `$${m}$`);
    })
    .join('');
}

const rehypePlugins: PluggableList = [
  [rehypeKatex, { throwOnError: false, strict: false }],
];

/** Safe Markdown + KaTeX math renderer for LLM output.
 *  No raw HTML is executed (rehype-raw is deliberately not enabled), so
 *  model-emitted <script> tags render as inert text. */
export default function Markdown({ text }: { text: string }) {
  return (
    <div className="md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={rehypePlugins}
      >
        {normalizeMathDelims(text)}
      </ReactMarkdown>
      <style jsx>{`
        .md > :first-child {
          margin-top: 0;
        }
        .md > :last-child {
          margin-bottom: 0;
        }
        .md p {
          margin: 0.5em 0;
          line-height: 1.55;
        }
        .md ul,
        .md ol {
          margin: 0.5em 0;
          padding-left: 1.4em;
        }
        .md li {
          margin: 0.25em 0;
        }
        .md pre {
          overflow-x: auto;
          background: rgba(127, 127, 127, 0.12);
          border: 1px solid var(--border, #ddd);
          border-radius: 8px;
          padding: 10px 12px;
          font-size: 13px;
        }
        .md code {
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 0.92em;
        }
        .md :not(pre) > code {
          background: rgba(127, 127, 127, 0.16);
          border-radius: 4px;
          padding: 1px 5px;
        }
        .md table {
          border-collapse: collapse;
          margin: 0.6em 0;
          font-size: 13px;
        }
        .md th,
        .md td {
          border: 1px solid var(--border, #ccc);
          padding: 5px 10px;
          text-align: left;
        }
        .md blockquote {
          border-left: 3px solid var(--accent-2, #2f6df6);
          margin: 0.5em 0;
          padding: 2px 0 2px 10px;
          opacity: 0.9;
        }
        .md h1,
        .md h2,
        .md h3,
        .md h4 {
          margin: 0.7em 0 0.4em;
          line-height: 1.3;
        }
        .md .katex-display {
          overflow-x: auto;
          overflow-y: hidden;
          padding: 4px 0;
        }
      `}</style>
    </div>
  );
}
