import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import { streamCopilot, scenarioBody } from '../lib/api'
import type { ChatMessage } from '../lib/api-types'
import { usePrefs } from '../lib/prefs'
import { useMeta } from '../lib/queries'
import { useScenario } from '../lib/scenario'
import { readStorage, writeStorage } from '../lib/utils'
import { IconClose, IconReset, IconSend, IconSpark, IconStop } from './icons'

interface Message extends ChatMessage {
  id: string
  provider?: string
  mode?: string
  fallback?: boolean
  streaming?: boolean
  error?: boolean
}

const SUGGESTIONS: Record<string, string[]> = {
  '': ['What is the market pricing in?', 'Explain this valuation', 'What are the biggest risks?', 'Write me the bull and bear case'],
  valuation: ['Which assumptions matter most?', 'Is the terminal value doing too much work?', 'Explain the WACC build'],
  expectations: ['What is priced in, in plain English?', 'How does that compare with history?', 'What would have to go right?'],
  comps: ['How do peers compare?', 'Why do comps and the DCF disagree?'],
  mna: ['Is this deal accretive?', 'What synergies are needed to break even?', 'Is the financing mix sensible?'],
  lbo: ['What drives the IRR?', 'Is the leverage sustainable?', 'How fragile are the returns?'],
  risk: ['What are the biggest risks?', 'Explain the tail risk in plain English', 'What regime is the stock in?'],
  data: ['How reliable is this data?', 'What was derived rather than reported?'],
  report: ['Summarise the investment case', 'What should the IC challenge?'],
}

const storageKey = (ticker: string) => `ve.chat.${ticker}`

// The markdown renderer (and its parser) loads the first time an answer is shown.
const Markdown = lazy(() => import('./Markdown').then((module) => ({ default: module.Markdown })))

export function CopilotOrb({ onClick, open }: { onClick: () => void; open: boolean }) {
  return (
    <button type="button" className={`copilot-orb ${open ? 'open' : ''}`} onClick={onClick} aria-label="Ask ValuAI">
      <span className="orb-core" />
      <span className="orb-glow" />
      <span className="orb-label">Ask ValuAI</span>
    </button>
  )
}

