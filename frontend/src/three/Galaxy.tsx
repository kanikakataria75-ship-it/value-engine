import { useEffect, useMemo, useRef, useState, type RefObject } from 'react'
import { Canvas, useFrame, useThree, type ThreeEvent } from '@react-three/fiber'
import { Html, OrbitControls } from '@react-three/drei'
import { Bloom, EffectComposer, Vignette } from '@react-three/postprocessing'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import * as THREE from 'three'
import type { RadarRow } from '../lib/api-types'
import { money, pct, points as pts } from '../lib/format'

/* The Expectations Galaxy.
   Every company is a star. Arms are sectors; distance from the core falls with market cap (USD);
   height above or below the disc is the expectations gap - how much faster (or slower) the share
   price assumes the company will grow than it actually has. The disc is the plane of history. */

export interface GalaxyFilter {
  country: 'all' | 'United States' | 'India'
  sector: string | null
}

interface Star {
  row: RadarRow
  position: THREE.Vector3
  color: THREE.Color
  size: number
  arm: number
}

const PALETTE = {
  slowdown: new THREE.Color('#5fd4c4'),
  neutral: new THREE.Color('#f3eee4'),
  optimistic: new THREE.Color('#e6c27d'),
  extreme: new THREE.Color('#ff7c5c'),
  unreachable: new THREE.Color('#b9a8ff'),
  muted: new THREE.Color('#2a2e3a'),
}
const HEIGHT_SCALE = 5.5
const GAP_CLAMP = 0.35

function gapColor(gap: number | null | undefined): THREE.Color {
  if (gap === null || gap === undefined || !Number.isFinite(gap)) return PALETTE.neutral.clone().multiplyScalar(0.55)
  const g = Math.max(-GAP_CLAMP, Math.min(GAP_CLAMP, gap)) / GAP_CLAMP
  if (g < 0) return PALETTE.neutral.clone().lerp(PALETTE.slowdown, Math.min(1, -g * 1.4))
  const warm = PALETTE.neutral.clone().lerp(PALETTE.optimistic, Math.min(1, g * 1.6))
  return g > 0.7 ? warm.lerp(PALETTE.extreme, (g - 0.7) / 0.3) : warm
}

export function layoutGalaxy(rows: RadarRow[]): { stars: Star[]; sectors: { name: string; angle: number; count: number }[] } {
  const bySector = new Map<string, RadarRow[]>()
  for (const row of rows) {
    const sector = row.sector ?? 'Unclassified'
    bySector.set(sector, [...(bySector.get(sector) ?? []), row])
  }
  const sectors = [...bySector.entries()].sort((a, b) => b[1].length - a[1].length)
  const stars: Star[] = []
  const armCount = sectors.length
  sectors.forEach(([, members], arm) => {
    const base = (arm / armCount) * Math.PI * 2
    const sorted = [...members].sort((a, b) => (b.market_cap_usd ?? 0) - (a.market_cap_usd ?? 0))
    sorted.forEach((row, rank) => {
      const radius = 1.25 + 0.62 * Math.sqrt(rank) + ((rank * 37) % 11) / 55
      const angle = base + radius * 0.34 + (((rank * 53) % 7) - 3) * 0.018
      const gap = row.model === 'excess_return'
        ? (row.implied_roe != null && row.current_roe != null ? (row.implied_roe - row.current_roe) * 2 : null)
        : row.expectations_gap
      let y = gap == null ? 0 : Math.max(-GAP_CLAMP, Math.min(GAP_CLAMP, gap)) / GAP_CLAMP * (HEIGHT_SCALE / 2)
      let color = gapColor(gap)
      if (row.status === 'NOT_REACHABLE') {
        y = HEIGHT_SCALE / 2 + 0.35
        color = PALETTE.unreachable.clone()
      }
      const cap = row.market_cap_usd ?? 1e9
      stars.push({
        row, arm, color,
        position: new THREE.Vector3(Math.cos(angle) * radius, y, Math.sin(angle) * radius),
        size: 0.045 + 0.034 * Math.log10(cap / 1e9 + 1),
      })
    })
  })
  return { stars, sectors: sectors.map(([name, members], arm) => ({ name, angle: (arm / armCount) * Math.PI * 2, count: members.length })) }
}

