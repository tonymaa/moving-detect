import cv2
import numpy as np
import time
import os
import base64
import threading
import logging
import requests
import json
import wave
import shutil
import subprocess
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


class AudioRecorder:
    def __init__(self, output_path):
        self.output_path = output_path
        self._stop_event = threading.Event()
        self._thread = None
        self._frames = []

    def start(self):
        self._stop_event.clear()
        self._frames = []
        self._thread = threading.Thread(target=self._record, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)

    def _record(self):
        try:
            import pyaudio
        except ImportError:
            return
        p = pyaudio.PyAudio()
        try:
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=44100,
                            input=True, frames_per_buffer=1024)
        except Exception as e:
            logger.warning(f"无法打开音频设备: {e}")
            p.terminate()
            return
        while not self._stop_event.is_set():
            try:
                data = stream.read(1024, exception_on_overflow=False)
                self._frames.append(data)
            except Exception:
                break
        stream.stop_stream()
        stream.close()
        p.terminate()
        if self._frames:
            wf = wave.open(self.output_path, 'wb')
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(44100)
            wf.writeframes(b''.join(self._frames))
            wf.close()


def _mux_audio_video(video_path, audio_path):
    output_path = video_path + '.tmp.avi'
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        logger.warning("未找到ffmpeg，保留纯视频")
        if os.path.exists(audio_path):
            os.remove(audio_path)
        return
    try:
        subprocess.run([
            ffmpeg, '-y', '-i', video_path, '-i', audio_path,
            '-c', 'copy', '-shortest', output_path
        ], check=True, capture_output=True)
        os.replace(output_path, video_path)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.warning(f"音频合成失败，保留纯视频: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)


_face_app = None


def _get_face_app():
    global _face_app
    if _face_app is None:
        from insightface.app import FaceAnalysis
        _face_app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
        _face_app.prepare(ctx_id=0, det_size=(640, 640))
        logger.info("InsightFace 模型加载完成")
    return _face_app


def _detect_faces(frame, video_filename, app):
    try:
        import face_db
        face_app = _get_face_app()
    except Exception as e:
        logger.warning(f"人脸检测库未就绪，跳过: {e}")
        app._face_detecting = False
        return
    try:
        faces = face_app.get(frame)
        if not faces:
            with app._frame_lock:
                app._face_boxes = []
            return
        boxes = []
        for face in faces:
            bbox = face.bbox.astype(int)
            x1, y1, x2, y2 = bbox
            encoding = face.embedding
            person_id = face_db.match_face(encoding)
            if person_id is None:
                crop = frame[y1:y2, x1:x2]
                if crop.size == 0:
                    continue
                _, crop_bytes = cv2.imencode('.jpg', crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
                person_id = face_db.add_unknown_face(encoding, crop_bytes.tobytes())
            else:
                face_db.add_encoding(person_id, encoding)
            if video_filename:
                face_db.add_video_face(video_filename, person_id)
            person = face_db.get_person(person_id)
            label = person['name'] if person and person['name'] else f'#{person_id}'
            boxes.append((y1, x2, y2, x1, label))
        with app._frame_lock:
            app._face_boxes = boxes
        if video_filename:
            annotated = frame.copy()
            for top, right, bottom, left, label in boxes:
                cv2.rectangle(annotated, (left, top), (right, bottom), (0, 255, 0), 2)
                cv2.putText(annotated, label, (left, top - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            base_name = os.path.splitext(video_filename)[0]
            thumb_path = os.path.join('./video', base_name + '.jpg')
            cv2.imwrite(thumb_path, annotated)
    except Exception as e:
        logger.warning(f"人脸检测异常: {e}")
    finally:
        app._face_detecting = False


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
        self._face_boxes = []
        self._face_detecting = False

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
        last_face_detect_time = 0

        if self.enable_detect: logger.info("开始检测...")

        while not self._stop_event.is_set():
            try:
                ret, frame2 = cap.read()
                if not ret:
                    logger.warning("摄像头读取失败，重试中...")
                    time.sleep(0.1)
                    continue

                # Face detection every ~1s
                current_time = time.time()
                if not self._face_detecting and current_time - last_face_detect_time >= 1.0:
                    last_face_detect_time = current_time
                    self._face_detecting = True
                    vf = os.path.basename(video_filename) if recording else None
                    threading.Thread(target=_detect_faces, args=(frame2.copy(), vf, self), daemon=True).start()

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
                            audio_path = os.path.join(self.video_dir, base_name + ".wav")
                            audio_recorder = AudioRecorder(audio_path)
                            audio_recorder.start()
                            start_time = time.time()
                            last_face_detect_time = 0

                if recording:
                    out.write(frame2)
                    if time.time() - start_time >= get_recording_duration() or not self.enable_detect:
                        recording = False
                        out.release()
                        audio_recorder.stop()
                        logger.info(f"视频录制完成: {video_filename}")
                        threading.Thread(target=_mux_audio_video, args=(video_filename, audio_path), daemon=True).start()

                gray1 = gray2

                with self._frame_lock:
                    display = frame2.copy()
                    for top, right, bottom, left, label in self._face_boxes:
                        cv2.rectangle(display, (left, top), (right, bottom), (0, 255, 0), 2)
                        cv2.putText(display, label, (left, top - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    self.latest_frame = display
                    _, buf = cv2.imencode('.jpg', display, [cv2.IMWRITE_JPEG_QUALITY, 70])
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
            audio_recorder.stop()
            threading.Thread(target=_mux_audio_video, args=(video_filename, audio_path), daemon=True).start()
        logger.info("检测结束.")

if __name__ == "__main__":
    App().start_detect(None, None, get_camera_index())
