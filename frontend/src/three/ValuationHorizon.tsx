import { useMemo, useRef } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Html, Line, MeshReflectorMaterial, RoundedBox } from '@react-three/drei'
import { Bloom, EffectComposer, Vignette } from '@react-three/postprocessing'
import * as THREE from 'three'
import { money } from '../lib/format'
import { niceTicks } from '../lib/utils'

/* A 3D football field: valuation ranges as glass bars floating over a dark reflective floor, cut by a
   soft curtain of light standing at the market price. The layout is fitted to the canvas aspect so the
   row labels on the left always stay in frame. */

export interface HorizonRange {
  key: string
  label: string
  sublabel?: string
  low: number
  high: number
  mid?: number | null
  tone: 'gold' | 'aurora' | 'violet' | 'ivory'
}

const TONES: Record<HorizonRange['tone'], string> = { gold: '#e6c27d', aurora: '#7ee6d8', violet: '#aa9dff', ivory: '#f3eee4' }
const ROW = 1.7
const FOV = 36
const CAMERA: [number, number, number] = [0, 5, 7.6]

function Bar({ range, x, z, delay }: { range: HorizonRange; x: (v: number) => number; z: number; delay: number }) {
  const group = useRef<THREE.Group>(null)
  const born = useRef<number | null>(null)
  const low = x(range.low)
  const high = x(range.high)
  const width = Math.max(0.06, high - low)
  const center = (low + high) / 2
  const color = TONES[range.tone]
  useFrame((state) => {
    if (!group.current) return
    if (born.current === null) born.current = state.clock.elapsedTime
    const t = Math.min(1, Math.max(0, (state.clock.elapsedTime - born.current - delay) / 1.1))
    const eased = 1 - Math.pow(1 - t, 4)
    group.current.scale.set(Math.max(0.001, eased), 1, 1)
    group.current.position.y = Math.sin(state.clock.elapsedTime * 0.9 + z) * 0.02
  })
  return (
    <group position={[center, 0.42, z]}>
      <group ref={group}>
        <RoundedBox args={[width, 0.32, 0.56]} radius={0.12} smoothness={4}>
          <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.22} transparent opacity={0.58}
                                roughness={0.2} metalness={0.3} />
        </RoundedBox>
        <mesh>
          <boxGeometry args={[width * 0.985, 0.03, 0.05]} />
          <meshBasicMaterial color={new THREE.Color(color).multiplyScalar(1.7)} toneMapped={false} />
        </mesh>
        {range.mid != null && (
          <mesh position={[x(range.mid) - center, 0, 0]}>
            <boxGeometry args={[0.03, 0.46, 0.6]} />
            <meshBasicMaterial color={new THREE.Color('#fff1cf').multiplyScalar(1.5)} toneMapped={false} />
          </mesh>
        )}
      </group>
    </group>
  )
}

/** A vertical sheet of light at the market price: brightest at the floor, fading upward and at the ends. */
function PriceCurtain({ x, depth }: { x: number; depth: number }) {
  const material = useMemo(() => new THREE.ShaderMaterial({
    uniforms: { uColor: { value: new THREE.Color('#f6dca6') }, uTime: { value: 0 } },
    vertexShader: /* glsl */ `
      varying vec2 vUv;
      void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }
    `,
    fragmentShader: /* glsl */ `
      uniform vec3 uColor;
      uniform float uTime;
      varying vec2 vUv;
      void main() {
        float rise = pow(1.0 - vUv.y, 2.4);
        float ends = smoothstep(0.0, 0.14, vUv.x) * smoothstep(1.0, 0.86, vUv.x);
        float shimmer = 0.85 + 0.15 * sin(vUv.y * 40.0 - uTime * 2.0);
        gl_FragColor = vec4(uColor, rise * ends * shimmer * 0.42);
      }
    `,
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending,
  }), [])
  useFrame((state) => { material.uniforms.uTime.value = state.clock.elapsedTime })
  return (
    <group>
      <mesh position={[x, 1.0, 0]} rotation={[0, Math.PI / 2, 0]} material={material}>
        <planeGeometry args={[depth + 0.8, 2.0]} />
      </mesh>
      <Line points={[[x, 0.012, -depth / 2 - 0.4], [x, 0.012, depth / 2 + 0.4]]} color="#fff1cf" lineWidth={1.6} transparent opacity={0.9} />
    </group>
  )
}

function Rig() {
  useFrame((state) => {
    const { camera, pointer } = state
    camera.position.x += (pointer.x * 0.7 - camera.position.x) * 0.04
    camera.position.y += (CAMERA[1] + pointer.y * 0.35 - camera.position.y) * 0.04
    camera.lookAt(0, 0.25, 0)
  })
  return null
}

