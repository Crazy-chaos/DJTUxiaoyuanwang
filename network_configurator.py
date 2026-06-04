import sys
import os
import ctypes
import subprocess
import tkinter as tk
from tkinter import messagebox
import tempfile
import webbrowser
import time
import json
import base64
import threading
import pystray
import urllib.request
import urllib.error
import re
from tkinter import ttk
from PIL import Image, ImageDraw

CREATE_NO_WINDOW = 0x08000000
CURRENT_VERSION = "0.1.2"

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def get_wired_interface():
    """
    通过 PowerShell 获取已连接 (Up) 且名称包含 '以太网' 或 'Ethernet' 的物理网卡
    """
    cmd = 'powershell -Command "Get-NetAdapter | Where-Object {($_.Name -like \'*以太网*\' -or $_.Name -like \'*Ethernet*\' -or $_.Name -like \'*本地连接*\') -and $_.Status -eq \'Up\'} | Select-Object -ExpandProperty Name"'
    try:
        result = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT, creationflags=CREATE_NO_WINDOW)
        names = result.strip().split('\n')
        for name in names:
            name = name.strip()
            if name:
                return name
    except Exception as e:
        print(f"检测网卡出错: {e}")
    return None

def set_ip(interface_name, ip, subnet, gateway, dns, alt_dns=None):
    try:
        # 配置 IP、子网掩码、网关
        cmd_ip = f'netsh interface ipv4 set address name="{interface_name}" static {ip} {subnet} {gateway}'
        subprocess.run(cmd_ip, shell=True, check=True, creationflags=CREATE_NO_WINDOW)
        
        # 配置 DNS
        if dns:
            cmd_dns = f'netsh interface ipv4 set dnsservers name="{interface_name}" static {dns} primary'
            subprocess.run(cmd_dns, shell=True, check=True, creationflags=CREATE_NO_WINDOW)
            
        if alt_dns:
            cmd_alt_dns = f'netsh interface ipv4 add dnsservers name="{interface_name}" address={alt_dns} index=2'
            subprocess.run(cmd_alt_dns, shell=True, check=True, creationflags=CREATE_NO_WINDOW)
            
        return True, "网络参数配置成功！"
    except subprocess.CalledProcessError as e:
        return False, f"配置失败，请确保输入格式正确。\n错误代码: {e.returncode}"

def auto_connect_ruijie(username, password):
    try:
        from pywinauto.application import Application
        import pywinauto.keyboard as keyboard
    except ImportError:
        return False, "自动化输入需要 pywinauto 库支持。\n请在命令行运行：pip install pywinauto\n安装完成后再进行测试或打包。"

    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 动态探测锐捷安装路径
    possible_paths = [
        os.path.join(app_dir, "Ruijie Supplicant", "RuijieSupplicant.exe"),
        r"C:\Program Files\锐捷网络\Ruijie Supplicant\RuijieSupplicant.exe",
        r"C:\Program Files (x86)\锐捷网络\Ruijie Supplicant\RuijieSupplicant.exe",
        r"C:\Program Files\Ruijie Networks\Ruijie Supplicant\RuijieSupplicant.exe",
        r"C:\Program Files (x86)\Ruijie Networks\Ruijie Supplicant\RuijieSupplicant.exe",
        r"C:\Ruijie Supplicant\RuijieSupplicant.exe"
    ]
    
    ruijie_path = None
    for p in possible_paths:
        if os.path.exists(p):
            ruijie_path = p
            break
            
    if not ruijie_path:
        return False, f"未找到锐捷客户端可执行文件！\n已尝试查找系统常见路径，均未发现安装。"
    
    try:
        # 启动锐捷客户端
        subprocess.Popen([ruijie_path], creationflags=CREATE_NO_WINDOW)
        
        # 给锐捷预留启动时间
        time.sleep(3)
        
        # 使用 pywinauto 连接到锐捷窗口 (通过正则匹配标题)
        app = Application(backend="win32").connect(title_re=".*认证客户端.*", timeout=10)
        dlg = app.top_window()
        dlg.set_focus()
        
        # 查找所有的文本输入框 (Edit 控件)
        # 锐捷的“用户名”往往是 ComboBox 内部的 Edit，而“密码”是独立的 Edit
        edits = dlg.descendants(class_name="Edit")
        
        if len(edits) >= 2:
            # 按照控件在窗口中的垂直 Y 坐标从上到下排序
            # 上面的必定是用户名，下面的是密码
            edits.sort(key=lambda e: e.rectangle().top)
            
            # 使用更底层的设值方法，直接填入内容，不用管光标在哪
            edits[0].set_edit_text(username)
            edits[1].set_edit_text(password)
            time.sleep(0.5)
            
            # 查找并点击认证按钮
            buttons = dlg.descendants(class_name="Button")
            clicked = False
            for btn in buttons:
                if "认证" in btn.window_text() and "自动" not in btn.window_text():
                    btn.click()
                    clicked = True
                    break
            
            if not clicked:
                keyboard.send_keys("{ENTER}")
                
            return True, "已通过底层 API 直接注入账号密码并点击认证！"
        else:
            # 兼容性备用方案：如果由于特殊版本找不到输入控件，则强行发送按键
            keyboard.send_keys("^a{BACKSPACE}" + username + "{TAB}^a{BACKSPACE}" + password + "{ENTER}")
            return True, "未能精准查找到输入框控件，已尝试向窗口强制发送键盘按键。"
            
    except Exception as e:
        return False, f"自动化输入发生异常: {e}"

