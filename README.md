
# moving-detect

**moving-detect** 是一个基于 **Python + OpenCV** 的简单运动检测项目，可通过摄像头或视频流检测画面中的运动变化，适合用于学习计算机视觉、简单监控或屏幕保护相关场景。

**moving-detect** is a simple **motion detection** project built with **Python and OpenCV**. It detects movement by analyzing frame differences from a webcam or video stream, making it suitable for computer vision learning, lightweight monitoring, or screensaver-related use cases.

---

## ✨ 功能特性 | Features

* 📷 基于摄像头的视频运动检测
* 🧠 通过帧差法检测画面中的变化
* 🖥 可扩展为屏保或空闲检测程序
* 📦 代码结构简单，适合学习与二次开发

---

* 📷 Motion detection using webcam input
* 🧠 Detects movement based on frame differencing
* 🖥 Can be extended to screensaver or idle-detection scenarios
* 📦 Simple and readable code, suitable for learning and customization

---

## 📁 项目结构 | Project Structure

```
moving-detect/
├── .gitignore
├── movingDetect.py
├── screenSaver.py
├── requirements.txt
├── icon.png
├── img.png
└── monitor.png
```

---

## 📄 文件说明 | File Description

| 文件 / File          | 说明 / Description                                |
| ------------------ | ----------------------------------------------- |
| `movingDetect.py`  | 主运动检测脚本 / Main motion detection script          |
| `screenSaver.py`   | 屏保或空闲检测逻辑 / Screensaver or idle detection logic |
| `requirements.txt` | Python 依赖列表 / Python dependencies               |
| `icon.png`         | 项目图标 / Project icon                             |
| `monitor.png`      | 示例或监控相关图片 / Monitoring-related image            |
| `img.png`          | 示例图片 / Sample image                             |

---

## 🚀 安装 | Installation

### 1️⃣ 克隆仓库 | Clone Repository

```bash
git clone https://github.com/tonymaa/moving-detect.git
cd moving-detect
```

---

### 2️⃣ 创建虚拟环境（推荐） | Create Virtual Environment (Recommended)

```bash
python3 -m venv venv
source venv/bin/activate   # macOS / Linux
venv\Scripts\activate      # Windows
```

---

### 3️⃣ 安装依赖 | Install Dependencies

```bash
pip install -r requirements.txt
```

依赖通常包括（示例）：

Dependencies usually include (example):

* `opencv-python`
* `numpy`

---

## ▶️ 使用方法 | Usage

### 运行运动检测脚本 | Run Motion Detection

```bash
python movingDetect.py
```

运行后程序会打开摄像头窗口，当画面中检测到运动时会进行标记或提示。

The script will open a webcam window and detect movement in the video stream. Motion areas will be highlighted or handled according to the logic in the script.

---

## 🧠 实现原理 | How It Works

* 将视频帧转换为灰度图像
* 对连续帧进行差分计算
* 使用阈值和轮廓检测判断是否存在运动

---

* Convert video frames to grayscale
* Compute differences between consecutive frames
* Detect contours based on thresholds to identify motion

---

## 🎯 应用场景 | Use Cases

* 🏠 简易家庭监控
* 💻 电脑空闲/屏保触发检测
* 📚 学习 OpenCV 与视频处理
* 🧪 运动检测算法实验

---

* 🏠 Simple home monitoring
* 💻 Idle detection or screensaver trigger
* 📚 Learning OpenCV and video processing
* 🧪 Experimenting with motion detection algorithms

---

## 🔧 可扩展方向 | Possible Extensions

* 保存检测到运动的截图或视频
* 增加邮件/消息提醒
* 调整检测灵敏度参数
* 支持视频文件输入

---

* Save snapshots or videos when motion is detected
* Add email or notification alerts
* Tune detection sensitivity
* Support video file input

---

