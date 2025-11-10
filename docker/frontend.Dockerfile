FROM node:20.11.1-bullseye

WORKDIR /app/frontend

COPY frontend/package.json frontend/pnpm-lock.yaml* frontend/tsconfig.json ./
COPY frontend/.eslintrc.cjs frontend/.prettierrc.json ./
COPY frontend/src ./src

RUN corepack enable && corepack prepare pnpm@8.15.4 --activate && pnpm install

CMD ["pnpm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]
