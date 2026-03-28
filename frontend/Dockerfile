# Use Node.js 20 Alpine as the base image
FROM node:20-alpine AS base

# Install dependencies only when needed
FROM base AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install

# Rebuild the source code only when needed
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED 1
RUN npm run build

# Production image
FROM base AS runner
WORKDIR /app

ENV NODE_ENV production
ENV NEXT_TELEMETRY_DISABLED 1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy full .next build output
COPY --from=builder --chown=nextjs:nodejs /app/.next ./.next

# Install production dependencies in runner
COPY --from=deps --chown=nextjs:nodejs /app/package.json ./package.json
COPY --from=deps --chown=nextjs:nodejs /app/package-lock.json* ./
USER root
RUN npm install --production --ignore-scripts
RUN chown -R nextjs:nodejs node_modules .next

# Create missing app-pages-internals.js
USER nextjs
RUN echo '/* empty chunk - app-pages-internals */' > .next/static/chunks/app-pages-internals.js && \
    echo '/* webpack runtime - placeholder */' > .next/static/chunks/webpack.js

EXPOSE 3000
ENV PORT 3000
ENV HOSTNAME "0.0.0.0"

CMD ["npx", "next", "start"]
