# -*- coding: utf-8 -*-
"""
桌面端预计算脚本（只在电脑上跑一次，不进 APK）
复用桌面脚本的 cv2 擦字逻辑，导出手机端所需素材：
  多彩: <key>_clean.png(首帧基底) + <key>_left.gif(左侧动画)
  全模板/gold: <key>_clean.gif(逐帧擦字后的干净动态图) + meta
  字形库 glyphs/
"""
import os, sys, json, importlib.util
import numpy as np
import cv2
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(ROOT, "app", "assets")
TDIR = os.path.join(ASSETS, "templates")
GDIR = os.path.join(ASSETS, "glyphs")
for d in (TDIR, GDIR):
    os.makedirs(d, exist_ok=True)
DESKTOP = "C:/Users/xxxxb/Desktop/图片生成"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def inpaint(rgb, mask, radius=5):
    return cv2.cvtColor(cv2.inpaint(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR),
                                    mask, radius, cv2.INPAINT_TELEA), cv2.COLOR_BGR2RGB)


def prepare_color():
    m = load_module("color_mod", os.path.join(DESKTOP, "多彩靓号一键生成包", "模板素材", "制作多彩靓号.py"))
    print("[多彩] 字形库...")
    glyphs = m._extract_glyphs()
    gmeta = {}
    for ch, (alpha, adv) in glyphs.items():
        Image.fromarray(alpha, "L").save(os.path.join(GDIR, f"g_{ord(ch)}.png"))
        gmeta[ch] = {"advance": int(adv), "w": int(alpha.shape[1]), "h": int(alpha.shape[0])}
    with open(os.path.join(GDIR, "glyphs.json"), "w", encoding="utf-8") as f:
        json.dump(gmeta, f, ensure_ascii=False)
    for key, c in m.TEMPLATES.items():
        src = Image.open(m.src_path(c["file"]))
        n = getattr(src, "n_frames", 1); H, W0 = src.size[1], src.size[0]; x0 = m.DIGIT_X0
        src.seek(0)
        ref = m.remove_watermark(np.array(src.convert("RGBA")).copy())
        rgb = ref[:, :, :3]
        clean = inpaint(rgb, m.build_mask(rgb, c), 5)
        Image.fromarray(np.dstack([clean, ref[:, :, 3]]), "RGBA").save(
            os.path.join(TDIR, f"color_{key}_clean.png"))
        left_frames, durs = [], []
        for i in range(n):
            src.seek(i)
            r = m.remove_watermark(np.array(src.convert("RGBA")).copy())
            left_frames.append(Image.fromarray(r[:, :x0, :], "RGBA"))
            durs.append(src.info.get("duration", 100))
        left_frames[0].save(os.path.join(TDIR, f"color_{key}_left.gif"), save_all=True,
                            append_images=left_frames[1:], duration=durs, loop=0,
                            disposal=2, optimize=False)
        meta = dict(key=key, kind="color", name=c["name"], rgb=list(c["rgb"]), ink=c["ink"],
                    W0=W0, H=H, x0=x0, split=m.SPLIT_X, ycenter=m.Y_CENTER,
                    y0=m.DIGIT_Y0, y1=m.DIGIT_Y1, side_pad=m.SIDE_PAD, min_mid=m.MIN_MID,
                    adv=m.ADVANCE, adv1=m.ADVANCE_1, frames=n, durs=durs)
        json.dump(meta, open(os.path.join(TDIR, f"color_{key}_meta.json"), "w", encoding="utf-8"), ensure_ascii=False)
        print(f"  color {key:>2} {c['name']:<6} {n}帧")


