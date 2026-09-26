import { useEffect, useMemo, useRef, useState } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Bloom, EffectComposer, Noise, Vignette } from '@react-three/postprocessing'
import * as THREE from 'three'

/* "Ignition": ~9,000 particles fly in from a nebula and assemble a gyroscopic armillary sphere
   (the engine), the wordmark resolves beneath it, and the camera dives through the core. */

// How long each phase lasts, in milliseconds of rendered time.
const PHASES = [
  { phase: 'forming', ms: 2300 },
  { phase: 'title', ms: 1200 },
  { phase: 'tagline', ms: 2100 },
  { phase: 'diving', ms: 1100 },
] as const

const vertexShader = /* glsl */ `
  uniform float uTime;
  uniform float uForm;
  uniform float uSpin;
  uniform float uPixelRatio;
  uniform float uScale;
  uniform float uDive;
  attribute vec3 aStart;
  attribute float aDelay;
  attribute float aSize;
  attribute vec3 aColor;
  attribute float aGroup;
  varying vec3 vColor;
  varying float vAlpha;

  mat3 rotX(float a) { float c = cos(a), s = sin(a); return mat3(1.0, 0.0, 0.0, 0.0, c, s, 0.0, -s, c); }
  mat3 rotY(float a) { float c = cos(a), s = sin(a); return mat3(c, 0.0, -s, 0.0, 1.0, 0.0, s, 0.0, c); }
  mat3 rotZ(float a) { float c = cos(a), s = sin(a); return mat3(c, s, 0.0, -s, c, 0.0, 0.0, 0.0, 1.0); }

  void main() {
    float t = clamp((uForm - aDelay) / 0.55, 0.0, 1.0);
    t = t * t * (3.0 - 2.0 * t);
    float a = uTime * uSpin;
    vec3 target = position;
    if (aGroup < 0.5) {
      target = rotY(a * 0.55) * target;
    } else if (aGroup < 1.5) {
      target = rotY(-a * 0.32) * target;
    } else if (aGroup < 2.5) {
      target = rotX(1.05) * target;
      target = rotY(a * 0.24) * (rotZ(a * 0.4) * target);
    } else if (aGroup < 3.5) {
      target = rotY(a * 0.18) * target * (1.0 + 0.045 * sin(uTime * 2.2));
    } else {
      target = rotY(a * 0.05) * target;
    }
    vec3 swirl = rotY((1.0 - t) * 2.6) * aStart;
    vec3 p = mix(swirl, target, t);
    p += 0.012 * sin(uTime * 1.6 + aDelay * 53.0) * normalize(p + vec3(1e-4));
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mv;
    // Size follows the viewport height so the sphere looks the same on a laptop and a 4K screen,
    // and is capped so particles passing the lens during the dive stay soft instead of flooding the frame.
    gl_PointSize = min(aSize * uPixelRatio * (uScale / -mv.z), 36.0 * uPixelRatio);
    vColor = aColor;
    vAlpha = mix(0.2, 1.0, t) * (1.0 - smoothstep(0.35, 0.95, uDive));
  }
`

const fragmentShader = /* glsl */ `
  varying vec3 vColor;
  varying float vAlpha;
  void main() {
    float d = length(gl_PointCoord - 0.5);
    float alpha = pow(smoothstep(0.5, 0.0, d), 1.7) * vAlpha;
    gl_FragColor = vec4(vColor, alpha);
  }
`

const GOLD = new THREE.Color('#e6c27d')
const GOLD_HOT = new THREE.Color('#fff1cf')
const AURORA = new THREE.Color('#7ee6d8')
const IVORY = new THREE.Color('#f3eee4')

