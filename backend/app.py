from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from yt_dlp import YoutubeDL
import os, uuid, threading, subprocess, random

app = Flask(__name__)
CORS(app)

WORK_DIR = "/downloads"
os.makedirs(WORK_DIR, exist_ok=True)
jobs = {}


def build_filter_complex(has_reaction, watermark_text, speed_factor=0.98, fps=29.970):
    """
    Constrói filter complex com técnicas anti-detecção:
    - Velocidade alterada
    - FPS não-padrão
    - Ajustes de cor sutis
    - Ruído invisível
    - Shift de matiz
    """
    wm = watermark_text.replace("'", "\\'")
    
    # Velocidade alterada via setpts
    speed_filter = f"setpts=PTS/{speed_factor},"
    
    # FPS não-padrão para quebrar fingerprints temporais
    fps_filter = f"fps=fps={fps},"
    
    # Ajustes de cor sutis (brightness, contrast, saturation, gamma)
    color_adjust = "eq=brightness=0.03:contrast=1.03:saturation=0.98:gamma=1.01"
    
    # Unsharp para alterar nitidez
    unsharp = "unsharp=luma_msize_x=3:luma_msize_y=3:luma_amount=0.5"
    
    # Ruído invisível que quebra hash visual
    noise = "noise=alls=3:allf=t+u"
    
    # Shift mínimo de matiz
    hue = "hue=h=0.5"
    
    # Drawtext com velocidade alterada e cores invertidas (branco com borda preta)
    drawtext = (
        f"drawtext=text='{wm}':fontsize=32:fontcolor=white:borderw=3:"
        f"bordercolor=black:x='abs(mod(t*{int(280*speed_factor)}\,2*(W-tw))-(W-tw))':"
        f"y='abs(mod(t*{int(240*speed_factor)}\,2*(H-th))-(H-th))'"
    )

    # Processamento direto sem pillarbox blur
    base_filter = (
        f"[0:v]{speed_filter}{fps_filter}format=yuv420p,scale=1080:1920:force_original_aspect_ratio=decrease,"
        f"{color_adjust},{unsharp}[processed];"
    )

    if has_reaction:
        return (
            f"[processed]{drawtext}[watermarked];"
            "[watermarked][1:v]overlay=W-w-60:H-h-60:enable='between(t,0,20)',"
            f"{noise},{hue}[final]"
        )
    else:
        return (
            f"[processed]{drawtext},{noise},{hue}[final]"
        )


def do_process(job_id, video_url, reaction_path, watermark_text):
    temp_video = os.path.join(WORK_DIR, f"{job_id}_temp.mp4")
    temp_processed = os.path.join(WORK_DIR, f"{job_id}_processed.mp4")
    output_path = os.path.join(WORK_DIR, f"{job_id}_final.mp4")
    
    try:
        jobs[job_id] = {"status": "downloading"}
        with YoutubeDL({"outtmpl": temp_video, "format": "mp4", "quiet": True}) as ydl:
            ydl.download([video_url])

        caption = ""
        try:
            r = subprocess.run(["yt-dlp","--no-update","--get-description","--quiet", video_url],
                               capture_output=True, text=True, timeout=30)
            caption = r.stdout.strip()
        except Exception:
            pass

        jobs[job_id] = {"status": "processing"}
        has_reaction = reaction_path and os.path.exists(reaction_path)
        
        # Metadados aleatórios para primeiro passo
        titles = ["Content Creator", "Original Video", "Creator Hub", "Video Studio", "Media Lab"]
        artists = ["CreatorName", "StudioX", "ContentMaker", "VideoArtist", "MediaPro"]
        
        # PRIMEIRO PASSO: Aplica todas as transformações visuais
        filter_complex_pass1 = build_filter_complex(
            has_reaction, watermark_text, 
            speed_factor=0.98, fps=29.970
        )
        
        cmd_pass1 = ["ffmpeg", "-y", "-i", temp_video]
        if has_reaction:
            cmd_pass1 += ["-i", reaction_path]
        
        # Corte de 0.5s no início, duração 59s (quebra hash de duração)
        cmd_pass1 += [
            "-ss", "00:00:00.5",
            "-t", "59",
            "-filter_complex", filter_complex_pass1,
            "-map", "[final]",
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "26",  # CRF mais baixo no primeiro passo
            "-profile:v", "high",
            "-level", "4.1",
            "-g", "48",
            "-movflags", "+faststart",
            "-pix_fmt", "yuv420p",
            "-an",  # Sem áudio
            "-metadata", f"title={random.choice(titles)}",
            "-metadata", f"artist={random.choice(artists)}",
            "-metadata", "comment=Original content",
            temp_processed
        ]

        proc1 = subprocess.run(cmd_pass1, capture_output=True, text=True)
        if proc1.returncode != 0:
            raise RuntimeError(f"Passo 1 falhou: {proc1.stderr[-2000:]}")

        # SEGUNDO PASSO: Re-encode com ruído adicional e metadados diferentes
        filter_complex_pass2 = "[0:v]format=yuv420p,noise=alls=2:allf=t+u[final]"
        
        cmd_pass2 = [
            "ffmpeg", "-y", "-i", temp_processed,
            "-filter_complex", filter_complex_pass2,
            "-map", "[final]",
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "28",  # CRF diferente no segundo passo
            "-profile:v", "high",
            "-level", "4.1",
            "-g", "48",
            "-movflags", "+faststart",
            "-pix_fmt", "yuv420p",
            "-an",
            "-metadata", "title=Final Video",
            "-metadata", f"artist={watermark_text}",
            "-metadata", "comment=Processed",
            output_path
        ]

        proc2 = subprocess.run(cmd_pass2, capture_output=True, text=True)
        if proc2.returncode != 0:
            raise RuntimeError(f"Passo 2 falhou: {proc2.stderr[-2000:]}")

        jobs[job_id] = {"status": "done", "file": output_path, "caption": caption}
        
    except Exception as e:
        jobs[job_id] = {"status": "error", "message": str(e)}
    finally:
        # Limpeza de arquivos temporários
        for f in [temp_video, temp_processed]:
            if os.path.exists(f):
                os.remove(f)


