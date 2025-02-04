# NurdViewer
A high-performance self-hosted remote desktop system using WebRTC.

## Features
- ✅ Low-latency screen sharing
- ✅ WebRTC peer-to-peer connections
- ✅ Secure, self-hosted signaling server

## Installation
Clone the repository and install dependencies:

```bash
git clone https://github.com/NurdRage/NurdViewer.git
cd NurdViewer
pip install -r requirements.txt
```

## Usage
1. Start the signaling server:
   ```bash
   python3 signaling_server.py
   ```

2. Run the **sender** on Machine A:
   ```bash
   python3 sender.py --signaling ws://SIGNALING_SERVER_IP:8000 --room testroom
   ```

3. Run the **receiver** on Machine B:
   ```bash
   python3 receiver.py --signaling ws://SIGNALING_SERVER_IP:8000 --room testroom
   ```

## Contributing
Feel free to open issues and pull requests!
