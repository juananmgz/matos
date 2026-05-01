import { useEffect, useState } from "react"

interface Health {
  status: string
  version: string
  env: string
}

export function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch("/api/health")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json() as Promise<Health>
      })
      .then(setHealth)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
  }, [])

  return (
    <main>
      <header>
        <h1>MATOS</h1>
        <p className="tagline">Reproductor del archivo de etnomusicología MNEMOSINE</p>
      </header>

      <section>
        <h2>Estado del backend</h2>
        {error && (
          <pre className="error">
            Error: {error}
            {"\n"}— ¿está el backend arriba? `make logs s=backend`
          </pre>
        )}
        {!error && !health && <p>Conectando...</p>}
        {health && (
          <dl className="kv">
            <dt>status</dt>
            <dd>
              <span className={`badge badge-${health.status}`}>{health.status}</span>
            </dd>
            <dt>version</dt>
            <dd>{health.version}</dd>
            <dt>env</dt>
            <dd>{health.env}</dd>
          </dl>
        )}
      </section>

      <section>
        <h2>Fase 0 ✓</h2>
        <p>
          Scaffold + docker + Caddy + hot reload activos. Próxima fase: schemas Pydantic
          (GeoUnit, Item, Song).
        </p>
      </section>
    </main>
  )
}
