from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from yt_dlp import YoutubeDL
import os, uuid, threading, subprocess, random, sqlite3, json, re
from datetime import datetime, timezone
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)
CORS(app)

WORK_DIR = "/downloads"
os.makedirs(WORK_DIR, exist_ok=True)
jobs = {}

PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:5001").rstrip("/")
HISTORY_DB = os.path.join(WORK_DIR, "history.db")

GOOGLE_SHEETS_ID = os.environ.get("GOOGLE_SHEETS_ID", "")
GOOGLE_SHEETS_CREDENTIALS_PATH = os.environ.get(
    "GOOGLE_SHEETS_CREDENTIALS_PATH", "/app/credentials/google-sheets.json"
)
SHEET_HEADER = ["Título", "Descrição", "URL", "Data"]

_worksheet_cache = {"worksheet": None}


def get_worksheet():
    if _worksheet_cache["worksheet"] is not None:
        return _worksheet_cache["worksheet"]
    if not GOOGLE_SHEETS_ID or not os.path.exists(GOOGLE_SHEETS_CREDENTIALS_PATH):
        return None
    try:
        creds = Credentials.from_service_account_file(
            GOOGLE_SHEETS_CREDENTIALS_PATH,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        client = gspread.authorize(creds)
        worksheet = client.open_by_key(GOOGLE_SHEETS_ID).sheet1
        _worksheet_cache["worksheet"] = worksheet
        return worksheet
    except Exception as e:
        print(f"[google-sheets] erro ao conectar: {e}")
        return None


def sheet_append_row(item):
    worksheet = get_worksheet()
    if worksheet is None:
        return False
    try:
        if not worksheet.get_all_values():
            worksheet.append_row(SHEET_HEADER)
        worksheet.append_row([
            item.get("title") or "",
            item.get("description") or "",
            item.get("video_url") or "",
            item.get("processed_at") or "",
        ])
        return True
    except Exception as e:
        print(f"[google-sheets] erro ao adicionar linha: {e}")
        return False


def sheet_remove_row(video_url):
    worksheet = get_worksheet()
    if worksheet is None or not video_url:
        return False
    try:
        cell = worksheet.find(video_url)
        if cell:
            worksheet.delete_rows(cell.row)
        return True
    except Exception as e:
        print(f"[google-sheets] erro ao remover linha: {e}")
        return False


def get_db():
    conn = sqlite3.connect(HISTORY_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS videos_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                description TEXT,
                video_url TEXT,
                processed_at TEXT,
                uploaded INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
        """)


init_db()


def fetch_video_metadata(video_url):
    try:
        result = subprocess.run(
            ["yt-dlp", "--no-update", "--dump-json", "--quiet", video_url],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return {"title": "", "description": ""}
        data = json.loads(result.stdout.strip().split("\n")[0])
        title = data.get("title", "")
        description = data.get("description", "")
        if not description and title:
            description = title
        return {"title": title, "description": description}
    except Exception:
        return {"title": "", "description": ""}


def save_history(title, description, video_url):
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO videos_history (title, description, video_url, processed_at, uploaded, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 0, ?, ?)",
            (title, description, video_url, now, now, now)
        )


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

    # Pillarbox Blur com parâmetros alterados
    base_filter = (
        f"[0:v]{speed_filter}{fps_filter}format=yuv420p,split[main][blur];"
        "[blur]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        "gblur=sigma=30,eq=brightness=-0.28:contrast=0.98[bg];"
        "[main]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:810,"
        f"{color_adjust},{unsharp}[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2[composited];"
    )

    if has_reaction:
        return (
            base_filter +
            f"[composited]{drawtext}[watermarked];"
            "[watermarked][1:v]overlay=W-w-60:H-h-60:enable='between(t,0,20)',"
            f"{noise},{hue}[final]"
        )
    else:
        return (
            base_filter +
            f"[composited]{drawtext},{noise},{hue}[final]"
        )


def do_process(job_id, video_url, reaction_path, watermark_text):
    temp_video = os.path.join(WORK_DIR, f"{job_id}_temp.mp4")
    temp_processed = os.path.join(WORK_DIR, f"{job_id}_processed.mp4")
    output_path = os.path.join(WORK_DIR, f"{job_id}_final.mp4")
    
    try:
        jobs[job_id] = {"status": "downloading"}
        with YoutubeDL({"outtmpl": temp_video, "format": "mp4", "quiet": True}) as ydl:
            ydl.download([video_url])

        metadata = fetch_video_metadata(video_url)
        title = metadata["title"]
        caption = metadata["description"]

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
        save_history(title, caption, f"{PUBLIC_BASE_URL}/videos/{job_id}")

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


UUID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")


@app.route("/videos/<job_id>")
def serve_video(job_id):
    if not UUID_RE.match(job_id):
        return jsonify({"error": "ID inválido"}), 400

    path = os.path.join(WORK_DIR, f"{job_id}_final.mp4")
    if not os.path.exists(path):
        return jsonify({"error": "Vídeo não encontrado"}), 404

    return send_file(path, mimetype="video/mp4")


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


SORT_COLUMNS = {
    "newest": "processed_at DESC",
    "oldest": "processed_at ASC",
    "title_asc": "title COLLATE NOCASE ASC",
    "title_desc": "title COLLATE NOCASE DESC",
}


@app.route("/history", methods=["GET"])
def get_history():
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("filter", "all")
    sort = request.args.get("sort", "newest")
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = max(1, min(100, int(request.args.get("per_page", 10))))
    except ValueError:
        page, per_page = 1, 10

    where = []
    params = []
    if search:
        where.append("(title LIKE ? OR description LIKE ? OR video_url LIKE ?)")
        like = f"%{search}%"
        params += [like, like, like]
    if status_filter == "sent":
        where.append("uploaded = 1")
    elif status_filter == "pending":
        where.append("uploaded = 0")

    where_clause = f"WHERE {' AND '.join(where)}" if where else ""
    order_clause = SORT_COLUMNS.get(sort, SORT_COLUMNS["newest"])

    with get_db() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM videos_history {where_clause}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM videos_history {where_clause} ORDER BY {order_clause} LIMIT ? OFFSET ?",
            params + [per_page, (page - 1) * per_page]
        ).fetchall()
        uploaded_count = conn.execute("SELECT COUNT(*) FROM videos_history WHERE uploaded = 1").fetchone()[0]
        total_count = conn.execute("SELECT COUNT(*) FROM videos_history").fetchone()[0]

    items = [dict(row) for row in rows]

    return jsonify({
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": max(1, (total + per_page - 1) // per_page),
        "stats": {
            "total": total_count,
            "uploaded": uploaded_count,
            "pending": total_count - uploaded_count,
        }
    })


@app.route("/history/<int:history_id>", methods=["PATCH"])
def update_history(history_id):
    data = request.get_json(silent=True) or {}
    if "uploaded" not in data:
        return jsonify({"error": "Campo 'uploaded' é obrigatório"}), 400

    uploaded = 1 if data["uploaded"] else 0
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        cur = conn.execute(
            "UPDATE videos_history SET uploaded = ?, updated_at = ? WHERE id = ?",
            (uploaded, now, history_id)
        )
        if cur.rowcount == 0:
            return jsonify({"error": "Registro não encontrado"}), 404
        row = conn.execute("SELECT * FROM videos_history WHERE id = ?", (history_id,)).fetchone()

    item = dict(row)
    if uploaded:
        sheet_append_row(item)
    else:
        sheet_remove_row(item.get("video_url"))

    return jsonify(item)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)