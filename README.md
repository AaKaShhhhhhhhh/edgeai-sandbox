# 🔐 Edge AI Metadata Stream

<p align="center">
  <img src="https://img.shields.io/badge/C%2B%2B-17-blue?style=for-the-badge&logo=c%2B%2B" alt="C++"/>
  <img src="https://img.shields.io/badge/Python-3.9-green?style=for-the-badge&logo=python" alt="Python"/>
  <img src="https://img.shields.io/badge/QEMU-aarch64-red?style=for-the-badge&logo=qemu" alt="QEMU"/>
  <img src="https://img.shields.io/badge/OpenCV-4.13-purple?style=for-the-badge&logo=opencv" alt="OpenCV"/>
  <img src="https://img.shields.io/badge/Systemd-Service-lightgrey?style=for-the-badge&logo=systemd" alt="Systemd"/>
</p>

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [System Flow](#system-flow)
- [Components](#components)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
- [Supported Classes](#supported-classes)
- [Troubleshooting](#troubleshooting)
- [Future Roadmap](#future-roadmap)

---

## 📖 Overview

**Edge AI Metadata Stream** is a production-ready, real-time object detection pipeline that offloads heavy ML inference to an **embedded aarch64 Linux device (QEMU VM)** over a TCP socket, while the **host machine** streams camera frames and renders live bounding-box overlays — achieving buttery smooth 30 FPS with minimal latency.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     EDGE AI METADATA STREAM PIPELINE                    │
└─────────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐         JPEG + Metadata         ┌───────────────────┐
  │              │  ───────────────────────────►   │                   │
  │   HOST MAC   │                                │  BUILDROOT/ARM VM  │
  │  (Python)    │ ◄───────────────────────────   │   (C++/OpenCV)    │
  │              │     Bounding Box Coordinates     │                   │
  └──────┬───────┘                                └────────┬──────────┘
         │                                                   │
         │  TCP :9999                                        │  9P VirtFS
         └───────────────────────────────────────────────────┘
                     Shared Folder: /mnt/sandbox
```

---

## ⚙️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              HOST MACHINE (macOS)                       │
│                                                                         │
│   ┌──────────────────┐    ┌──────────────────┐    ┌─────────────────┐ │
│   │                  │    │                  │    │                 │ │
│   │  view_stream.py  │───►│   TCP Socket     │◄───│  Camera / IP    │ │
│   │                  │    │   Port :9999     │    │  Webcam         │ │
│   │  • Stream Frames │    │                  │    │                 │ │
│   │  • Receive BBox  │    │                  │    └─────────────────┘ │
│   │  • Draw Overlays │    └──────────────────┘                         │
│   │                  │   Thread: phone_camera_receiver                  │
│   │                  │   Thread: buildroot_metadata_worker              │
│   └────────┬─────────┘                                                  │
│            │ 9P virtio-9p                                              │
└────────────┼────────────────────────────────────────────────────────────┘
             │ mount_tag=sandbox_share
             │
┌────────────▼────────────────────────────────────────────────────────────┐
│                    QEMU ARM64 VIRTUAL MACHINE                           │
│                                                                         │
│   ┌──────────────────────────────────────────────────────────────────┐ │
│   │                      BUILDROOT LINUX                              │ │
│   │                                                                   │ │
│   │   ┌──────────────┐         ┌─────────────────┐                   │ │
│   │   │              │         │                 │   /mnt/sandbox/   │ │
│   │   │  edge_ai_node │◄───────►│ MobileNet-SSD   │                   │ │
│   │   │   (C++17)     │  model  │   (Caffe)       │   • deploy.prot.  │ │
│   │   │              │         │                 │   • mobilenet_... │ │
│   │   │  • Receive   │         └─────────────────┘                   │ │
│   │   │    JPEG Frame│                                                  │ │
│   │   │  • DNN Forward│                                                  │ │
│   │   │  • NMS Filter │                                                  │ │
│   │   └──────┬───────┘                                                  │ │
│   │          │ Send Metadata (TCP :9999)                               │ │
│   └──────────┼────────────────────────────────────────────────────────┘ │
│              │ Config: /etc/systemd/system/edgeai.service                │
│              │ Auto-restart: systemd daemon                              │
└──────────────┼────────────────────────────────────────────────────────────┘
               │
               ▼
      QEMU Hardware Emulation
      • CPU: cortex-a53 (x2 cores)
      • RAM: 2 GB
      • Network: user-mode
      • Platform: virt + 9p shared FS
```

---

## 🔁 System Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  LIVE PIPELINE SEQUENCE                                                │
└─────────────────────────────────────────────────────────────────────────┘

 STEP 1          STEP 2          STEP 3         STEP 4        STEP 5
  ────           ────           ────           ─────         ─────
  Camera      Resize/JPEG      TCP Send       C++ Receive   DNN Inference
  (IP Feed)      300x300       over :9999     from Host     (MobileNet)
       │               │             │             │              │
       ▼               ▼             ▼             ▼              ▼
    [Webcam]     [cv::imencode]  [sendall()]   [recv loop]  [blobFromImage]
                  quality=50     4B header     stream buf    [net.forward()]

 STEP 6          STEP 7          STEP 8         STEP 9        STEP 10
  ────           ────           ────           ─────         ─────
  Parse Boxes   TCP Return       Python        Draw Green      Display to
  (class,       4B+payload      Recv &         Rectangles      Screen
  conf, coords)  to Host        Parse JSON     + Labels       (1280x720)
       │               │             │             │              │
       ▼               ▼             ▼             ▼              ▼
  [std::to_string] [htonl/      [struct.     [cv2.rect]    [cv2.imshow]
  format pipe]      send()]      unpack()]    [cv2.putText]  30 FPS


  DETAILED PACKET PROTOCOL
  ══════════════════════════

  ┌───────────────────     Host → Edge     ┌──────────────────┐
  │  [4B: N][N bytes: JPEG frame]──────►    │                  │
  │                          :9999          │   edge_ai_node   │
  └─────────────────────────────────       │                  │
                                           └────────┬─────────┘
                                                    │
  ┌───────────────────     Edge → Host     ┌────────▼─────────┐
  │  [4B: L][L bytes: "c,x,y,z..."]         │                  │
  │ ◄──────────────────────      :9999      │   view_stream.py │
  └─────────────────────────────────       └──────────────────┘

  Protocol: class_id, confidence, x1, y1, x2, y2 separated by commas
  Example: "16,0.92,120,200,340,480|6,0.87,50,80,200,300"
```

---

## 🧩 Components

| Component | File | Language | Role |
|-----------|------|----------|------|
| **Edge Node** | `main.cpp` | C++17 | Object detection inference on embedded device |
| **Stream Server** | `view_stream.py` | Python 3.9 | Camera receiver + metadata renderer |
| **VM Launcher** | `run_vm.sh` | Bash | QEMU VM boot script (aarch64) |
| **Systemd Unit** | `edgeai.service` | INI | Auto-start & crash recovery service |

---

## 🛠 Tech Stack

```
┌──────────────┬──────────────────────────────────────────────────┐
│ Layer        │ Technology                                       │
├──────────────┼──────────────────────────────────────────────────┤
│ Inference    │ OpenCV DNN + MobileNet-SSD (Caffe)               │
│ Edge Runtime │ Custom Buildroot Linux (aarch64)                 │
│ VM           │ QEMU System Emulation (virt machine)             │
│ Host         │ macOS + Python 3.9 + OpenCV                      │
│ Communication│ Raw TCP Sockets (custom protocol)                 │
│ Display      │ OpenCV HighGUI (cv::imshow)                      │
│ Daemon/Init  │ Systemd (auto-restart on failure)                │
│ Build        │ GCC Cross-compiler (aarch64-linux-g++)          │
└──────────────┴──────────────────────────────────────────────────┘
```

---

## 📦 Prerequisites

```
   Host Machine
   ────────────
   • macOS / Linux
   • Python 3.9+
   • pip (for OpenCV, numpy, threading)
   • Terminal, CV2, Struct

   Edge VM Toolchain
   ─────────────────
   • aarch64-buildroot-linux-gnu_sdk-buildroot (pre-built SDK)
   • QEMU (qemu-system-aarch64)
   • Image (Linux kernel)
   • rootfs.ext4 (Buildroot root filesystem)

   Pre-trained Models
   ──────────────────
   • deploy.prototxt  (SSD architecture config)
   • mobilenet_iter_73000.caffemodel  (trained weights)
```

---

## 🚀 Setup & Installation

### Option A: Native Linux / recommended

```bash
# 1. Clone the repository
git clone https://github.com/your-username/edgeai-metadata-stream.git
cd edgeai-metadata-stream

# 2. Create Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install Python dependencies
pip install opencv-python numpy

# 4. Cross-compile C++ binary (requires aarch64 SDK)
export PATH=$PATH:/path/to/aarch64-buildroot-linux-gnu_sdk-buildroot
make

# 5. Copy binary + shared libs into VM rootfs
# (libopencv_*.so*, libprotobuf.so*)
```

### Option B: QEMU VM Only

```bash
# 1. Launch the ARM64 virtual machine
bash run_vm.sh

# 2. Inside the VM, deploy the binary to /mnt/sandbox/
#    and shared libs to /usr/lib/

# 3. Enable and start the systemd service
sudo systemctl daemon-reload
sudo systemctl enable edgeai.service
sudo systemctl start edgeai.service

# 4. Back on host — start stream server
python3 view_stream.py
```

---

## 🎮 Usage

### Start the Pipeline

```bash
# Terminal 1 — Start the VM
bash run_vm.sh

# Terminal 2 — Start the stream server (on host)
source .venv/bin/activate
python3 view_stream.py

# Result: A 1280×720 window opens showing live camera feed + green bounding boxes
```

### Rebuild After Code Changes

```bash
make clean
make
# Re-deploy binary to VM /mnt/sandbox/edge_ai_node
sudo systemctl restart edgeai.service   # inside VM
```

### Enable on Virtual Machine Boot

```bash
sudo systemctl enable edgeai.service
```

---

## 📂 Project Structure

```
edgeai-sandbox/
│
├── 📁 aarch64-buildroot-linux-gnu_sdk-buildroot/   # Cross-compiler SDK
│
├── 🔧 Makefile                                      # C++ build script
│
├── 🧠 main.cpp                                      # Edge inference node (C++17)
│
├── 🐍 view_stream.py                                # Host stream server + renderer
│
├── 🤖 run_vm.sh                                     # QEMU ARM64 VM launcher
│
├── 🔧 edgeai.service                                # Systemd service unit
│
├── 🧠 deploy.prototxt                               # SSD architecture definition
├── 🧠 mobilenet_iter_73000.caffemodel               # Pre-trained weights
│
├── 🔮 yolov4-tiny.cfg                               # YOLOv4-tiny config (future)
├── 🔮 yolov4-tiny.weights                           # YOLOv4-tiny weights  (future)
│
├── 🏷️ coco.names                                    # 80-class COCO label map
│
├── 📁 .venv/                                        # Python virtual environment
└── 📄 .gitignore                                    # Ignores cache, binaries, etc.
```

---

## 🔬 How It Works

### Host: `view_stream.py`

```
  Thread 1 — Camera Receiver
  ───────────────────────────
  1. Connects to IP webcam stream (http://192.168.29.78:8080/video)
  2. Reads frames continuously in background (daemon thread)
  3. Stores latest frame in thread-safe buffer

  Thread 2 — Buildroot Metadata Worker
  ─────────────────────────────────────
  1. Resizes frame to 300×300 (SSD input size)
  2. JPEG-encodes at quality=50
  3. Prepends 4-byte big-endian length header
  4. Sends over TCP socket to VM (:9999)
  5. Receives 4-byte metadata response header
  6. Reads payload: "class_id,conf,x1,y1,x2,y2|..."
  7. Parses bounding boxes into global list

  Main Thread — Display Loop
  ──────────────────────────
  1. Copies latest frame (thread-safe)
  2. Re-scales bounding boxes from 300×300 → full resolution
  3. Draws green rectangles + class labels
  4. Renders "PRODUCTION EDGE METADATA STREAM - 30 FPS" watermark
  5. Shows in 1280×720 OpenCV window
```

### Edge: `main.cpp`

```
  Main Loop
  ─────────
  1. Loads MobileNet-SSD model (Caffe) from shared folder
     • /mnt/sandbox/deploy.prototxt
     • /mnt/sandbox/mobilenet_iter_73000.caffemodel

  2. Connects TCP socket to host (10.0.2.2:9999) with retry loop

  3. Frame Reception Loop
     a. Reads 4-byte message length prefix (big-endian)
     b. Reads N bytes of JPEG frame
     c. Decodes JPEG → cv::Mat using imdecode

  4. Object Detection
     a. blobFromImage: 300×300, BGR→RGB, mean subtraction
     b. net.setInput(blob)
     c. net.forward() → raw detections tensor

  5. Post-processing
     a. Iterate over detections (rows = max detections)
     b. Filter: confidence > 0.5 (50% threshold)
     c. Extract: class_id, x1, y1, x2, y2 (normalized 0-1)

  6. Metadata Encoding
     a. Format: "class_id,conf,x1,y1,x2,y2|"
     b. Send length prefix (htonl, 4 bytes)
     c. Send payload via TCP
```

---

## 🏷️ Supported Classes

```
┌──────┬─────────┬────────┬─────────────┬─────────────┬──────────────────────┐
│ #    │ Name    │   #    │ Name        │   #         │ Name                 │
├──────┼─────────┼────────┼─────────────┼─────────────┼──────────────────────┤
│  0   │ background │  7  │ car          │  14         │ horse                │
│  1   │ aeroplane  │  8  │ cat          │  15         │ motorbike            │
│  2   │ bicycle    │  9  │ chair        │  16         │ person               │
│  3   │ bird       │ 10  │ cow          │  17         │ pottedplant          │
│  4   │ boat       │ 11  │ diningtable  │  18         │ sheep                │
│  5   │ bottle     │ 12  │ dog          │  19         │ sofa                 │
│  6   │ bus        │ 13  │ horse        │  20         │ train / tvmonitor    │
└──────┴─────────┴──────┴─────────────┴─────────────┴──────────────────────┘
```

---

## 🐛 Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `QEMU boot hangs` | Rootfs not found | Verify `rootfs.ext4` path exists |
| `Camera stream 404` | Wrong IP in `view_stream.py` | Update `192.168.29.78` to IP Webcam address |
| `TCP connection refused` | VM network not started | Check QEMU `-netdev user` flag |
| `Cannot open shared lib` | Missing `.so` files in VM | Copy `libopencv_*.so*` to VM `/usr/lib/` |
| `imshow window black` | Slow decode / high latency | Reduce JPEG quality to 30–40 |
| `Service exits on boot` | Missing `mnt-sandbox.mount` | Add `Requires=mnt-sandbox.mount` |

---

## 🗺️ Future Roadmap

```
  Phase 0:  ✔  Real-time frame streaming (TCP)
  Phase 1:  ✔  Caffe MobileNet-SSD inference on ARM64
  Phase 2:  ✔  Bounding box overlay on host
  Phase 3:  🔄  Replace MobileNet with YOLOv4-tiny (faster, COCO 80-class)
  Phase 4:  📋  Multi-person tracking + trajectory drawing
  Phase 5:  📋  REST API for metadata history querying
  Phase 6:  📋  TinyML TFLite model on Cortex-A53 (NPU offload)
  Phase 7:  📋  Kubernetes edge node deployment
```

---

## 📄 License

MIT License

---

<p align="center">
  <b>Built with ❤️ by the Edge AI Team</b>
</p>
