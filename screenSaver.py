from time import sleep
import cv2
import threading
import tkinter as tk
from PIL import Image, ImageTk, ImageEnhance
import pystray
from movingDetect import App
import numpy as np

class LockScreen:
    def __init__(self, master):
        self.monitor_camera = App()
        self.master = master
        self.master.title("Lock Screen")
        self.is_full_screen = False

        self.master.bind("<Escape>", self.exit_fullscreen)  # 按 Esc 键退出全屏

        window_width = 200
        window_height = 250

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
        self.frame = tk.Frame(root, width=200, height=200, bg="snow")
        self.frame.pack(fill=tk.BOTH, expand=True)  # 使用 pack 方法放置 Frame

        # 创建一个标签，撑满可用空间
        top_frame = tk.Frame(self.frame)
        top_frame.pack(fill=tk.BOTH, expand=True)  # 填满并扩展

        # 创建第一个 Label
        self.video_label = tk.Label(top_frame, height=200)  # 添加背景色以便于观察
        self.video_label.pack(fill=tk.BOTH, expand=True)  # 水平放置，第一个 Label

        # 创建一个固定高度的底部框架
        bottom_frame = tk.Frame(self.frame, height=50)
        bottom_frame.pack(fill=tk.X)  # 填满 X 轴

        self.toggle_detect_btn = tk.Button(bottom_frame, text= "关闭检测" if self.monitor_camera.enable_detect else "开启检测", command=self.toggle_detect)
        self.toggle_detect_btn.pack()

        self.screen_saver_btn = tk.Button(bottom_frame, text="开启屏保", command=self.lock)
        self.screen_saver_btn.pack()

        self.monitor_label = tk.Label(self.master, width=120, height=120)

        self.menu = pystray.Menu(
            pystray.MenuItem("屏保", self.lock),
        )
        image = Image.open("icon.png")
        self.menu.icon = ImageTk.PhotoImage(image)
        self.tray_icon = pystray.Icon("开启屏保", image, menu=self.menu)
        self.start_tary()


        video_stream = threading.Thread(target=lambda: self.monitor_camera.start_detect(self.loadFrameToUI, self.onDetect))
        video_stream.setDaemon(True)
        video_stream.start()

    def toggle_detect(self):
        if self.monitor_camera.enable_detect:
            self.monitor_camera.enable_detect = False
            self.toggle_detect_btn.configure(text="开启检测")
        else:
            self.monitor_camera.enable_detect = True
            self.toggle_detect_btn.configure(text="关闭检测")

    def onDetect(self, frame):
        if self.is_full_screen:
            monitor_img = Image.open("monitor.png")  # 替换为你的图片路径
            monitor_img = monitor_img.resize(
                (120, 120),
                Image.LANCZOS  # 使用 LANCZOS 代替 ANTIALIAS
            )
            self.monitor_photo = ImageTk.PhotoImage(monitor_img)

            # 创建标签显示背景
            self.monitor_label = tk.Label(self.master, image=self.monitor_photo, width=120, height=120)
            self.monitor_label.place(x=60, y=60)

            # 调整亮度，降低暗度
            enhancer = ImageEnhance.Brightness(self.background_image)
            # 0.5 表示降低亮度，1.0 表示原始亮度
            enhancer_bg_img= ImageTk.PhotoImage(enhancer.enhance(0.5))
            self.label.configure(image=enhancer_bg_img)

            sleep(15)
            self.label.configure(image=self.background_photo)
            self.monitor_label.destroy()



    def loadFrameToUI(self, frame):
        if self.is_full_screen: return
        # 获取 Label 的当前大小
        label_width = self.video_label.winfo_width()
        label_height = self.video_label.winfo_height()
        # 获取原始帧的大小
        frame_height, frame_width, _ = frame.shape
        # 计算缩放因子
        scale = min(label_width / frame_width, label_height / frame_height)

        # 计算缩放后的新尺寸
        new_width = int(frame_width * scale)
        new_height = int(frame_height * scale)

        # 转换为 RGB
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # 调整帧的大小
        frame = cv2.resize(frame, (new_width, new_height))

        # 创建一个新的空白图像，并填充为白色（或其他背景色）
        new_frame = 0 * np.ones(shape=[label_height, label_width, 3], dtype=np.uint8)

        # 计算放置图像的位置，以便居中
        x_offset = (label_width - new_width) // 2
        y_offset = (label_height - new_height) // 2

        # 将调整大小后的帧放入新图像中
        new_frame[y_offset:y_offset + new_height, x_offset:x_offset + new_width] = frame

        # 将帧转换为 Image
        img = Image.fromarray(new_frame)
        img_tk = ImageTk.PhotoImage(image=img)

        # 更新标签以显示新帧
        self.video_label.imgtk = img_tk
        self.video_label.configure(image=img_tk)


    def lock(self):
        # 全屏
        self.master.attributes("-fullscreen", True)
        self.screen_saver_btn.pack_forget()
        self.is_full_screen = True
        self.frame.pack_forget()

    def start_tary(self):
        thread = threading.Thread(target=self.tray_icon.run)
        thread.setDaemon(True)
        thread.start()

    def exit_fullscreen(self, event=None):
        self.master.attributes("-fullscreen", False)
        self.screen_saver_btn.pack()
        self.is_full_screen = False
        self.frame.pack(fill=tk.BOTH, expand=True)
        self.monitor_label.destroy()
#         self.master.quit()

if __name__ == "__main__":
    root = tk.Tk()
    lock_screen = LockScreen(root)
    root.mainloop()
