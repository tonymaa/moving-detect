from time import sleep
import threading
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageEnhance
import pystray
from movingDetect import App, list_cameras, get_camera_index, save_camera_index, load_config, get_recording_duration, save_recording_duration, get_show_face_boxes, save_show_face_boxes, get_show_camera, save_show_camera, get_record_mode, save_record_mode, get_trigger_person_ids, save_trigger_person_ids, get_exclude_person_ids, save_exclude_person_ids
import webbrowser
import web_server
from enum import Enum

class Mode(Enum):
    ScreenSaver = 1
    DarkScreen = 2

class LockScreen:
    def __init__(self, master):
        self.monitor_camera = App()
        self.master = master
        self.master.title("Lock Screen")
        self.mode = None
        self.video_stream = None
        self.web_running = False

        self.master.bind("<Escape>", self.exit_fullscreen)  # 按 Esc 键退出全屏

        window_width = 200
        window_height = 440

        # 获取屏幕的宽度和高度
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()

        # 计算窗口的 x 和 y 坐标，使其居中
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)

        # 设置窗口的位置和大小
        root.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # 加载背景图片
        self.background_image = Image.open("img.png")  # 替换为你的图片路径
        self.background_image = self.background_image.resize(
            (self.master.winfo_screenwidth(), self.master.winfo_screenheight()),
            Image.LANCZOS  # 使用 LANCZOS 代替 ANTIALIAS
        )
        self.background_photo = ImageTk.PhotoImage(self.background_image)

        # 创建标签显示背景
        self.label = tk.Label(master, image=self.background_photo)
        self.label.place(x=0, y=0, relwidth=1, relheight=1)

        # 可以在这里添加其他控件，例如时间、消息等
#         self.message_label = tk.Label(master, text="锁屏界面", font=("Arial", 50), bg="black", fg="white")
#         self.message_label.pack(pady=20)
        # 创建标签用于显示视频帧

#         root.wm_attributes("-transparentcolor", "snow")
#         tk.Style().configure("TP.TFrame", background="snow")
        # root.attributes("-alpha",0.5)
