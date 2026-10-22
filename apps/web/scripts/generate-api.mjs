import { spawnSync } from 'node:child_process'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import openapiTS, { astToString } from 'openapi-typescript'

// Exporta o contrato real sem servidor, conexão com o banco ou leitura de segredos.
const args = process.argv.slice(2)
const check = args.includes('--check')
const source = args.find((arg) => arg !== '--check')
let schema
if (source) {
  schema = new URL(source)
} else {
  const backend = fileURLToPath(new URL('../../backend/', import.meta.url))
  const result = spawnSync(`${backend}.venv/bin/python`, [
    '-c', 'import json; from app.api.main import app; print(json.dumps(app.openapi()))',
  ], {
    cwd: backend,
    encoding: 'utf8',
    env: {
      ...process.env,
      APP_ENV: 'test',
      DATABASE_URL: 'postgresql+psycopg://sintetico:sintetico@127.0.0.1/contrato_sem_conexao',
      JWT_SECRET_KEY: 'somente-exportacao-openapi',
      LOGIN_HASH_KEY: 'somente-exportacao-openapi-hash',
    },
  })
  if (result.error || result.status !== 0) {
    throw new Error('Prepare apps/backend/.venv com uv sync ou informe a URL do OpenAPI.', {
      cause: result.error ?? result.stderr,
    })
  }
  schema = JSON.parse(result.stdout)
}
const output = new URL('../src/shared/api/generated/schema.d.ts', import.meta.url)
const contents = astToString(await openapiTS(schema))
if (check) {
  if (await readFile(output, 'utf8') !== contents) {
    throw new Error('Tipos desatualizados. Execute npm run api:generate.')
  }
} else {
  await mkdir(new URL('.', output), { recursive: true })
  await writeFile(output, contents)
}
console.info(check ? 'Tipos OpenAPI atualizados.' : 'Tipos OpenAPI gerados.')
