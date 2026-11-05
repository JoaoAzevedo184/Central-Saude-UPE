# Build do frontend sem Node na VM: gera /app/dist (copiado para ./apps/web/dist pelo compose).
# Imagem glibc (slim) de propósito: os binários opcionais do rollup/esbuild têm build para
# amd64 e arm64 (o lockfile lista todos).
FROM node:22-slim

WORKDIR /app

# Dependências antes do código, para aproveitar o cache pelo lockfile.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

CMD ["npm", "run", "build"]
