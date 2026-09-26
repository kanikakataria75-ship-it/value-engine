import { lazy } from 'react'
import { Route, Routes } from 'react-router-dom'
import { CompanyLayout } from './components/CompanyLayout'
import { Shell } from './components/Shell'
import { Home } from './pages/Home'

// Pages load on demand so the first paint only carries the shell and the Observatory.
const named = <K extends string>(loader: () => Promise<Record<K, React.ComponentType>>, name: K) =>
  lazy(() => loader().then((module) => ({ default: module[name] })))

const Radar = named(() => import('./pages/Radar'), 'Radar')
const Methodology = named(() => import('./pages/Methodology'), 'Methodology')
const NotFound = named(() => import('./pages/NotFound'), 'NotFound')
const Overview = named(() => import('./pages/company/Overview'), 'Overview')
const Valuation = named(() => import('./pages/company/Valuation'), 'Valuation')
const Expectations = named(() => import('./pages/company/Expectations'), 'Expectations')
const Comps = named(() => import('./pages/company/Comps'), 'Comps')
const Mna = named(() => import('./pages/company/Mna'), 'Mna')
const Lbo = named(() => import('./pages/company/Lbo'), 'Lbo')
const Risk = named(() => import('./pages/company/Risk'), 'Risk')
const Data = named(() => import('./pages/company/Data'), 'Data')
const Report = named(() => import('./pages/company/Report'), 'Report')

export default function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<Home />} />
        <Route path="radar" element={<Radar />} />
        <Route path="methodology" element={<Methodology />} />
        <Route path="c/:ticker" element={<CompanyLayout />}>
          <Route index element={<Overview />} />
          <Route path="valuation" element={<Valuation />} />
          <Route path="expectations" element={<Expectations />} />
          <Route path="comps" element={<Comps />} />
          <Route path="mna" element={<Mna />} />
          <Route path="lbo" element={<Lbo />} />
          <Route path="risk" element={<Risk />} />
          <Route path="data" element={<Data />} />
          <Route path="report" element={<Report />} />
          <Route path="*" element={<NotFound />} />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