function visible(star: Star, filter: GalaxyFilter): boolean {
  if (filter.country !== 'all' && star.row.country !== filter.country) return false
  if (filter.sector && star.row.sector !== filter.sector) return false
  return true
}

function Stars({ stars, filter, hovered, selected, onHover, onSelect, onOpen }: {
  stars: Star[]; filter: GalaxyFilter; hovered: number | null; selected: string | null
  onHover: (index: number | null) => void; onSelect: (star: Star) => void; onOpen: (star: Star) => void
}) {
  const mesh = useRef<THREE.InstancedMesh>(null)
  const matrix = useMemo(() => new THREE.Matrix4(), [])
  const scratch = useMemo(() => new THREE.Color(), [])
  const time = useRef(0)

  useFrame((_, delta) => {
    const m = mesh.current
    if (!m) return
    time.current += delta
    stars.forEach((star, i) => {
      const shown = visible(star, filter)
      const active = i === hovered || star.row.ticker === selected
      const twinkle = 1 + 0.08 * Math.sin(time.current * 2.1 + i * 1.7)
      const scale = star.size * (active ? 2.3 : shown ? twinkle : 0.55)
      matrix.makeScale(scale, scale, scale).setPosition(star.position)
      m.setMatrixAt(i, matrix)
      scratch.copy(shown ? star.color : PALETTE.muted)
      if (active) scratch.multiplyScalar(2.2)
      else if (shown) scratch.multiplyScalar(1.35)
      m.setColorAt(i, scratch)
    })
    m.instanceMatrix.needsUpdate = true
    if (m.instanceColor) m.instanceColor.needsUpdate = true
  })

  return (
    <instancedMesh
      ref={mesh}
      args={[undefined, undefined, stars.length]}
      onPointerMove={(e: ThreeEvent<PointerEvent>) => {
        e.stopPropagation()
        if (e.instanceId !== undefined && visible(stars[e.instanceId], filter)) onHover(e.instanceId)
      }}
      onPointerOut={() => onHover(null)}
      onClick={(e: ThreeEvent<MouseEvent>) => {
        e.stopPropagation()
        if (e.instanceId !== undefined && visible(stars[e.instanceId], filter)) onSelect(stars[e.instanceId])
      }}
      onDoubleClick={(e: ThreeEvent<MouseEvent>) => {
        e.stopPropagation()
        if (e.instanceId !== undefined && visible(stars[e.instanceId], filter)) onOpen(stars[e.instanceId])
      }}
    >
      <sphereGeometry args={[1, 18, 14]} />
      <meshBasicMaterial toneMapped={false} />
    </instancedMesh>
  )
}

function Stems({ stars, filter }: { stars: Star[]; filter: GalaxyFilter }) {
  const geometry = useMemo(() => {
    const positions: number[] = []
    const colors: number[] = []
    for (const star of stars) {
      if (!visible(star, filter) || Math.abs(star.position.y) < 0.04) continue
      const { x, y, z } = star.position
      positions.push(x, 0, z, x, y, z)
      const c = star.color
      colors.push(c.r * 0.12, c.g * 0.12, c.b * 0.12, c.r * 0.7, c.g * 0.7, c.b * 0.7)
    }
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
    g.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3))
    return g
  }, [stars, filter])
  useEffect(() => () => geometry.dispose(), [geometry])
  return (
    <lineSegments geometry={geometry}>
      <lineBasicMaterial vertexColors transparent opacity={0.55} depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
    </lineSegments>
  )
}

