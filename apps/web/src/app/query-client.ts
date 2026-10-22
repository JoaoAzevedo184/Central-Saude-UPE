import { QueryClient } from '@tanstack/react-query'

export function criarQueryClient() {
  return new QueryClient({
    defaultOptions: {
      // Evita repetir escritas e sobrepor retries à renovação já feita pelo HTTP.
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
}
