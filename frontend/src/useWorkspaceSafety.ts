import { useEffect, useRef } from 'react'

export function useWorkspaceSync(check: () => Promise<boolean>) {
  const latest = useRef(check)
  latest.current = check
  useEffect(() => {
    const refresh = () => {
      if (document.visibilityState === 'visible') void latest.current()
    }
    window.addEventListener('focus', refresh)
    document.addEventListener('visibilitychange', refresh)
    const timer = window.setInterval(refresh, 5000)
    return () => {
      window.removeEventListener('focus', refresh)
      document.removeEventListener('visibilitychange', refresh)
      window.clearInterval(timer)
    }
  }, [])
}

export function useNavigationGuard(pending: boolean, busy: boolean, onError: (message: string) => void) {
  useEffect(() => {
    const preventUnload = (event: BeforeUnloadEvent) => {
      if (pending || busy) event.preventDefault()
    }
    const navigate = (event: MouseEvent) => {
      const link = event.target instanceof Element ? event.target.closest('a[href]') : null
      if (!(link instanceof HTMLAnchorElement) || link.hasAttribute('download')) return
      const url = new URL(link.href)
      if (url.origin !== window.location.origin || url.pathname.startsWith('/api/')) return
      if (url.pathname === window.location.pathname && url.search === window.location.search) return
      if (busy) {
        event.preventDefault()
        onError('Bitte die laufende Aktion abwarten, bevor Sie die Ansicht wechseln.')
      } else if (pending) {
        event.preventDefault()
        if (window.confirm('Ungespeicherte Eingaben oder offene Bestätigungen verwerfen und die Ansicht wechseln?')) {
          window.removeEventListener('beforeunload', preventUnload)
          window.location.assign(url.href)
        }
      }
    }
    window.addEventListener('beforeunload', preventUnload)
    document.addEventListener('click', navigate)
    return () => {
      window.removeEventListener('beforeunload', preventUnload)
      document.removeEventListener('click', navigate)
    }
  }, [pending, busy, onError])
}
