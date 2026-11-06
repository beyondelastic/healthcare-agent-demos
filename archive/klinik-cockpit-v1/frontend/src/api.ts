export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init, headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    const data: { detail?: unknown } = await response.json()
    throw new ApiError(typeof data.detail === 'string' ? data.detail : `Anfrage fehlgeschlagen (${response.status}). Bitte Eingaben prüfen.`, response.status)
  }
  return response.json() as Promise<T>
}
export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message)
    this.name = 'ApiError'
  }
}
