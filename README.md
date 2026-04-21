# TikTok Downloader

Download de vídeos do TikTok com processamento de vídeo via interface web usando Docker.

## 📋 O que faz

- **Download**: Baixa vídeos do TikTok/YouTube via yt-dlp
- **Processamento**: Aplica filtros de vídeo (escala, overlay, watermark)
- **Reação**: Suporta adicionar vídeo de reação em overlay
- **Extração**: Extrai metadados (título, descrição, autor, duração)

## 🚀 Quick Start

```bash
docker compose up --build
```

Acesse: **http://localhost:8080**

## 📁 Estrutura

```
tiktok-downloader/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── README.md
├── backend/
│   ├── app.py              # API Flask (porta 5000)
│   ├── Dockerfile
│   └── requirements.txt
└── frontend/
    ├── index.html          # Interface web (porta 80)
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
- `PYTHONUNBUFFERED=1` - Saída sem buffer

### Portas
- **Frontend**: 8080 (nginx)
- **Backend**: 5000 (Flask)
- **API**: 8000 (exposta via docker-compose)

## 📝 Notas

- Vídeos são salvos em `/downloads`
- Suporta TikTok e YouTube
- Processamento é assíncrono (threading)
- Arquivos temporários são removidos após conclusão

## 🔧 Requisitos

- Docker
- Docker Compose
- FFmpeg (instalado nos containers)

## 📜 Licença

Confira os Termos de Serviço do TikTok antes de usar.