function Disc({ sectors, highlight }: { sectors: { name: string; angle: number }[]; highlight: string | null }) {
  const rings = useMemo(() => [2, 4, 6, 8, 10].map((radius, i) => {
    const pts = Array.from({ length: 161 }, (_, k) => {
      const a = (k / 160) * Math.PI * 2
      return new THREE.Vector3(Math.cos(a) * radius, 0, Math.sin(a) * radius)
    })
    const material = new THREE.LineBasicMaterial({ color: '#e6c27d', transparent: true, opacity: 0.07 - i * 0.008, depthWrite: false })
    return new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(pts), material)
  }), [])
  const arms = useMemo(() => sectors.map((sector) => {
    const pts = Array.from({ length: 80 }, (_, i) => {
      const r = 1.1 + (i / 79) * 9.5
      const a = sector.angle + r * 0.34
      return new THREE.Vector3(Math.cos(a) * r, 0, Math.sin(a) * r)
    })
    const material = new THREE.LineBasicMaterial({ color: '#8f897e', transparent: true, opacity: 0.09, depthWrite: false })
    return { name: sector.name, line: new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), material) }
  }), [sectors])
  useEffect(() => {
    for (const arm of arms) {
      const material = arm.line.material as THREE.LineBasicMaterial
      const on = highlight === arm.name
      material.color.set(on ? '#f6dca6' : '#8f897e')
      material.opacity = on ? 0.5 : 0.09
    }
  }, [arms, highlight])
  useEffect(() => () => {
    for (const obj of [...rings, ...arms.map((a) => a.line)]) {
      obj.geometry.dispose()
      ;(obj.material as THREE.Material).dispose()
    }
  }, [rings, arms])
  return (
    <group>
      {rings.map((ring, i) => <primitive key={i} object={ring} />)}
      {arms.map((arm) => <primitive key={arm.name} object={arm.line} />)}
    </group>
  )
}

function Nebula({ stars }: { stars: Star[] }) {
  const geometry = useMemo(() => {
    const count = 5200
    const positions = new Float32Array(count * 3)
    const colors = new Float32Array(count * 3)
    const armCount = Math.max(1, new Set(stars.map((s) => s.arm)).size)
    for (let i = 0; i < count; i++) {
      const arm = i % armCount
      const r = 0.4 + Math.pow(Math.random(), 0.65) * 10.5
      const spread = (Math.random() - 0.5) * (0.35 + r * 0.04)
      const a = (arm / armCount) * Math.PI * 2 + r * 0.34 + spread
      const y = (Math.random() - 0.5) * 0.25 * Math.exp(-r / 6)
      positions.set([Math.cos(a) * r, y, Math.sin(a) * r], i * 3)
      const warmth = Math.exp(-r / 3)
      const c = new THREE.Color('#7ee6d8').lerp(new THREE.Color('#e6c27d'), warmth).multiplyScalar(0.28 + warmth * 0.5)
      colors.set([c.r, c.g, c.b], i * 3)
    }
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    g.setAttribute('color', new THREE.BufferAttribute(colors, 3))
    return g
  }, [stars])
  const ref = useRef<THREE.Points>(null)
  useFrame((_, delta) => {
    if (ref.current) ref.current.rotation.y += delta * 0.012
  })
  return (
    <points ref={ref} geometry={geometry}>
      <pointsMaterial size={0.05} vertexColors transparent opacity={0.8} depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
    </points>
  )
}

function Starfield() {
  const geometry = useMemo(() => {
    const count = 3000
    const positions = new Float32Array(count * 3)
    for (let i = 0; i < count; i++) {
      const v = new THREE.Vector3().randomDirection().multiplyScalar(40 + Math.random() * 60)
      positions.set([v.x, v.y, v.z], i * 3)
    }
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    return g
  }, [])
  return (
    <points geometry={geometry}>
      <pointsMaterial size={0.09} color="#d9d2c3" transparent opacity={0.5} depthWrite={false} />
    </points>
  )
}

function Core() {
  const ref = useRef<THREE.Mesh>(null)
  useFrame((state) => {
    if (ref.current) ref.current.scale.setScalar(0.34 + 0.03 * Math.sin(state.clock.elapsedTime * 1.4))
  })
  return (
    <mesh ref={ref}>
      <sphereGeometry args={[1, 32, 24]} />
      <meshBasicMaterial color={new THREE.Color('#fff1cf').multiplyScalar(2.4)} toneMapped={false} />
    </mesh>
  )
}

