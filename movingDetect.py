import cv2
import numpy as np
import time
import os
import base64
import threading
import logging
import requests
from datetime import datetime

camera_index = 1

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

def notify_by_qq(frame):
    logger.info("notify_by_qq...")
    # 将图像转换为 JPEG 格式
    _, buffer = cv2.imencode('.jpg', frame)

    # 将图像编码为 Base64
    encoded_string = base64.b64encode(buffer).decode('utf-8')
    # 构建请求体
    data = {
        "user_id": "1605337475",
        "message": [
            {
                "type": "image",
                "data": {
                    "file": f"data:image/jpeg;base64,{encoded_string}"
                }
            }
        ]
    }
    # 发送 POST 请求
    url = 'http://192.168.1.100:2701/send_private_msg'
    response = requests.post(url, json=data, headers={"Content-Type": "application/json"})
    logger.info('Status Code: %s', response.status_code)
    logger.info('Response: %s', response)

class App:
    def __init__(self, enable_detect = True):
        # 创建视频保存目录
        self.video_dir = './video'
        os.makedirs(self.video_dir, exist_ok=True)
        self.enable_detect = enable_detect

    def start_detect(self, onGetFrame, onDetected):
        # 初始化摄像头
        cap = cv2.VideoCapture(camera_index)

        # 读取第一帧
        ret, frame1 = cap.read()
        gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        gray1 = cv2.GaussianBlur(gray1, (21, 21), 0)

        # 设置去抖动时间（秒）
        debounce_time = 2  # 例如2秒
        last_alert_time = 0  # 上次打印时间
        recording = False  # 录制状态

        if self.enable_detect: logger.info("开始检测...")
        
        while True:
            # 读取下一帧
            ret, frame2 = cap.read()
            gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.GaussianBlur(gray2, (21, 21), 0)

            # 如果正在录制，则跳过变化检测
            if self.enable_detect and not recording:
                # 计算帧之间的差异
                delta = cv2.absdiff(gray1, gray2)
                thresh = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]

                # 计算变化的像素数量
                change_pixels = np.sum(thresh) / 255  # 计算白色像素的数量
                total_pixels = thresh.size  # 总像素数

                # 计算变化比例
                change_percentage = (change_pixels / total_pixels) * 100

                # 如果变化超过10%
                if change_percentage > 10:
                    current_time = time.time()  # 获取当前时间
                    # 检查是否超过去抖动时间
                    if current_time - last_alert_time > debounce_time:
                        last_alert_time = current_time  # 更新上次打印时间
                        
                        # 创建通知任务
                        notify_task = threading.Thread(target=lambda: notify_by_qq(frame2))
                        notify_task.start()

                        if onDetected is not None:
                            onDetectedTask = threading.Thread(target=lambda: onDetected(frame2))
                            onDetectedTask.start()


                        logger.info(f"录制视频: 变化超过10%: {change_percentage:.2f}%")
                        # 开始录制视频
                        recording = True
                        video_filename = os.path.join(self.video_dir, datetime.now().strftime("%Y%m%d_%H%M%S") + ".avi")
                        fourcc = cv2.VideoWriter_fourcc(*'XVID')
                        out = cv2.VideoWriter(video_filename, fourcc, 20.0, (frame2.shape[1], frame2.shape[0]))
                        
                        # 录制30秒
                        start_time = time.time()

            # 如果正在录制
            if recording:
                out.write(frame2)  # 写入当前帧
                if time.time() - start_time >= 30 or not self.enable_detect:  # 录制30秒
                    recording = False
                    out.release()  # 释放视频写入对象
                    logger.info(f"视频录制完成: {video_filename}")

            # 更新上一帧
            gray1 = gray2

            # 显示当前帧
            if onGetFrame is not None:
                onGetFrame(frame2)
            else: cv2.imshow("Frame", frame2)

            # 按 'q' 键退出
            if cv2.waitKey(33) & 0xFF == ord('q'):
                break

        # 释放摄像头和关闭所有窗口
        cap.release()
        if recording:
            out.release()  # 确保在退出时释放视频写入对象
        cv2.destroyAllWindows()
        logger.info("检测结束.")

if __name__ == "__main__":
    App().start_detect(None, None)