function buildArmillary() {
  const positions: number[] = []
  const starts: number[] = []
  const delays: number[] = []
  const sizes: number[] = []
  const colors: number[] = []
  const groups: number[] = []
  const rand = (min: number, max: number) => min + Math.random() * (max - min)

  const push = (p: THREE.Vector3, delay: number, size: number, color: THREE.Color, group: number, intensity = 1) => {
    positions.push(p.x, p.y, p.z)
    const angle = Math.random() * Math.PI * 2
    const radius = rand(6.5, 15)
    starts.push(Math.cos(angle) * radius, rand(-1.2, 1.2) * (radius / 15), Math.sin(angle) * radius - 6)
    delays.push(delay)
    sizes.push(size)
    colors.push(color.r * intensity, color.g * intensity, color.b * intensity)
    groups.push(group)
  }

  const ring = (radius: number, count: number, plane: 'xz' | 'xy', group: number, color: THREE.Color) => {
    for (let i = 0; i < count; i++) {
      const theta = (i / count) * Math.PI * 2 + rand(-0.004, 0.004)
      const r = radius + rand(-0.018, 0.018)
      const jitter = rand(-0.02, 0.02)
      const p = plane === 'xz'
        ? new THREE.Vector3(Math.cos(theta) * r, jitter, Math.sin(theta) * r)
        : new THREE.Vector3(Math.cos(theta) * r, Math.sin(theta) * r, jitter)
      const mixed = color.clone().lerp(GOLD_HOT, Math.random() * 0.35)
      push(p, 0.45 * (i / count) * 0.9 + rand(0, 0.03), rand(0.8, 1.7), mixed, group, rand(0.85, 1.45))
    }
  }

  ring(2.25, 2200, 'xz', 0, GOLD)
  ring(2.25, 2000, 'xy', 1, GOLD)
  ring(1.8, 1700, 'xz', 2, AURORA)

  for (let i = 0; i < 1500; i++) {
    const p = new THREE.Vector3().randomDirection().multiplyScalar(0.52 * Math.cbrt(Math.random()))
    push(p, rand(0.3, 0.45), rand(0.7, 1.4), GOLD_HOT, 3, rand(1.1, 1.9))
  }
  for (let i = 0; i < 1700; i++) {
    const p = new THREE.Vector3().randomDirection().multiplyScalar(rand(3.1, 3.5))
    push(p, rand(0.05, 0.45), rand(0.45, 1.0), IVORY, 4, rand(0.18, 0.42))
  }

  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
  geometry.setAttribute('aStart', new THREE.Float32BufferAttribute(starts, 3))
  geometry.setAttribute('aDelay', new THREE.Float32BufferAttribute(delays, 1))
  geometry.setAttribute('aSize', new THREE.Float32BufferAttribute(sizes, 1))
  geometry.setAttribute('aColor', new THREE.Float32BufferAttribute(colors, 3))
  geometry.setAttribute('aGroup', new THREE.Float32BufferAttribute(groups, 1))
  return geometry
}

function Armillary({ diving }: { diving: boolean }) {
  const geometry = useMemo(buildArmillary, [])
  const gl = useThree((state) => state.gl)
  const height = useThree((state) => state.size.height)
  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader,
        fragmentShader,
        uniforms: {
          uTime: { value: 0 },
          uForm: { value: 0 },
          uSpin: { value: 0 },
          uPixelRatio: { value: Math.min(gl.getPixelRatio(), 2) },
          uScale: { value: 32 },
          uDive: { value: 0 },
        },
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    [gl],
  )
  const start = useRef<number | null>(null)
  const diveStart = useRef<number | null>(null)

  useEffect(() => {
    material.uniforms.uScale.value = Math.max(18, height * 0.036)
  }, [height, material])

  useFrame((state) => {
    if (start.current === null) start.current = state.clock.elapsedTime
    const t = state.clock.elapsedTime - start.current
    const u = material.uniforms
    u.uTime.value = t
    u.uForm.value = Math.min(1, Math.max(0, (t - 0.35) / 2.6))
    u.uSpin.value = Math.min(1, Math.max(0, (t - 1.6) / 2.2)) * (diving ? 3 : 1)
    if (diving && diveStart.current === null) diveStart.current = t
    u.uDive.value = diveStart.current === null ? 0 : Math.min(1, (t - diveStart.current) / 1.05)
  })

  useEffect(() => () => { geometry.dispose(); material.dispose() }, [geometry, material])
  return <points geometry={geometry} material={material} frustumCulled={false} />
}

function Dust() {
  const geometry = useMemo(() => {
    const count = 2600
    const positions = new Float32Array(count * 3)
    for (let i = 0; i < count; i++) {
      const v = new THREE.Vector3().randomDirection().multiplyScalar(18 + Math.random() * 40)
      positions.set([v.x, v.y, v.z], i * 3)
    }
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    return g
  }, [])
  const ref = useRef<THREE.Points>(null)
  useFrame((_, delta) => {
    if (ref.current) ref.current.rotation.y += delta * 0.01
  })
  return (
    <points ref={ref} geometry={geometry}>
      <pointsMaterial size={0.06} color="#cfc6b3" transparent opacity={0.55} sizeAttenuation depthWrite={false} />
    </points>
  )
}

