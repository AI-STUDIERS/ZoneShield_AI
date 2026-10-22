FROM nginx:alpine

# Copy static frontend files
COPY frontend/index.html /usr/share/nginx/html/index.html

# Expose frontend port
EXPOSE 3000

# Nginx config for SPA-like behavior
RUN echo 'server { \
    listen 3000; \
    server_name localhost; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
}' > /etc/nginx/conf.d/default.conf

CMD ["nginx", "-g", "daemon off;"]