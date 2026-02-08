import os
import math
import cv2
from flask import Flask, render_template, Response, request, redirect
from ultralytics import YOLO

app = Flask(__name__)

# --- CONFIGURATION ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
current_video_path = None

# --- LOAD AI MODEL ---
model = YOLO("yolov8n.pt")  # YOLOv8 Nano for speed

classNames = [
    "person","bicycle","car","motorbike","aeroplane","bus","train","truck","boat",
    "traffic light","fire hydrant","stop sign","parking meter","bench","bird","cat",
    "dog","horse","sheep","cow","elephant","bear","zebra","giraffe","backpack","umbrella",
    "handbag","tie","suitcase","frisbee","skis","snowboard","sports ball","kite",
    "baseball bat","baseball glove","skateboard","surfboard","tennis racket","bottle",
    "wine glass","cup","fork","knife","spoon","bowl","banana","apple","sandwich","orange",
    "broccoli","carrot","hot dog","pizza","donut","cake","chair","sofa","pottedplant",
    "bed","diningtable","toilet","tvmonitor","laptop","mouse","remote","keyboard",
    "cell phone","microwave","oven","toaster","sink","refrigerator","book","clock",
    "vase","scissors","teddy bear","hair drier","toothbrush"
]

def generate_frames():
    global current_video_path

    if not current_video_path or not os.path.exists(current_video_path):
        return

    cap = cv2.VideoCapture(current_video_path)

    while cap.isOpened():
        success, img = cap.read()
        if not success:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        results = model(img, stream=True)

        car_count = bus_count = truck_count = bike_count = 0

        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = round(float(box.conf[0]), 2)
                cls = int(box.cls[0])
                currentClass = classNames[cls]

                if currentClass in ["car", "bus", "truck", "motorbike"] and conf > 0.3:
                    if currentClass == "bus":
                        color = (0, 165, 255)
                    elif currentClass == "truck":
                        color = (255, 0, 255)
                    elif currentClass == "motorbike":
                        color = (0, 255, 255)
                    else:
                        color = (255, 0, 0)

                    cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(
                        img,
                        f"{currentClass} {conf}",
                        (x1, max(20, y1)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (255, 255, 255),
                        1
                    )

                    if currentClass == "car":
                        car_count += 1
                    elif currentClass == "bus":
                        bus_count += 1
                    elif currentClass == "truck":
                        truck_count += 1
                    elif currentClass == "motorbike":
                        bike_count += 1

        # --- Density Logic ---
        density_score = (
            car_count * 1.0 +
            bus_count * 2.5 +
            truck_count * 2.0 +
            bike_count * 0.5
        )

        if density_score > 20:
            sig_color, text = (0, 255, 0), "GREEN LIGHT"
        elif density_score > 10:
            sig_color, text = (0, 255, 255), "YELLOW LIGHT"
        else:
            sig_color, text = (0, 0, 255), "RED LIGHT"

        # --- OVERLAY UI (MORE UPWARDS) ---
        cv2.putText(
            img,
            f"SIGNAL: {text}",
            (40, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            sig_color,
            3
        )

        cv2.putText(
            img,
            f"Density Score: {density_score:.1f}",
            (40, 55),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        ret, buffer = cv2.imencode(".jpg", img)
        frame = buffer.tobytes()

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
        )

    cap.release()

# --- ROUTES ---

@app.route("/", methods=["GET", "POST"])
def index():
    global current_video_path

    if request.method == "POST":
        if "video" not in request.files:
            return redirect(request.url)

        file = request.files["video"]
        if file.filename == "":
            return redirect(request.url)

        filepath = os.path.join(app.config["UPLOAD_FOLDER"], "input_video.mp4")
        file.save(filepath)
        current_video_path = filepath

        return render_template("demo.html", video_uploaded=True)

    return render_template("demo.html", video_uploaded=False)

@app.route("/video_feed")
def video_feed():
    if not current_video_path:
        return "No video uploaded", 400

    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

@app.route("/details.html")
def details():
    return render_template("details.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
