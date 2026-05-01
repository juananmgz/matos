# syntax=docker/dockerfile:1.7

# ─────────────────────────────────────────────────────────────────────────────
# base — node + pnpm vía corepack
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS base
RUN corepack enable && corepack prepare pnpm@9.7.0 --activate
WORKDIR /app

# ─────────────────────────────────────────────────────────────────────────────
# deps — instala node_modules
# ─────────────────────────────────────────────────────────────────────────────
FROM base AS deps

# pnpm-lock.yaml* permite ausencia (primera vez antes de `make lock`).
COPY frontend/package.json frontend/pnpm-lock.yaml* ./

RUN --mount=type=cache,id=pnpm,target=/root/.local/share/pnpm/store \
    pnpm install --prefer-frozen-lockfile || pnpm install

# ─────────────────────────────────────────────────────────────────────────────
# dev — Vite dev server con HMR; código por bind mount
# ─────────────────────────────────────────────────────────────────────────────
FROM deps AS dev
EXPOSE 5173
CMD ["pnpm", "dev", "--host", "0.0.0.0", "--port", "5173"]

# ─────────────────────────────────────────────────────────────────────────────
# build — genera dist/ estático
# ─────────────────────────────────────────────────────────────────────────────
FROM deps AS build
COPY frontend/ ./
RUN pnpm build

# ─────────────────────────────────────────────────────────────────────────────
# prod — Caddy alpine sirviendo estáticos
# ─────────────────────────────────────────────────────────────────────────────
FROM caddy:2-alpine AS prod
COPY --from=build /app/dist /srv
COPY docker/Caddyfile.frontend /etc/caddy/Caddyfile
EXPOSE 80