@app.route("/process", methods=["POST"])
def process():
    video_url = request.form.get("url", "").strip()
    watermark = request.form.get("watermark", "@meucanal").strip()
    if not video_url:
        return jsonify({"error": "URL is required"}), 400

    job_id = str(uuid.uuid4())
    job_dir = os.path.join(WORK_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    reaction_path = None
    reaction_file = request.files.get("reaction")
    if reaction_file and reaction_file.filename:
        reaction_path = os.path.join(job_dir, "reaction.mp4")
        reaction_file.save(reaction_path)

    jobs[job_id] = {"status": "pending"}
    threading.Thread(target=do_process, args=(job_id, video_url, reaction_path, watermark)).start()
    return jsonify({"job_id": job_id}), 202


@app.route("/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)
    return jsonify(job) if job else (jsonify({"error": "Job not found"}), 404)


@app.route("/file/<job_id>")
def get_file(job_id):
    job = jobs.get(job_id)
    if not job or job["status"] != "done":
        return jsonify({"error": "File not ready"}), 404
    return send_file(job["file"], as_attachment=True, download_name="video_processado.mp4")

@app.route("/extract-info", methods=["POST"])
def extract_info():
    if request.is_json:
        video_url = request.json.get("url", "").strip()
    else:
        video_url = request.form.get("url", "").strip()
    
    if not video_url:
        return jsonify({"error": "URL is required"}), 400
    
    try:
        # Usa --dump-json para pegar TODOS os metadados de uma vez
        result = subprocess.run(
            ["yt-dlp", "--no-update", "--dump-json", "--quiet", video_url],
            capture_output=True, text=True, timeout=30
        )
        
        if result.returncode != 0:
            return jsonify({"error": result.stderr.strip()}), 500
        
        import json
        data = json.loads(result.stdout.strip().split('\n')[0])  # pega primeiro JSON se houver múltiplos
        
        # Campos relevantes para TikTok/YouTube
        title = data.get("title", "")
        description = data.get("description", "")
        uploader = data.get("uploader", data.get("channel", ""))
        duration = data.get("duration", 0)
        thumbnail = data.get("thumbnail", "")
        
        # Fallback: se description vazia, tenta usar title (TikTok coloca caption no title às vezes)
        if not description and title:
            description = title
        
        return jsonify({
            "title": title,
            "description": description,
            "uploader": uploader,
            "duration": duration,
            "thumbnail": thumbnail
        })
        
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timeout ao extrair informações"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)