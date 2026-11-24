# -*- coding: utf-8 -*-
"""
靓号展示条生成器 · Android App
UI 外壳参考 GitHub Novfensec/SAMPLE-KIVYMD-APP（KivyMD / Material Design）；
内部交互用 Kivy 稳定原生控件，避免 KivyMD 组件 API 版本差异导致构建失败。
业务引擎 badge_engine.py：纯 Pillow+numpy，无 cv2。
"""
import os
import traceback
from threading import Thread

from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.utils import platform
from kivymd.app import MDApp

import badge_engine as engine

APP_KV = """
<RootBox@MDBoxLayout>:
    orientation: 'vertical'

MDScreen:
    md_bg_color: 0.98, 0.98, 0.98, 1

    MDBoxLayout:
        orientation: 'vertical'

        MDTopAppBar:
            title: '靓号展示条生成器'
            elevation: 2

        MDBoxLayout:
            orientation: 'horizontal'
            size_hint_y: None
            height: dp(48)
            padding: dp(8)
            spacing: dp(8)

            ToggleButton:
                id: tab_color
                text: '多彩靓号(10)'
                group: 'tabs'
                state: 'down'
                background_normal: ''
                background_color: 0.13, 0.35, 0.72, 1
                color: 1, 1, 1, 1
                on_press: app.switch_tab('color')
            ToggleButton:
                id: tab_all
                text: '全模板(8)'
                group: 'tabs'
                background_normal: ''
                background_color: 0.45, 0.48, 0.52, 1
                color: 1, 1, 1, 1
                on_press: app.switch_tab('all')

        ScrollView:
            id: scroller
            MDBoxLayout:
                id: form
                orientation: 'vertical'
                adaptive_height: True
                padding: dp(16)
                spacing: dp(12)

                Label:
                    id: hint_title
                    text: '多彩靓号 · 10 种配色'
                    size_hint_y: None
                    height: dp(28)
                    color: 0.1, 0.1, 0.1, 1
                    bold: True
                    halign: 'left'

                TextInput:
                    id: key_input
                    hint_text: '模板号（多彩 1-10 / 全模板 1-8）'
                    text: '3'
                    size_hint_y: None
                    height: dp(44)
                    multiline: False
                    input_type: 'number'
                    background_color: 1, 1, 1, 1

                TextInput:
                    id: num_input
                    hint_text: '号码 / 文字 / 字母，例：5062222222'
                    text: '5062222222'
                    size_hint_y: None
                    height: dp(44)
                    multiline: False
                    background_color: 1, 1, 1, 1

                TextInput:
                    id: name_input
                    hint_text: '名字（仅全模板 5 号黑金双条需要）'
                    text: 'H8888'
                    size_hint_y: None
                    height: dp(44)
                    multiline: False
                    opacity: 0
                    disabled: True
                    background_color: 1, 1, 1, 1

                Label:
                    id: help_text
                    text: '1黑金 2棕黑 3亮橙 4酒红 5藏青 6草绿 7宝蓝 8紫罗兰 9雾蓝 10驼棕'
                    size_hint_y: None
                    height: dp(60)
                    color: 0.35, 0.35, 0.35, 1
                    halign: 'left'
                    valign: 'top'
                    text_size: self.width, None

                Button:
                    id: gen_btn
                    text: '生成多彩靓号 GIF'
                    size_hint_y: None
                    height: dp(52)
                    background_normal: ''
                    background_color: 0.13, 0.35, 0.72, 1
                    on_release: app.generate()

                Label:
                    id: status
                    text: '成品会保存到手机的「Download/靓号展示条」文件夹'
                    size_hint_y: None
                    height: dp(80)
                    color: 0.2, 0.2, 0.2, 1
                    halign: 'center'
                    valign: 'middle'
                    text_size: self.width, None
"""


class BadgeApp(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.theme_style = "Light"
        self.current = "color"

    def build(self):
        self.title = "靓号展示条生成器"
        Window.clearcolor = (0.98, 0.98, 0.98, 1)
        return Builder.load_string(APP_KV)

    def switch_tab(self, which):
        self.current = which
        r = self.root.ids
        if which == "color":
            r.hint_title.text = "多彩靓号 · 10 种配色"
            r.key_input.text = "3"
            r.num_input.text = "5062222222"
            r.help_text.text = "1黑金 2棕黑 3亮橙 4酒红 5藏青 6草绿 7宝蓝 8紫罗兰 9雾蓝 10驼棕"
            r.gen_btn.text = "生成多彩靓号 GIF"
            r.name_input.opacity = 0; r.name_input.disabled = True
            r.tab_color.state = 'down'; r.tab_color.background_color = (0.13, 0.35, 0.72, 1)
            r.tab_all.state = 'normal'; r.tab_all.background_color = (0.45, 0.48, 0.52, 1)
        else:
            r.hint_title.text = "全模板 · 8 种展示条"
            r.key_input.text = "1"
            r.num_input.text = "5062112"
            r.help_text.text = "1蓝条 2忍者 3企鹅 4橙发动漫 5黑金双条 6蓝条长号 7海绵宝宝 8黑白动漫（5号填名字）"
            r.gen_btn.text = "生成展示条 GIF"
            r.name_input.opacity = 1; r.name_input.disabled = False
            r.tab_all.state = 'down'; r.tab_all.background_color = (0.13, 0.35, 0.72, 1)
            r.tab_color.state = 'normal'; r.tab_color.background_color = (0.45, 0.48, 0.52, 1)

    def _status(self, text):
        Clock.schedule_once(lambda dt: setattr(self.root.ids.status, 'text', text), 0)

    def _outdir(self):
        if platform == "android":
            try:
                from android.storage import primary_external_storage_path
                d = os.path.join(primary_external_storage_path(), "Download", "靓号展示条")
            except Exception:
                d = os.path.join(os.getcwd(), "靓号成品")
        else:
            d = engine.OUTDIR
        os.makedirs(d, exist_ok=True)
        return d

    def generate(self):
        r = self.root.ids
        key = r.key_input.text.strip()
        num = r.num_input.text.strip()
        name = r.name_input.text.strip() or "H8888"
        if not key or not num:
            self._status("请填写模板号和号码")
            return
        self._status("生成中，请稍候…")
        def work():
            try:
                out_dir = self._outdir()
                if self.current == "color":
                    if key not in [str(i) for i in range(1, 11)]:
                        raise ValueError("多彩模板号应为 1-10")
                    path, frames, size = engine.generate_color(
                        num, key, os.path.join(out_dir, f"靓彩_{key}_{num}.gif"))
                else:
                    if key not in [str(i) for i in range(1, 9)]:
                        raise ValueError("全模板号应为 1-8")
                    if key == "5":
                        path, frames, size = engine.generate_gold(
                            num, name, os.path.join(out_dir, f"黑金动_{num}_{name}.gif"))
                    else:
                        path, frames, size = engine.generate_all(
                            num, key, os.path.join(out_dir, f"靓_{key}_{num}.gif"))
                msg = f"已生成：{os.path.basename(path)}\n{frames} 帧 · {size[0]}x{size[1]}\n保存于 Download/靓号展示条"
            except Exception as e:
                msg = f"生成失败：{e}"
                traceback.print_exc()
            self._status(msg)
        Thread(target=work, daemon=True).start()


if __name__ == "__main__":
    BadgeApp().run()
