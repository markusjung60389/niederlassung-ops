FROM node:22-alpine AS build
WORKDIR /app

ARG VITE_API_BASE_URL=http://localhost:8000
ARG VITE_AUTH_MODE=dev
ARG VITE_AZURE_TENANT_ID=
ARG VITE_AZURE_CLIENT_ID=
ARG VITE_AZURE_API_SCOPE=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_AUTH_MODE=$VITE_AUTH_MODE \
    VITE_AZURE_TENANT_ID=$VITE_AZURE_TENANT_ID \
    VITE_AZURE_CLIENT_ID=$VITE_AZURE_CLIENT_ID \
    VITE_AZURE_API_SCOPE=$VITE_AZURE_API_SCOPE

COPY package.json package-lock.json ./
# `npm ci` installs exactly what the lockfile pins; `npm install` may drift.
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
