import { describe, expect, it } from 'vitest'
import { parseSseChunk, scenarioBody } from './api'

describe('parseSseChunk', () => {
  it('parses complete frames and keeps the partial remainder', () => {
    const buffer = 'event: meta\ndata: {"provider":"offline"}\n\nevent: delta\ndata: {"text":"Hel"}\n\nevent: delta\ndata: {"te'
    const { events, rest } = parseSseChunk(buffer)
    expect(events).toEqual([
      { event: 'meta', data: { provider: 'offline' } },
      { event: 'delta', data: { text: 'Hel' } },
    ])
    expect(rest).toBe('event: delta\ndata: {"te')
  })

  it('completes a frame once the rest of it arrives', () => {
    const first = parseSseChunk('event: delta\ndata: {"te')
    const second = parseSseChunk(`${first.rest}xt":"lo"}\n\n`)
    expect(second.events).toEqual([{ event: 'delta', data: { text: 'lo' } }])
    expect(second.rest).toBe('')
  })

  it('skips malformed JSON frames instead of throwing', () => {
    const { events } = parseSseChunk('event: delta\ndata: {not json}\n\nevent: done\ndata: {}\n\n')
    expect(events).toEqual([{ event: 'done', data: {} }])
  })
})

describe('scenarioBody', () => {
  it('sends only the overrides alongside ticker and mode', () => {
    expect(scenarioBody('AAPL', 'local', { dcf: { wacc: 0.09 } })).toEqual({ ticker: 'AAPL', mode: 'local', dcf: { wacc: 0.09 } })
  })
})
