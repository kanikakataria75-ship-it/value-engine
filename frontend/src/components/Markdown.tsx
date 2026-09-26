import type { ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { slug } from '../lib/utils'

const text = (node: ReactNode): string =>
  typeof node === 'string' || typeof node === 'number' ? String(node)
    : Array.isArray(node) ? node.map(text).join('')
      : node && typeof node === 'object' && 'props' in node ? text((node.props as { children?: ReactNode }).children) : ''

/* Markdown renderer for copilot answers, memos and methodology. Raw HTML is never rendered.
   With `anchors`, second-level headings get ids so a table of contents can link to them. */
export function Markdown({ children, className, anchors }: { children: string; className?: string; anchors?: boolean }) {
  return (
    <div className={`prose ${className ?? ''}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}
                     components={{
                       a: ({ children: label, href }) => <a href={href} target="_blank" rel="noreferrer">{label}</a>,
                       ...(anchors ? { h2: ({ children: heading }) => <h2 id={slug(text(heading))}>{heading}</h2> } : {}),
                     }}>
        {children}
      </ReactMarkdown>
    </div>
  )
}
