# Stage 1: Build production React/Vite assets
FROM node:22-alpine AS builder

WORKDIR /app

# Copy package descriptors first for Docker layer caching
COPY package*.json ./

# Install dependencies strictly
RUN npm ci

# Copy full frontend source code
COPY . .

# Embed production API URL during Vite build
ARG VITE_API_BASE_URL=https://psw-api.lcrana.in
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Build static bundle to dist/
RUN npm run build

# Stage 2: Serve static files with lightweight Nginx
FROM nginx:1.27-alpine

# Remove default nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy built frontend assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy optimized nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1:80/ > /dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
