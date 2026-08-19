import React, { useState, useRef, useEffect } from 'react'
import { api } from '../services/api'
import type { DataMode, CopilotResponse } from '../types/api'

interface CopilotPanelProps {
  ticker: string
  mode: DataMode
  isOpen: boolean
  onClose: () => void
  pageContext: string
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  loading?: boolean
  error?: boolean
  meta?: {
    provider?: string
    isFallback?: boolean
    contextTicker?: string
  }
}

const QUICK_PROMPTS = [
  "Explain this valuation",
  "What is driving the DCF?",
  "Compare DCF vs Comps",
  "What are the biggest risks?",
  "What's the bull case?",
  "Which assumptions matter most?"
]

export const CopilotPanel: React.FC<CopilotPanelProps> = ({ ticker, mode, isOpen, onClose, pageContext }) => {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSend = async (text: string) => {
    if (!text.trim() || isLoading) return
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: text.trim() }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsLoading(true)
    
    const loadingId = Date.now().toString() + '-loading'
    setMessages(prev => [...prev, { id: loadingId, role: 'assistant', content: '', loading: true }])

    try {
      const res = await api.copilot(text, ticker, "current_company", pageContext)
      setMessages(prev => prev.filter(m => m.id !== loadingId))
      
      if (res.status === 'VALID' && res.data) {
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'assistant',
          content: res.data.answer,
          meta: {
            provider: res.data.provider,
            isFallback: res.data.is_fallback,
            contextTicker: res.data.context_used?.ticker
          }
        }])
      } else {
        const errorContent = res.errors && res.errors.length > 0 
          ? res.errors.join("\n") 
          : "AI Copilot is temporarily unavailable.";
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'assistant',
          content: errorContent,
          error: true
        }])
      }
    } catch (err: any) {
      setMessages(prev => prev.filter(m => m.id !== loadingId))
      
      let errorMsg = "An unexpected error occurred.";
      if (err.message) {
          if (err.message.includes('404')) {
              errorMsg = "Copilot backend unavailable. Check backend connection.";
          } else {
              errorMsg = err.message;
          }
      }
      
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: errorMsg,
        error: true
      }])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend(input)
    }
  }

  if (!isOpen) return null

  return (
    <div className="copilot-panel">
      <div className="copilot-header">
        <div>
          <h2>VALUAI</h2>
          <p>Financial Copilot &bull; <span className={messages.some(m => m.error) && messages.length === 1 ? 'warning' : 'positive'}>
            {messages.length === 0 ? 'Connecting...' : (messages.some(m => m.meta?.provider) ? 'Provider Ready' : 'Connected')}
          </span></p>
        </div>
        <button className="icon-btn" onClick={onClose} title="Close Panel">×</button>
      </div>

      <div className="copilot-meta">
        <span>{ticker || 'NO TICKER'} &bull; {mode.toUpperCase()}</span>
        <span>Context: {pageContext.toUpperCase()}</span>
      </div>

      <div className="copilot-messages">
        {messages.length === 0 ? (
          <div className="copilot-empty">
            <p>I am ValuAI, your institutional financial analyst.</p>
            <p className="sub">I can explain DCF models, LBO returns, risk metrics, and comparable analyses using the current verified context.</p>
            <div className="quick-prompts">
              {QUICK_PROMPTS.map(p => (
                <button key={p} onClick={() => handleSend(p)}>{p}</button>
              ))}
            </div>
          </div>
        ) : (
          messages.map(msg => (
            <div key={msg.id} className={`chat-message ${msg.role} ${msg.error ? 'error' : ''}`}>
              <div className="message-content">
                {msg.loading ? (
                  <div className="loading-dots"><span>.</span><span>.</span><span>.</span></div>
                ) : (
                  msg.content.split('\n').map((line, i) => <p key={i}>{line}</p>)
                )}
              </div>
              {msg.meta && (
                <div className="message-meta">
                  <span>Provider: {msg.meta.provider} {msg.meta.isFallback && '· Fallback'}</span>
                  <span>Context: {msg.meta.contextTicker}</span>
                </div>
              )}
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="copilot-input-area">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask ValuAI about this valuation..."
          disabled={isLoading || !ticker}
          rows={2}
        />
        <div className="input-actions">
          <button className="clear-btn" onClick={() => setMessages([])} disabled={isLoading || messages.length === 0}>Clear</button>
          <button className="send-btn" onClick={() => handleSend(input)} disabled={!input.trim() || isLoading || !ticker}>Send</button>
        </div>
      </div>
    </div>
  )
}
