import { useMutation } from '@tanstack/react-query'
import { useCompanyContext } from '../../components/CompanyLayout'
import { IconDoc, IconDownload, IconSpark } from '../../components/icons'
import { Markdown } from '../../components/Markdown'
import { useToast } from '../../components/Toast'
import { Button, Empty, Orbit, PageTitle, Panel } from '../../components/ui'
import { api, scenarioBody } from '../../lib/api'
import type { MemoResult } from '../../lib/api-types'
import { shortDate } from '../../lib/format'
import { usePrefs } from '../../lib/prefs'
import { useScenario } from '../../lib/scenario'

const SECTIONS = ['Valuation', 'What the market is pricing in', 'Relative value', 'Transaction perspectives (LBO and M&A)', 'Key risks', 'Assumptions to challenge']

export function Report() {
  const { ticker, company } = useCompanyContext()
  const { mode } = usePrefs()
  const { scenario, modified } = useScenario(ticker)
  const toast = useToast()
  const memo = useMutation({
    mutationFn: async () => {
      const envelope = await api.memo(scenarioBody(ticker, mode, scenario))
      if (!envelope.data) throw new Error(envelope.errors[0] ?? 'Could not build the memo.')
      return envelope.data
    },
    onError: (error: Error) => toast(error.message, 'bad'),
  })
  const data: MemoResult | undefined = memo.data

  const download = (content: BlobPart, type: string, filename: string) => {
    const url = URL.createObjectURL(new Blob([content], { type }))
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 2000)
  }

  const exportExcel = async () => {
    toast('Building your Excel model…')
    const result = await api.excel(scenarioBody(ticker, mode, scenario))
    if ('error' in result) return toast(result.error, 'bad')
    download(result.blob, result.blob.type, result.filename)
    toast(`Downloaded ${result.filename}`)
  }

  return (
    <div className="page">
      <PageTitle eyebrow="Investment committee memo"
                 title={<>Everything, on <em>one page</em></>}
                 lede="A committee-ready memo written from the live model outputs for your current scenario. With an LLM key configured it is drafted by ValuAI; without one, a deterministic analyst template writes it from the same numbers."
                 actions={
                   <>
                     <Button variant="primary" icon={<IconSpark size={15} />} onClick={() => memo.mutate()} disabled={memo.isPending}>
                       {data ? 'Regenerate' : 'Write the memo'}
                     </Button>
                     <Button icon={<IconDownload size={15} />} onClick={exportExcel}>Excel model</Button>
                   </>
                 } />
      {memo.isPending && <div className="page-center memo-wait"><Orbit label="Reading the models and drafting" /></div>}
      {!memo.isPending && !data && (
        <Panel className="memo-preview">
          <div className="memo-preview-grid">
            <div className="memo-sheet" aria-hidden="true">
              <i /><i /><i /><i className="short" /><i /><i className="short" />
            </div>
            <div>
              <h3 className="display">{company.company_name} <em>· {ticker}</em></h3>
              <p className="muted">Scenario: {modified ? 'your custom assumptions' : 'the company baseline'}{scenario.mna ? ` · deal with ${scenario.mna.acquirer_ticker}` : ''} · {mode === 'live' ? 'live data' : 'local data'}</p>
              <ol className="memo-sections">{SECTIONS.map((s) => <li key={s}>{s}</li>)}</ol>
              <Button variant="primary" icon={<IconDoc size={15} />} onClick={() => memo.mutate()}>Write the memo</Button>
            </div>
          </div>
        </Panel>
      )}
      {!memo.isPending && data && (
        <article className="memo-paper">
          <header className="memo-meta">
            <span className="pill pill-gold">{data.mode === 'llm' ? `Drafted by ${data.provider}` : 'Analyst template (offline)'}</span>
            <span className="muted">Generated {shortDate(data.generated_at)} · {new Date(data.generated_at).toLocaleTimeString()}</span>
            <div className="memo-actions">
              <button type="button" className="link-quiet" onClick={() => window.print()}>Print / PDF</button>
              <button type="button" className="link-quiet" onClick={async () => {
                try { await navigator.clipboard.writeText(data.markdown); toast('Markdown copied') } catch { toast('Could not copy', 'bad') }
              }}>Copy markdown</button>
              <button type="button" className="link-quiet" onClick={() => download(data.markdown, 'text/markdown', `${ticker}_IC_memo.md`)}>Download .md</button>
            </div>
          </header>
          <Markdown className="memo-body">{data.markdown}</Markdown>
        </article>
      )}
      {memo.isError && !data && <Empty title="The memo could not be written" message={memo.error.message} />}
    </div>
  )
}
