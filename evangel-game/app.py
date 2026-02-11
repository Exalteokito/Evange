from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
import random
import uuid
import re

app = Flask(__name__)

# -------------------------------------------------
# Base paths (works on Windows + Render)
# -------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
GENERATED_FOLDER = os.path.join(BASE_DIR, "static", "generated")
LOGO_PATH = os.path.join(BASE_DIR, "static", "logo.png")
FONT_DIR = os.path.join(BASE_DIR, "static", "fonts")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GENERATED_FOLDER, exist_ok=True)

# -------------------------------------------------
# Event / Church Info (EDIT THESE)
# -------------------------------------------------
CHURCH_NAME = "ICC Ottawa"
EVENT_TITLE = "GAGNEURS D’ÂMES"
DATE_TIME = "À 12h00"
LOCATION = " "
TAGLINE = "Sortie d’évangélisation"

# -------------------------------------------------
# Results
# title = headline shown big
# msg   = full sentence shown under title (wrapped)
# -------------------------------------------------
RESULTS = [
    {"title": "Célibataire détecté", "msg": "Mission assignée : Rideau (14 février)."},
    {"title": "Statut confirmé", "msg": "Célibataire & en mission — on se retrouve ce samedi à Rideau pour l’évangélisation."},
    {"title": "Mission", "msg": "Gagner des âmes à Rideau. 14 février."},
    {"title": "Je suis célibataire", "msg": "Donc ce samedi je serai en mission pour gagner des âmes à Rideau."},
]

# -------------------------------------------------
# Fonts (DO NOT BREAK ON RENDER)
# Put these files in: static/fonts/
#   - DejaVuSans.ttf
#   - DejaVuSans-Bold.ttf
# -------------------------------------------------
def try_font(size: int, bold: bool = False):
    ttf = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    path = os.path.join(FONT_DIR, ttf)
    try:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    except:
        pass

    # Windows fallback for local dev (optional)
    win = r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"
    try:
        if os.path.exists(win):
            return ImageFont.truetype(win, size)
    except:
        pass

    return ImageFont.load_default()

def sanitize_for_poster(text: str) -> str:
    # Remove emojis/symbols that can show as □ on some servers
    text = re.sub(r"[^\w\sÀ-ÿ’'-:,.!?]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text

# -------------------------------------------------
# Image helpers
# -------------------------------------------------
def make_mission_background(w=1080, h=1080):
    base = Image.new("RGB", (w, h), (8, 12, 25))
    px = base.load()

    top = (8, 12, 25)
    bottom = (16, 28, 70)

    for y in range(h):
        t = y / (h - 1)
        r = int(top[0] + t * (bottom[0] - top[0]))
        g = int(top[1] + t * (bottom[1] - top[1]))
        b = int(top[2] + t * (bottom[2] - top[2]))
        for x in range(w):
            px[x, y] = (r, g, b)

    base = base.convert("RGBA")

    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((w * 0.15, -h * 0.15, w * 0.85, h * 0.55), fill=(255, 255, 255, 35))
    glow = glow.filter(ImageFilter.GaussianBlur(40))
    base = Image.alpha_composite(base, glow)

    vignette = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vignette)
    vd.rectangle((0, 0, w, h), outline=(0, 0, 0, 130), width=120)
    vignette = vignette.filter(ImageFilter.GaussianBlur(18))
    base = Image.alpha_composite(base, vignette)

    return base

