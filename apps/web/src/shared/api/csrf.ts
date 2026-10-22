export function lerCsrf(cookie = document.cookie): string | undefined {
  const value = cookie.split(';').map((part) => part.trim())
    .find((part) => part.startsWith('csrf_token='))?.slice('csrf_token='.length)
  if (!value) return undefined
  try {
    return decodeURIComponent(value)
  } catch {
    return undefined
  }
}
