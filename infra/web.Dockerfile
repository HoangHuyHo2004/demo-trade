FROM node:20-alpine AS deps
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml* ./
COPY apps/web/package.json apps/web/package.json
COPY packages/contracts/package.json packages/contracts/package.json
COPY packages/config/package.json packages/config/package.json
RUN pnpm install --no-frozen-lockfile

FROM node:20-alpine AS dev
WORKDIR /app
RUN corepack enable
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/apps/web/node_modules ./apps/web/node_modules
COPY . .
WORKDIR /app/apps/web
EXPOSE 3000
CMD ["pnpm", "dev"]
