FROM node:22-alpine AS build

WORKDIR /app

ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_PUBLISHABLE_KEY

ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL
ENV VITE_SUPABASE_PUBLISHABLE_KEY=$VITE_SUPABASE_PUBLISHABLE_KEY

RUN npm install -g pnpm

COPY ./app/package.json ./app/pnpm-lock.yaml ./app/pnpm-workspace.yaml ./

COPY ./app/patches ./patches

RUN pnpm install --frozen-lockfile

COPY ./app/ ./

RUN pnpm run build

FROM nginx:1.28-alpine

RUN rm -rf /usr/share/nginx/html/*

COPY --from=build /app/dist /usr/share/nginx/html

COPY ./generate-env-config.sh /docker-entrypoint.d/20-generate-env-config.sh
RUN chmod +x /docker-entrypoint.d/20-generate-env-config.sh

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]