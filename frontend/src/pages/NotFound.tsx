import { Link } from 'react-router-dom'
import { EngineMark } from '../components/EngineMark'
import { IconArrowRight } from '../components/icons'

export function NotFound() {
  return (
    <div className="page page-center not-found">
      <div className="lost-orbit" aria-hidden="true">
        <EngineMark size={120} />
        <span className="lost-satellite" />
      </div>
      <div className="eyebrow">404 · off the map</div>
      <h1 className="display">This page drifted <em>out of orbit</em></h1>
      <p className="muted">The address does not match anything in ValuEngine. The Observatory is a better place to start.</p>
      <Link to="/" className="btn btn-primary"><span>Back to the Observatory</span><IconArrowRight size={15} /></Link>
    </div>
  )
}