#         ttk.Style().configure("TP.TFrame", background="")

        # 创建一个 Frame
        self.frame = tk.Frame(root, width=200, height=280, bg="snow")
        self.frame.pack(fill=tk.BOTH, expand=True)  # 使用 pack 方法放置 Frame

        # 创建一个标签，撑满可用空间
        top_frame = tk.Frame(self.frame)
        top_frame.pack(fill=tk.BOTH, expand=True)  # 填满并扩展

        # 创建第一个 Label
        self.video_label = tk.Label(top_frame, height=200)  # 添加背景色以便于观察
        self.video_label.pack(fill=tk.BOTH, expand=True)  # 水平放置，第一个 Label

        # 创建一个固定高度的底部框架
        bottom_frame = tk.Frame(self.frame, height=window_height - 200)
        bottom_frame.pack(fill=tk.X)  # 填满 X 轴

        # 摄像头选择器
        cam_frame = tk.Frame(bottom_frame)
        cam_frame.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(cam_frame, text="摄像头:").pack(side=tk.LEFT)
        self.cameras = list_cameras()
        cam_names = [c['name'] for c in self.cameras]
        saved_idx = get_camera_index()
        self.selected_camera = tk.StringVar()
        # 默认选中已保存的摄像头
        default_name = f'Camera {saved_idx}'
        if default_name in cam_names:
            self.selected_camera.set(default_name)
        elif cam_names:
            self.selected_camera.set(cam_names[0])
        self.cam_combo = ttk.Combobox(cam_frame, textvariable=self.selected_camera,
                                       values=cam_names, state='readonly', width=12)
        self.cam_combo.pack(side=tk.LEFT, padx=5)
        self.cam_combo.bind("<<ComboboxSelected>>", self.on_camera_changed)

        # 录制时长配置
        dur_frame = tk.Frame(bottom_frame)
        dur_frame.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(dur_frame, text="录制时长(秒):").pack(side=tk.LEFT)
        self.duration_var = tk.StringVar(value=str(get_recording_duration()))
        self.duration_entry = tk.Entry(dur_frame, textvariable=self.duration_var, width=5)
        self.duration_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(dur_frame, text="保存", command=self.save_duration).pack(side=tk.LEFT)

        self.monitor_camera.enable_detect = False

        # 显示人脸框开关
        self.face_box_var = tk.BooleanVar(value=get_show_face_boxes())
        face_box_cb = tk.Checkbutton(bottom_frame, text="显示人脸框", variable=self.face_box_var, command=self.toggle_face_boxes)
        face_box_cb.pack()

        # 录制触发模式
        mode_frame = tk.Frame(bottom_frame)
        mode_frame.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(mode_frame, text="录制触发:").pack(side=tk.LEFT)
        self.record_mode_var = tk.StringVar(value=get_record_mode())
        mode_combo = ttk.Combobox(mode_frame, textvariable=self.record_mode_var,
                                   values=['motion', 'face', 'new_face', 'specific_face'], state='readonly', width=12)
        mode_combo.pack(side=tk.LEFT, padx=5)
        mode_combo.bind("<<ComboboxSelected>>", self.on_record_mode_changed)

        self.trigger_person_btn = tk.Button(bottom_frame, text="选择触发人脸", command=self.open_trigger_person_dialog)
        self.exclude_person_btn = tk.Button(bottom_frame, text="排除人脸", command=self.open_exclude_person_dialog)
        mode = get_record_mode()
        if mode == 'specific_face':
            self.trigger_person_btn.pack()
            self.exclude_person_btn.pack_forget()
        elif mode in ('face', 'new_face'):
            self.trigger_person_btn.pack_forget()
            self.exclude_person_btn.pack()
        else:
            self.trigger_person_btn.pack_forget()
            self.exclude_person_btn.pack_forget()

        self.toggle_video_btn = tk.Button(bottom_frame, text="隐藏画面", command=self.toggle_video)
        self.toggle_video_btn.pack()
        if not get_show_camera():
            self.video_label.pack_forget()
            self.toggle_video_btn.configure(text="显示画面")
        self.toggle_detect_btn = tk.Button(bottom_frame, text= "关闭检测" if self.monitor_camera.enable_detect else "开启检测", command=self.toggle_detect)
        self.toggle_detect_btn.pack()

        self.screen_saver_btn = tk.Button(bottom_frame, text="开启屏保并检测", command=self.lock)
        self.screen_saver_btn.pack()

        self.dark_mode_btn = tk.Button(bottom_frame, text="开启暗屏并检测", command=self.dark_mode)
        self.dark_mode_btn.pack()

        self.web_btn = tk.Button(bottom_frame, text="启动Web服务", command=self.toggle_web)
        self.web_btn.pack()

        self.monitor_label = tk.Label(self.master, width=120, height=120)