function CameraFlight({ target, controls, reduced }: {
  target: THREE.Vector3 | null; controls: RefObject<OrbitControlsImpl>; reduced: boolean
}) {
  const camera = useThree((state) => state.camera)
  const home = useMemo(() => ({ position: new THREE.Vector3(0, 7.5, 15.5), target: new THREE.Vector3(0, 0, 0) }), [])
  const goal = useRef<{ position: THREE.Vector3; target: THREE.Vector3 } | null>(null)

  useEffect(() => {
    if (target) {
      const outward = target.clone().setY(0).normalize()
      goal.current = {
        target: target.clone(),
        position: target.clone().add(outward.multiplyScalar(3.2)).add(new THREE.Vector3(0, 1.4, 0)),
      }
    } else {
      goal.current = { position: home.position.clone(), target: home.target.clone() }
    }
  }, [target, home])

  useFrame((_, delta) => {
    const c = controls.current
    if (!c || !goal.current) return
    const k = reduced ? 1 : 1 - Math.pow(0.02, delta)
    camera.position.lerp(goal.current.position, k)
    c.target.lerp(goal.current.target, k)
    c.update()
    if (camera.position.distanceTo(goal.current.position) < 0.01) goal.current = null
  })
  return null
}

/** Renders the galaxy right of centre on wide screens, so it sits beside the hero copy instead of under it. */
function ViewShift() {
  const camera = useThree((state) => state.camera) as THREE.PerspectiveCamera
  const width = useThree((state) => state.size.width)
  const height = useThree((state) => state.size.height)
  useEffect(() => {
    const shift = width > 1024 ? 0.1 : 0
    camera.setViewOffset(width, height, -width * shift, 0, width, height)
    camera.updateProjectionMatrix()
    return () => {
      camera.clearViewOffset()
    }
  }, [camera, width, height])
  return null
}