function CameraRig({ diving }: { diving: boolean }) {
  const camera = useThree((state) => state.camera) as THREE.PerspectiveCamera
  const diveStart = useRef<number | null>(null)
  const start = useRef<number | null>(null)
  useFrame((state) => {
    if (start.current === null) start.current = state.clock.elapsedTime
    const t = state.clock.elapsedTime - start.current
    if (!diving) {
      const k = Math.min(1, t / 5)
      const eased = 1 - Math.pow(1 - k, 3)
      camera.position.set(Math.sin(t * 0.18) * 0.9, 0.55 - eased * 0.25, 11 - eased * 3.6)
      camera.lookAt(0, 0, 0)
      return
    }
    if (diveStart.current === null) diveStart.current = t
    const k = Math.min(1, (t - diveStart.current) / 1.05)
    const eased = k * k * k
    camera.position.set(camera.position.x * (1 - eased), 0.3 * (1 - eased), 7.4 - eased * 7.2)
    camera.fov = 45 + eased * 50
    camera.updateProjectionMatrix()
    camera.lookAt(0, 0, 0)
  })
  return null
}

const WORD = 'ValuEngine'

type Phase = (typeof PHASES)[number]['phase']

/** Advances the intro on the scene's own clock, from the first rendered frame and at most one phase per
    frame, so a hidden tab or a slow machine pauses or slows the intro rather than skipping parts of it. */
function Director({ onPhase, onFinish, onFirstFrame }: { onPhase: (phase: Phase) => void; onFinish: () => void; onFirstFrame: () => void }) {
  const index = useRef(0)
  const since = useRef<number | null>(null)
  useFrame((state) => {
    const now = state.clock.elapsedTime * 1000
    if (since.current === null) {
      since.current = now
      onFirstFrame()
      return
    }
    if (index.current >= PHASES.length || now - since.current < PHASES[index.current].ms) return
    index.current += 1
    since.current = now
    if (index.current >= PHASES.length) onFinish()
    else onPhase(PHASES[index.current].phase)
  })
  return null
}

export default function IntroExperience({ onDone, companyCount }: { onDone: () => void; companyCount?: number }) {
  const [phase, setPhase] = useState<Phase>('forming')
  const finished = useRef(false)
  const rendered = useRef(false)
  const finish = () => {
    if (finished.current) return
    finished.current = true
    onDone()
  }

  useEffect(() => {
    const skip = (event: KeyboardEvent) => {
      if (['Enter', 'Escape', ' '].includes(event.key)) finish()
    }
    // Safety net: if the scene never renders a frame while the page is visible (a lost or blocked
    // WebGL context), do not hold the user behind a black screen.
    let fallback = 0
    const watchdog = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return
      window.clearInterval(watchdog)
      fallback = window.setTimeout(() => { if (!rendered.current) finish() }, 2500)
    }, 400)
    window.addEventListener('keydown', skip)
    return () => {
      window.clearInterval(watchdog)
      window.clearTimeout(fallback)
      window.removeEventListener('keydown', skip)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const status = phase === 'forming' ? 'Calibrating the instruments' :
    phase === 'title' ? `Aligning ${companyCount ?? 'every'} companies` : 'Reading what the market believes'

  return (
    <div className={`intro ${phase}`} role="dialog" aria-label="ValuEngine introduction">
      <Canvas className="intro-canvas" dpr={[1, 2]} camera={{ fov: 45, position: [0, 0.55, 11], near: 0.05, far: 200 }}
              gl={{ antialias: true, powerPreference: 'high-performance' }}>
        <color attach="background" args={['#030409']} />
        <Director onPhase={setPhase} onFinish={finish} onFirstFrame={() => { rendered.current = true }} />
        <Dust />
        <Armillary diving={phase === 'diving'} />
        <CameraRig diving={phase === 'diving'} />
        <EffectComposer multisampling={0}>
          <Bloom intensity={0.95} luminanceThreshold={0.16} luminanceSmoothing={0.3} mipmapBlur radius={0.7} />
          <Noise opacity={0.035} />
          <Vignette eskil={false} offset={0.18} darkness={0.85} />
        </EffectComposer>
      </Canvas>

      <div className="intro-overlay">
        <div className="intro-corner eyebrow muted">ValuEngine · v2.0</div>
        <div className="intro-title">
          <h1 className="intro-word display" aria-label={WORD}>
            {WORD.split('').map((letter, i) => (
              <span key={i} style={{ animationDelay: `${i * 70}ms` }} aria-hidden="true">{letter}</span>
            ))}
          </h1>
          <div className="intro-rule" />
          <p className="intro-tagline eyebrow">Valuation · Deals · Risk — read what the market believes</p>
        </div>
        <div className="intro-status mono">
          <span className="intro-status-dot" />
          {status}
        </div>
        <button type="button" className="intro-skip" onClick={finish}>
          Skip intro <kbd>↵</kbd>
        </button>
      </div>
      <div className="intro-flash" />
    </div>
  )
}
