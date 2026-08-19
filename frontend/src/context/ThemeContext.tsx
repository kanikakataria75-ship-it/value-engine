import React, { createContext, useContext, useState, useEffect } from 'react'

export type Theme = 'purple' | 'white' | 'dark' | 'amber'

export interface ThemeColors {
  primary: string
  secondary: string
  downside: string
  median: string
  market: string
  grid: string
  text: string
  textMuted: string
  cardBg: string
  tooltipBg: string
}

const themeColorPalettes: Record<Theme, ThemeColors> = {
  purple: {
    primary: '#6366f1',
    secondary: '#8b5cf6',
    downside: 'rgba(239, 68, 68, 0.8)',
    median: '#10b981',
    market: '#f59e0b',
    grid: 'rgba(255, 255, 255, 0.06)',
    text: '#f8fafc',
    textMuted: '#64748b',
    cardBg: '#0f172a',
    tooltipBg: '#090e1c',
  },
  white: {
    primary: '#2563eb',
    secondary: '#7c3aed',
    downside: 'rgba(220, 38, 38, 0.85)',
    median: '#059669',
    market: '#d97706',
    grid: 'rgba(0, 0, 0, 0.07)',
    text: '#0f172a',
    textMuted: '#64748b',
    cardBg: '#ffffff',
    tooltipBg: '#ffffff',
  },
  dark: {
    primary: '#3b82f6',
    secondary: '#6366f1',
    downside: 'rgba(239, 68, 68, 0.8)',
    median: '#10b981',
    market: '#f59e0b',
    grid: 'rgba(255, 255, 255, 0.08)',
    text: '#f9fafb',
    textMuted: '#9ca3af',
    cardBg: '#1f2937',
    tooltipBg: '#111827',
  },
  amber: {
    primary: '#f59e0b',
    secondary: '#fbbf24',
    downside: 'rgba(239, 68, 68, 0.8)',
    median: '#10b981',
    market: '#38bdf8',
    grid: 'rgba(245, 158, 11, 0.08)',
    text: '#fef3c7',
    textMuted: '#a88d67',
    cardBg: '#1c180e',
    tooltipBg: '#141008',
  },
}

interface ThemeContextType {
  theme: Theme
  setTheme: (t: Theme) => void
  themeColors: ThemeColors
}

const ThemeContext = createContext<ThemeContextType>({
  theme: 'purple',
  setTheme: () => {},
  themeColors: themeColorPalettes.purple,
})

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [theme, setThemeState] = useState<Theme>(() => {
    const saved = localStorage.getItem('valuengine_theme')
    if (saved === 'white' || saved === 'dark' || saved === 'amber' || saved === 'purple') {
      return saved
    }
    return 'purple'
  })

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme)
    localStorage.setItem('valuengine_theme', newTheme)
    document.documentElement.setAttribute('data-theme', newTheme)
  }

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  return (
    <ThemeContext.Provider value={{ theme, setTheme, themeColors: themeColorPalettes[theme] }}>
      {children}
    </ThemeContext.Provider>
  )
}

export const useTheme = () => useContext(ThemeContext)
