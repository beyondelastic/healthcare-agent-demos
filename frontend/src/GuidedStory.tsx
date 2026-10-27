import { Check, LoaderCircle } from 'lucide-react'
import type { AgentRun, Encounter } from './types'
import type { derivePresentationStory } from './demoStory'

export default function GuidedStory({ story, encounter, run }: {
  story: ReturnType<typeof derivePresentationStory>; encounter: Encounter; run: AgentRun | null
}) {
  const { steps, active } = story
  const brief = story.currentProposal ? 'Neuer Vorschlag · nicht übernommen'
    : story.copy ? 'Aktueller Stand übergeben'
      : encounter.draft?.source_version === encounter.source_version
        ? encounter.status === 'approved' ? 'Freigegeben · Übergabe ausstehend' : 'Entwurf · menschlich zu prüfen'
        : encounter.draft ? 'Alter Entwurf · neue Quellen' : 'Noch kein gespeicherter Entwurf'
  const initialCheck = story.stage === 'start' && !run?.proposal
  return <section className="guided-story" aria-label="Geführte Fallbearbeitung">
    <div className="guided-chapters" aria-label="Arbeitsbereiche">
      <strong aria-current={story.chapter === 1 ? 'step' : undefined}>1 · Entlassdokumentation</strong>
      <strong aria-current={story.chapter === 2 ? 'step' : undefined}>2 · Befundnachverfolgung</strong>
    </div>
    <ol className="guided-steps" style={{ gridTemplateColumns: `repeat(${steps.length}, minmax(0, 1fr))` }} aria-label="Ablauf und aktueller Schritt">{steps.map((step, index) =>
      <li key={step} aria-current={index === active ? 'step' : undefined}
        className={story.milestones[index] ? 'completed' : ''}>
        <span>{story.milestones[index] ? <Check size={15} aria-hidden="true" /> : index + 1}</span><strong>{step}</strong>
      </li>)}</ol>
    <div className="guided-focus" aria-live="polite">
      <div className="eyebrow">{story.stage === 'done' ? 'ABGESCHLOSSEN'
        : story.stage === 'initial-done' ? 'ENTLASSDOKUMENTATION ABGELEGT'
          : `SCHRITT ${active + 1} VON ${steps.length}`}</div>
      <h1>{story.waiting && <LoaderCircle size={24} className="spin" aria-hidden="true" />}{story.title}</h1>
      <p><strong>Aktueller Stand</strong>{story.happened}</p>
      <div className="guided-next"><strong>{story.waiting ? 'In Bearbeitung' : 'Nächster Schritt'}</strong><span>{story.next}</span></div>
      {story.error && <p className="message error" role="alert">{story.error} Ereignisdetails unter „Scan und Nachverfolgung ansehen“ öffnen.</p>}
    </div>
    <dl className="guided-context">
      <div><dt>{initialCheck ? 'Quellenprüfung' : story.chapter === 1 ? 'Medikationsplan' : 'Scan'}</dt><dd>{initialCheck
        ? story.waiting ? 'In Bearbeitung' : 'Noch nicht gestartet' : story.chapter === 1
        ? encounter.kis.medication_released ? 'Als Quelle freigegeben' : 'Noch nicht freigegeben'
        : encounter.intakes.some(item => item.status === 'accepted') ? 'Als Quelle bestätigt' : 'Noch nicht bestätigt'}</dd></div>
      <div><dt>{story.chapter === 1 ? 'Menschliche Freigabe' : 'Verantwortung'}</dt><dd>{story.chapter === 1
        ? encounter.status === 'approved' ? 'Ausdrücklich erteilt' : 'Noch nicht erteilt'
        : story.task?.role_label ?? 'Noch nicht zugeordnet'}</dd></div>
      <div><dt>{initialCheck ? 'Quellenstand' : 'Abschlussbefund'}</dt><dd>{initialCheck
        ? encounter.source_version : story.reportAvailable ? 'Liegt vor' : 'Steht aus'}</dd></div>
      <div><dt>Brief</dt><dd>{brief}</dd></div>
    </dl>
    {run?.trigger && <details className="guided-trigger"><summary>Warum lief der Agent erneut?</summary>
      <p>Auslöser dieses Auftrags: {run.trigger.title}. Der lokale Server hat einen echten Foundry-Aufruf gestartet.
        Ein neuer Lauf ist noch keine Briefübernahme oder klinische Freigabe.</p>
    </details>}
  </section>
}
