import socket
import cv2
import threading
import struct
import numpy as np

# Official 21-Class MobileNet-SSD Labels Dataset Mapping array
CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat",
           "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
           "dog", "horse", "motorbike", "person", "pottedplant", "sheep",
           "sofa", "train", "tvmonitor"]

latest_phone_frame = None
active_boxes = []
frame_lock = threading.Lock()
box_lock = threading.Lock()

def phone_camera_receiver():
    global latest_phone_frame
    cap = cv2.VideoCapture("http://192.168.29.78:8080/video")
    while True:
        ret, frame = cap.read()
        if ret and frame is not None:
            with frame_lock:
                latest_phone_frame = frame

def buildroot_metadata_worker(conn):
    global active_boxes, latest_phone_frame
    while True:
        with frame_lock:
            if latest_phone_frame is not None:
                small_frame = cv2.resize(latest_phone_frame, (300, 300))
            else:
                small_frame = None

        if small_frame is not None:
            _, img_encoded = cv2.imencode('.jpg', small_frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
            data_bytes = img_encoded.tobytes()
            
            try:
                conn.sendall(struct.pack('!I', len(data_bytes)) + data_bytes)

                header_bytes = b''
                while len(header_bytes) < 4:
                    chunk = conn.recv(4 - len(header_bytes))
                    if not chunk: break
                    header_bytes += chunk
                
                if len(header_bytes) == 4:
                    msg_size = struct.unpack('!I', header_bytes)[0]
                    payload_bytes = b''
                    while len(payload_bytes) < msg_size:
                        chunk = conn.recv(msg_size - len(payload_bytes))
                        if not chunk: break
                        payload_bytes += chunk
                    
                    payload = payload_bytes.decode('utf-8')
                    
                    new_boxes = []
                    if payload != "none":
                        for box in payload.split('|'):
                            if box:
                                data_tokens = [float(num) for num in box.split(',')]
                                if len(data_tokens) == 6:
                                    new_boxes.append({
                                        "class_id": int(data_tokens[0]),
                                        "confidence": data_tokens[1],
                                        "coords": data_tokens[2:]
                                    })
                    
                    with box_lock:
                        active_boxes = new_boxes

            except socket.error:
                break

# Initialize Connection matrix
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('0.0.0.0', 9999))
server.listen(1)
print("[MAC] Waiting for Buildroot connection...")
conn, addr = server.accept()

threading.Thread(target=phone_camera_receiver, daemon=True).start()
threading.Thread(target=buildroot_metadata_worker, args=(conn,), daemon=True).start()

while True:
    with frame_lock:
        display_frame = latest_phone_frame.copy() if latest_phone_frame is not None else None

    if display_frame is not None:
        h, w, _ = display_frame.shape

        with box_lock:
            current_boxes_snapshot = list(active_boxes)

        for obj in current_boxes_snapshot:
            # Re-scale bounding metrics to fit full screen size
            x1 = int(obj["coords"][0] * w)
            y1 = int(obj["coords"][1] * h)
            x2 = int(obj["coords"][2] * w)
            y2 = int(obj["coords"][3] * h)
            
            # Fetch human-readable class text name
            class_name = CLASSES[obj["class_id"]] if obj["class_id"] < len(CLASSES) else "Unknown"
            label = f"{class_name.upper()} ({int(obj['confidence'] * 100)}%)"
            
            # Draw green bounding target box
            cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
            
            # Render background label banner safely above coordinates box anchor line
            cv2.rectangle(display_frame, (x1, y1 - 35), (x1 + len(label)*15, y1), (0, 255, 0), -1)
            cv2.putText(display_frame, label, (x1 + 5, y1 - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

        cv2.putText(display_frame, "PRODUCTION EDGE METADATA STREAM - 30 FPS", (30, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
        
        cv2.imshow("Buttery Smooth Edge AI Window", cv2.resize(display_frame, (1280, 720)))

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cv2.destroyAllWindows()
conn.close()
server.close()