import cv2
import numpy as np
import time
import os
import base64
import threading
import logging
import requests
import json
from datetime import datetime

CONFIG_FILE = 'config.json'


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_config(config: dict) -> None:
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)


def get_camera_index() -> int:
    return load_config().get('camera_index', 0)


def save_camera_index(index: int) -> None:
    config = load_config()
    config['camera_index'] = index
    save_config(config)


def get_recording_duration() -> int:
    return load_config().get('recording_duration', 15)


def save_recording_duration(duration: int) -> None:
    config = load_config()
    config['recording_duration'] = max(5, min(300, duration))
    save_config(config)
_cached_cameras = None


def list_cameras(max_test: int = 5) -> list[dict]:
    """Enumerate available cameras. Result is cached after first call."""
    global _cached_cameras
    if _cached_cameras is not None:
        return _cached_cameras
    cameras = []
    for i in range(max_test):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                cameras.append({'index': i, 'name': f'Camera {i}'})
            cap.release()
    _cached_cameras = cameras
    return cameras


def get_cached_cameras() -> list[dict]:
    return list_cameras()

# 设置日志记录
log_dir = './logs'
os.makedirs(log_dir, exist_ok=True)

# 获取当前日期并格式化为字符串
log_filename = datetime.now().strftime("%Y%m%d") + '.log'

# 创建日志记录器
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# 创建文件处理器
file_handler = logging.FileHandler(os.path.join(log_dir, log_filename))
file_handler.setLevel(logging.INFO)

# 创建控制台处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# 设置日志格式
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# 添加处理器到记录器
logger.addHandler(file_handler)
logger.addHandler(console_handler)


class App:
    def __init__(self, enable_detect=True):
        # 创建视频保存目录
        self.video_dir = './video'
        os.makedirs(self.video_dir, exist_ok=True)
        self.enable_detect = enable_detect
        self._stop_event = threading.Event()
        self._stopped = False
        self.latest_frame = None
        self._latest_jpeg = None
        self._frame_lock = threading.Lock()
        self._notification_callbacks = []

    def stop(self):
        self._stop_event.set()

    def on_notification(self, callback):
        self._notification_callbacks.append(callback)

    def get_frame_jpeg(self):
        with self._frame_lock:
            return self._latest_jpeg

    def start_detect(self, onGetFrame, onDetected, camera_idx=None):
        self._stop_event.clear()
        self._stopped = False
        if camera_idx is None:
            camera_idx = get_camera_index()
        self._camera_idx = camera_idx
        # 初始化摄像头
        cap = cv2.VideoCapture(camera_idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            logger.error(f"无法打开摄像头 {camera_idx}")
            self._stopped = True
            return

        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # 读取第一帧
        while not self._stop_event.is_set():
            ret, frame1 = cap.read()
            if ret:
                break
            logger.warning("等待摄像头就绪...")
            time.sleep(0.5)
        else:
            cap.release()
            self._stopped = True
            return

        gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        gray1 = cv2.GaussianBlur(gray1, (21, 21), 0)

        debounce_time = 2
        last_alert_time = 0
        recording = False

        if self.enable_detect: logger.info("开始检测...")

        while not self._stop_event.is_set():
            try:
                ret, frame2 = cap.read()
                if not ret:
                    logger.warning("摄像头读取失败，重试中...")
                    time.sleep(0.1)
                    continue

                gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
                gray2 = cv2.GaussianBlur(gray2, (21, 21), 0)

                if self.enable_detect and not recording:
                    delta = cv2.absdiff(gray1, gray2)
                    thresh = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]
                    change_pixels = np.sum(thresh) / 255
                    total_pixels = thresh.size
                    change_percentage = (change_pixels / total_pixels) * 100

                    if change_percentage > 10:
                        current_time = time.time()
                        if current_time - last_alert_time > debounce_time:
                            last_alert_time = current_time

                            if onDetected is not None:
                                onDetectedTask = threading.Thread(target=lambda: onDetected(frame2))
                                onDetectedTask.start()

                            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            for cb in self._notification_callbacks:
                                try:
                                    cb(ts, change_percentage)
                                except Exception:
                                    pass

                            logger.info(f"录制视频: 变化超过10%: {change_percentage:.2f}%")
                            recording = True
                            base_name = datetime.now().strftime("%Y%m%d_%H%M%S")
                            video_filename = os.path.join(self.video_dir, base_name + ".avi")
                            fourcc = cv2.VideoWriter_fourcc(*'XVID')
                            out = cv2.VideoWriter(video_filename, fourcc, 20.0, (frame2.shape[1], frame2.shape[0]))
                            thumb_path = os.path.join(self.video_dir, base_name + ".jpg")
                            cv2.imwrite(thumb_path, frame2)
                            start_time = time.time()

                if recording:
                    out.write(frame2)
                    if time.time() - start_time >= get_recording_duration() or not self.enable_detect:
                        recording = False
                        out.release()
                        logger.info(f"视频录制完成: {video_filename}")

                gray1 = gray2

                with self._frame_lock:
                    self.latest_frame = frame2.copy()
                    _, buf = cv2.imencode('.jpg', frame2, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    self._latest_jpeg = buf.tobytes()

                if onGetFrame is not None:
                    onGetFrame(frame2)

            except Exception as e:
                logger.error(f"检测循环异常: {e}")
                time.sleep(0.1)

            time.sleep(0.03)

        cap.release()
        if recording:
            out.release()
        logger.info("检测结束.")

if __name__ == "__main__":
    App().start_detect(None, None, get_camera_index())
