[app]

title = 靓号展示条生成器
package.name = lianghao
package.domain = com.nightdye.lianghao

source.dir = app

# 包含 python 源码、字体、字形、模板素材(zip/png/json/gif)
source.include_exts = py,png,jpg,kv,atlas,json,gif,zip,ttf,otf,TTF
source.include_patterns = assets/**,assets/fonts/**,assets/glyphs/**,assets/templates/**

version = 1.0

# numpy/pillow 有 p4a recipe；KivyMD 2.0 按官方模板依赖
requirements = python3,kivy==2.3.1,https://github.com/kivymd/KivyMD/archive/master.zip,exceptiongroup,asynckivy,asyncgui,materialyoucolor,android,materialshapes,pycairo,numpy,pillow

orientation = portrait
fullscreen = 0

android.api = 36
android.minapi = 30
android.permissions = android.permission.WRITE_EXTERNAL_STORAGE,android.permission.READ_EXTERNAL_STORAGE
android.archs = arm64-v8a,armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 1
