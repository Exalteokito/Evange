from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
import random
import uuid
import re

app = Flask(__name__)

# ----------------------------
# Folders
# ----------------------------
UPLOAD_FOLDER = os.path.join("static", "uploads")
GENERATED_FOLDER = os.path.join("static", "generated")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GENERATED_FOLDER, exist_ok=True)

# ----------------------------
# LOGO
# Put logo at static\logo.png
LOGO_PATH = os.path.join("static", "logo.png")




CHURCH_NAME = "ICC Ottawa"
EVENT_TITLE = "GAGNEURS D’ÂMES"
TAGLINE = "Sortie d’évangélisation"

# ----------------------------
# Results
# title = short headline
# msg   = full sentence to display under title
# ----------------------------
RESULTS = [
    {"title": "Célibataire détecté", "msg": "Mission assignée : Rideau (14 février)."},
    {"title": "Statut confirmé", "msg": "Célibataire & en mission — on se retrouve à Rideau pour l’évangélisation."},
    {"title": "Mission", "msg": "Gagner des âmes à Rideau. 14 février."},
    {"title": "Je suis célibataire", "msg": "Donc ce samedi je serai en mission pour gagner des âmes à Rideau."},
]

# ----------------------------
# Fonts
# ----------------------------
def try_font(size: int, bold=False):
    here = os.path.dirname(os.path.abspath(__file__))
    font_dir = os.path.join(here, "static", "fonts")
    font_path = os.path.join(font_dir, "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")

    try:
        if os.path.exists(font_path):
            return ImageFont.truetype(font_path, size)
    except:
        pass

    return ImageFont.load_default()



def sanitize_for_poster(text: str) -> str:
    text = re.sub(r"[^\w\sÀ-ÿ’'-:,.!?]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text

# ----------------------------
# Background / helpers
# ----------------------------
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
    im = im.convert("RGBA")
    im = im.resize((size, size))
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse((0, 0, size, size), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out

def draw_centered(draw, text, y, font, fill, W=1080):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (W - tw) // 2
    draw.text((x, y), text, font=font, fill=fill)

def wrap_by_pixel(draw, text, font, max_width):
    """Wrap text into multiple lines based on pixel width (best wrapping)."""
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

def generate_result_poster(photo_path: str, result_title: str, result_msg: str):
    W, H = 1080, 1080
    base = make_mission_background(W, H)
    draw = ImageDraw.Draw(base)

    # Fonts
    f_church = try_font(48, bold=True)
    f_small = try_font(32, bold=False)
    f_title = try_font(70, bold=True)      # main title
    f_result = try_font(46, bold=True)     # headline result (bigger)
    f_msg = try_font(32, bold=False)       # message under result

    # Colors
    WHITE = (245, 248, 255, 255)
    SOFT = (200, 210, 230, 235)
    ACCENT = (90, 180, 255, 255)
    BORDER = (90, 180, 255, 255)

    # Logo
    if os.path.exists(LOGO_PATH):
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo.thumbnail((160, 160))
        base.paste(logo, (70, 70), logo)

    # Top text
    draw.text((250, 78), CHURCH_NAME, font=f_church, fill=WHITE)
    if TAGLINE.strip():
        draw.text((250, 138), TAGLINE, font=f_small, fill=SOFT)

    # Main Title
    draw_centered(draw, EVENT_TITLE, y=190, font=f_title, fill=WHITE, W=W)

    # Divider line
    line_y = 340
    draw.rounded_rectangle((260, line_y, 820, line_y + 6), radius=3, fill=ACCENT)

    # Photo circle
    user_img = Image.open(photo_path)
    circle = crop_circle(user_img, 520)

    border = Image.new("RGBA", (570, 570), (0, 0, 0, 0))
    bd = ImageDraw.Draw(border)
    bd.ellipse((0, 0, 569, 569), outline=BORDER, width=14)

    x = (W - 570) // 2
    y = 380
    base.paste(border, (x, y), border)
    base.paste(circle, (x + 25, y + 25), circle)

    # Result headline + message (FULL)
    clean_title = sanitize_for_poster(result_title).upper()
    clean_msg = sanitize_for_poster(result_msg)

    headline_y = 920  # below photo
    draw_centered(draw, clean_title, y=headline_y, font=f_result, fill=WHITE, W=W)

    # Wrap message under headline (2-3 lines)
    max_text_width = 900  # pixels
    lines = wrap_by_pixel(draw, clean_msg, f_msg, max_text_width)
    lines = lines[:3]  # limit to 3 lines max

    msg_y = headline_y + 60  # spacing under headline
    for i, line in enumerate(lines):
        draw_centered(draw, line, y=msg_y + (i * 40), font=f_msg, fill=SOFT, W=W)

    # Footer details

    # Save
    out_name = f"{uuid.uuid4().hex}.png"
    out_path = os.path.join(GENERATED_FOLDER, out_name)
    base.save(out_path, "PNG")
    return out_path

# ----------------------------
# Routes
# ----------------------------
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

    poster_url = "/" + generated_path.replace("\\", "/")
    return render_template("result.html", poster_url=poster_url)

if __name__ == "__main__":
    app.run(debug=True)
