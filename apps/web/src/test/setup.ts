import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(cleanup)

// jsdom não implementa o comportamento modal nativo. O navegador real também é conferido.
Object.defineProperties(HTMLDialogElement.prototype, {
  showModal: { configurable: true, value() { this.setAttribute('open', '') } },
  close: { configurable: true, value() { this.removeAttribute('open') } },
})
