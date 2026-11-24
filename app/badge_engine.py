# -*- coding: utf-8 -*-
"""
手机端渲染引擎（纯 Pillow + numpy，无 cv2）
=============================================
干净底图/字形库由桌面端 prepare_assets.py 预算好，本引擎只做：
  读干净基底 -> 三段拉伸 -> 画新文字 -> 合成逐帧 GIF。
"""
import os, json, re
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
TDIR = os.path.join(ASSETS, "templates")
GDIR = os.path.join(ASSETS, "glyphs")
FDIR = os.path.join(ASSETS, "fonts")
OUTDIR = os.path.join(HERE, "output")


def _font(name, size):
    p = os.path.join(FDIR, name)
    try:
        return ImageFont.truetype(p, size)
    except Exception:
        return ImageFont.load_default()


def _meta(key):
    with open(os.path.join(TDIR, f"{key}_meta.json"), encoding="utf-8") as f:
        return json.load(f)


def _load_clean(key):
    return np.array(Image.open(os.path.join(TDIR, f"{key}_clean.png")).convert("RGBA"))


def _load_left(key):
    im = Image.open(os.path.join(TDIR, f"{key}_left.gif"))
    frames = []
    for i in range(getattr(im, "n_frames", 1)):
        im.seek(i)
        frames.append(np.array(im.convert("RGBA")))
    return frames


# ------------------------------------------------------------
# 通用：三段伸缩（中段用 Pillow 双线性重采样，两端锚定）
# ------------------------------------------------------------
def _stretch(clean_rgba, x0, split, nw, W, H):
    out = np.zeros((H, W, 4), np.uint8)
    # 左段固定
    out[:, :x0] = clean_rgba[:, :x0]
    # 中段重采样
    seg = Image.fromarray(clean_rgba[:, x0:split], "RGBA").resize(
        (nw, H), Image.BILINEAR)
    out[:, x0:x0 + nw] = np.array(seg)
    # 右段整体右移
    delta = nw - (split - x0)
    cw = clean_rgba.shape[1] - split
    out[:, split + delta:split + delta + cw] = clean_rgba[:, split:]
    return out, delta


# ------------------------------------------------------------
# 多彩靓号：源图抠字形 + 精确字色
# ------------------------------------------------------------
_GLYPH = None
def _glyphs():
    global _GLYPH
    if _GLYPH is not None:
        return _GLYPH
    with open(os.path.join(GDIR, "glyphs.json"), encoding="utf-8") as f:
        meta = json.load(f)
    g = {}
    for ch, info in meta.items():
        alpha = np.array(Image.open(os.path.join(GDIR, f"g_{ord(ch)}.png")), np.uint8)
        g[ch] = (alpha, info["advance"])
    _GLYPH = g
    return g


