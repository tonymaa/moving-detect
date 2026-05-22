import os
import io
import time
import json
import hashlib
import threading
import queue
from datetime import datetime
from flask import Flask, Response, render_template, jsonify, request, send_from_directory, session, redirect
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

    def _get_access_keys():
        from movingDetect import load_config
        return load_config().get('access_keys', [])

    def _is_auth_enabled():
        return bool(_get_access_keys())

    @_web_app.before_request
    def _check_auth():
        if not _is_auth_enabled():
            return None
        if request.path in ('/login', '/api/login'):
            return None
        if session.get('authenticated'):
            return None
        if request.path.startswith('/api/'):
            return jsonify({'error': 'unauthorized'}), 401
        return redirect('/login')

    # Set secret_key for session signing
    keys = _get_access_keys()
    _web_app.secret_key = hashlib.sha256(keys[0].encode()).hexdigest() if keys else os.urandom(24).hex()

    @_web_app.route('/')
    def index():
        return render_template('index.html')

    @_web_app.route('/login')
    def login_page():
        if not _is_auth_enabled() or session.get('authenticated'):
            return redirect('/')
        return render_template('login.html')

    @_web_app.route('/api/login', methods=['POST'])
    def login():
        data = request.get_json(force=True)
        key = data.get('key', '')
        if key in _get_access_keys():
            session['authenticated'] = True
            return jsonify({'status': 'ok'})
        return jsonify({'status': 'error', 'message': '密钥错误'}), 403

    @_web_app.route('/api/logout', methods=['POST'])
    def logout():
        session.pop('authenticated', None)
        return jsonify({'status': 'ok'})

    @_web_app.route('/api/auth_status')
    def auth_status():
        return jsonify({'auth_enabled': _is_auth_enabled(), 'authenticated': session.get('authenticated', False)})

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
        ls = getattr(_web_app.detect_app, '_lock_screen', None)
        mode = ls.mode if ls else None
        from movingDetect import get_recording_duration, get_show_face_boxes
        return jsonify({
            'detecting': _web_app.detect_app.enable_detect,
            'camera_index': _web_app.detect_app._camera_idx if hasattr(_web_app.detect_app, '_camera_idx') else 0,
            'mode': mode,
            'recording_duration': get_recording_duration(),
            'show_face_boxes': get_show_face_boxes()
        })

    @_web_app.route('/api/set_recording_duration', methods=['POST'])
    def set_recording_duration():
        from movingDetect import save_recording_duration
        data = request.get_json(force=True)
        duration = int(data.get('duration', 15))
        save_recording_duration(duration)
        return jsonify({'recording_duration': duration})

    @_web_app.route('/api/set_show_face_boxes', methods=['POST'])
    def set_show_face_boxes():
        from movingDetect import save_show_face_boxes
        data = request.get_json(force=True)
        enabled = bool(data.get('enabled', False))
        save_show_face_boxes(enabled)
        return jsonify({'show_face_boxes': enabled})

    @_web_app.route('/api/toggle_detect', methods=['POST'])
    def toggle_detect():
        _web_app.detect_app.enable_detect = not _web_app.detect_app.enable_detect
        return jsonify({'detecting': _web_app.detect_app.enable_detect})

    @_web_app.route('/api/set_detect', methods=['POST'])
    def set_detect():
        data = request.get_json(force=True)
        _web_app.detect_app.enable_detect = bool(data.get('enabled', True))
        return jsonify({'detecting': _web_app.detect_app.enable_detect})

    @_web_app.route('/api/lock', methods=['POST'])
    def lock():
        ls = getattr(_web_app.detect_app, '_lock_screen', None)
        if ls:
            ls.master.after(0, ls.lock)
            return jsonify({'status': 'ok'})
        return jsonify({'status': 'error', 'message': '桌面端未运行'}), 400

    @_web_app.route('/api/dark_mode', methods=['POST'])
    def dark_mode():
        ls = getattr(_web_app.detect_app, '_lock_screen', None)
        if ls:
            ls.master.after(0, ls.dark_mode)
            return jsonify({'status': 'ok'})
        return jsonify({'status': 'error', 'message': '桌面端未运行'}), 400

    @_web_app.route('/api/exit_lock', methods=['POST'])
    def exit_lock():
        ls = getattr(_web_app.detect_app, '_lock_screen', None)
        if ls:
            ls.master.after(0, ls.exit_fullscreen)
            return jsonify({'status': 'ok'})
        return jsonify({'status': 'error', 'message': '桌面端未运行'}), 400

    @_web_app.route('/api/persons')
    def persons():
        import face_db
        return jsonify(face_db.get_all_persons())

    @_web_app.route('/api/persons/<int:person_id>', methods=['PUT'])
    def update_person(person_id):
        import face_db
        data = request.get_json(force=True)
        face_db.update_person_name(person_id, data.get('name', ''))
        return jsonify({'status': 'ok'})

    @_web_app.route('/api/persons/<int:person_id>', methods=['DELETE'])
    def delete_person(person_id):
        import face_db
        face_db.delete_person(person_id)
        return jsonify({'status': 'ok'})

    @_web_app.route('/api/persons/<int:person_id>/photo')
    def person_photo(person_id):
        import face_db
        person = face_db.get_person(person_id)
        if person and person['photo_path'] and os.path.exists(person['photo_path']):
            return send_from_directory(os.path.dirname(person['photo_path']),
                                       os.path.basename(person['photo_path']))
        return '', 404

    @_web_app.route('/api/persons/<int:person_id>/videos')
    def person_videos(person_id):
        import face_db
        filenames = face_db.get_person_videos(person_id)
        result = []
        for f in filenames:
            name = os.path.splitext(f)[0]
            try:
                dt = datetime.strptime(name, "%Y%m%d_%H%M%S")
                display = dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                display = name
            has_thumb = os.path.exists(os.path.join(_web_app.detect_app.video_dir, name + '.jpg'))
            result.append({'filename': f, 'display': display, 'thumb': has_thumb})
        return jsonify(result)

    @_web_app.route('/api/cameras')
    def cameras():
        from movingDetect import get_cached_cameras
        return jsonify(get_cached_cameras())

    @_web_app.route('/api/videos')
    def videos():
        import face_db
        video_dir = _web_app.detect_app.video_dir
        videos_faces = face_db.get_videos_with_faces()
        files = []
        if os.path.exists(video_dir):
            for f in sorted(os.listdir(video_dir), reverse=True):
                if f.endswith('.avi') or f.endswith('.mp4'):
                    path = os.path.join(video_dir, f)
                    size_mb = os.path.getsize(path) / (1024 * 1024)
                    name = os.path.splitext(f)[0]
                    has_thumb = os.path.exists(os.path.join(video_dir, name + '.jpg'))
                    try:
                        dt = datetime.strptime(name, "%Y%m%d_%H%M%S")
                        display = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        display = name
                    faces = videos_faces.get(f, [])
                    has_unnamed = any(p['name'] is None for p in faces)
                    named = [p['name'] for p in faces if p['name']]
                    if not faces:
                        level = '摄像头移动'
                        level_type = 'motion'
                    elif has_unnamed:
                        level = '有陌生人走动'
                        level_type = 'stranger'
                    else:
                        level = '熟人: ' + ', '.join(named)
                        level_type = 'known'
                    files.append({
                        'filename': f, 'display': display, 'size_mb': round(size_mb, 2),
                        'thumb': has_thumb, 'faces': faces, 'level': level, 'level_type': level_type
                    })
        return jsonify(files)

    @_web_app.route('/api/thumb/<filename>')
    def thumb_file(filename):
        return send_from_directory(_web_app.detect_app.video_dir, filename)

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
    data = {'type': 'detect', 'time': timestamp, 'change': round(change_pct, 2)}
    dead = []
    for q in _web_app.notification_queues:
        try:
            q.put_nowait(data)
        except queue.Full:
            dead.append(q)
    for q in dead:
        _web_app.notification_queues.remove(q)


def notify_mode_change(mode):
    if _web_app is None:
        return
    data = {'type': 'mode', 'mode': mode}
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
