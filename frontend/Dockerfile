FROM node:20-alpine AS builder
WORKDIR /app
# Allow overriding the backend URL at build time (render.yaml passes it as a
# runtime env; this ARG lets local/CI builds set it too). The production
# default lives in next.config.mjs.
ARG BACKEND_URL
ENV BACKEND_URL=$BACKEND_URL
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY frontend/package*.json ./
RUN npm ci --omit=dev
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/next.config.mjs ./next.config.mjs
EXPOSE 3000
CMD ["sh", "-c", "npx next start -H 0.0.0.0 -p ${PORT:-3000}"]
