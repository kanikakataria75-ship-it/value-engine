import { useEffect, useMemo } from 'react'
import { Canvas } from '@react-three/fiber'
import { Html, Line, OrbitControls } from '@react-three/drei'
import { Bloom, EffectComposer, Vignette } from '@react-three/postprocessing'
import * as THREE from 'three'
import type { DcfExpectations } from '../lib/api-types'
import { money, pct } from '../lib/format'

/* Value as a landscape over (revenue growth x target margin). The market price is a glass plane;
   the gold curve where they intersect is the set of futures that exactly justify today's price. */

const SIZE = 6
const HEIGHT = 3.4

export interface SurfaceLayers {
  cloud: boolean
  history: boolean
  frontier: boolean
}

function robustRange(values: number[]): [number, number] {
  const sorted = [...values].sort((a, b) => a - b)
  const lo = sorted[Math.floor(sorted.length * 0.02)] ?? 0
  const hi = sorted[Math.ceil(sorted.length * 0.98) - 1] ?? 1
  return lo === hi ? [lo - 1, hi + 1] : [lo, hi]
}

function useMapping(data: DcfExpectations) {
  return useMemo(() => {
    const { growth, margin, values } = data.surface
    const flat = values.flat().filter((v): v is number => v !== null && Number.isFinite(v))
    const [vLow, vHigh] = robustRange([...flat, data.market_price])
    const gx = (g: number) => ((g - growth[0]) / (growth[growth.length - 1] - growth[0]) - 0.5) * SIZE
    const mz = (m: number) => (0.5 - (m - margin[0]) / (margin[margin.length - 1] - margin[0])) * SIZE
    const vy = (v: number) => Math.max(-0.05, Math.min(HEIGHT * 1.08, ((v - vLow) / (vHigh - vLow)) * HEIGHT))
    const interpolate = (g: number, m: number): number | null => {
      const fi = ((g - growth[0]) / (growth[growth.length - 1] - growth[0])) * (growth.length - 1)
      const fj = ((m - margin[0]) / (margin[margin.length - 1] - margin[0])) * (margin.length - 1)
      if (fi < 0 || fj < 0 || fi > growth.length - 1 || fj > margin.length - 1) return null
      const i0 = Math.floor(fi), j0 = Math.floor(fj)
      const i1 = Math.min(i0 + 1, growth.length - 1), j1 = Math.min(j0 + 1, margin.length - 1)
      const [a, b, c, d] = [values[j0][i0], values[j0][i1], values[j1][i0], values[j1][i1]]
      if ([a, b, c, d].some((v) => v === null)) return null
      const tx = fi - i0, ty = fj - j0
      return (a! * (1 - tx) + b! * tx) * (1 - ty) + (c! * (1 - tx) + d! * tx) * ty
    }
    return { gx, mz, vy, vLow, vHigh, interpolate }
  }, [data])
}

function Surface({ data, map }: { data: DcfExpectations; map: ReturnType<typeof useMapping> }) {
  const geometry = useMemo(() => {
    const { growth, margin, values } = data.surface
    const nx = growth.length, nz = margin.length
    const positions = new Float32Array(nx * nz * 3)
    const colors = new Float32Array(nx * nz * 3)
    const below = new THREE.Color('#ff7c5c'), deep = new THREE.Color('#8f2f1c'), at = new THREE.Color('#f3eee4')
    const above = new THREE.Color('#e6c27d'), far = new THREE.Color('#fff1cf')
    const span = Math.max(Math.abs(map.vHigh - data.market_price), Math.abs(data.market_price - map.vLow), 1e-9)
    for (let j = 0; j < nz; j++) {
      for (let i = 0; i < nx; i++) {
        const k = j * nx + i
        const v = values[j][i] ?? map.vLow
        positions.set([map.gx(growth[i]), map.vy(v), map.mz(margin[j])], k * 3)
        const d = (v - data.market_price) / span
        const c = d < 0 ? at.clone().lerp(below, Math.min(1, -d * 3)) : at.clone().lerp(above, Math.min(1, d * 3))
        if (d < -0.4) c.lerp(deep, Math.min(1, (-d - 0.4) / 0.6))
        if (d > 0.6) c.lerp(far, Math.min(1, (d - 0.6) / 0.4))
        c.multiplyScalar(0.6 + 0.4 * Math.min(1, Math.abs(d) * 2))
        colors.set([c.r, c.g, c.b], k * 3)
      }
    }
    const indices: number[] = []
    for (let j = 0; j < nz - 1; j++) {
      for (let i = 0; i < nx - 1; i++) {
        const a = j * nx + i, b = a + 1, c = a + nx, d = c + 1
        indices.push(a, c, b, b, c, d)
      }
    }
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    g.setAttribute('color', new THREE.BufferAttribute(colors, 3))
    g.setIndex(indices)
    g.computeVertexNormals()
    return g
  }, [data, map])
  const wire = useMemo(() => new THREE.WireframeGeometry(geometry), [geometry])
  useEffect(() => () => { geometry.dispose(); wire.dispose() }, [geometry, wire])
  return (
    <group>
      <mesh geometry={geometry}>
        <meshStandardMaterial vertexColors side={THREE.DoubleSide} roughness={0.55} metalness={0.15} transparent opacity={0.92} />
      </mesh>
      <lineSegments geometry={wire}>
        <lineBasicMaterial color="#f6dca6" transparent opacity={0.07} depthWrite={false} />
      </lineSegments>
    </group>
  )
}

