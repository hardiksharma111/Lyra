#!/data/data/com.termux/files/usr/bin/bash
# Lyra auto-start on boot
# This file lives at: ~/.termux/boot/start_lyra.sh

# Wait for system to settle
sleep 10

# Keep screen on and acquire wake lock so Android doesn't kill Termux
termux-wake-lock

# Start Lyra silently in background
cd ~/Lyra
python main.py >> ~/lyra_boot.log 2>&1