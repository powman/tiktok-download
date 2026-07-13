#!/bin/sh
# Gera config.js a partir das variáveis de ambiente

cat > /usr/share/nginx/html/config.js << EOF
// Configurações do frontend - gerado dinamicamente
window.APP_CONFIG = {
  API: "${VITE_API_URL:-http://localhost:5001}"
};
EOF

exec nginx -g 'daemon off;'