function PricePlane({ y, label }: { y: number; label: string }) {
  const edge = useMemo(() => {
    const h = SIZE / 2 + 0.15
    return [[-h, y, -h], [h, y, -h], [h, y, h], [-h, y, h], [-h, y, -h]] as [number, number, number][]
  }, [y])
  return (
    <group>
      <mesh position={[0, y, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[SIZE + 0.3, SIZE + 0.3]} />
        <meshPhysicalMaterial color="#f3eee4" transparent opacity={0.1} roughness={0.1} metalness={0} side={THREE.DoubleSide} depthWrite={false} />
      </mesh>
      <Line points={edge} color="#f3eee4" lineWidth={1} transparent opacity={0.45} />
      <Html position={[-SIZE / 2 - 0.15, y + 0.05, -SIZE / 2 - 0.15]} center style={{ pointerEvents: 'none' }}>
        <div className="surface-tag price">{label}</div>
      </Html>
    </group>
  )
}

function Axes({ data, map }: { data: DcfExpectations; map: ReturnType<typeof useMapping> }) {
  const { growth, margin } = data.surface
  const h = SIZE / 2
  const gTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => growth[0] + f * (growth[growth.length - 1] - growth[0]))
  const mTicks = [0, 0.5, 1].map((f) => margin[0] + f * (margin[margin.length - 1] - margin[0]))
  const frame: [number, number, number][] = [[-h, 0, h], [h, 0, h], [h, 0, -h], [-h, 0, -h], [-h, 0, h]]
  return (
    <group>
      <Line points={frame} color="#8f897e" lineWidth={1} transparent opacity={0.4} />
      <Line points={[[-h, 0, -h], [-h, HEIGHT, -h]]} color="#8f897e" lineWidth={1} transparent opacity={0.4} />
      {gTicks.map((g) => (
        <Html key={`g${g}`} position={[map.gx(g), -0.05, h + 0.45]} center style={{ pointerEvents: 'none' }}>
          <div className="surface-axis">{pct(g, 0)}</div>
        </Html>
      ))}
      <Html position={[0, -0.05, h + 1.05]} center style={{ pointerEvents: 'none' }}>
        <div className="surface-axis-title">Revenue growth · per year</div>
      </Html>
      {mTicks.map((m) => (
        <Html key={`m${m}`} position={[h + 0.5, -0.05, map.mz(m)]} center style={{ pointerEvents: 'none' }}>
          <div className="surface-axis">{pct(m, 0)}</div>
        </Html>
      ))}
      <Html position={[h + 1.15, -0.05, 0]} center style={{ pointerEvents: 'none' }}>
        <div className="surface-axis-title vertical">EBITDA margin</div>
      </Html>
      {[0, 0.5, 1].map((f) => (
        <Html key={`v${f}`} position={[-h - 0.2, f * HEIGHT, -h]} center style={{ pointerEvents: 'none' }}>
          <div className="surface-axis">{money(map.vLow + f * (map.vHigh - map.vLow), data.currency)}</div>
        </Html>
      ))}
    </group>
  )
}

