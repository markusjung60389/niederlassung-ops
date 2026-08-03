FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
# `npm ci` installs exactly what the lockfile pins; `npm install` may drift.
RUN npm ci
COPY . .
# No VITE_* build args: configuration is injected at container start by
# docker-entrypoint.sh, so one image can serve any environment.
RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY docker-entrypoint.sh /docker-entrypoint.d/99-ops-config.sh
RUN chmod +x /docker-entrypoint.d/99-ops-config.sh

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1/healthz || exit 1
