import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { IconAlert, IconCheck } from './icons'

type Tone = 'ok' | 'bad'
interface ToastItem { id: number; message: string; tone: Tone }

const ToastContext = createContext<(message: string, tone?: Tone) => void>(() => {})

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const push = useCallback((message: string, tone: Tone = 'ok') => {
    const id = Date.now() + Math.random()
    setItems((all) => [...all, { id, message, tone }])
    window.setTimeout(() => setItems((all) => all.filter((t) => t.id !== id)), 3600)
  }, [])
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toasts" aria-live="polite">
        <AnimatePresence>
          {items.map((t) => (
            <motion.div key={t.id} className={`toast toast-${t.tone}`} initial={{ opacity: 0, y: 16, scale: 0.96 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 8, scale: 0.98 }}
                        transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}>
              {t.tone === 'ok' ? <IconCheck size={15} /> : <IconAlert size={15} />}
              {t.message}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)