export default function ValueSurface({ data, layers, autoRotate }: { data: DcfExpectations; layers: SurfaceLayers; autoRotate: boolean }) {
  const map = useMapping(data)
  const priceY = map.vy(data.market_price)
  const frontier = useMemo(
    () => data.frontier
      .filter((p) => p.revenue_growth >= data.surface.growth[0] && p.revenue_growth <= data.surface.growth[data.surface.growth.length - 1]
        && p.required_margin >= data.surface.margin[0] && p.required_margin <= data.surface.margin[data.surface.margin.length - 1])
      .map((p) => [map.gx(p.revenue_growth), priceY + 0.012, map.mz(p.required_margin)] as [number, number, number]),
    [data, map, priceY],
  )
  const cloud = useMemo(() => {
    const beats: number[] = [], misses: number[] = []
    for (const p of data.cloud) {
      const target = p.beats_price ? beats : misses
      target.push(map.gx(p.revenue_growth), map.vy(p.value) + 0.02, map.mz(p.ebitda_margin))
    }
    const make = (arr: number[]) => {
      const g = new THREE.BufferGeometry()
      g.setAttribute('position', new THREE.Float32BufferAttribute(arr, 3))
      return g
    }
    return { beats: make(beats), misses: make(misses) }
  }, [data, map])
  const scenarioValue = data.scenario_value
  const scenarioPos: [number, number, number] = [map.gx(data.scenario.revenue_growth), map.vy(scenarioValue), map.mz(data.scenario.ebitda_margin)]

  return (
    <Canvas className="surface-canvas" dpr={[1, 2]} camera={{ fov: 38, position: [8.7, 6.7, 9.6], near: 0.1, far: 100 }}>
      <color attach="background" args={['#05060c']} />
      <ambientLight intensity={0.55} />
      <directionalLight position={[5, 9, 4]} intensity={1.3} color="#fff1cf" />
      <pointLight position={[-6, 3, -4]} intensity={18} color="#7ee6d8" />
      <group position={[0, -1.3, 0]}>
        <Surface data={data} map={map} />
        <PricePlane y={priceY} label={`Market ${money(data.market_price, data.currency, { precise: true })}`} />
        <Axes data={data} map={map} />
        {layers.frontier && frontier.length > 1 && (
          <Line points={frontier} color={new THREE.Color('#f6dca6').multiplyScalar(2.2)} lineWidth={3.2} toneMapped={false} />
        )}
        {layers.cloud && (
          <>
            <points geometry={cloud.beats}>
              <pointsMaterial size={0.055} color={new THREE.Color('#7ee6d8').multiplyScalar(1.6)} transparent opacity={0.85}
                              depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
            </points>
            <points geometry={cloud.misses}>
              <pointsMaterial size={0.055} color={new THREE.Color('#ff7c5c').multiplyScalar(1.4)} transparent opacity={0.75}
                              depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
            </points>
          </>
        )}
        {layers.history && data.history_points.map((point) => {
          const value = map.interpolate(point.revenue_growth, point.ebitda_margin)
          if (value === null) return null
          const position: [number, number, number] = [map.gx(point.revenue_growth), map.vy(value) + 0.06, map.mz(point.ebitda_margin)]
          return (
            <group key={point.period_end} position={position}>
              <mesh>
                <sphereGeometry args={[0.075, 20, 16]} />
                <meshBasicMaterial color={new THREE.Color('#f3eee4').multiplyScalar(1.5)} toneMapped={false} />
              </mesh>
              <Html center position={[0, -0.26, 0]} style={{ pointerEvents: 'none' }}>
                <div className="surface-tag history">FY{point.period_end.slice(0, 4)}</div>
              </Html>
            </group>
          )
        })}
        <group position={scenarioPos}>
          <mesh>
            <sphereGeometry args={[0.11, 24, 18]} />
            <meshBasicMaterial color={new THREE.Color('#aa9dff').multiplyScalar(2.4)} toneMapped={false} />
          </mesh>
          <Html center position={[0, 0.5, 0]} style={{ pointerEvents: 'none' }}>
            <div className="surface-tag scenario">Your scenario · {money(scenarioValue, data.currency, { precise: true })}</div>
          </Html>
        </group>
      </group>
      <OrbitControls enablePan={false} enableDamping dampingFactor={0.07} minDistance={6} maxDistance={20}
                     maxPolarAngle={Math.PI * 0.48} autoRotate={autoRotate} autoRotateSpeed={0.35} />
      <EffectComposer multisampling={0}>
        <Bloom intensity={0.9} luminanceThreshold={0.6} mipmapBlur radius={0.6} />
        <Vignette eskil={false} offset={0.25} darkness={0.7} />
      </EffectComposer>
    </Canvas>
  )
}
