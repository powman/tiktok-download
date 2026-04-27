# TikTok Download

Download de vídeos do TikTok com processamento de vídeo via interface web usando Docker.

<div align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Flask-000000?style=flat&logo=flask&logoColor=white" />
  <img src="https://img.shields.io/badge/FFmpeg-007880?style=flat&logo=ffmpeg&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white" />
</div>

## 📋 O que faz

- **Download**: Baixa vídeos do TikTok/YouTube via yt-dlp
- **Processamento**: Aplica filtros de vídeo (escala, overlay, watermark)
- **Reação**: Suporta adicionar vídeo de reação em overlay
- **Extração**: Extrai metadados (título, descrição, autor, duração)

## 🚀 Quick Start

```bash
# Copie o arquivo .env.example para .env (opcional - para customizar)
cp .env.example .env

docker compose up --build
```

Acesse: **http://localhost:8082**

## 📁 Estrutura

```
tiktok-download/
├── .env.example            # Exemplo de variáveis de ambiente
├── docker-compose.yml
├── README.md
├── backend/
│   ├── app.py              # API Flask (porta 5000)
│   ├── Dockerfile
│   └── requirements.txt
└── frontend/
    ├── index.html          # Interface web
    ├── config.js.template  # Template de configuração
    ├── nginx-entrypoint.sh # Script de startup do nginx
    └── Dockerfile
```

## 🛠️ Tech Stack

- **Backend**: Python + Flask + yt-dlp
- **Frontend**: HTML + CSS + JavaScript
- **Processamento**: FFmpeg
- **Infra**: Docker + Docker Compose

## 📡 API Endpoints

### `POST /process`
Processa um vídeo

**Parâmetros:**
- `url` (string) - URL do vídeo
- `watermark` (string) - Texto da marca d'água
- `reaction` (file) - Arquivo de reação (opcional)

**Resposta:**
```json
{
  "job_id": "uuid-da-tarefa"
}
```

### `GET /status/<job_id>`
Status da tarefa

**Resposta:**
```json
{
  "status": "downloading|processing|done|error",
  "file": "caminho/do/arquivo",
  "caption": "descrição do vídeo",
  "message": "mensagem de erro (se houver)"
}
```

### `GET /file/<job_id>`
Download do arquivo processado

### `POST /extract-info`
Extrai metadados do vídeo

**Parâmetros:**
- `url` (string) - URL do vídeo

**Resposta:**
```json
{
  "title": "...",
  "description": "...",
  "uploader": "...",
  "duration": 123,
  "thumbnail": "url"
}
```

## ⚙️ Configuração

### Variáveis de Ambiente

No arquivo `.env` (copie de `.env.example`), você pode configurar:

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `VITE_API_URL` | URL da API para o frontend | `http://localhost:5000` |
| `VITE_EXTRACT_API_URL` | URL para extração de metadados | `http://localhost:5000` |
| `CORS_ORIGINS` | Origins permitidos | `http://localhost:8082` |

### Portas
- **Frontend**: 8082 (nginx)
- **Backend**: 5000 (Flask)

### Rebuild após alterar variáveis

```bash
docker compose down
docker compose up -d --build
```

## 📝 Notas

- Vídeos são salvos no diretório `./downloads` (montado como volume)
- Suporta TikTok e YouTube
- Processamento é assíncrono (threading)
- Arquivos temporários são removidos após conclusão
- O frontend lê a configuração via `config.js` gerado no startup do container

## 🔧 Requisitos

- Docker
- Docker Compose
- FFmpeg (instalado nos containers)

## 📜 Licença

Confira os Termos de Serviço do TikTok antes de usar.
