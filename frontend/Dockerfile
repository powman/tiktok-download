FROM nginx:alpine
COPY nginx-entrypoint.sh /entrypoint.sh
COPY index.html /usr/share/nginx/html/index.html
COPY config.js.template /usr/share/nginx/html/config.js
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
EXPOSE 80
