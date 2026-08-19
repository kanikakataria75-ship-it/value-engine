import { useState, useEffect } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { Dashboard } from './pages/Dashboard'
import { DcfPage } from './pages/DcfPage'
import { MnaPage } from './pages/MnaPage'
import { LboPage } from './pages/LboPage'
import { CompsPage } from './pages/CompsPage'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { ReportsPage } from './pages/ReportsPage'
import { CompanyPage } from './pages/CompanyPage'
import { DataPage } from './pages/DataPage'
import { AuditPage } from './pages/AuditPage'
import { RiskLabPage } from './pages/RiskLabPage'
import type { DataMode } from './types/api'

export function App() {
  const [ticker, setTicker] = useState('RELIANCE.NSE')
  const [dataMode, setDataModeState] = useState<DataMode>(() => {
    const saved = localStorage.getItem('valuengine_data_mode')
    return saved === 'live' ? 'live' : 'local'
  })

  const setDataMode = (mode: DataMode) => {
    setDataModeState(mode)
    localStorage.setItem('valuengine_data_mode', mode)
  }

  useEffect(() => {
    localStorage.setItem('valuengine_data_mode', dataMode)
  }, [dataMode])

  return (
    <BrowserRouter>
      <AppShell
        ticker={ticker}
        setTicker={setTicker}
        dataMode={dataMode}
        setDataMode={setDataMode}
      >
        <Routes>
          <Route path="/" element={<Dashboard ticker={ticker} dataMode={dataMode} />} />
          <Route path="/dcf" element={<DcfPage ticker={ticker} dataMode={dataMode} />} />
          <Route path="/mna" element={<MnaPage ticker={ticker} dataMode={dataMode} />} />
          <Route path="/lbo" element={<LboPage ticker={ticker} dataMode={dataMode} />} />
          <Route path="/comps" element={<CompsPage ticker={ticker} dataMode={dataMode} />} />
          <Route path="/analytics" element={<AnalyticsPage ticker={ticker} dataMode={dataMode} />} />
          <Route path="/risk-lab" element={<RiskLabPage ticker={ticker} dataMode={dataMode} />} />
          <Route path="/reports" element={<ReportsPage ticker={ticker} dataMode={dataMode} />} />
          <Route path="/company" element={<CompanyPage ticker={ticker} dataMode={dataMode} />} />
          <Route path="/data" element={<DataPage ticker={ticker} dataMode={dataMode} />} />
          <Route path="/audit" element={<AuditPage ticker={ticker} dataMode={dataMode} />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  )
}