def show_announcement(parent):
    dlg = tk.Toplevel(parent)
    dlg.title("公告")
    dlg.geometry("520x260")
    dlg.configure(bg="#f8f9fa")
    
    # 设置为模态窗口
    dlg.transient(parent)
    dlg.grab_set()
    
    # 标题
    tk.Label(dlg, text="欢迎使用大连交通大学非官方校园网登录软件", font=("Microsoft YaHei", 12, "bold"), bg="#f8f9fa", fg="#0d6efd").pack(pady=15)
    
    # 第一行提示文字
    tk.Label(dlg, text="本软件目的是方便同学上网，完全免费", font=("Microsoft YaHei", 10), bg="#f8f9fa").pack(pady=(5, 0))
    
    # 作者B站信息和链接单独一行
    frame_bili = tk.Frame(dlg, bg="#f8f9fa")
    frame_bili.pack(pady=5)
    tk.Label(frame_bili, text="作者B站疯狂混沌：", font=("Microsoft YaHei", 10), bg="#f8f9fa").pack(side=tk.LEFT)
    lbl_bili = tk.Label(frame_bili, text="https://space.bilibili.com/396813530", font=("Microsoft YaHei", 10, "underline"), fg="blue", bg="#f8f9fa", cursor="hand2")
    lbl_bili.pack(side=tk.LEFT)
    lbl_bili.bind("<Button-1>", lambda e: webbrowser.open_new_tab("https://space.bilibili.com/396813530"))
    
    # 第二行文本和链接
    frame_qq = tk.Frame(dlg, bg="#f8f9fa")
    frame_qq.pack(pady=5)
    tk.Label(frame_qq, text="如果出问题加入qq群：838041168 ", font=("Microsoft YaHei", 10), bg="#f8f9fa").pack(side=tk.LEFT)
    lbl_qq = tk.Label(frame_qq, text="点击加入或扫码", font=("Microsoft YaHei", 10, "underline"), fg="blue", bg="#f8f9fa", cursor="hand2")
    lbl_qq.pack(side=tk.LEFT)
    lbl_qq.bind("<Button-1>", lambda e: webbrowser.open_new_tab("https://qm.qq.com/q/bf7pvZLKko"))
    
    dlg.qq_qr_image = tk.PhotoImage(data=QQ_QR_BASE64.strip())
    
    def show_qq_qr_tooltip(event):
        if getattr(dlg, 'qq_tooltip', None): return
        x = event.x_root + 15
        y = event.y_root + 10
        dlg.qq_tooltip = tk.Toplevel(dlg)
        dlg.qq_tooltip.wm_overrideredirect(True)
        dlg.qq_tooltip.geometry(f"+{x}+{y}")
        dlg.qq_tooltip.configure(bg="white", highlightbackground="black", highlightthickness=1)
        tk.Label(dlg.qq_tooltip, text="QQ群：838041168", font=("Microsoft YaHei", 9), bg="white").pack(padx=10, pady=(10, 5))
        tk.Label(dlg.qq_tooltip, image=dlg.qq_qr_image, bg="white").pack(padx=10, pady=(0, 10))

    def hide_qq_qr_tooltip(event):
        if getattr(dlg, 'qq_tooltip', None):
            dlg.qq_tooltip.destroy()
            dlg.qq_tooltip = None

    lbl_qq.bind("<Enter>", show_qq_qr_tooltip)
    lbl_qq.bind("<Leave>", hide_qq_qr_tooltip)
    
    # 确认按钮
    btn_close = tk.Button(dlg, text="我已知晓", command=dlg.destroy, font=("Microsoft YaHei", 10, "bold"), bg="#0d6efd", fg="white", relief=tk.FLAT, width=15)
    btn_close.pack(pady=25)
    
    # 居中对齐逻辑
    dlg.update_idletasks()
    x = parent.winfo_x() + (parent.winfo_width() // 2) - (520 // 2)
    y = parent.winfo_y() + (parent.winfo_height() // 2) - (260 // 2)
    dlg.geometry(f"+{x}+{y}")

QR_BASE64 = """
iVBORw0KGgoAAAANSUhEUgAAAJYAAACWAQMAAAAGz+OhAAAABlBMVEX///8AAABVwtN+AAAACXBIWXMAAA7EAAAOxAGVKw4bAAABJklEQVRIib2WPa6EMAyEjSgoc4QcJRdbLcvNOEqOkDIFYt7YBukhbbmxu3wpmIz/EPkSKxi7pB1VJOuh/5y9+J20H2lfeMofkSmIJRDwgrJ63oAtktEGfX04m5vo6yOZeY9Wej7lkY+xzGuNciikP+pvLPOYARb4fYpg1HIk0APWOOp7qe8YZlHUA3WdIIitTdx7yedSV9S1xzAOMGrRnuYMO69aG8+Y7Rne0x8bY/g9e9lHtX9Zz+L5DWE6nCkH1r8wn0OYCil3H639miUBrNheKFSBayVFMA/ab6+fdAuHMJ+TaLJwI9io7CHM94J6r65Pd87HM9+/rcDC8xHGWOZmx2b7KI7Re1RN+PLvH2Qsk2vve2/xJoZ5rR3sLZzPf9ux7Ev8AYbV2ebR9fCkAAAAAElFTkSuQmCC
"""

QQ_QR_BASE64 = """
iVBORw0KGgoAAAANSUhEUgAAAIQAAACEAQAAAAB5P74KAAABH0lEQVR4nMWWQWrFMAxEn0P34xv8+x8rNxifYIqcX0q7lKE1BBQvBulJGWWEn2ddvy7gb2/GGJM1mGvusKujhKEMpits6nzAEGEJ77CvAywmGQ/yE50ZUfkc6YQZbi122NQZGaD3ywLdPR1Sx7KeKO7qSJItHEXu6lzc+N7hZN7q8qGKYieSINSuK46derZYW8eWQlKo7X4+UoywZFVOXR1cMoEq6yAfFKsQeze/3XfBa6H1fGL9vnt3vEizIbU5ExWg1Pwc8HHNkPb8HPChsGhLmfLYNmcnJqM8I7R9njJTFWmourp8rr0vGKu8bDtrn4+KD18jfbIZ7VUTZF5nG3ZOaQ1Y7nPWYxkqzif+w24UxvXtd/v1XqLf55//Wz4BzjDMVWuokUMAAAAASUVORK5CYII=
"""

REPAIR_QR_BASE64 = """
iVBORw0KGgoAAAANSUhEUgAAAHQAAAB0AQAAAAB84SuKAAAA5klEQVR4nL1VwW0EQQgz0f1NB9t/WduBqcARO/fI5QdSgrQSSOORjRk2jJ9RXx8l8Pd1RCSqcJI5njZwIfJJFnwiEbj0JGs9lbPzv+pq7ku8BQKhTsb4cKDhzQHgPcXDHX0FO9Gcf0akdbf/Oef/Alh3EE6x5niYMvR8EMf8X0BC6TTCO//ky1FZyFjpR91hZE8wx+8XJgmKMDb6YbYCue/wDm8KaPaczw+e+aMhGov5Q5tGUTx9WPB3t+DNQRv9ZDdgp//UBQqs2uzPDl5FSFy9H5vH/zZy1/9eQMeI+f76KP/9//UNpVKDjwlqGH4AAAAASUVORK5CYII=
"""

class App(tk.Tk):
    def __init__(self, silent_mode=False):
        super().__init__()
        self.silent_mode = silent_mode
        self.title(f"大连交通大学有线网认证 v{CURRENT_VERSION}")
        self.geometry("450x780")
        self.configure(bg="#f8f9fa")
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 尝试加载图标
        icon_path = self.get_resource_path("icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except:
                pass
        
        self.setting_close_mode = tk.StringVar(value="最小化到托盘")
        self.setting_auto_boot = tk.BooleanVar(value=False)
        self.setting_auto_auth = tk.BooleanVar(value=False)
        
        self.tray_icon = None
        self.setup_tray_icon()
        
        self.interface_name = None
        
        # 顶部工具栏 (用于放置设置按钮)
        self.frame_top = tk.Frame(self, bg="#f8f9fa")
        self.frame_top.pack(fill=tk.X, padx=15, pady=(15, 0))
        btn_settings = tk.Label(self.frame_top, text="⚙️ 设置", font=("Microsoft YaHei", 10), fg="gray", cursor="hand2", bg="#f8f9fa")
        btn_settings.pack(side=tk.RIGHT)
        btn_settings.bind("<Button-1>", lambda e: self.open_settings())
        
        # 顶部状态区域
        self.frame_status = tk.Frame(self, bg="#f8f9fa")
        self.frame_status.pack(pady=20, fill=tk.X)
        
        self.lbl_status = tk.Label(self.frame_status, text="正在检测有线网络连接...", font=("Microsoft YaHei", 12, "bold"), bg="#f8f9fa")
        self.lbl_status.pack()
        
        self.btn_check = tk.Button(self.frame_status, text="重新检测网线", command=self.check_connection, font=("Microsoft YaHei", 10))
        self.btn_check.pack(pady=10)
        
        # 表单区域
        self.frame_inputs = tk.Frame(self, bg="#f8f9fa")
        
        font_label = ("Microsoft YaHei", 10)
        font_entry = ("Consolas", 11)
        font_title = ("Microsoft YaHei", 11, "bold")
        
        # --- 第一步：配置IP ---
        tk.Label(self.frame_inputs, text="第一步：配置 IP", font=font_title, bg="#f8f9fa", fg="#0d6efd").grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky="w", padx=10)
        
        tk.Label(self.frame_inputs, text="IPv4 地址:", font=font_label, bg="#f8f9fa").grid(row=1, column=0, pady=10, padx=10, sticky="e")
        self.ent_ip = tk.Entry(self.frame_inputs, font=font_entry, width=20)
        self.ent_ip.grid(row=1, column=1, pady=10, padx=10)
        
        def on_ip_change(event):
            ip_val = self.ent_ip.get().strip()
            parts = ip_val.split('.')
            if len(parts) == 4 and parts[0] and parts[1] and parts[2]:
                gateway = f"{parts[0]}.{parts[1]}.{parts[2]}.1"
                self.ent_gateway.delete(0, tk.END)
                self.ent_gateway.insert(0, gateway)
                
        self.ent_ip.bind('<KeyRelease>', on_ip_change)
        
        self.qr_image = tk.PhotoImage(data=QR_BASE64.strip())
        self.tooltip_win = None
        
        self.lbl_help = tk.Label(self.frame_inputs, text="填宿舍号或扫码获取", font=("Microsoft YaHei", 9, "underline"), fg="blue", bg="#f8f9fa", cursor="hand2")
        self.lbl_help.grid(row=1, column=2, padx=5, sticky="w")
        self.lbl_help.bind("<Button-1>", self.show_ip_selector)
        
        tk.Label(self.frame_inputs, text="子网掩码:", font=font_label, bg="#f8f9fa").grid(row=2, column=0, pady=10, padx=10, sticky="e")
        self.ent_subnet = tk.Entry(self.frame_inputs, font=font_entry, width=20)
        self.ent_subnet.insert(0, "255.255.255.0")
        self.ent_subnet.grid(row=2, column=1, pady=10, padx=10)
        
        tk.Label(self.frame_inputs, text="默认网关:", font=font_label, bg="#f8f9fa").grid(row=3, column=0, pady=10, padx=10, sticky="e")
        self.ent_gateway = tk.Entry(self.frame_inputs, font=font_entry, width=20)
        self.ent_gateway.grid(row=3, column=1, pady=10, padx=10)
        
        tk.Label(self.frame_inputs, text="首选 DNS:", font=font_label, bg="#f8f9fa").grid(row=4, column=0, pady=10, padx=10, sticky="e")
        self.ent_dns = tk.Entry(self.frame_inputs, font=font_entry, width=20)
        self.ent_dns.grid(row=4, column=1, pady=10, padx=10)

        tk.Label(self.frame_inputs, text="备用 DNS:", font=font_label, bg="#f8f9fa").grid(row=5, column=0, pady=10, padx=10, sticky="e")
        self.ent_alt_dns = tk.Entry(self.frame_inputs, font=font_entry, width=20)
        self.ent_alt_dns.grid(row=5, column=1, pady=10, padx=10)

        # IP已配置跳过此步骤
        self.var_skip_ip = tk.BooleanVar(value=False)
        self.chk_skip_ip = tk.Checkbutton(self.frame_inputs, text="IP已配置，跳过此步骤", variable=self.var_skip_ip, font=("Microsoft YaHei", 9), bg="#f8f9fa", command=self.toggle_ip_state)
        self.chk_skip_ip.grid(row=6, column=1, sticky="e", pady=(0, 10), padx=10)

        # 锐捷认证输入区域
        tk.Frame(self.frame_inputs, height=1, bg="#dee2e6").grid(row=7, column=0, columnspan=3, sticky="ew", pady=10)

        # --- 第二步：锐捷认证 ---
        tk.Label(self.frame_inputs, text="第二步：锐捷认证", font=font_title, bg="#f8f9fa", fg="#0d6efd").grid(row=8, column=0, columnspan=2, pady=(0, 10), sticky="w", padx=10)

        tk.Label(self.frame_inputs, text="锐捷账号:", font=font_label, bg="#f8f9fa").grid(row=9, column=0, pady=10, padx=10, sticky="e")
        self.ent_rj_user = ttk.Combobox(self.frame_inputs, font=font_entry, width=18)
        self.ent_rj_user.grid(row=9, column=1, pady=10, padx=10)
        
        self.lbl_rj_help = tk.Label(self.frame_inputs, text="不知道填什么？", font=("Microsoft YaHei", 9, "underline"), fg="blue", bg="#f8f9fa", cursor="hand2")
        self.lbl_rj_help.grid(row=9, column=2, padx=5, sticky="w")
        self.lbl_rj_help.bind("<Enter>", self.show_rj_help_tooltip)
        self.lbl_rj_help.bind("<Leave>", self.hide_rj_help_tooltip)
        
        tk.Label(self.frame_inputs, text="锐捷密码:", font=font_label, bg="#f8f9fa").grid(row=10, column=0, pady=10, padx=10, sticky="e")
        self.ent_rj_pass = tk.Entry(self.frame_inputs, font=font_entry, width=20, show="*")
        self.ent_rj_pass.grid(row=10, column=1, pady=10, padx=10)
        
        self.var_save_pass = tk.BooleanVar(value=True)
        self.chk_save_pass = tk.Checkbutton(self.frame_inputs, text="保存密码", variable=self.var_save_pass, font=("Microsoft YaHei", 9), bg="#f8f9fa")
        self.chk_save_pass.grid(row=10, column=2, sticky="w")
        
        self.rj_accounts = {}
        
        def on_rj_user_select(event=None):
            user = self.ent_rj_user.get().strip()
            if user in self.rj_accounts:
                enc_pass = self.rj_accounts[user]
                self.ent_rj_pass.delete(0, tk.END)
                if enc_pass:
                    try:
                        dec_pass = base64.b64decode(enc_pass.encode("utf-8")).decode("utf-8")
                        self.ent_rj_pass.insert(0, dec_pass)
                        self.var_save_pass.set(True)
                    except:
                        pass
                else:
                    self.var_save_pass.set(False)
                    
        self.ent_rj_user.bind("<<ComboboxSelected>>", on_rj_user_select)
        self.ent_rj_user.bind("<KeyRelease>", on_rj_user_select)
        self.ent_rj_user.bind("<FocusOut>", on_rj_user_select)
        
        self.var_auto_rj = tk.BooleanVar(value=True)
        self.chk_auto_rj = tk.Checkbutton(self.frame_inputs, text="执行此步骤以自动连接锐捷认证", variable=self.var_auto_rj, font=font_label, bg="#f8f9fa")
        self.chk_auto_rj.grid(row=11, column=0, columnspan=3, pady=5)
        
        # 按钮
        self.btn_apply = tk.Button(self.frame_inputs, text="应用配置 (需管理员)", command=self.apply_settings, 
                                   font=("Microsoft YaHei", 11, "bold"), bg="#0d6efd", fg="white", 
                                   activebackground="#0b5ed7", activeforeground="white", width=30,
                                   relief=tk.FLAT, pady=5)
        self.btn_apply.grid(row=12, column=0, columnspan=3, pady=20)
        
        # 初始检测与读取配置
        self.load_ip_data()
        self.load_config()
        self.check_connection()
        
        if self.silent_mode:
            self.withdraw()
            if self.setting_auto_auth.get():
                # 延迟执行自动认证，确保网卡准备就绪及系统完全启动
                self.after(8000, lambda: self.apply_settings(silent_trigger=True))
        else:
            # 启动时弹窗公告
            self.after(200, lambda: show_announcement(self))
            if self.setting_auto_auth.get():
                self.after(8000, lambda: self.apply_settings(silent_trigger=False))

    def get_resource_path(self, relative_path):
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, relative_path)

    def center_dialog(self, dialog, width, height):
        self.update_idletasks()
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - width) // 2
        y = self.winfo_y() + (self.winfo_height() - height) // 2
        dialog.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")

    def get_tray_image(self):
        png_path = self.get_resource_path("icon.png")
        ico_path = self.get_resource_path("icon.ico")
        
        try:
            if os.path.exists(png_path):
                return Image.open(png_path)
            elif os.path.exists(ico_path):
                return Image.open(ico_path)
        except Exception as e:
            print("加载托盘图标失败:", e)

        # 默认图标
        image = Image.new('RGB', (64, 64), color=(13, 110, 253))
        draw = ImageDraw.Draw(image)
        draw.rectangle([16, 16, 48, 48], fill=(255, 255, 255))
        return image

    def setup_tray_icon(self):
        def on_show(icon, item):
            self.after(0, self.show_window)
        
        def on_auth(icon, item):
            self.after(0, lambda: self.apply_settings(silent_trigger=True))
            
        def on_quit(icon, item):
            self.after(0, self.quit_app)

        menu = pystray.Menu(
            pystray.MenuItem("显示主窗口", on_show, default=True),
            pystray.MenuItem("执行认证", on_auth),
            pystray.MenuItem("彻底退出", on_quit)
        )
        self.tray_icon = pystray.Icon("NetworkConfigurator", self.get_tray_image(), "大连交通大学有线网认证", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def on_closing(self):
        if getattr(self, 'setting_close_mode', None) and self.setting_close_mode.get() == "退出":
            self.quit_app()
        else:
            self.withdraw()
            
    def quit_app(self):
        if self.tray_icon:
            self.tray_icon.stop()
        self.destroy()
        sys.exit(0)

    def load_config(self):
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(app_dir, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                
                if "ip" in config and config["ip"]: 
                    self.ent_ip.delete(0, tk.END)
                    self.ent_ip.insert(0, config["ip"])
                if "subnet" in config and config["subnet"]: 
                    self.ent_subnet.delete(0, tk.END)
                    self.ent_subnet.insert(0, config["subnet"])
                if "gateway" in config and config["gateway"]: 
                    self.ent_gateway.delete(0, tk.END)
                    self.ent_gateway.insert(0, config["gateway"])
                if "dns" in config and config["dns"]: 
                    self.ent_dns.delete(0, tk.END)
                    self.ent_dns.insert(0, config["dns"])
                if "alt_dns" in config and config["alt_dns"]: 
                    self.ent_alt_dns.delete(0, tk.END)
                    self.ent_alt_dns.insert(0, config["alt_dns"])
                
                if "skip_ip" in config:
                    self.var_skip_ip.set(config["skip_ip"])
                    self.toggle_ip_state()
                    
                self.rj_accounts = config.get("rj_accounts", {})
                if not self.rj_accounts and "rj_user" in config and config["rj_user"]:
                    self.rj_accounts[config["rj_user"]] = config.get("rj_pass", "")
                    
                users = list(self.rj_accounts.keys())
                self.ent_rj_user['values'] = users
                
                last_user = config.get("last_rj_user", config.get("rj_user", ""))
                if last_user:
                    self.ent_rj_user.set(last_user)
                    if last_user in self.rj_accounts:
                        enc_pass = self.rj_accounts[last_user]
                        if enc_pass:
                            try:
                                dec_pass = base64.b64decode(enc_pass.encode("utf-8")).decode("utf-8")
                                self.ent_rj_pass.delete(0, tk.END)
                                self.ent_rj_pass.insert(0, dec_pass)
                                self.var_save_pass.set(True)
                            except:
                                pass
                        else:
                            self.var_save_pass.set(False)
                if "auto_rj" in config: 
                    self.var_auto_rj.set(config["auto_rj"])
                    
                if "close_mode" in config: self.setting_close_mode.set(config["close_mode"])
                if "auto_boot" in config: self.setting_auto_boot.set(config["auto_boot"])
                if "auto_auth" in config: self.setting_auto_auth.set(config["auto_auth"])
            except Exception as e:
                print("加载配置失败:", e)

    def save_config(self):
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(app_dir, "config.json")
        
        user = self.ent_rj_user.get().strip()
        pwd = self.ent_rj_pass.get().strip()
        if user:
            if self.var_save_pass.get():
                self.rj_accounts[user] = base64.b64encode(pwd.encode("utf-8")).decode("utf-8")
            else:
                self.rj_accounts[user] = ""
            
            # 更新下拉框
            users = list(self.rj_accounts.keys())
            self.ent_rj_user['values'] = users

        config = {
            "ip": self.ent_ip.get().strip(),
            "subnet": self.ent_subnet.get().strip(),
            "gateway": self.ent_gateway.get().strip(),
            "dns": self.ent_dns.get().strip(),
            "alt_dns": self.ent_alt_dns.get().strip(),
            "skip_ip": self.var_skip_ip.get(),
            "rj_accounts": self.rj_accounts,
            "last_rj_user": user,
            "auto_rj": self.var_auto_rj.get(),
            "close_mode": self.setting_close_mode.get(),
            "auto_boot": self.setting_auto_boot.get(),
            "auto_auth": self.setting_auto_auth.get()
        }
        
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print("保存配置失败:", e)

    def open_settings(self):
        dlg = tk.Toplevel(self)
        dlg.title("设置")
        dlg.configure(bg="#f8f9fa")
        dlg.transient(self)
        dlg.grab_set()
        self.center_dialog(dlg, 380, 390)
        
        tk.Label(dlg, text="常规设置", font=("Microsoft YaHei", 11, "bold"), bg="#f8f9fa").pack(pady=10)
        
        chk_boot = tk.Checkbutton(dlg, text="开机静默启动", variable=self.setting_auto_boot, font=("Microsoft YaHei", 10), bg="#f8f9fa")
        chk_boot.pack(anchor="w", padx=20, pady=5)
        
        chk_auth = tk.Checkbutton(dlg, text="开机/启动后自动执行网络配置与锐捷认证", variable=self.setting_auto_auth, font=("Microsoft YaHei", 10), bg="#f8f9fa")
        chk_auth.pack(anchor="w", padx=20, pady=5)
        
        frame_close = tk.Frame(dlg, bg="#f8f9fa")
        frame_close.pack(anchor="w", padx=20, pady=10)
        tk.Label(frame_close, text="点击右上角关闭按钮时：", font=("Microsoft YaHei", 10), bg="#f8f9fa").pack(side=tk.LEFT)
        tk.Radiobutton(frame_close, text="最小化到托盘", variable=self.setting_close_mode, value="最小化到托盘", bg="#f8f9fa").pack(side=tk.LEFT)
        tk.Radiobutton(frame_close, text="直接退出", variable=self.setting_close_mode, value="退出", bg="#f8f9fa").pack(side=tk.LEFT)
        
        btn_update = tk.Button(dlg, text="检查更新", command=self.check_for_updates, font=("Microsoft YaHei", 9), bg="#198754", fg="white", relief=tk.FLAT, width=20)
        btn_update.pack(pady=5)
        
        btn_feedback = tk.Button(dlg, text="反馈 Bug / 功能建议", command=self.show_feedback_dialog, font=("Microsoft YaHei", 9), bg="#ffc107", fg="black", relief=tk.FLAT, width=20)
        btn_feedback.pack(pady=5)
        
        btn_reset = tk.Button(dlg, text="一键重置网络 (恢复自动获取)", command=self.reset_network, font=("Microsoft YaHei", 9), bg="#dc3545", fg="white", relief=tk.FLAT, width=25)
        btn_reset.pack(pady=5)
        
        def save_and_close():
            self.save_config()
            self.update_schtasks()
            dlg.destroy()
            
        tk.Button(dlg, text="保存设置", command=save_and_close, font=("Microsoft YaHei", 10), bg="#0d6efd", fg="white", relief=tk.FLAT, width=15).pack(pady=15)

    def show_feedback_dialog(self):
        fb_win = tk.Toplevel(self)
        fb_win.title("反馈问题")
        fb_win.configure(bg="#f8f9fa")
        fb_win.transient(self)
        fb_win.grab_set()
        self.center_dialog(fb_win, 280, 320)
        
        tk.Label(fb_win, text="请选择反馈方式", font=("Microsoft YaHei", 11, "bold"), bg="#f8f9fa").pack(pady=(15, 10))
        
        btn_github = tk.Button(fb_win, text="前往 GitHub 提交 Issue", command=lambda: webbrowser.open_new_tab("https://github.com/Crazy-chaos/DJTU_Network_Configurator/issues"), font=("Microsoft YaHei", 9), bg="#24292e", fg="white", relief=tk.FLAT, width=22)
        btn_github.pack(pady=5)
        
        tk.Label(fb_win, text="或扫码加入 QQ 群反馈:", font=("Microsoft YaHei", 10), bg="#f8f9fa").pack(pady=(15, 5))
        
        fb_win.qr_img = tk.PhotoImage(data=QQ_QR_BASE64.strip())
        tk.Label(fb_win, image=fb_win.qr_img, bg="#f8f9fa").pack(pady=5)

    def update_schtasks(self):
        task_name = "DJTUNetworkConfigurator"
        if self.setting_auto_boot.get():
            if getattr(sys, 'frozen', False):
                task_run = f'"{sys.executable}" --silent'
            else:
                task_run = f'"{sys.executable}" "{os.path.abspath(__file__)}" --silent'
            subprocess.run([
                "schtasks", "/create", "/tn", task_name, "/tr", task_run,
                "/sc", "onlogon", "/rl", "highest", "/f"
            ], creationflags=CREATE_NO_WINDOW)
        else:
            subprocess.run(["schtasks", "/delete", "/tn", task_name, "/f"], creationflags=CREATE_NO_WINDOW)

    def reset_network(self):
        if not self.interface_name:
            self.check_connection()
        if not self.interface_name:
            messagebox.showwarning("错误", "未检测到有线网络连接，无法重置！")
            return
            
        if not messagebox.askyesno("确认", "此操作将把您的有线网卡(IP和DNS)重置为自动获取(DHCP)，是否继续？"):
            return
            
        try:
            cmd_ip = f'netsh interface ipv4 set address name="{self.interface_name}" source=dhcp'
            subprocess.run(cmd_ip, shell=True, check=True, creationflags=CREATE_NO_WINDOW)
            
            cmd_dns = f'netsh interface ipv4 set dnsservers name="{self.interface_name}" source=dhcp'
            subprocess.run(cmd_dns, shell=True, check=True, creationflags=CREATE_NO_WINDOW)
            
            messagebox.showinfo("成功", "已成功将网络重置为自动获取(DHCP)。")
        except subprocess.CalledProcessError as e:
            messagebox.showerror("失败", f"重置失败，请确保您以管理员身份运行了程序。\n错误代码: {e.returncode}")

    def parse_version(self, v_str):
        v_str = re.sub(r'[^\d\.]', '', v_str)
        return [int(x) if x else 0 for x in v_str.split('.')]

    def check_for_updates(self):
        def _check():
            api_url = "https://api.github.com/repos/Crazy-chaos/DJTU_Network_Configurator/releases/latest"
            try:
                req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    
                latest_version = data.get('tag_name', '')
                assets = data.get('assets', [])
                
                if not latest_version:
                    self.after(0, lambda: messagebox.showinfo("检查更新", "暂未获取到版本信息。"))
                    return
                    
                cur_v = self.parse_version(CURRENT_VERSION)
                lat_v = self.parse_version(latest_version)
                
                is_newer = False
                for c, l in zip(cur_v + [0]*3, lat_v + [0]*3):
                    if l > c:
                        is_newer = True
                        break
                    elif l < c:
                        break
                        
                if is_newer:
                    exe_url = None
                    for asset in assets:
                        if asset['name'].endswith('.exe'):
                            exe_url = asset['browser_download_url']
                            break
                    
                    if exe_url:
                        def prompt():
                            if messagebox.askyesno("发现新版本", f"发现新版本 {latest_version}，是否立即下载并更新？\n\n更新说明:\n{data.get('body', '无')}"):
                                self.download_and_install(exe_url)
                        self.after(0, prompt)
                    else:
                        def prompt_web():
                            if messagebox.askyesno("发现新版本", f"发现新版本 {latest_version}，但未找到自动下载包。\n是否前往浏览器下载？"):
                                webbrowser.open_new_tab(data.get('html_url', ''))
                        self.after(0, prompt_web)
                else:
                    self.after(0, lambda: messagebox.showinfo("检查更新", f"当前已是最新版本 (v{CURRENT_VERSION})。"))
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    self.after(0, lambda: messagebox.showinfo("检查更新", "目前还没有发布任何正式版本。"))
                else:
                    self.after(0, lambda: messagebox.showerror("检查更新失败", f"网络请求错误: {e}"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("检查更新失败", f"发生错误: {e}"))
                
        threading.Thread(target=_check, daemon=True).start()

    def download_and_install(self, url):
        dl_win = tk.Toplevel(self)
        dl_win.title("正在下载更新")
        dl_win.transient(self)
        dl_win.grab_set()
        self.center_dialog(dl_win, 350, 120)
        
        lbl_status = tk.Label(dl_win, text="正在准备下载...", font=("Microsoft YaHei", 9))
        lbl_status.pack(pady=(15, 5))
        
        progress = ttk.Progressbar(dl_win, orient=tk.HORIZONTAL, length=300, mode='determinate')
        progress.pack(pady=10)
        
        def _download():
            temp_dir = tempfile.gettempdir()
            installer_path = os.path.join(temp_dir, "NetworkConfigurator_Update.exe")
            
            def reporthook(count, block_size, total_size):
                if total_size > 0:
                    percent = int(count * block_size * 100 / total_size)
                    percent = min(100, percent)
                    self.after(0, lambda p=percent: progress.config(value=p))
                    self.after(0, lambda p=percent: lbl_status.config(text=f"正在下载... {p}%"))
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=15) as response, open(installer_path, 'wb') as out_file:
                    file_size = int(response.info().get('Content-Length', -1))
                    downloaded = 0
                    block_size = 8192
                    while True:
                        buffer = response.read(block_size)
                        if not buffer:
                            break
                        downloaded += len(buffer)
                        out_file.write(buffer)
                        reporthook(downloaded // block_size, block_size, file_size)

                self.after(0, lambda: lbl_status.config(text="下载完成，正在启动安装程序..."))
                time.sleep(1)
                os.startfile(installer_path)
                self.after(0, self.quit_app)
            except Exception as e:
                self.after(0, lambda err=e: messagebox.showerror("下载失败", f"更新下载失败: {err}"))
                self.after(0, dl_win.destroy)

        threading.Thread(target=_download, daemon=True).start()

    def show_toast(self, title, msg):
        toast = tk.Toplevel(self)
        toast.wm_overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(bg="#333333")
        
        tk.Label(toast, text=title, font=("Microsoft YaHei", 10, "bold"), fg="white", bg="#333333").pack(anchor="w", padx=15, pady=(15, 2))
        tk.Label(toast, text=msg, font=("Microsoft YaHei", 9), fg="#cccccc", bg="#333333", justify=tk.LEFT).pack(anchor="w", padx=15, pady=(0, 15))
        
        toast.update_idletasks()
        width = toast.winfo_width()
        height = toast.winfo_height()
        
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = screen_width - width - 20
        y = screen_height - height - 60
        
        toast.geometry(f"+{x}+{y}")
        
        def fade(alpha):
            if alpha > 0:
                try:
                    toast.attributes("-alpha", alpha)
                    self.after(50, fade, alpha - 0.05)
                except tk.TclError:
                    pass
            else:
                toast.destroy()
                
        self.after(5000, lambda: fade(1.0))

    def load_ip_data(self):
        self.ip_data = {}
        path = self.get_resource_path("ip_data.dat")
        if os.path.exists(path):
            try:
                import zlib
                with open(path, "rb") as f:
                    encoded_data = f.read()
                compressed_data = base64.b64decode(encoded_data)
                text_data = zlib.decompress(compressed_data).decode('utf-8')
                
                for line in text_data.splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 4 and "-" in parts[0]:
                        bldg, room = parts[0].split("-", 1)
                        if bldg == "宿舍楼":
                            continue
                        if bldg not in self.ip_data:
                            self.ip_data[bldg] = {}
                        start_ip = parts[1]
                        gateway = parts[3]
                        self.ip_data[bldg][room] = (start_ip, gateway)
            except Exception as e:
                print("加载IP数据失败:", e)

    def show_ip_selector(self, event):
        if hasattr(self, 'selector_win') and self.selector_win and self.selector_win.winfo_exists():
            self.selector_win.focus()
            return
            
        x = event.x_root + 15
        y = event.y_root + 10
        
        self.selector_win = tk.Toplevel(self)
        self.selector_win.title("获取宿舍网络信息")
        self.selector_win.geometry(f"280x350+{x}+{y}")
        self.selector_win.configure(bg="#f8f9fa")
        self.selector_win.transient(self)
        self.selector_win.grab_set()
        
        tk.Label(self.selector_win, text="请选择您的宿舍", font=("Microsoft YaHei", 10, "bold"), bg="#f8f9fa").pack(pady=(15, 5))
        
        frame_sel = tk.Frame(self.selector_win, bg="#f8f9fa")
        frame_sel.pack(fill=tk.X, padx=20)
        
        tk.Label(frame_sel, text="宿舍楼:", font=("Microsoft YaHei", 9), bg="#f8f9fa").grid(row=0, column=0, pady=5, sticky="e")
        bldgs = list(self.ip_data.keys())
        combo_bldg = ttk.Combobox(frame_sel, values=bldgs, state="readonly", font=("Microsoft YaHei", 9), width=16)
        combo_bldg.grid(row=0, column=1, pady=5, padx=5)
        
        tk.Label(frame_sel, text="房间号:", font=("Microsoft YaHei", 9), bg="#f8f9fa").grid(row=1, column=0, pady=5, sticky="e")
        combo_room = ttk.Combobox(frame_sel, state="readonly", font=("Microsoft YaHei", 9), width=16)
        combo_room.grid(row=1, column=1, pady=5, padx=5)
        
        def on_bldg_select(e):
            bldg = combo_bldg.get()
            if bldg in self.ip_data:
                rooms = list(self.ip_data[bldg].keys())
                combo_room.config(values=rooms)
                if rooms:
                    combo_room.current(0)
                    
        combo_bldg.bind("<<ComboboxSelected>>", on_bldg_select)
        
        def on_confirm():
            bldg = combo_bldg.get()
            room = combo_room.get()
            if bldg in self.ip_data and room in self.ip_data[bldg]:
                ip, gw = self.ip_data[bldg][room]
                self.ent_ip.delete(0, tk.END)
                self.ent_ip.insert(0, ip)
                self.ent_gateway.delete(0, tk.END)
                self.ent_gateway.insert(0, gw)
                self.ent_dns.delete(0, tk.END)
                self.ent_dns.insert(0, "114.114.114.114")
                self.ent_alt_dns.delete(0, tk.END)
                self.ent_alt_dns.insert(0, "8.8.8.8")
            self.selector_win.destroy()
            
        tk.Button(frame_sel, text="自动填写", command=on_confirm, bg="#0d6efd", fg="white", relief=tk.FLAT, font=("Microsoft YaHei", 9), width=10).grid(row=2, column=0, columnspan=2, pady=10)
        
        tk.Frame(self.selector_win, height=1, bg="#dee2e6").pack(fill=tk.X, padx=20, pady=5)
        
        tk.Label(self.selector_win, text="或微信扫码获取", font=("Microsoft YaHei", 9), bg="#f8f9fa").pack()
        tk.Label(self.selector_win, image=self.qr_image, bg="#f8f9fa").pack(pady=(5, 10))
        
        # 柔和出现动画
        self.selector_win.attributes("-alpha", 0.0)
        def fade_in(alpha):
            if alpha < 1.0:
                try:
                    self.selector_win.attributes("-alpha", alpha)
                    self.after(30, lambda: fade_in(alpha + 0.1))
                except tk.TclError:
                    pass
            else:
                try:
                    self.selector_win.attributes("-alpha", 1.0)
                except tk.TclError:
                    pass
        fade_in(0.0)

    def show_rj_help_tooltip(self, event):
        if self.tooltip_win:
            return
        
        x = event.x_root + 15
        y = event.y_root + 10
        
        self.tooltip_win = tk.Toplevel(self)
        self.tooltip_win.wm_overrideredirect(True)
        self.tooltip_win.geometry(f"+{x}+{y}")
        self.tooltip_win.configure(bg="white", highlightbackground="black", highlightthickness=1)
        
        text = ("用户名为本人一卡通号（即学号），密码为本人生日\n"
                "（与身份证中生日相同，长度为8位，格式为年年年年月月日日，例如19940101）。\n\n"
                "例：\n"
                "锐捷账号：2612010110\n"
                "锐捷密码：19940101")
        lbl_text = tk.Label(self.tooltip_win, text=text, font=("Microsoft YaHei", 9), bg="white", justify=tk.LEFT)
        lbl_text.pack(padx=10, pady=10)

    def hide_rj_help_tooltip(self, event):
        if self.tooltip_win:
            self.tooltip_win.destroy()
            self.tooltip_win = None

    def toggle_ip_state(self):
        state = tk.DISABLED if self.var_skip_ip.get() else tk.NORMAL
        self.ent_ip.config(state=state)
        self.ent_subnet.config(state=state)
        self.ent_gateway.config(state=state)
        self.ent_dns.config(state=state)
        self.ent_alt_dns.config(state=state)

    def show_repair_tooltip(self, event):
        if self.tooltip_win:
            return
        x = event.x_root + 15
        y = event.y_root + 10
        self.tooltip_win = tk.Toplevel(self)
        self.tooltip_win.wm_overrideredirect(True)
        self.tooltip_win.geometry(f"+{x}+{y}")
        self.tooltip_win.configure(bg="white", highlightbackground="black", highlightthickness=1)
        tk.Label(self.tooltip_win, text="微信扫码进行网口报修", font=("Microsoft YaHei", 9), bg="white").pack(padx=10, pady=(10, 5))
        tk.Label(self.tooltip_win, image=self.repair_qr_image, bg="white").pack(padx=10, pady=(0, 10))

    def hide_repair_tooltip(self, event):
        if self.tooltip_win:
            self.tooltip_win.destroy()
            self.tooltip_win = None

    def check_connection(self):
        self.lbl_status.config(text="正在检测...", fg="black")
        self.update()
        
        self.interface_name = get_wired_interface()
        if self.interface_name:
            self.lbl_status.config(text=f"✅ 已检测到网线插入\n目标网卡: {self.interface_name}", fg="#198754")
            self.frame_inputs.pack(pady=10)
            if hasattr(self, 'lbl_repair') and self.lbl_repair.winfo_exists():
                self.lbl_repair.pack_forget()
        else:
            self.lbl_status.config(text="❌ 未检测到有线网络连接\n请检查网线是否插好。", fg="#dc3545")
            self.frame_inputs.pack_forget()
            
            if not hasattr(self, 'lbl_repair'):
                self.lbl_repair = tk.Label(self.frame_status, text="如果检查出不是电脑网线问题，可能是网口损坏，点此或扫码报修", font=("Microsoft YaHei", 9, "underline"), fg="blue", bg="#f8f9fa", cursor="hand2")
                self.lbl_repair.bind("<Enter>", self.show_repair_tooltip)
                self.lbl_repair.bind("<Leave>", self.hide_repair_tooltip)
                self.lbl_repair.bind("<Button-1>", lambda e: webbrowser.open_new_tab("https://wlbx.djtu.edu.cn/"))
                self.repair_qr_image = tk.PhotoImage(data=REPAIR_QR_BASE64.strip())
            self.lbl_repair.pack(pady=(5, 0))

    def apply_settings(self, silent_trigger=False):
        if not self.interface_name:
            self.check_connection()
            
        self.save_config()
        skip_ip = self.var_skip_ip.get()
        
        def notify(title, msg):
            if silent_trigger:
                self.show_toast(title, msg)
            else:
                if "失败" in title:
                    messagebox.showwarning(title, msg)
                else:
                    messagebox.showinfo(title, msg)
        
        if not skip_ip:
            if not self.interface_name:
                notify("错误", "未检测到有效的有线网卡！无法配置IP。请检查网线连接，或尝试手动配置。")
                return
                
            ip = self.ent_ip.get().strip()
            subnet = self.ent_subnet.get().strip()
            gateway = self.ent_gateway.get().strip()
            dns = self.ent_dns.get().strip()
            alt_dns = self.ent_alt_dns.get().strip()
            
            if not ip or not subnet or not gateway:
                if not silent_trigger: messagebox.showwarning("输入错误", "IPv4、子网掩码和网关都不能为空！")
                return
                
            success, msg = set_ip(self.interface_name, ip, subnet, gateway, dns, alt_dns)
            if not success:
                notify("配置失败", msg)
                return
        else:
            success = True
            msg = "IP 配置已跳过。"

        if self.var_auto_rj.get():
            rj_user = self.ent_rj_user.get().strip()
            rj_pass = self.ent_rj_pass.get().strip()
            if not rj_user or not rj_pass:
                if not silent_trigger: messagebox.showinfo("执行完成", msg + "\n\n提示: 您没有填写锐捷账号或密码，已跳过自动认证环节。")
                return
            
            rj_success, rj_msg = auto_connect_ruijie(rj_user, rj_pass)
            if rj_success:
                notify("执行完成", msg + "\n" + rj_msg)
            else:
                notify("执行完成 (锐捷启动失败)", msg + "\n" + rj_msg)
        else:
            notify("执行完成", msg)

if __name__ == "__main__":
    silent_mode = "--silent" in sys.argv
    
    # 单实例互斥体检测
    mutex_name = "DJTUNetworkConfigurator_SingleInstance_Mutex"
    app_mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
    if ctypes.windll.kernel32.GetLastError() == 183: # ERROR_ALREADY_EXISTS
        if not silent_mode:
            temp_root = tk.Tk()
            temp_root.withdraw()
            messagebox.showinfo("提示", "大连交通大学有线网认证助手已经在运行中。\n请在屏幕右下角的系统托盘中查找。")
            temp_root.destroy()
        sys.exit(0)
        
    if not is_admin():
        try:
            params = " --silent" if silent_mode else ""
            if getattr(sys, 'frozen', False):
                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
            else:
                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{__file__}"{params}', None, 1)
        except Exception:
            pass
        sys.exit()
    
    app = App(silent_mode=silent_mode)
    app.mainloop()