#         self.menu = pystray.Menu(
#             pystray.MenuItem("屏保", self.lock),
#         )
#         image = Image.open("icon.png")
#         self.menu.icon = ImageTk.PhotoImage(image)
#         self.tray_icon = pystray.Icon("开启屏保", image, menu=self.menu)
#         self.start_tary()


        self._start_video_stream()

        self.monitor_camera._lock_screen = self

        # 默认启动Web服务
        self.toggle_web()

    def toggle_detect(self):
        if self.monitor_camera.enable_detect:
            self.monitor_camera.enable_detect = False
            self.toggle_detect_btn.configure(text="开启检测")
        else:
            self.monitor_camera.enable_detect = True
            self.toggle_detect_btn.configure(text="关闭检测")

    def save_duration(self):
        try:
            val = max(5, min(300, int(self.duration_var.get())))
        except ValueError:
            val = 15
        self.duration_var.set(str(val))
        save_recording_duration(val)

    def toggle_face_boxes(self):
        save_show_face_boxes(self.face_box_var.get())

    def on_record_mode_changed(self, event=None):
        mode = self.record_mode_var.get()
        save_record_mode(mode)
        if mode == 'specific_face':
            self.trigger_person_btn.pack()
            self.exclude_person_btn.pack_forget()
        elif mode in ('face', 'new_face'):
            self.trigger_person_btn.pack_forget()
            self.exclude_person_btn.pack()
        else:
            self.trigger_person_btn.pack_forget()
            self.exclude_person_btn.pack_forget()

    def open_trigger_person_dialog(self):
        import face_db
        persons = face_db.get_all_persons()
        if not persons:
            return
        dialog = tk.Toplevel(self.master)
        dialog.title("选择触发人脸")
        dialog.geometry("250x300")
        dialog.transient(self.master)
        dialog.grab_set()
        trigger_ids = get_trigger_person_ids()
        vars_ = {}
        for p in persons:
            var = tk.BooleanVar(value=p['id'] in trigger_ids)
            vars_[p['id']] = var
            name = p['name'] or f"未命名 #{p['id']}"
            tk.Checkbutton(dialog, text=name, variable=var).pack(anchor='w', padx=10)
        def save():
            ids = [pid for pid, v in vars_.items() if v.get()]
            save_trigger_person_ids(ids)
            dialog.destroy()
        tk.Button(dialog, text="确定", command=save).pack(pady=10)

    def open_exclude_person_dialog(self):
        import face_db
        persons = face_db.get_all_persons()
        if not persons:
            return
        dialog = tk.Toplevel(self.master)
        dialog.title("排除人脸")
        dialog.geometry("250x300")
        dialog.transient(self.master)
        dialog.grab_set()
        exclude_ids = get_exclude_person_ids()
        vars_ = {}
        for p in persons:
            var = tk.BooleanVar(value=p['id'] in exclude_ids)
            vars_[p['id']] = var
            name = p['name'] or f"未命名 #{p['id']}"
            tk.Checkbutton(dialog, text=name, variable=var).pack(anchor='w', padx=10)
        def save():
            ids = [pid for pid, v in vars_.items() if v.get()]
            save_exclude_person_ids(ids)
            dialog.destroy()
        tk.Button(dialog, text="确定", command=save).pack(pady=10)

    def toggle_video(self):
        if self.video_label.winfo_ismapped():
            self.video_label.pack_forget()
            self.toggle_video_btn.configure(text="显示画面")
            save_show_camera(False)
        else:
            self.video_label.pack(fill=tk.BOTH, expand=True)
            self.toggle_video_btn.configure(text="隐藏画面")
            save_show_camera(True)

    def _get_selected_camera_index(self) -> int:
        name = self.selected_camera.get()
        for c in self.cameras:
            if c['name'] == name:
                return c['index']
        return 0

    def _start_video_stream(self):
        cam_idx = self._get_selected_camera_index()
        self.video_stream = threading.Thread(
            target=lambda: self.monitor_camera.start_detect(None, self.onDetect, cam_idx)
        )
        self.video_stream.setDaemon(True)
        self.video_stream.start()
        self._poll_frame()

    def _poll_frame(self):
        if self.mode is not None:
            self.master.after(50, self._poll_frame)
            return
        try:
            frame = None
            with self.monitor_camera._frame_lock:
                if self.monitor_camera.latest_frame is not None:
                    frame = self.monitor_camera.latest_frame.copy()
            if frame is not None:
                self._update_video_label(frame)
        except Exception:
            pass
        self.master.after(33, self._poll_frame)

    def on_camera_changed(self, event=None):
        cam_idx = self._get_selected_camera_index()
        save_camera_index(cam_idx)
        # 停止当前检测循环，然后重启
        self.monitor_camera.stop()
        if self.video_stream and self.video_stream.is_alive():
            self.video_stream.join(timeout=3)
        self._start_video_stream()

    def toggle_web(self):
        if self.web_running:
            self.web_btn.configure(text="启动Web服务")
            self.web_running = False
        else:
            port = load_config().get('web_port', 9999)
            web_server.start_server_thread(self.monitor_camera, port)
            self.web_running = True
            self.web_btn.configure(text=f"Web:{port}")
            webbrowser.open(f'http://localhost:{port}')


    def onDetect(self, frame):
        if not self.monitor_camera.enable_detect: return
        def show_monitor_img():
            monitor_img = Image.open("monitor.png")  # 替换为你的图片路径
            monitor_img = monitor_img.resize(
                (120, 120),
                Image.LANCZOS  # 使用 LANCZOS 代替 ANTIALIAS
            )
            self.monitor_photo = ImageTk.PhotoImage(monitor_img)

            # 创建标签显示背景
            self.monitor_label = tk.Label(self.master, image=self.monitor_photo, width=120, height=120)
            self.monitor_label.place(x=60, y=60)
        def hide_monitor_img():
            self.monitor_label.destroy()
        if self.mode == Mode.ScreenSaver.name:
            show_monitor_img()

            # 调整亮度，降低暗度
            enhancer = ImageEnhance.Brightness(self.background_image)
            # 0.5 表示降低亮度，1.0 表示原始亮度
            enhancer_bg_img= ImageTk.PhotoImage(enhancer.enhance(0.5))
            self.label.configure(image=enhancer_bg_img)

            sleep(15)
            if not self.monitor_camera.enable_detect: return
            self.label.configure(image=self.background_photo)
            hide_monitor_img()
        elif self.mode == Mode.DarkScreen.name:
            show_monitor_img()
            self.label.configure(image=self.background_photo)
            sleep(15)
            if not self.monitor_camera.enable_detect: return
            self.dark_mode()
            hide_monitor_img()



    def _update_video_label(self, frame):
        label_width = self.video_label.winfo_width()
        label_height = self.video_label.winfo_height()
        if label_width < 2 or label_height < 2:
            return
        frame_height, frame_width, _ = frame.shape
        scale = min(label_width / frame_width, label_height / frame_height)
        new_width = int(frame_width * scale)
        new_height = int(frame_height * scale)

        rgb = frame[:, :, ::-1]  # BGR -> RGB via numpy slice, no OpenCV
        img = Image.fromarray(rgb).resize((new_width, new_height), Image.LANCZOS)

        canvas = Image.new('RGB', (label_width, label_height), (0, 0, 0))
        x_offset = (label_width - new_width) // 2
        y_offset = (label_height - new_height) // 2
        canvas.paste(img, (x_offset, y_offset))

        img_tk = ImageTk.PhotoImage(image=canvas)
        self.video_label.imgtk = img_tk
        self.video_label.configure(image=img_tk)

    def dark_mode(self):
        if not self.monitor_camera.enable_detect: self.toggle_detect()
        self.mode = Mode.DarkScreen.name
        self.master.attributes("-fullscreen", True)
        self.master.attributes("-topmost", True)
        # 调整亮度，降低暗度
        enhancer = ImageEnhance.Brightness(self.background_image)
        # 0.5 表示降低亮度，1.0 表示原始亮度
        self.enhancer_bg_img= ImageTk.PhotoImage(enhancer.enhance(0))
        self.label.configure(image=self.enhancer_bg_img)
        self.frame.pack_forget()
        web_server.notify_mode_change(self.mode)

    def lock(self):
        if not self.monitor_camera.enable_detect: self.toggle_detect()
        # 全屏
        self.master.attributes("-fullscreen", True)
        self.master.attributes("-topmost", True)
        self.mode = Mode.ScreenSaver.name
        self.frame.pack_forget()
        web_server.notify_mode_change(self.mode)


    def start_tary(self):
        thread = threading.Thread(target=self.tray_icon.run)
        thread.setDaemon(True)
        thread.start()

    def exit_fullscreen(self, event=None):
        if self.monitor_camera.enable_detect: self.toggle_detect()
#         if self.mode = Mode.ScreenSaver.name:
        # 退出屏保
        self.master.attributes("-fullscreen", False)
        self.master.attributes("-topmost", False)
        self.mode = None
        self.frame.pack(fill=tk.BOTH, expand=True)
        self.monitor_label.destroy()
        self.label.configure(image=self.background_photo)
        web_server.notify_mode_change(None)
#         elif self.mode = Mode.DarkScreen.name:
        # 退出暗屏
#         self.master.quit()

if __name__ == "__main__":
    root = tk.Tk()
    lock_screen = LockScreen(root)
    root.mainloop()
