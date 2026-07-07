#!/bin/bash

KERNEL="./Image"
ROOTFS="./rootfs.ext4"
SHARED_DIR="$(pwd)"

echo "========================================================"
echo " Launching Custom OS in High-Speed Host Gateway Mode    "
echo "========================================================"

qemu-system-aarch64 \
    -M virt \
    -cpu cortex-a53 \
    -smp 2 \
    -m 2G \
    -kernel "$KERNEL" \
    -hda "$ROOTFS" \
    -append "root=/dev/vda console=ttyAMA0 mem=2G init=/usr/lib/systemd/systemd" \
    -nographic \
    -netdev user,id=net0,hostfwd=tcp::8080-:8080 -device virtio-net-pci,netdev=net0 \
    -fsdev local,id=sandbox_dev,path="$SHARED_DIR",security_model=none \
    -device virtio-9p-device,fsdev=sandbox_dev,mount_tag=sandbox_share