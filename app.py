# app.py
from flask import Flask, render_template, request, redirect, url_for, Response, send_from_directory
import os
import cv2
import threading
import time

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Shared state (simple)
video_path = {"path": None}
lock = threading.Lock()

@app.route('/')
def index():
    return redirect(url_for('demo'))

@app.route('/demo', methods=['GET', 'POST'])
def demo():
    if request.method == 'POST':
        file = request.files.get('video')
        if not file:
            return "No file uploaded", 400
        filename = file.filename
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(save_path)
        with lock:
            video_path['path'] = save_path
        # After POST, redirect to GET so template sees video_uploaded True
        return redirect(url_for('demo'))

    # GET
    with lock:
        uploaded = bool(video_path['path'])
    return render_template('demo.html', video_uploaded=uploaded)

def generate_frames():
    """Generator that yields frames as multipart/x-mixed-replace for <img> streaming."""
    while True:
        with lock:
            path = video_path['path']
        if not path:
            time.sleep(0.1)
            continue

        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            # cannot open file; yield a placeholder image (one-time) and break to avoid tight loop
            print("ERROR: cv2 can't open", path)
            blank = 255 * np.ones((480, 640, 3), dtype=np.uint8)
            _, jpeg = cv2.imencode('.jpg', blank)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
            break

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break  # video ended; break back to top to re-open or stop
            # --- PLACEHOLDER for YOLO inference ---
            # Replace below lines with your YOLO inference and drawing code.
            h, w = frame.shape[:2]
            # draw fake detection for visibility
            cv2.rectangle(frame, (int(w*0.2), int(h*0.3)), (int(w*0.6), int(h*0.7)), (0,255,0), 2)
            cv2.putText(frame, "vehicle:0.78", (int(w*0.2), int(h*0.3)-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)

            # encode as jpeg
            ret2, jpeg = cv2.imencode('.jpg', frame)
            if not ret2:
                continue

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
            time.sleep(0.03)  # ~30 FPS throttle

        cap.release()
        # loop to reopen file (if you want continuous replay), or break to stop streaming
        # break
        time.sleep(0.5)

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    # debug on port 5000; make sure you access http://127.0.0.1:5000/demo
    app.run(host='0.0.0.0', port=5000, debug=True)
