/* The ValuEngine mark: a tiny armillary sphere built with CSS 3D transforms.
   Three gimballed rings orbit a glowing core; they spin up on hover. */

export function EngineMark({ size = 30 }: { size?: number }) {
  return (
    <span className="engine-mark" style={{ width: size, height: size }} aria-hidden="true">
      <span className="engine-ring r1" />
      <span className="engine-ring r2" />
      <span className="engine-ring r3" />
      <span className="engine-core" />
    </span>
  )
}

export function Wordmark() {
  return (
    <span className="wordmark">
      <span className="display">Valu</span>
      <span className="display wordmark-accent">Engine</span>
    </span>
  )
}
