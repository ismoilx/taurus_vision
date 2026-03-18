# ============================================================
# Taurus Vision Frontend — Production Dockerfile
# ============================================================
# Bu fayl docker-compose.prod.yml tomonidan ishlatiladi.
# Development uchun: Dockerfile.dev
# ============================================================

# ── Stage 1: Build ──────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Dependencies (layer caching uchun alohida)
COPY package*.json ./
RUN npm ci

# Source code
COPY . .

# Build arguments (docker-compose.prod.yml dan keladi)
ARG VITE_API_URL=""
ARG VITE_WS_URL=""
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_WS_URL=$VITE_WS_URL

# Production build
RUN npm run build

# ── Stage 2: Production runtime (Nginx) ─────────────────────
FROM nginx:1.25-alpine AS production

# Built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Nginx config (frontend/nginx.conf dan)
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