def prepare_all():
    m = load_module("all_mod", os.path.join(DESKTOP, "全模板一键生成包", "模板素材", "制作全部模板.py"))
    for key, c in m.TEMPLATES.items():
        src = Image.open(m.src_path(c["file"]))
        n = getattr(src, "n_frames", 1); H, W0 = src.size[1], src.size[0]; x0 = c["digit_x0"]
        src.seek(0 if n > 1 else 1)
        ref_alpha = np.array(src.convert("RGBA"))[:, :, 3]
        clean_frames = []
        durs = []
        for i in range(n):
            src.seek(i)
            rgb = np.array(src.convert("RGBA"))[:, :, :3]
            clean = inpaint(rgb, m.build_mask(rgb, c), c["inpaint"])
            clean_frames.append(np.dstack([clean, ref_alpha]))
            durs.append(src.info.get("duration", 80))
        # 逐帧干净动态图（RGB 无压缩损失用 PNG 序列存 ZIP，体积可控）
        import zipfile
        zpath = os.path.join(TDIR, f"all_{key}_clean.zip")
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for i, fr in enumerate(clean_frames):
                from io import BytesIO
                buf = BytesIO()
                Image.fromarray(fr, "RGBA").save(buf, "PNG")
                z.writestr(f"{i:03d}.png", buf.getvalue())
        meta = dict(key=key, kind="all", name=c["name"], W0=W0, H=H, x0=x0,
                    split=c["split_x"], ycenter=c["y_center"],
                    y0=c["bbox_y0"], y1=c["bbox_y1"], pad=c["pad"],
                    min_mid=c["min_mid"], font=c["font"], size=c["size"], ss=c["ss"],
                    stroke=c["stroke"], grad=c["grad"], italic=c.get("italic", 0),
                    shadow=c.get("shadow"), frames=n, durs=durs)
        json.dump(meta, open(os.path.join(TDIR, f"all_{key}_meta.json"), "w", encoding="utf-8"), ensure_ascii=False)
        print(f"  all  {key:>2} {c['name']:<8} {n}帧")


def prepare_gold():
    m = load_module("gold_mod", os.path.join(DESKTOP, "全模板一键生成包", "模板素材", "make_anim_badge.py"))
    src = Image.open(m.SRC)
    n, (W0, H) = src.n_frames, src.size
    src.seek(0)
    f0 = np.array(src.convert("RGB"))
    mask = np.maximum(m.gold_mask(f0, m.NUM_BOX, 1), m.gold_mask(f0, m.NAME_BOX, 2))
    src.seek(1 if n > 1 else 0)
    ref_alpha = np.array(src.convert("RGBA"))[:, :, 3]
    import zipfile
    from io import BytesIO
    clean_frames, alpha_frames, durs = [], [], []
    for i in range(n):
        src.seek(i)
        rgba = np.array(src.convert("RGBA"))
        rgb, alpha = rgba[:, :, :3], rgba[:, :, 3]
        clean = inpaint(rgb, mask, 5)
        clean_frames.append(np.dstack([clean, ref_alpha]))   # 输出用参考帧 alpha（消除边框跳动）
        alpha_frames.append(alpha)                            # 逐帧真实 alpha（左段平涂判断用）
        durs.append(src.info.get("duration", 100))
    with zipfile.ZipFile(os.path.join(TDIR, "gold_clean.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        for i, fr in enumerate(clean_frames):
            buf = BytesIO(); Image.fromarray(fr, "RGBA").save(buf, "PNG")
            z.writestr(f"{i:03d}.png", buf.getvalue())
    with zipfile.ZipFile(os.path.join(TDIR, "gold_alpha.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        for i, al in enumerate(alpha_frames):
            buf = BytesIO(); Image.fromarray(al, "L").save(buf, "PNG")
            z.writestr(f"{i:03d}.png", buf.getvalue())
    Image.fromarray(mask, "L").save(os.path.join(TDIR, "gold_mask.png"))
    meta = dict(key="5", kind="gold", name="黑金双条", W0=W0, H=H, frames=n, durs=durs,
                shine_sigma=m.SHINE_SIGMA, shine_slope=m.SHINE_SLOPE,
                shine_color=list(map(float, m.SHINE_COLOR)), shine_strength=float(m.SHINE_STRENGTH),
                band_top=list(m.BAND_TOP), band_bot=list(m.BAND_BOT),
                split_top_l=m.SPLIT_TOP_L, split_top_r=m.SPLIT_TOP_R,
                cap_start_top=m.CAP_START_TOP, cap_start_bot=m.CAP_START_BOT,
                split_bot_l=m.SPLIT_BOT_L, split_bot_r=m.SPLIT_BOT_R,
                num_box=list(m.NUM_BOX), name_box=list(m.NAME_BOX),
                upper_flat=m.UPPER_FLAT_FROM)
    json.dump(meta, open(os.path.join(TDIR, "gold_meta.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print(f"  gold  {n}帧")


if __name__ == "__main__":
    prepare_color(); prepare_all(); prepare_gold()
    print("\n完成:", TDIR)
