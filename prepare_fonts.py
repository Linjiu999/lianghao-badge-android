# -*- coding: utf-8 -*-
"""裁剪字体：只保留数字/字母/常用中文，减小 APK 体积。"""
import os
from fontTools import subset
from fontTools.ttLib import TTFont, TTCollection

ROOT = os.path.dirname(os.path.abspath(__file__))
FDIR = os.path.join(ROOT, "app", "assets", "fonts")
os.makedirs(FDIR, exist_ok=True)
WIN = "C:/Windows/Fonts/"

# 需要的字符：数字、大小写字母、 punctuation、常用中文（模板名+通用）
chars = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
chars.update(" ·-_./:+*#()[]{}，。！？、：；（）【】丽橙酒藏青草绿紫罗雾棕黑金蓝忍者企鹅动漫海绵宝普通亮")
chars.update("靓彩展示条号码名字黑金双条蓝条长号")

FONTS = {
    "Deng.ttf": "Deng.ttf",
    "Dengb.ttf": "Dengb.ttf",
    "Dengl.ttf": "Dengl.ttf",
    "arial.ttf": "arial.ttf",
    "arialbd.ttf": "arialbd.ttf",
    "DUBAI-LIGHT.TTF": "DUBAI-LIGHT.TTF",
    "bahnschrift.ttf": "bahnschrift.ttf",
    "msyh.ttc": "msyh.ttc",
}


def subset_ttf(src, dst, text):
    font = TTFont(src)
    opts = subset.Options()
    opts.name_IDs = ["*"]
    opts.name_legacy = True
    opts.notdef_outline = True
    opts.recalc_bounds = True
    sub = subset.Subsetter(options=opts)
    sub.populate(text=text)
    sub.subset(font)
    font.save(dst)


def subset_ttc(src, dst, text, index=0):
    col = TTCollection(src)
    font = col.fonts[index]
    opts = subset.Options()
    opts.name_IDs = ["*"]
    opts.notdef_outline = True
    sub = subset.Subsetter(options=opts)
    sub.populate(text=text)
    sub.subset(font)
    font.save(dst)


text = "".join(sorted(chars))
for out_name, in_name in FONTS.items():
    src = WIN + in_name
    if not os.path.exists(src):
        print("MISS", in_name)
        continue
    dst = os.path.join(FDIR, out_name)
    try:
        if in_name.lower().endswith(".ttc"):
            subset_ttc(src, dst, text)
        else:
            subset_ttf(src, dst, text)
        print(f"OK  {out_name:<20} {os.path.getsize(src)//1024}KB -> {os.path.getsize(dst)//1024}KB")
    except Exception as e:
        print("ERR", in_name, e)

# 复制完整bahnschrift备用（变体字重可能裁剪后失效，先试裁剪版）
print("done")
