import { useEffect, useMemo, useState } from 'react'
import doc from '../../../docs/METHODOLOGY.md?raw'
import { Markdown } from '../components/Markdown'
import { PageTitle } from '../components/ui'
import { cn, slug } from '../lib/utils'

export function Methodology() {
  const body = useMemo(() => doc.replace(/^# .*\n/, ''), [])
  const headings = useMemo(() => [...body.matchAll(/^## (.+)$/gm)].map((m) => ({ text: m[1], id: slug(m[1]) })), [body])
  const [active, setActive] = useState<string | null>(headings[0]?.id ?? null)

  useEffect(() => {
    const nodes = headings.map((h) => document.getElementById(h.id)).filter((n): n is HTMLElement => Boolean(n))
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
      if (visible[0]) setActive(visible[0].target.id)
    }, { rootMargin: '-80px 0px -65% 0px' })
    nodes.forEach((n) => observer.observe(n))
    return () => observer.disconnect()
  }, [headings])

  return (
    <div className="page methodology">
      <PageTitle eyebrow="Methodology"
                 title={<>How every number is <em>made</em></>}
                 lede="The formulas, defaults and limitations behind each engine, written so an analyst can audit the model rather than trust it." />
      <div className="methodology-grid">
        <nav className="toc" aria-label="Contents">
          <div className="eyebrow muted">Contents</div>
          {headings.map((h) => (
            <a key={h.id} href={`#${h.id}`} className={cn(active === h.id && 'on')}
               onClick={(e) => { e.preventDefault(); document.getElementById(h.id)?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }}>
              {h.text}
            </a>
          ))}
        </nav>
        <Markdown className="methodology-body" anchors>{body}</Markdown>
      </div>
    </div>
  )
}
