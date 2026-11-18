FROM node:22-alpine AS build
WORKDIR /ui
COPY package.json package-lock.json ./
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -s /run/secrets/extra_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/extra_ca; fi; npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
ENV NGINX_RESOLVER=127.0.0.11 FLO_API_UPSTREAM=http://api:8000 NGINX_ENVSUBST_FILTER="^(NGINX_RESOLVER|FLO_API_UPSTREAM)$"
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /ui/dist /usr/share/nginx/html
EXPOSE 8080