function Scene({ ranges, marketPrice, currency }: { ranges: HorizonRange[]; marketPrice: number; currency: string }) {
  const width = useThree((state) => state.size.width)
  const height = useThree((state) => state.size.height)

  const layout = useMemo(() => {
    // Visible half-width of the floor at the scene centre, then room for labels on the left.
    const distance = Math.hypot(CAMERA[1], CAMERA[2])
    const halfWidth = Math.tan(THREE.MathUtils.degToRad(FOV / 2)) * distance * (width / Math.max(1, height))
    const left = -halfWidth + 3.6
    const right = halfWidth - 0.4
    const half = Math.max(1.1, (right - left) / 2)
    const centre = (right + left) / 2
    const values = ranges.flatMap((r) => [r.low, r.high]).concat(marketPrice)
    let min = Math.min(...values)
    let max = Math.max(...values)
    const pad = (max - min) * 0.06 || Math.abs(max) * 0.1 || 1
    min -= pad
    max += pad
    const x = (v: number) => centre + ((v - min) / (max - min) - 0.5) * 2 * half
    const ticks = niceTicks(min, max, 5).filter((t) => t >= min && t <= max)
    return { x, ticks, labelX: centre - half - 0.22 }
  }, [ranges, marketPrice, width, height])

  const depth = ranges.length * ROW
  const zOf = (i: number) => (i - (ranges.length - 1) / 2) * ROW
  const px = layout.x(marketPrice)
  const tick = (v: number) => money(v, currency).replace(/\.00$/, '')

  return (
    <>
      <color attach="background" args={['#05060c']} />
      <fog attach="fog" args={['#05060c', 9, 22]} />
      <ambientLight intensity={0.5} />
      <pointLight position={[-4, 3.5, 3]} intensity={22} color="#e6c27d" />
      <pointLight position={[5, 2.5, -2]} intensity={16} color="#7ee6d8" />

      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[30, 30]} />
        <MeshReflectorMaterial blur={[300, 80]} resolution={512} mixBlur={1} mixStrength={7} roughness={0.95}
                               depthScale={1} minDepthThreshold={0.4} maxDepthThreshold={1.3} color="#07080d" metalness={0.5}
                               mirror={0.35} />
      </mesh>

      {layout.ticks.map((t) => (
        <group key={t}>
          <Line points={[[layout.x(t), 0.003, -depth / 2 - 0.3], [layout.x(t), 0.003, depth / 2 + 0.3]]} color="#8f897e"
                lineWidth={1} transparent opacity={0.2} />
          <Html position={[layout.x(t), 0.01, depth / 2 + 0.7]} center style={{ pointerEvents: 'none' }}>
            <div className="horizon-tick">{tick(t)}</div>
          </Html>
        </group>
      ))}

      {ranges.map((range, i) => (
        <group key={range.key}>
          <Bar range={range} x={layout.x} z={zOf(i)} delay={0.15 + i * 0.12} />
          <Html position={[layout.labelX, 0.42, zOf(i)]} style={{ pointerEvents: 'none', transform: 'translate(-100%, -50%)' }}>
            <div className={`horizon-label tone-${range.tone}`}>
              <b>{range.label}</b>
              {range.sublabel && <span>{range.sublabel}</span>}
              <em>{money(range.low, currency, { precise: true })} – {money(range.high, currency, { precise: true })}</em>
            </div>
          </Html>
        </group>
      ))}

      <PriceCurtain x={px} depth={depth} />
      <Html position={[px, 2.15, -depth / 2 - 0.2]} center style={{ pointerEvents: 'none' }}>
        <div className="horizon-market">Market · {money(marketPrice, currency, { precise: true })}</div>
      </Html>

      <Rig />
      <EffectComposer multisampling={0}>
        <Bloom intensity={0.7} luminanceThreshold={0.62} mipmapBlur radius={0.5} />
        <Vignette eskil={false} offset={0.2} darkness={0.72} />
      </EffectComposer>
    </>
  )
}

export default function ValuationHorizon({ ranges, marketPrice, currency }: {
  ranges: HorizonRange[]; marketPrice: number; currency: string
}) {
  return (
    <Canvas className="horizon-canvas" dpr={[1, 2]} camera={{ fov: FOV, position: CAMERA, near: 0.1, far: 60 }}>
      <Scene ranges={ranges} marketPrice={marketPrice} currency={currency} />
    </Canvas>
  )
}