def crop_circle(im: Image.Image, size: int):
    im = im.convert("RGBA").resize((size, size))
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse((0, 0, size, size), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out

def draw_centered(draw: ImageDraw.ImageDraw, text: str, y: int, font: ImageFont.ImageFont, fill, W: int):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (W - tw) // 2
    draw.text((x, y), text, font=font, fill=fill)

def wrap_by_pixel(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int):
    words = text.split()
    lines = []
    current = ""
    for w in words:
        test = (current + " " + w).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines

# -------------------------------------------------
# Poster generator (what was working + stable spacing)
# -------------------------------------------------
def generate_result_poster(photo_path: str, result_title: str, result_msg: str):
    W, H = 1080, 1080
    base = make_mission_background(W, H)
    draw = ImageDraw.Draw(base)

    # Colors
    WHITE = (245, 248, 255, 255)
    SOFT = (200, 210, 230, 235)
    ACCENT = (90, 180, 255, 255)
    BORDER = (90, 180, 255, 255)

    # Fonts
    f_church = try_font(48, bold=True)
    f_small = try_font(32, bold=False)
    f_title = try_font(68, bold=True)
    f_result = try_font(48, bold=True)
    f_msg = try_font(32, bold=False)

    # Logo (top-left)
    logo_w = 0
    if os.path.exists(LOGO_PATH):
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo.thumbnail((140, 140))
        base.paste(logo, (70, 60), logo)
        logo_w = logo.size[0]

    # Top text (church + tagline)
    top_x = 70 + (logo_w + 25 if logo_w else 0)
    draw.text((top_x, 70), CHURCH_NAME, font=f_church, fill=WHITE)
    if TAGLINE.strip():
        draw.text((top_x, 130), TAGLINE, font=f_small, fill=SOFT)

    # Event title (center)
    title_y = 190
    draw_centered(draw, EVENT_TITLE, y=title_y, font=f_title, fill=WHITE, W=W)

    # Divider
    div_y = title_y + 95
    draw.rounded_rectangle((260, div_y, 820, div_y + 6), radius=3, fill=ACCENT)

    # Photo circle (center)
    CIRCLE = 470
    BORDER_SIZE = CIRCLE + 46
    photo_x = (W - BORDER_SIZE) // 2
    photo_y = div_y + 35

    user_img = Image.open(photo_path)
    circle = crop_circle(user_img, CIRCLE)

    border = Image.new("RGBA", (BORDER_SIZE, BORDER_SIZE), (0, 0, 0, 0))
    bd = ImageDraw.Draw(border)
    bd.ellipse((0, 0, BORDER_SIZE - 1, BORDER_SIZE - 1), outline=BORDER, width=14)

    base.paste(border, (photo_x, photo_y), border)
    base.paste(circle, (photo_x + 23, photo_y + 23), circle)

    photo_bottom = photo_y + BORDER_SIZE

    # Result headline + message (FULL)
    clean_title = sanitize_for_poster(result_title).upper()
    clean_msg = sanitize_for_poster(result_msg)

    headline_y = photo_bottom + 24
    draw_centered(draw, clean_title, y=headline_y, font=f_result, fill=WHITE, W=W)

    lines = wrap_by_pixel(draw, clean_msg, f_msg, 900)[:2]
    msg_y = headline_y + 64
    for i, line in enumerate(lines):
        draw_centered(draw, line, y=msg_y + i * 38, font=f_msg, fill=SOFT, W=W)

    # Footer details
    details = f"{DATE_TIME}  •  {LOCATION}"
    draw_centered(draw, details, y=H - 70, font=f_small, fill=SOFT, W=W)

    # Save
    out_name = f"{uuid.uuid4().hex}.png"
    out_path = os.path.join(GENERATED_FOLDER, out_name)
    base.save(out_path, "PNG")
    return out_path

# -------------------------------------------------
# Routes
# -------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    if "photo" not in request.files:
        return redirect(url_for("index"))

    file = request.files["photo"]
    if file.filename == "":
        return redirect(url_for("index"))

    filename = secure_filename(file.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        return "Format non supporté. Utilise JPG/PNG/WebP.", 400

    unique_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(UPLOAD_FOLDER, unique_name)
    file.save(save_path)

    result = random.choice(RESULTS)

    generated_path = generate_result_poster(
        photo_path=save_path,
        result_title=result["title"],
        result_msg=result["msg"]
    )

    # URL for browser
    poster_url = "/static/generated/" + os.path.basename(generated_path)

    # (Optional) caption only for copy button (does not change anything else)
    caption = f"{EVENT_TITLE} • {LOCATION} • {DATE_TIME}"

    return render_template("result.html", poster_url=poster_url, caption=caption)

if __name__ == "__main__":
    # Local run only. On Render you run with gunicorn.
    app.run(debug=True)
