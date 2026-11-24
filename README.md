# 靓号展示条生成器 · Android APK

把原来的两套桌面脚本（多彩靓号 10 模板 + 全模板 8 种）做成手机 App。

## 原理
- 桌面端 `prepare_assets.py` 用 cv2 把模板旧数字擦掉，预计算成干净底图/字形库打包进 APK
- 手机端 `app/badge_engine.py` 纯 Pillow+numpy 渲染（不依赖 cv2），KivyMD 界面
- GitHub Actions 云端用 Buildozer 构建 APK

## 目录
- `app/` — App 源码与素材（main.py KivyMD 界面、badge_engine.py 引擎、assets/ 素材）
- `buildozer.spec` — 构建配置
- `.github/workflows/build.yml` — 云端构建 workflow（push 到 main 自动触发）
- `prepare_assets.py` / `prepare_fonts.py` — 桌面端素材预计算（不进 APK）

## 使用
在 App 里选择「多彩靓号」或「全模板」，输入模板号与号码，点生成，
成品 GIF 保存到手机的 `Download/靓号展示条` 目录。
