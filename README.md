# 🎵 TikTok Downloader

Baixe vídeos do TikTok sem marca d'água via interface web, rodando com Docker.

## Estrutura


ffmpeg -y -i "video_processado.mp4" -ss 00:00:00.5 -t 59 -filter_complex "[0:v]setpts=PTS/0.98,fps=fps=29.970,format=yuv420p,split[main][blur];[blur]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=30,eq=brightness=-0.28:contrast=0.98[bg];[main]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:810,eq=brightness=0.03:contrast=1.03:saturation=0.98:gamma=1.01,unsharp=luma_msize_x=3:luma_msize_y=3:luma_amount=0.5[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[composited];[composited]drawtext=text='@meucanal':fontsize=32:fontcolor=white:borderw=3:bordercolor=black:x='abs(mod(t*280\,2*(W-tw))-(W-tw))':y='abs(mod(t*240\,2*(H-th))-(H-th))',noise=alls=3:allf=t+u,hue=h=0.5[final]" -map "[final]" -c:v libx264 -preset slow -crf 26 -an -metadata title="Content Creator" -metadata artist="CreatorName" -metadata comment="Original content" -movflags +faststart "temp_saida.mp4" && ffmpeg -y -i "temp_saida.mp4" -filter_complex "[0:v]format=yuv420p,noise=alls=2:allf=t+u[final]" -map "[final]" -c:v libx264 -preset slow -crf 28 -an -metadata title="Final Video" -metadata artist="@meucanal" -movflags +faststart "saida.mp4" && rm temp_saida.mp4

```
tiktok-downloader/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py
└── frontend/
    ├── Dockerfile
    └── index.html
```

## Como usar

```bash
docker compose up --build
```

Acesse: http://localhost:8080

## Stack

- **Frontend:** HTML + CSS + JS puro (servido via nginx)
- **Backend:** Python + Flask + yt-dlp
- **Infra:** Docker + Docker Compose
