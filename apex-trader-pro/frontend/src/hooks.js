import { useCallback, useEffect, useState } from 'react'

export function useApi(fn, deps = [], intervalMs = 0) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const load = useCallback(async () => {
    try { setData(await fn()); setError('') } catch (e) { setError(e.message) }
  }, deps) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    load()
    if (!intervalMs) return undefined
    const id = setInterval(load, intervalMs)
    return () => clearInterval(id)
  }, [load, intervalMs])
  return { data, error, reload: load }
}
