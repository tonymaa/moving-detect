import cv2
import threading
import tkinter as tk
from PIL import Image, ImageTk
import pystray
from movingDetect import App
import numpy as np

class LockScreen:
    def __init__(self, master):
        self.master = master
        self.master.title("Lock Screen")


        self.master.bind("<Escape>", self.exit_fullscreen)  # 按 Esc 键退出全屏

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
        self.video_label = tk.Label(master, width=50, height=50)
        self.video_label.pack(pady=20)

        self.menu = pystray.Menu(
            pystray.MenuItem("锁屏", self.lock),
        )
        image = Image.open("icon.png")
        self.menu.icon = ImageTk.PhotoImage(image)
        self.tray_icon = pystray.Icon("锁屏", image, menu=self.menu)
        self.start_tary()

        video_stream = threading.Thread(target=lambda: App().start_detect(self.loadFrameToUI, self.onDetect))
        video_stream.setDaemon(True)
        video_stream.start()

    def onDetect(self, frame):
        self.video_label.pack(fill=tk.BOTH, expand=True)  # 显示 Canvas


    def loadFrameToUI(self, frame):
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


    def start_tary(self):
        thread = threading.Thread(target=self.tray_icon.run)
        thread.setDaemon(True)
        thread.start()

    def exit_fullscreen(self, event=None):
        self.master.attributes("-fullscreen", False)
#         self.master.quit()

if __name__ == "__main__":
    root = tk.Tk()
    lock_screen = LockScreen(root)
    root.mainloop()