export function Copilot({ open, onClose, ticker, page }: { open: boolean; onClose: () => void; ticker: string | null; page: string }) {
  const { mode } = usePrefs()
  const meta = useMeta().data?.data
  const scenarioApi = useScenario(ticker ?? '_')
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const abort = useRef<AbortController | null>(null)
  const scroller = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    setMessages(ticker ? readStorage<Message[]>(storageKey(ticker), [], window.sessionStorage) : [])
  }, [ticker])

  useEffect(() => {
    if (ticker && !busy) writeStorage(storageKey(ticker), messages.slice(-30), window.sessionStorage)
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: 'smooth' })
  }, [messages, ticker, busy])

  useEffect(() => {
    if (open) window.setTimeout(() => inputRef.current?.focus(), 250)
  }, [open])

  const send = async (text: string) => {
    const question = text.trim()
    if (!question || !ticker || busy) return
    const history: ChatMessage[] = messages.filter((m) => !m.error && m.content).slice(-10).map(({ role, content }) => ({ role, content }))
    const assistantId = `a${Date.now()}`
    setMessages((all) => [...all, { id: `u${Date.now()}`, role: 'user', content: question },
      { id: assistantId, role: 'assistant', content: '', streaming: true }])
    setInput('')
    setBusy(true)
    const controller = new AbortController()
    abort.current = controller
    const patch = (fn: (m: Message) => Message) => setMessages((all) => all.map((m) => (m.id === assistantId ? fn(m) : m)))
    try {
      for await (const event of streamCopilot({
        message: question, ticker, page: page || 'overview', mode, history,
        scenario: scenarioBody(ticker, mode, scenarioApi.scenario),
      }, controller.signal)) {
        if (event.event === 'meta') {
          patch((m) => ({ ...m, provider: String(event.data.provider ?? ''), mode: String(event.data.mode ?? ''), fallback: Boolean(event.data.is_fallback) }))
        } else if (event.event === 'delta') {
          patch((m) => ({ ...m, content: m.content + String(event.data.text ?? '') }))
        } else if (event.event === 'error') {
          patch((m) => ({ ...m, content: m.content || String(event.data.message ?? 'The copilot could not answer.'), error: !m.content }))
        }
      }
    } catch {
      patch((m) => ({ ...m, content: m.content || 'Stopped.', error: !m.content }))
    } finally {
      patch((m) => ({ ...m, streaming: false }))
      setBusy(false)
      abort.current = null
    }
  }

  const providers = meta?.llm_providers ?? []
  const suggestions = SUGGESTIONS[page] ?? SUGGESTIONS['']

  return (
    <AnimatePresence>
      {open && (
        <motion.aside className="copilot" initial={{ x: 40, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: 40, opacity: 0 }}
                      transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }} aria-label="ValuAI copilot">
          <header className="copilot-head">
            <span className="copilot-avatar"><span className="orb-core" /></span>
            <div>
              <h3 className="display">ValuAI</h3>
              <p className="muted">{providers.length ? `${providers.join(' → ')} · offline analyst as backup` : 'Offline analyst · add an LLM key for free-form answers'}</p>
            </div>
            <div className="copilot-head-actions">
              {messages.length > 0 && (
                <button type="button" className="icon-btn" title="Clear conversation" onClick={() => setMessages([])}><IconReset size={15} /></button>
              )}
              <button type="button" className="icon-btn" title="Close" onClick={onClose}><IconClose size={16} /></button>
            </div>
          </header>
          {ticker ? (
            <div className="copilot-context">
              <span className="pill pill-gold">{ticker}</span>
              <span className="muted">{page || 'overview'} · {scenarioApi.modified ? 'your custom scenario' : 'baseline scenario'}</span>
            </div>
          ) : null}

          <div className="copilot-body" ref={scroller}>
            {!ticker ? (
              <div className="copilot-empty">
                <IconSpark size={26} />
                <p className="display">Open a company and ask me anything about it.</p>
                <p className="muted">I answer from the same numbers the models compute — your scenario, not generic defaults.</p>
                <Link to="/c/RELIANCE.NSE" className="btn btn-ghost" onClick={onClose}>Try Reliance Industries</Link>
              </div>
            ) : messages.length === 0 ? (
              <div className="copilot-empty">
                <IconSpark size={26} />
                <p className="display">What would you like to understand about {ticker}?</p>
                <div className="copilot-suggestions">
                  {suggestions.map((s) => <button key={s} type="button" onClick={() => send(s)}>{s}</button>)}
                </div>
              </div>
            ) : (
              messages.map((m) => (
                <div key={m.id} className={`msg msg-${m.role} ${m.error ? 'msg-error' : ''}`}>
                  {m.role === 'assistant' ? (
                    <>
                      {m.content ? (
                        <Suspense fallback={<p>{m.content}</p>}><Markdown>{m.content}</Markdown></Suspense>
                      ) : <div className="typing"><i /><i /><i /></div>}
                      {m.streaming && m.content && <span className="caret" />}
                      {m.provider && !m.streaming && (
                        <div className="msg-meta">{m.mode === 'offline' ? 'Rule-based offline analyst' : m.provider}{m.fallback ? ' · fallback' : ''}</div>
                      )}
                    </>
                  ) : (
                    <p>{m.content}</p>
                  )}
                </div>
              ))
            )}
          </div>

          {ticker && messages.length > 0 && !busy && (
            <div className="copilot-chips">
              {suggestions.slice(0, 3).map((s) => <button key={s} type="button" onClick={() => send(s)}>{s}</button>)}
            </div>
          )}
          <form className="copilot-input" onSubmit={(e) => { e.preventDefault(); send(input) }}>
            <textarea ref={inputRef} rows={2} value={input} disabled={!ticker} placeholder={ticker ? `Ask about ${ticker}…` : 'Open a company first'}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault()
                          send(input)
                        }
                      }} />
            {busy ? (
              <button type="button" className="send" onClick={() => abort.current?.abort()} aria-label="Stop"><IconStop size={16} /></button>
            ) : (
              <button type="submit" className="send" disabled={!input.trim() || !ticker} aria-label="Send"><IconSend size={16} /></button>
            )}
          </form>
        </motion.aside>
      )}
    </AnimatePresence>
  )
}