def _draw_color_digits(text, rgb, x_center, y_center, font_size=76):
    glyphs = _glyphs()
    H = int(round(font_size * 1.5))
    advances = [glyphs[ch][1] if ch in glyphs else 46 for ch in text]
    strip_w = int(round(sum(advances) + 16))
    strip = Image.new("L", (strip_w, H), 0)
    x = 8.0
    for ch, adv in zip(text, advances):
        if ch in glyphs:
            a = glyphs[ch][0]
        else:
            a = _render_digit(ch, font_size)
        gh, gw = a.shape[:2]
        strip.paste(Image.fromarray(a, "L"), (int(round(x)), int(round((H - gh) / 2))))
        x += adv
    ar = np.array(strip)
    ys, xs = np.where(ar > 2)
    if not len(xs):
        return np.zeros((1, 1, 4), np.uint8), 0, 0
    alpha = ar[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    hh, ww = alpha.shape
    out = np.zeros((hh, ww, 4), np.uint8)
    out[:, :, :3] = np.array(rgb, np.uint8)
    out[:, :, 3] = alpha
    return out, int(round(x_center - ww / 2.0)), int(round(y_center - hh / 2.0))


def _render_digit(ch, size):
    """兜底数字（3/8 已含字形库，这里处理其它缺字）。"""
    f = _font("Dengl.ttf", size)
    b = f.getbbox(ch)
    tile = Image.new("L", (b[2] - b[0] + 20, b[3] - b[1] + 20), 0)
    ImageDraw.Draw(tile).text((10 - b[0], 10 - b[1]), ch, font=f, fill=255)
    ar = np.array(tile)
    ys, xs = np.where(ar > 8)
    return ar[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def _draw_color_mixed(text, rgb, x_center, y_center):
    font_num = _font("Dengl.ttf", 76)
    font_cjk = _font("msyh.ttc", 72)
    tiles, x = [], 0.0
    for ch in text:
        if ch.isdigit():
            font, adv = font_num, (32 if ch == "1" else 46)
        elif ord(ch) > 127:
            font, adv = font_cjk, 80.0
        else:
            font, adv = font_num, max(34.0, font_num.getlength(ch) + 10)
        b = font.getbbox(ch)
        w, h = b[2] - b[0], b[3] - b[1]
        if w <= 0 or h <= 0:
            continue
        tile = Image.new("L", (w + 24, h + 24), 0)
        ImageDraw.Draw(tile).text((12 - b[0], 12 - b[1]), ch, font=font, fill=255)
        ar = np.array(tile)
        ys, xs = np.where(ar > 8)
        if not len(xs):
            x += adv; continue
        tight = tile.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
        tiles.append((tight, x))
        x += adv
    if not tiles:
        return np.zeros((1, 1, 4), np.uint8), 0, 0
    sh = max(t.height for t, _ in tiles)
    sw = int(round(max(x + t.width for t, x in tiles)))
    strip = Image.new("L", (sw, sh), 0)
    for t, px in tiles:
        strip.paste(t, (int(round(px)), (sh - t.height) // 2))
    alpha = np.array(strip, np.uint8)
    hh, ww = alpha.shape
    out = np.zeros((hh, ww, 4), np.uint8)
    out[:, :, :3] = np.array(rgb, np.uint8)
    out[:, :, 3] = alpha
    return out, int(round(x_center - ww / 2.0)), int(round(y_center - hh / 2.0))


def generate_color(number, key, out_path=None):
    """多彩靓号：返回 (输出路径, 帧数, (W,H))。"""
    meta = _meta(f"color_{key}")
    text = str(number)
    clean = _load_clean(f"color_{key}")
    H, W0 = meta["H"], meta["W0"]
    x0, split = meta["x0"], meta["split"]
    # 按实际墨迹宽度决定中段
    probe, _, _ = (_draw_color_digits(text, meta["rgb"], 0, 0) if text.isdigit()
                   else _draw_color_mixed(text, meta["rgb"], 0, 0))
    tw = probe.shape[1]
    nw = max(int(round(tw + 2 * meta["side_pad"])), meta["min_mid"])
    delta = nw - (split - x0)
    base, _ = _stretch(clean, x0, split, nw, W0 + delta, H)
    W = base.shape[1]
    # 画字
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g, gx, gy = (_draw_color_digits(text, meta["rgb"], x0 + nw / 2.0, meta["ycenter"])
                 if text.isdigit() else
                 _draw_color_mixed(text, meta["rgb"], x0 + nw / 2.0, meta["ycenter"]))
    ov.paste(Image.fromarray(g, "RGBA"), (gx, gy))
    base_img = Image.alpha_composite(Image.fromarray(base, "RGBA"), ov)
    base_arr = np.array(base_img)
    # 透明区填邻近色
    opaque = base_arr[:, :, 3] > 0
    if opaque.any():
        samples = base_arr[:, x0:x0 + 3, :3][base_arr[:, x0:x0 + 3, 3] > 0]
        if len(samples):
            base_arr[~opaque, :3] = np.clip(np.median(samples, axis=0), 0, 255).astype(np.uint8)
    # 逐帧：只替换左侧动画区
    left = _load_left(f"color_{key}")
    frames, durs = [], []
    for i in range(meta["frames"]):
        f = base_arr.copy()
        if i < len(left) and left[i].shape[1] == x0:
            f[:, :x0] = left[i]
        frames.append(Image.fromarray(f, "RGBA"))
        durs.append(meta["durs"][i] if i < len(meta["durs"]) else 100)
    if out_path is None:
        os.makedirs(OUTDIR, exist_ok=True)
        out_path = os.path.join(OUTDIR, f"靓彩_{key}_{number}.gif")
    frames[0].save(out_path, save_all=True, append_images=frames[1:],
                   duration=durs, loop=0, disposal=2, optimize=False)
    return out_path, len(frames), (W, H)


# ------------------------------------------------------------
# 全模板（7 个单条）
# ------------------------------------------------------------
def _draw_gradient(text, meta, x_center, y_center):
    ss, size = meta["ss"], meta["size"]
    font = _font(meta["font"], size * ss)
    b = font.getbbox(text)
    pad = 4 * ss
    big = Image.new("L", ((b[2] - b[0]) + pad * 2, (b[3] - b[1]) + pad * 2), 0)
    ImageDraw.Draw(big).text((pad - b[0], pad - b[1]), text, font=font,
                             fill=255, stroke_width=meta["stroke"], stroke_fill=255)
    if meta.get("italic"):
        sh = meta["italic"] * ss
        arr = np.array(big); h, w = arr.shape
        addw = int(round(sh)) + 2
        shifted = np.zeros((h, w + addw), np.uint8)
        for yy in range(h):
            dx = int(round(sh * (1 - yy / max(1, h - 1))))
            shifted[yy, dx:dx + w] = arr[yy, :]
        big = Image.fromarray(shifted)
    ar = np.array(big)
    ys, xs = np.where(ar > 8)
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
    tight = big.crop((x0, y0, x1, y1))
    layer = tight.resize((max(1, int(round((x1 - x0) / ss))),
                          max(1, int(round((y1 - y0) / ss)))), Image.LANCZOS)
    alpha = np.array(layer, np.float32)
    hh, ww = alpha.shape
    stops = meta["grad"]
    grad = np.zeros((hh, 3), np.float32)
    for y in range(hh):
        t = y / max(1, hh - 1)
        for k in range(len(stops) - 1):
            t0, c0 = stops[k]; t1, c1 = stops[k + 1]
            if t <= t1:
                f = (t - t0) / max(1e-6, (t1 - t0))
                grad[y] = [c0[j] * (1 - f) + c1[j] * f for j in range(3)]
                break
        else:
            grad[y] = stops[-1][1]
    out = np.zeros((hh, ww, 4), np.uint8)
    out[:, :, :3] = np.clip(grad[:, None, :], 0, 255).astype(np.uint8)
    out[:, :, 3] = np.clip(alpha, 0, 255).astype(np.uint8)
    return out, int(round(x_center - ww / 2.0)), int(round(y_center - hh / 2.0))


def _measure(text, meta):
    font = _font(meta["font"], meta["size"] * meta["ss"])
    b = font.getbbox(text)
    tw = (b[2] - b[0]) / meta["ss"]
    if meta.get("italic"):
        tw += meta["italic"] * (b[3] - b[1]) / meta["ss"]
    return tw


import zipfile
from io import BytesIO


def _load_clean_seq(key):
    z = zipfile.ZipFile(os.path.join(TDIR, f"{key}_clean.zip"))
    frames = []
    for i in range(len(z.namelist())):
        frames.append(np.array(Image.open(BytesIO(z.read(f"{i:03d}.png"))).convert("RGBA")))
    return frames


def _fill_matte(arr, x0):
    opaque = arr[:, :, 3] > 0
    if opaque.any():
        samples = arr[:, x0:x0 + 3, :3][arr[:, x0:x0 + 3, 3] > 0]
        if len(samples):
            arr[~opaque, :3] = np.clip(np.median(samples, axis=0), 0, 255).astype(np.uint8)
    return arr


def generate_all(number, key, out_path=None):
    meta = _meta(f"all_{key}")
    H, W0 = meta["H"], meta["W0"]
    x0, split = meta["x0"], meta["split"]
    text = str(number)
    tw = _measure(text, meta)
    avail = split - x0
    delta = max(int(round(tw + meta["pad"] * 2 - avail)), meta["min_mid"] - avail)
    nw = avail + delta
    g, gx, gy = _draw_gradient(text, meta, x0 + nw / 2.0, meta["ycenter"])
    clean_seq = _load_clean_seq(f"all_{key}")
    frames, durs = [], []
    for i, clean in enumerate(clean_seq):
        base, _ = _stretch(clean, x0, split, nw, W0 + delta, H)
        ov = Image.new("RGBA", (W0 + delta, H), (0, 0, 0, 0))
        ov.paste(Image.fromarray(g, "RGBA"), (gx, gy))
        arr = np.array(Image.alpha_composite(Image.fromarray(base, "RGBA"), ov))
        arr = _fill_matte(arr, x0)
        frames.append(Image.fromarray(arr, "RGBA"))
        durs.append(meta["durs"][i] if i < len(meta["durs"]) else 80)
    if out_path is None:
        os.makedirs(OUTDIR, exist_ok=True)
        out_path = os.path.join(OUTDIR, f"靓_{key}_{number}.gif")
    frames[0].save(out_path, save_all=True, append_images=frames[1:],
                   duration=durs, loop=0, disposal=2, optimize=False)
    return out_path, len(frames), (W0 + delta, H)


if __name__ == "__main__":
    import sys
    os.makedirs(OUTDIR, exist_ok=True)
    print(generate_color("1909754625", "3"))
    print(generate_all("5062112", "1"))


# ------------------------------------------------------------
# 黑金双条：完整复刻（streamer/圆角帽/上下两条/流光）
# ------------------------------------------------------------
_GOLD_CONST = dict(NUM_SIZE=74, NAME_SIZE=66, NUM_W_REF=280, NAME_W_REF=235,
                   NAME_MAX_SPACING=12, NAME_LEFT=236, NAME_TOP=285)


def _gold_font(name, size):
    return _font(name, size)


def _gold_calc_delta(number, name, meta):
    nf = _gold_font("DUBAI-LIGHT.TTF", _GOLD_CONST["NUM_SIZE"])
    d_top = max(0, int(nf.getlength(str(number)) - _GOLD_CONST["NUM_W_REF"]))
    hf = _gold_font("arial.ttf", _GOLD_CONST["NAME_SIZE"])
    adv = [hf.getlength(c) for c in str(name)]
    tw = sum(adv); n = max(1, len(str(name)) - 1)
    sp = min(_GOLD_CONST["NAME_MAX_SPACING"], max(0.5, (_GOLD_CONST["NAME_W_REF"] - tw) / n))
    d_bot = max(0, int((tw + sp * n) - _GOLD_CONST["NAME_W_REF"]))
    return max(d_top, d_bot)


def _gold_draw_num(d, text, box_l, box_r, y_center, gold=(245, 205, 145)):
    font = _gold_font("DUBAI-LIGHT.TTF", _GOLD_CONST["NUM_SIZE"])
    b = font.getbbox(text); bw, bh = b[2] - b[0], b[3] - b[1]
    tx = box_l + ((box_r - box_l) - bw) / 2 - b[0]
    ty = y_center - bh / 2 - b[1]
    d.text((tx, ty), text, font=font, fill=gold + (255,))


def _gold_draw_name(d, text, name_gold=(245, 194, 128)):
    font = _gold_font("arial.ttf", _GOLD_CONST["NAME_SIZE"])
    b = font.getbbox(text)
    adv = [font.getlength(c) for c in text]; tw = sum(adv)
    n = max(1, len(text) - 1)
    sp = min(_GOLD_CONST["NAME_MAX_SPACING"], max(0.5, (_GOLD_CONST["NAME_W_REF"] - tw) / n))
    x = _GOLD_CONST["NAME_LEFT"] - b[0]; y = _GOLD_CONST["NAME_TOP"] - b[1]
    for c, aa in zip(text, adv):
        d.text((x, y), c, font=font, fill=name_gold + (255,))
        x += aa + sp


def _gold_stretch_band(clean, alpha, alpha_ref, y0, y1, sl, sr, delta,
                       out_rgb, out_al, meta, smooth_bg=False):
    x_start = sl + delta
    mid_w = (sr - sl) + delta
    strip = clean[y0:y1, :]
    left = strip[:, :sl].copy()
    right = strip[:, sr:]
    if smooth_bg:
        cap_a = alpha_ref[y0 + 8:y1 - 8, sr:sr + 6]
        cap_rgb = clean[y0 + 8:y1 - 8, sr:sr + 6]
        picked = cap_rgb[cap_a > 200]
        base = np.median(picked.reshape(-1, 3), axis=0) if len(picked) else np.median(cap_rgb.reshape(-1, 3), axis=0)
        base_u = np.clip(base, 0, 255).astype(np.uint8)
        mid_st = np.tile(base_u, (y1 - y0, mid_w, 1))
        lx0 = min(meta["upper_flat"], sl)
        if lx0 < sl:
            sub = left[:, lx0:sl].astype(int)
            non_gold = (sub[:, :, 0] < 180) & (alpha[y0:y1, lx0:sl] > 128)
            left[:, lx0:sl] = np.where(non_gold[:, :, None], base_u[None, None, :], left[:, lx0:sl])
    else:
        mid_st = np.array(Image.fromarray(strip[:, sl:sr], "RGB").resize((mid_w, y1 - y0), Image.BILINEAR))
        cs = clean[y0 + 8:y1 - 8, sr:sr + 6]; ca = alpha_ref[y0 + 8:y1 - 8, sr:sr + 6]
        pv = cs[ca > 200]
        cb = np.median(pv.reshape(-1, 3), axis=0) if len(pv) else np.median(cs.reshape(-1, 3), axis=0)
        w = min(12, mid_w); t = np.linspace(0, 1, w).reshape(1, -1, 1)
        mid_st[:, -w:] = np.clip(mid_st[:, -w:].astype(np.float32) * (1 - t) + cb[None, None, :] * t, 0, 255).astype(np.uint8)
        mid_st[0, :] = mid_st[1, :]
    out_rgb[y0:y1, :sl] = left
    out_rgb[y0:y1, x_start:x_start + mid_w] = mid_st
    out_rgb[y0:y1, x_start + mid_w:x_start + mid_w + right.shape[1]] = right
    sa = alpha[y0:y1, :]; refa = alpha_ref[y0:y1, :]
    ra = refa[:, sr:]
    out_al[y0:y1, :sl] = sa[:, :sl]
    out_al[y0:y1, x_start:x_start + mid_w] = 255
    out_al[y0:y1, x_start + mid_w:x_start + mid_w + ra.shape[1]] = ra
    ry = (y1 - y0) / 2.0
    cap_len = min(int(np.ceil(ry)), ra.shape[1])
    if cap_len > 0:
        rx = float(cap_len); yc = (y0 + y1) / 2.0
        ys = (np.arange(y0, y1, dtype=np.float32) + 0.5)[:, None]
        xs = (np.arange(cap_len, dtype=np.float32) + 0.5)[None, :]
        half_h = ry * np.sqrt(np.clip(1.0 - (xs / rx) ** 2, 0, 1))
        ell = np.clip((half_h - np.abs(ys - yc) + 0.5) * 255, 0, 255).astype(np.uint8)
        out_al[y0:y1, x_start:x_start + cap_len] = ell
        cap_rgb = right[:, :cap_len]
        valid = cap_rgb[ra[:, :cap_len] > 200]
        cap_base = np.median(valid, axis=0) if len(valid) else np.median(cap_rgb.reshape(-1, 3), axis=0)
        region = out_rgb[y0:y1, x_start:x_start + cap_len]
        region[ell > 0] = np.clip(cap_base, 0, 255).astype(np.uint8)


def _gold_fill_matte(rgb, alpha):
    """最近不透明像素填色：逐行左右扩散近似（无需 cv2 distanceTransform）。"""
    out = rgb.copy()
    solid = alpha > 0
    h, w = alpha.shape
    # 对每行，用最近实色填充透明段
    for y in range(h):
        row = solid[y]
        if not row.any():
            continue
        idx = np.where(row)[0]
        for x in range(w):
            if not row[x]:
                near = idx[np.argmin(np.abs(idx - x))]
                out[y, x] = rgb[y, near]
    return out


def _gold_shine(img_rgba, i, n, meta):
    w = img_rgba.width
    y0, y1 = meta["band_top"]
    a = np.array(img_rgba)
    rgb = a[y0:y1, :, :3].astype(np.float32)
    al = a[y0:y1, :, 3:4].astype(np.float32) / 255.0
    yy, xx = np.mgrid[y0:y1, 0:w]
    phase = (i % n) / n
    frac = 2.0 * phase if phase < 0.5 else 2.0 * (1.0 - phase)
    cx = 30.0 + frac * (w - 60.0)
    d = (xx - cx) + (yy - (y0 + y1) / 2.0) * meta["shine_slope"]
    band = np.exp(-(d ** 2) / (2 * meta["shine_sigma"] ** 2))[:, :, None]
    glow = band * np.array(meta["shine_color"], np.float32)[None, None, :] * meta["shine_strength"] * al
    a[y0:y1, :, :3] = np.clip(rgb + glow, 0, 255).astype(np.uint8)
    return Image.fromarray(a, "RGBA")


def generate_gold(number, name, out_path=None):
    meta = _meta("gold")
    H, W0 = meta["H"], meta["W0"]
    delta = _gold_calc_delta(number, name, meta)
    nw = W0 + delta
    clean_seq = _load_clean_seq("gold")
    alpha_ref = np.array(Image.open(os.path.join(TDIR, "gold_alpha_ref.png")), np.uint8)
    # 逐帧真实 alpha（左段平涂判断用）
    za = zipfile.ZipFile(os.path.join(TDIR, "gold_alpha.zip"))
    alpha_seq = [np.array(Image.open(BytesIO(za.read(f"{i:03d}.png"))), np.uint8)
                 for i in range(len(za.namelist()))]
    frames, durs = [], []
    for i, clean_rgba in enumerate(clean_seq):
        clean = clean_rgba[:, :, :3]
        alpha = alpha_seq[i] if i < len(alpha_seq) else clean_rgba[:, :, 3]
        new_rgb = np.zeros((H, nw, 3), np.uint8)
        new_al = np.zeros((H, nw), np.uint8)
        ty0, ty1 = meta["band_top"]; by0, by1 = meta["band_bot"]
        _gold_stretch_band(clean, alpha, alpha_ref, ty0, ty1, meta["split_top_l"],
                           meta["cap_start_top"], delta, new_rgb, new_al, meta, True)
        _gold_stretch_band(clean, alpha, alpha_ref, by0, by1, meta["split_bot_l"],
                           meta["cap_start_bot"], delta, new_rgb, new_al, meta, False)
        for yy in range(H):
            if ty0 <= yy < ty1 or by0 <= yy < by1:
                continue
            new_rgb[yy, :meta["split_top_r"]] = clean[yy, :meta["split_top_r"]]
            new_rgb[yy, meta["split_top_r"] + delta:] = clean[yy, meta["split_top_r"]:]
            new_al[yy, :meta["split_top_r"]] = alpha[yy, :meta["split_top_r"]]
            new_al[yy, meta["split_top_r"] + delta:] = alpha[yy, meta["split_top_r"]:]
        overlay = Image.new("RGBA", (nw, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        _gold_draw_num(d, number, meta["split_top_l"] + 4, meta["split_top_r"] + delta - 4, 167)
        _gold_draw_name(d, name)
        composed = Image.alpha_composite(Image.fromarray(np.dstack([new_rgb, new_al]), "RGBA"), overlay)
        composed = _gold_shine(composed, i, len(clean_seq), meta)
        arr = np.array(composed)
        arr[:, :, :3] = _gold_fill_matte(arr[:, :, :3], arr[:, :, 3])
        frames.append(Image.fromarray(arr, "RGBA"))
        durs.append(meta["durs"][i] if i < len(meta["durs"]) else 100)
    if out_path is None:
        os.makedirs(OUTDIR, exist_ok=True)
        out_path = os.path.join(OUTDIR, f"黑金动_{number}_{name}.gif")
    frames[0].save(out_path, save_all=True, append_images=frames[1:],
                   duration=durs, loop=0, disposal=2, optimize=False, transparency=0)
    return out_path, len(frames), (nw, H)
