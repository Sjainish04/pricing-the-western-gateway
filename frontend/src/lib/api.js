/* Thin fetch wrapper plus a hook that keeps loading and error states honest.
 *
 * Results are cached per request key: the model is deterministic and stateless,
 * so a repeated request cannot return anything different, and the heavier
 * endpoints (the leader search, Monte Carlo) are expensive enough to be worth
 * not asking twice.
 */
import { useEffect, useRef, useState } from 'react'

const BASE = ''
const cache = new Map()

async function request(path, options) {
  const res = await fetch(`${BASE}${path}`, options)
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) detail = body.detail
    } catch { /* keep the status line */ }
    throw new Error(detail)
  }
  return res.json()
}

export function get(path) {
  if (!cache.has(path)) {
    cache.set(path, request(path).catch((err) => {
      cache.delete(path)          // let a failure be retried
      throw err
    }))
  }
  return cache.get(path)
}

export function post(path, body) {
  const key = `POST ${path} ${JSON.stringify(body)}`
  if (!cache.has(key)) {
    cache.set(key, request(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body ?? {}),
    }).catch((err) => {
      cache.delete(key)
      throw err
    }))
  }
  return cache.get(key)
}

/** GET a path, tracking loading and error. Pass null to skip. */
export function useApi(path) {
  const [state, setState] = useState({ data: null, error: null, loading: !!path })
  useEffect(() => {
    if (!path) { setState({ data: null, error: null, loading: false }); return }
    let live = true
    setState((s) => ({ ...s, loading: true, error: null }))
    get(path).then(
      (data) => { if (live) setState({ data, error: null, loading: false }) },
      (error) => { if (live) setState({ data: null, error, loading: false }) },
    )
    return () => { live = false }
  }, [path])
  return state
}

/** POST a body, refetching whenever the serialised body changes. */
export function usePost(path, body, enabled = true) {
  const [state, setState] = useState({ data: null, error: null, loading: enabled })
  const key = JSON.stringify(body)
  const latest = useRef(0)

  useEffect(() => {
    if (!enabled || !path) return
    const ticket = ++latest.current
    setState((s) => ({ ...s, loading: true, error: null }))
    post(path, body).then(
      (data) => { if (ticket === latest.current) setState({ data, error: null, loading: false }) },
      (error) => { if (ticket === latest.current) setState({ data: null, error, loading: false }) },
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, key, enabled])

  return state
}