export default function Galaxy({ rows, filter, selected, reducedMotion, onSelect, onOpen, onHover }: {
  rows: RadarRow[]; filter: GalaxyFilter; selected: string | null; reducedMotion: boolean
  onSelect: (row: RadarRow | null) => void; onOpen: (row: RadarRow) => void; onHover?: (row: RadarRow | null) => void
}) {
  const { stars, sectors } = useMemo(() => layoutGalaxy(rows), [rows])
  const [hovered, setHovered] = useState<number | null>(null)
  const controls = useRef<OrbitControlsImpl>(null)
  const selectedStar = stars.find((s) => s.row.ticker === selected) ?? null
  const hoveredStar = hovered !== null ? stars[hovered] : null
  const interacting = hovered !== null || selected !== null
  // Wheel zoom only while Ctrl / Cmd is held, so scrolling over the hero still scrolls the page.
  const [zoomKey, setZoomKey] = useState(false)

  useEffect(() => {
    const sync = (event: KeyboardEvent) => setZoomKey(event.ctrlKey || event.metaKey)
    const release = () => setZoomKey(false)
    window.addEventListener('keydown', sync)
    window.addEventListener('keyup', sync)
    window.addEventListener('blur', release)
    return () => {
      window.removeEventListener('keydown', sync)
      window.removeEventListener('keyup', sync)
      window.removeEventListener('blur', release)
    }
  }, [])

  useEffect(() => {
    onHover?.(hoveredStar?.row ?? null)
    document.body.style.cursor = hoveredStar ? 'pointer' : ''
    return () => { document.body.style.cursor = '' }
  }, [hoveredStar, onHover])

  return (
    <Canvas className="galaxy-canvas" dpr={[1, 2]} camera={{ fov: 42, position: [0, 7.5, 15.5], near: 0.1, far: 300 }}
            onPointerMissed={() => onSelect(null)} gl={{ antialias: true }}>
      <color attach="background" args={['#030409']} />
      <fog attach="fog" args={['#030409', 22, 60]} />
      <ViewShift />
      <Starfield />
      <Nebula stars={stars} />
      <Disc sectors={sectors} highlight={filter.sector} />
      <Stems stars={stars} filter={filter} />
      <Core />
      <Stars stars={stars} filter={filter} hovered={hovered} selected={selected} onHover={setHovered}
             onSelect={(star) => onSelect(star.row)} onOpen={(star) => onOpen(star.row)} />

      {sectors.map((sector) => {
        const r = 11.2
        const a = sector.angle + r * 0.34
        const dim = filter.sector && filter.sector !== sector.name
        return (
          <Html key={sector.name} position={[Math.cos(a) * r, 0.2, Math.sin(a) * r]} center zIndexRange={[5, 0]}
                style={{ pointerEvents: 'none' }}>
            <div className={`galaxy-sector ${dim ? 'dim' : ''} ${filter.sector === sector.name ? 'on' : ''}`}>
              {sector.name}<span>{sector.count}</span>
            </div>
          </Html>
        )
      })}

      {hoveredStar && (
        <Html position={hoveredStar.position} zIndexRange={[20, 10]} style={{ pointerEvents: 'none' }}>
          <StarCard star={hoveredStar} />
        </Html>
      )}
      {selectedStar && selectedStar !== hoveredStar && (
        <Html position={selectedStar.position} zIndexRange={[20, 10]} style={{ pointerEvents: 'none' }}>
          <div className="galaxy-ping" />
        </Html>
      )}

      <OrbitControls ref={controls} makeDefault enablePan={false} enableZoom={zoomKey} enableDamping dampingFactor={0.06} minDistance={3}
                     maxDistance={28} maxPolarAngle={Math.PI * 0.49} autoRotate={!reducedMotion && !interacting}
                     autoRotateSpeed={0.28} rotateSpeed={0.55} zoomSpeed={0.7} />
      <CameraFlight target={selectedStar ? selectedStar.position : null} controls={controls} reduced={reducedMotion} />
      <EffectComposer multisampling={0}>
        <Bloom intensity={1.05} luminanceThreshold={0.22} luminanceSmoothing={0.3} mipmapBlur radius={0.65} />
        <Vignette eskil={false} offset={0.22} darkness={0.75} />
      </EffectComposer>
    </Canvas>
  )
}

function StarCard({ star }: { star: Star }) {
  const r = star.row
  const bank = r.model === 'excess_return'
  return (
    <div className="star-card">
      <div className="star-card-head">
        <span className="star-card-ticker mono">{r.ticker.replace('.NSE', '')}</span>
        <span className="star-card-country">{r.country === 'India' ? 'NSE' : 'US'}</span>
      </div>
      <div className="star-card-name">{r.company_name}</div>
      <div className="star-card-row"><span>Price</span><b className="num">{money(r.price, r.currency, { precise: true })}</b></div>
      {bank ? (
        <>
          <div className="star-card-row"><span>ROE priced in</span><b className="num">{pct(r.implied_roe)}</b></div>
          <div className="star-card-row"><span>Current ROE</span><b className="num">{pct(r.current_roe)}</b></div>
        </>
      ) : r.status === 'NOT_REACHABLE' ? (
        <div className="star-card-note">Price implies more than 60% annual growth at today's margin — beyond the model's range.</div>
      ) : (
        <>
          <div className="star-card-row"><span>Growth priced in</span><b className="num">{pct(r.implied_growth)}</b></div>
          <div className="star-card-row"><span>3-yr history</span><b className="num">{pct(r.historical_cagr)}</b></div>
          <div className="star-card-row"><span>Gap</span><b className={`num ${(r.expectations_gap ?? 0) > 0 ? 'gold' : 'pos'}`}>{pts(r.expectations_gap)}</b></div>
        </>
      )}
      <div className="star-card-hint">Click to focus · double-click to open</div>
    </div>
  )
}
