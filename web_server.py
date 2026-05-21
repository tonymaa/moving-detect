import os
import io
import time
import json
import threading
import queue
from datetime import datetime
from flask import Flask, Response, render_template, jsonify, request, send_from_directory
import cv2
from PIL import Image

app_instance = None
_web_app = None


def create_web_app(detect_app):
    global _web_app
    _web_app = Flask(__name__,
                     template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
                     static_folder=os.path.join(os.path.dirname(__file__), 'static'))
    _web_app.detect_app = detect_app
    _web_app.notification_queues = []

    @_web_app.route('/')
    def index():
        return render_template('index.html')

    @_web_app.route('/api/stream')
    def stream():
        def generate():
            while True:
                jpeg = _web_app.detect_app.get_frame_jpeg()
                if jpeg:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n')
                time.sleep(0.1)
        return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

    @_web_app.route('/api/status')
    def status():
        return jsonify({
            'detecting': _web_app.detect_app.enable_detect,
            'camera_index': _web_app.detect_app._camera_idx if hasattr(_web_app.detect_app, '_camera_idx') else 0
        })

    @_web_app.route('/api/toggle_detect', methods=['POST'])
    def toggle_detect():
        _web_app.detect_app.enable_detect = not _web_app.detect_app.enable_detect
        return jsonify({'detecting': _web_app.detect_app.enable_detect})

    @_web_app.route('/api/set_detect', methods=['POST'])
    def set_detect():
        data = request.get_json(force=True)
        _web_app.detect_app.enable_detect = bool(data.get('enabled', True))
        return jsonify({'detecting': _web_app.detect_app.enable_detect})

    @_web_app.route('/api/cameras')
    def cameras():
        from movingDetect import get_cached_cameras
        return jsonify(get_cached_cameras())

    @_web_app.route('/api/videos')
    def videos():
        video_dir = _web_app.detect_app.video_dir
        files = []
        if os.path.exists(video_dir):
            for f in sorted(os.listdir(video_dir), reverse=True):
                if f.endswith('.avi') or f.endswith('.mp4'):
                    path = os.path.join(video_dir, f)
                    size_mb = os.path.getsize(path) / (1024 * 1024)
                    # parse datetime from filename: YYYYMMDD_HHMMSS.avi
                    name = os.path.splitext(f)[0]
                    try:
                        dt = datetime.strptime(name, "%Y%m%d_%H%M%S")
                        display = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        display = name
                    files.append({'filename': f, 'display': display, 'size_mb': round(size_mb, 2)})
        return jsonify(files)

    @_web_app.route('/api/video/<filename>')
    def video_file(filename):
        return send_from_directory(_web_app.detect_app.video_dir, filename)

    @_web_app.route('/api/play/<filename>')
    def play_video(filename):
        def generate():
            path = os.path.join(_web_app.detect_app.video_dir, filename)
            cap = cv2.VideoCapture(path)
            fps = cap.get(cv2.CAP_PROP_FPS) or 20.0
            delay = 1.0 / fps
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                rgb = frame[:, :, ::-1]
                img = Image.fromarray(rgb)
                buf = io.BytesIO()
                img.save(buf, format='JPEG', quality=70)
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buf.getvalue() + b'\r\n')
                time.sleep(delay)
            cap.release()
        return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

    @_web_app.route('/api/notifications')
    def notifications():
        q = queue.Queue(maxsize=50)
        _web_app.notification_queues.append(q)

        def generate():
            try:
                while True:
                    try:
                        data = q.get(timeout=30)
                        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                    except queue.Empty:
                        yield f": keepalive\n\n"
            except GeneratorExit:
                pass
            finally:
                if q in _web_app.notification_queues:
                    _web_app.notification_queues.remove(q)

        return Response(generate(), mimetype='text/event-stream',
                        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    return _web_app


def notify_web(timestamp, change_pct):
    if _web_app is None:
        return
    data = {'time': timestamp, 'change': round(change_pct, 2)}
    dead = []
    for q in _web_app.notification_queues:
        try:
            q.put_nowait(data)
        except queue.Full:
            dead.append(q)
    for q in dead:
        _web_app.notification_queues.remove(q)


def start_server(detect_app, port=9999):
    global app_instance
    app_instance = create_web_app(detect_app)
    detect_app.on_notification(notify_web)
    app_instance.run(host='0.0.0.0', port=port, threaded=True)


def start_server_thread(detect_app, port=9999):
    t = threading.Thread(target=start_server, args=(detect_app, port), daemon=True)
    t.start()
    return t
