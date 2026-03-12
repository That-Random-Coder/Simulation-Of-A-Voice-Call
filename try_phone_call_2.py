import sys
import math
import time
import random
import socket
import struct
import threading
import base64
import logging
import numpy as np
from scipy import signal as scipy_signal
from collections import deque

import sounddevice as sd

from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QSlider, QComboBox, QLineEdit,
    QGroupBox, QFrame, QSplitter, QProgressBar, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QColor, QPalette, QSurfaceFormat

from OpenGL.GL import *
from OpenGL.GLU import *
from PyQt5.QtOpenGL import QGLWidget

logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('engineio').setLevel(logging.ERROR)
logging.getLogger('socketio').setLevel(logging.ERROR)

CHUNK = 1024
RATE = 16000
CHANNELS = 1
WEB_PORT = 8080


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


MOBILE_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>Voice Call</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;overflow:hidden;font-family:'Segoe UI',system-ui,sans-serif}
body{background:linear-gradient(135deg,#060a14 0%,#0a1025 50%,#060a14 100%);
color:#c0dde8;display:flex;flex-direction:column;align-items:center;justify-content:center}
.card{background:rgba(10,18,35,0.85);border:1px solid rgba(0,180,255,0.2);
border-radius:20px;padding:30px 25px;width:90%;max-width:400px;
backdrop-filter:blur(20px);box-shadow:0 0 40px rgba(0,150,255,0.08)}
.title{text-align:center;font-size:15px;font-weight:700;color:#00ffaa;
letter-spacing:2px;margin-bottom:6px}
.subtitle{text-align:center;font-size:11px;color:#446688;margin-bottom:24px}
.status{text-align:center;font-size:13px;padding:10px;border-radius:10px;
background:rgba(0,0,0,0.3);margin-bottom:20px;font-weight:600;color:#556688;
transition:all 0.3s}
.status.active{color:#00ff66;box-shadow:0 0 20px rgba(0,255,100,0.1)}
.status.error{color:#ff4444}
.vis{height:100px;border-radius:12px;background:rgba(0,0,0,0.4);
border:1px solid rgba(0,180,255,0.1);margin-bottom:20px;position:relative;overflow:hidden}
.vis canvas{width:100%;height:100%}
.meter{display:flex;gap:12px;margin-bottom:20px}
.meter-box{flex:1;background:rgba(0,0,0,0.3);border-radius:10px;padding:10px;
border:1px solid rgba(0,180,255,0.1)}
.meter-label{font-size:9px;color:#446688;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px}
.meter-bar{height:6px;border-radius:3px;background:rgba(255,255,255,0.05);overflow:hidden}
.meter-fill{height:100%;border-radius:3px;transition:width 0.1s;width:0%}
.meter-fill.in{background:linear-gradient(90deg,#00ff88,#00ccff)}
.meter-fill.out{background:linear-gradient(90deg,#ff6644,#ffaa00)}
.meter-val{font-size:18px;font-weight:700;color:#00ccff;margin-top:4px}
btn{display:block;width:100%;padding:16px;border:none;border-radius:12px;
font-size:15px;font-weight:700;letter-spacing:1px;cursor:pointer;
transition:all 0.2s;font-family:inherit}
.btn-call{background:linear-gradient(135deg,#004830,#006644);
color:#00ff88;border:2px solid #00ff88}
.btn-call:hover{box-shadow:0 0 30px rgba(0,255,136,0.2)}
.btn-call:active{transform:scale(0.98)}
.btn-end{background:linear-gradient(135deg,#3a1010,#551515);
color:#ff4444;border:2px solid #ff4444}
.btn-end:hover{box-shadow:0 0 30px rgba(255,68,68,0.2)}
.stats{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:16px}
.stat{background:rgba(0,0,0,0.25);border-radius:8px;padding:8px 10px;
border:1px solid rgba(0,180,255,0.06)}
.stat-label{font-size:8px;color:#335566;text-transform:uppercase;letter-spacing:1px}
.stat-val{font-size:14px;font-weight:600;color:#00aacc}
.id-badge{text-align:center;margin-top:12px;font-size:10px;color:#335566}
.id-badge span{color:#00ccff;font-weight:600}
.glow-ring{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
width:60px;height:60px;border-radius:50%;border:2px solid rgba(0,255,170,0.3);
animation:pulse-ring 2s infinite;pointer-events:none;display:none}
.glow-ring.active{display:block}
@keyframes pulse-ring{0%{transform:translate(-50%,-50%) scale(1);opacity:0.6}
100%{transform:translate(-50%,-50%) scale(2.5);opacity:0}}
button{display:block;width:100%;padding:16px;border:none;border-radius:12px;
font-size:15px;font-weight:700;letter-spacing:1px;cursor:pointer;
transition:all 0.2s;font-family:inherit}
</style>
</head>
<body>
<div class="card">
<div class="title">VOICE CALL SIMULATOR</div>
<div class="subtitle">MOBILE CLIENT</div>
<div class="status" id="status">TAP TO CONNECT</div>
<div class="vis"><canvas id="wave"></canvas><div class="glow-ring" id="ring"></div></div>
<div class="meter">
<div class="meter-box"><div class="meter-label">INPUT</div>
<div class="meter-bar"><div class="meter-fill in" id="inBar"></div></div>
<div class="meter-val" id="inVal">0.00</div></div>
<div class="meter-box"><div class="meter-label">OUTPUT</div>
<div class="meter-bar"><div class="meter-fill out" id="outBar"></div></div>
<div class="meter-val" id="outVal">0.00</div></div>
</div>
<button class="btn-call" id="callBtn" onclick="toggleCall()">START CALL</button>
<div class="stats">
<div class="stat"><div class="stat-label">SENT</div><div class="stat-val" id="sSent">0</div></div>
<div class="stat"><div class="stat-label">RECEIVED</div><div class="stat-val" id="sRecv">0</div></div>
<div class="stat"><div class="stat-label">LOST</div><div class="stat-val" id="sLost">0</div></div>
<div class="stat"><div class="stat-label">LATENCY</div><div class="stat-val" id="sLat">0ms</div></div>
</div>
<div class="id-badge">Client ID: <span id="cid">---</span></div>
</div>

<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<script>
const RATE=16000,CHUNK=1024;
let sio,actx,micStream,scriptNode,playing=false,connected=false;
let sent=0,recv=0,lost=0,inLevel=0,outLevel=0;
let waveData=new Float32Array(CHUNK);
const canvas=document.getElementById('wave');
const ctx=canvas.getContext('2d');
let animId;

function resizeCanvas(){canvas.width=canvas.offsetWidth*2;canvas.height=canvas.offsetHeight*2;ctx.scale(2,2)}
window.addEventListener('resize',resizeCanvas);
resizeCanvas();

function drawWave(){
  const w=canvas.width/2,h=canvas.height/2;
  ctx.clearRect(0,0,w,h);
  ctx.lineWidth=2;
  const grd=ctx.createLinearGradient(0,0,w,0);
  grd.addColorStop(0,'#00ff88');grd.addColorStop(0.5,'#00ccff');grd.addColorStop(1,'#cc44ff');
  ctx.strokeStyle=grd;
  ctx.beginPath();
  const step=Math.max(1,Math.floor(waveData.length/w));
  for(let i=0;i<w;i++){
    const idx=Math.min(i*step,waveData.length-1);
    const v=waveData[idx]/32768;
    const y=h/2+v*h*0.4;
    i===0?ctx.moveTo(i,y):ctx.lineTo(i,y);
  }
  ctx.stroke();
  animId=requestAnimationFrame(drawWave);
}
drawWave();

function toggleCall(){
  if(!connected)startCall();else endCall();
}

async function startCall(){
  try{
    if(typeof io==='undefined'){document.getElementById('status').textContent='ERROR: Socket.IO not loaded. Need internet for first load.';document.getElementById('status').className='status error';return;}
    document.getElementById('status').textContent='CONNECTING...';
    sio=io(window.location.origin,{transports:['polling','websocket'],reconnection:true,reconnectionAttempts:10,reconnectionDelay:1000,timeout:20000});
    sio.on('connect_error',(err)=>{
      document.getElementById('status').textContent='ERROR: '+err.message;
      document.getElementById('status').className='status error';
    });
    sio.on('connect',async()=>{
      connected=true;
      document.getElementById('cid').textContent=sio.id.substring(0,8);
      document.getElementById('status').textContent='CONNECTED';
      document.getElementById('status').className='status active';
      document.getElementById('ring').className='glow-ring active';
      document.getElementById('callBtn').textContent='END CALL';
      document.getElementById('callBtn').className='btn-end';
      try{await startAudio();}catch(ae){document.getElementById('status').textContent='MIC ERROR: '+ae.message;document.getElementById('status').className='status error';}
    });
    sio.on('audio_out',(data)=>{
      recv++;
      document.getElementById('sRecv').textContent=recv;
      const arr=new Int16Array(data);
      waveData=new Float32Array(arr.length);
      for(let i=0;i<arr.length;i++)waveData[i]=arr[i];
      playPCM(arr);
    });
    sio.on('stats',(d)=>{
      document.getElementById('sLost').textContent=d.lost||0;
      document.getElementById('sLat').textContent=(d.latency||0)+'ms';
    });
    sio.on('disconnect',()=>{endCall()});
  }catch(e){
    document.getElementById('status').textContent='ERROR: '+e.message;
    document.getElementById('status').className='status error';
  }
}

function endCall(){
  connected=false;
  if(sio){sio.disconnect();sio=null}
  if(micStream){micStream.getTracks().forEach(t=>t.stop());micStream=null}
  if(scriptNode){scriptNode.disconnect();scriptNode=null}
  if(actx){actx.close();actx=null}
  document.getElementById('status').textContent='DISCONNECTED';
  document.getElementById('status').className='status';
  document.getElementById('ring').className='glow-ring';
  document.getElementById('callBtn').textContent='START CALL';
  document.getElementById('callBtn').className='btn-call';
  sent=0;recv=0;lost=0;
}

async function startAudio(){
  actx=new AudioContext({sampleRate:RATE});
  await actx.resume();
  if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia){throw new Error('getUserMedia not available. Use HTTPS (accept the certificate warning first).');}
  micStream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
  const src=actx.createMediaStreamSource(micStream);
  scriptNode=actx.createScriptProcessor(CHUNK,1,1);
  scriptNode.onaudioprocess=(e)=>{
    if(!connected)return;
    const f32=e.inputBuffer.getChannelData(0);
    const i16=new Int16Array(f32.length);
    let sum=0;
    for(let i=0;i<f32.length;i++){i16[i]=Math.max(-32768,Math.min(32767,Math.round(f32[i]*32768)));sum+=Math.abs(i16[i])}
    inLevel=sum/f32.length/32768;
    document.getElementById('inBar').style.width=Math.min(inLevel*500,100)+'%';
    document.getElementById('inVal').textContent=inLevel.toFixed(3);
    sent++;
    document.getElementById('sSent').textContent=sent;
    sio.emit('audio_in',i16.buffer);
  };
  src.connect(scriptNode);
  scriptNode.connect(actx.destination);
}

let playQueue=[];
let isPlaying=false;
function playPCM(i16){
  if(!actx)return;
  const buf=actx.createBuffer(1,i16.length,RATE);
  const ch=buf.getChannelData(0);
  let sum=0;
  for(let i=0;i<i16.length;i++){ch[i]=i16[i]/32768;sum+=Math.abs(i16[i])}
  outLevel=sum/i16.length/32768;
  document.getElementById('outBar').style.width=Math.min(outLevel*500,100)+'%';
  document.getElementById('outVal').textContent=outLevel.toFixed(3);
  const src=actx.createBufferSource();
  src.buffer=buf;
  src.connect(actx.destination);
  src.start();
}
</script>
</body></html>
"""


class MobileServer:
    def __init__(self, engine):
        self.engine = engine
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'voicecall_sim'
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", async_mode='threading',
                                 max_http_buffer_size=1024*1024, ping_timeout=60, ping_interval=25)
        self.clients = {}
        self.running = False
        self._setup_routes()
        self._setup_events()

    def _setup_routes(self):
        @self.app.route('/')
        def index():
            return render_template_string(MOBILE_HTML)

    def _setup_events(self):
        @self.socketio.on('connect')
        def on_connect():
            from flask import request as flask_request
            sid = flask_request.sid
            self.clients[sid] = {'connected': True}
            self.engine.transmission_active = True
            print(f"Mobile client connected: {sid[:8]}")

        @self.socketio.on('disconnect')
        def on_disconnect():
            from flask import request as flask_request
            sid = flask_request.sid
            self.clients.pop(sid, None)
            if not self.clients:
                self.engine.transmission_active = False

        @self.socketio.on('audio_in')
        def on_audio_in(data):
            from flask import request as flask_request
            sid = flask_request.sid
            try:
                samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                self.engine.current_input_level = float(np.abs(samples).mean()) / 32768.0
                self.engine.raw_buffer.append(samples.copy())
                processed = self.engine._apply_effects(samples)
                self.engine.processed_buffer.append(processed.copy())
                self.engine.packets_sent += 1
                if random.random() < self.engine.packet_loss:
                    self.engine.packets_lost += 1
                    self.engine.packet_events.append(("lost", time.time()))
                    emit('stats', {'lost': self.engine.packets_lost, 'latency': self.engine.latency_ms})
                    return
                self.engine.packets_received += 1
                self.engine.packet_events.append(("ok", time.time()))
                output = np.clip(processed, -32768, 32767).astype(np.int16)
                self.engine.current_output_level = float(np.abs(output.astype(np.float32)).mean()) / 32768.0
                self.engine.output_buffer.append(output.astype(np.float32))
                out_bytes = output.tobytes()
                for other_sid in list(self.clients.keys()):
                    if other_sid != sid:
                        self.socketio.emit('audio_out', out_bytes, room=other_sid)
                    else:
                        if len(self.clients) == 1:
                            emit('audio_out', out_bytes)
                emit('stats', {'lost': self.engine.packets_lost, 'latency': self.engine.latency_ms})
            except Exception as e:
                print(f"Audio processing error: {e}")

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        try:
            self.socketio.run(self.app, host='0.0.0.0', port=WEB_PORT, debug=False, use_reloader=False, allow_unsafe_werkzeug=True, ssl_context='adhoc')
        except Exception as e:
            print(f'HTTPS failed ({e}), falling back to HTTP')
            self.socketio.run(self.app, host='0.0.0.0', port=WEB_PORT, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)

    def stop(self):
        self.running = False


class AudioEngine(QObject):
    def __init__(self):
        super().__init__()
        self.running = False
        self.noise_level = 0.0
        self.latency_ms = 0
        self.packet_loss = 0.0
        self.raw_buffer = deque(maxlen=200)
        self.processed_buffer = deque(maxlen=200)
        self.output_buffer = deque(maxlen=200)
        self.current_input_level = 0.0
        self.current_output_level = 0.0
        self.packets_sent = 0
        self.packets_lost = 0
        self.packets_received = 0
        self.packet_events = deque(maxlen=100)
        self.transmission_active = False
        self.mode = "loopback"
        self.target_ip = "127.0.0.1"
        self.port = 50007
        self.send_socket = None
        self.recv_socket = None
        self.bandwidth_hz = 8000
        self.jitter_ms = 0

    def _apply_effects(self, samples):
        out = samples.copy().astype(np.float64)
        if self.noise_level > 0:
            noise_power = self.noise_level * 8000
            out += np.random.normal(0, noise_power, len(out))
        if self.bandwidth_hz < 7900:
            nyq = RATE / 2.0
            cutoff = min(self.bandwidth_hz, nyq - 1) / nyq
            if 0 < cutoff < 1:
                b, a = scipy_signal.butter(4, cutoff, btype='low')
                out = scipy_signal.lfilter(b, a, out)
        return out

    def start_loopback(self):
        self.running = True
        self.transmission_active = True
        self.mode = "loopback"
        threading.Thread(target=self._loopback_loop, daemon=True).start()

    def start_network_send(self, ip):
        self.target_ip = ip
        self.running = True
        self.transmission_active = True
        self.mode = "send"
        self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        threading.Thread(target=self._send_loop, daemon=True).start()

    def start_network_recv(self):
        self.running = True
        self.transmission_active = True
        self.mode = "recv"
        self.recv_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.recv_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.recv_socket.bind(("0.0.0.0", self.port))
        self.recv_socket.settimeout(1.0)
        threading.Thread(target=self._recv_loop, daemon=True).start()

    def start_full_duplex(self, ip):
        self.target_ip = ip
        self.running = True
        self.transmission_active = True
        self.mode = "duplex"
        self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.recv_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.recv_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.recv_socket.bind(("0.0.0.0", self.port))
        self.recv_socket.settimeout(1.0)
        threading.Thread(target=self._send_loop, daemon=True).start()
        threading.Thread(target=self._recv_loop, daemon=True).start()

    def _loopback_loop(self):
        try:
            with sd.Stream(samplerate=RATE, blocksize=CHUNK, channels=CHANNELS, dtype='int16') as stream:
                while self.running:
                    data, _ = stream.read(CHUNK)
                    samples = data[:, 0].astype(np.float32)
                    self.current_input_level = float(np.abs(samples).mean()) / 32768.0
                    self.raw_buffer.append(samples.copy())
                    processed = self._apply_effects(samples)
                    self.processed_buffer.append(processed.copy())
                    self.packets_sent += 1
                    if random.random() < self.packet_loss:
                        self.packets_lost += 1
                        self.packet_events.append(("lost", time.time()))
                        continue
                    self.packets_received += 1
                    self.packet_events.append(("ok", time.time()))
                    if self.latency_ms > 0:
                        jitter = random.uniform(-self.jitter_ms, self.jitter_ms) if self.jitter_ms > 0 else 0
                        delay = max(0, (self.latency_ms + jitter) / 1000.0)
                        time.sleep(delay)
                    output = np.clip(processed, -32768, 32767).astype(np.int16)
                    self.current_output_level = float(np.abs(output.astype(np.float32)).mean()) / 32768.0
                    self.output_buffer.append(output.astype(np.float32))
                    stream.write(output.reshape(-1, 1))
        except Exception as e:
            print(f"Loopback error: {e}")
            self.running = False

    def _send_loop(self):
        try:
            with sd.InputStream(samplerate=RATE, blocksize=CHUNK, channels=CHANNELS, dtype='int16') as stream:
                while self.running:
                    data, _ = stream.read(CHUNK)
                    samples = data[:, 0].astype(np.float32)
                    self.current_input_level = float(np.abs(samples).mean()) / 32768.0
                    self.raw_buffer.append(samples.copy())
                    processed = self._apply_effects(samples)
                    self.processed_buffer.append(processed.copy())
                    self.packets_sent += 1
                    if random.random() < self.packet_loss:
                        self.packets_lost += 1
                        self.packet_events.append(("lost", time.time()))
                        continue
                    self.packet_events.append(("ok", time.time()))
                    output = np.clip(processed, -32768, 32767).astype(np.int16).tobytes()
                    self.send_socket.sendto(output, (self.target_ip, self.port))
                    if self.latency_ms > 0:
                        time.sleep(self.latency_ms / 1000.0)
        except Exception as e:
            print(f"Send error: {e}")
            self.running = False

    def _recv_loop(self):
        try:
            with sd.OutputStream(samplerate=RATE, blocksize=CHUNK, channels=CHANNELS, dtype='int16') as stream:
                while self.running:
                    try:
                        data, addr = self.recv_socket.recvfrom(CHUNK * 2 + 100)
                        self.packets_received += 1
                        samples = np.frombuffer(data, dtype=np.int16)
                        self.current_output_level = float(np.abs(samples.astype(np.float32)).mean()) / 32768.0
                        self.output_buffer.append(samples.astype(np.float32))
                        stream.write(samples.reshape(-1, 1))
                    except socket.timeout:
                        continue
        except Exception as e:
            print(f"Recv error: {e}")
            self.running = False

    def stop(self):
        self.running = False
        self.transmission_active = False
        time.sleep(0.2)
        for s in [self.send_socket, self.recv_socket]:
            if s:
                try:
                    s.close()
                except Exception:
                    pass
        self.send_socket = None
        self.recv_socket = None
        self.packets_sent = 0
        self.packets_lost = 0
        self.packets_received = 0


# ─────────────────────────────────────────────────────────────────────────────
#  BLOCK DIAGRAM WIDGET  –  interactive engineering pipeline view
#  Uses Qt2D painter so we can render text, arrows, waveforms and live data
#  without OpenGL font limitations.
# ─────────────────────────────────────────────────────────────────────────────
from PyQt5.QtWidgets import QScrollArea
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QFontMetrics, QPolygonF, QLinearGradient, QPainterPath
from PyQt5.QtCore import QRectF, QPointF, Qt as Qt2

class BlockDiagramWidget(QWidget):
    """
    Full interactive block diagram showing the complete voice transmission chain.
    Top row  : SENDER side  (MIC → Preamp → ADC → Frame → Encode → Packetize → UDP TX)
    Middle   : CHANNEL       (Network/WiFi with live noise/loss/latency effects shown)
    Bottom   : RECEIVER side (UDP RX → Depacketize → Decode → DAC → Postproc → SPEAKER)
    Live animated packets travel along the arrows.
    Each block shows a mini live waveform/meter when active.
    Clicking a block shows a large detail panel on the right.
    """

    STAGES = [
        # (id,  label,         sublabel,                            row, col, color_hex)
        ("mic",    "MIC",      "Acoustic→Electric\nTransducer",      0,  0,  "#00ff88"),
        ("preamp", "PRE-AMP",  "Signal Amplify\n& Impedance Match",  0,  1,  "#00ddaa"),
        ("adc",    "ADC",      "Analog→Digital\n16-bit / 16kHz",     0,  2,  "#00ccff"),
        ("frame",  "FRAMING",  "Chunk into\n1024-sample frames",     0,  3,  "#0088ff"),
        ("encode", "ENCODE",   "PCM Int16\nQuantization",            0,  4,  "#4444ff"),
        ("pack",   "PACKETIZE","Add seq#, timestamp\nUDP payload",   0,  5,  "#8844ff"),
        ("tx",     "UDP TX",   "Send over\nIP Network",              0,  6,  "#cc44ff"),
        ("ch",     "CHANNEL",  "WiFi / LAN\nNoise · Loss · Delay",  1,  3,  "#ff4444"),
        ("rx",     "UDP RX",   "Receive\nDatagram",                  2,  6,  "#cc44ff"),
        ("depack", "DEPACKET.", "Extract PCM\nCheck seq#",           2,  5,  "#8844ff"),
        ("decode", "DECODE",   "Int16→Float32\nDe-quantize",         2,  4,  "#4444ff"),
        ("buf",    "JITTER BUF","Reorder pkts\nSmooth timing",       2,  3,  "#0088ff"),
        ("dac",    "DAC",      "Digital→Analog\n16-bit / 16kHz",     2,  2,  "#00ccff"),
        ("postamp","POST-AMP", "Vol Control\n& Filtering",           2,  1,  "#00ddaa"),
        ("spk",    "SPEAKER",  "Electric→Acoustic\nTransducer",      2,  0,  "#00ff88"),
    ]

    ARROWS = [
        # (from_id, to_id,  label)
        ("mic",    "preamp", "analog\nsignal"),
        ("preamp", "adc",    "amplified\nvoltage"),
        ("adc",    "frame",  "raw PCM\nsamples"),
        ("frame",  "encode", "1024\nsamples"),
        ("encode", "pack",   "Int16\nbytes"),
        ("pack",   "tx",     "UDP\npayload"),
        ("tx",     "ch",     ""),
        ("ch",     "rx",     ""),
        ("rx",     "depack", "UDP\ndatagram"),
        ("depack", "decode", "raw PCM\nbytes"),
        ("decode", "buf",    "Float32\nsamples"),
        ("buf",    "dac",    "ordered\nsamples"),
        ("dac",    "postamp","analog\nsignal"),
        ("postamp","spk",    "amplified\nvoltage"),
    ]

    DETAIL = {
        "mic":    ("MICROPHONE",    "Converts sound pressure waves into an\nanalog electrical voltage via a diaphragm\nand transducer element.\nFreq range: 20 Hz – 20 kHz\nOutput: ~1–100 mV AC"),
        "preamp": ("PRE-AMPLIFIER", "Boosts the weak mic signal (mV range)\nto line level (~1V). Provides impedance\nmatching to drive the ADC input.\nGain: typically 20–60 dB"),
        "adc":    ("ADC  (Analog→Digital Converter)",
                   "Samples the continuous analog signal at\n16,000 times per second (16 kHz).\nEach sample quantized to 16 bits.\nDynamic range: 96 dB (16-bit PCM)\nNyquist freq: 8 kHz"),
        "frame":  ("FRAMING",       "Groups individual PCM samples into chunks\nof 1024 samples per frame.\nFrame duration = 1024 / 16000 = 64 ms\nEach frame becomes one UDP packet."),
        "encode": ("PCM ENCODING",  "Converts float32 audio to Int16 PCM.\nValues normalized –1.0…1.0 → –32768…32767\nThis IS the data that travels over the network.\nBit rate = 16000 × 16 = 256 kbps"),
        "pack":   ("PACKETIZATION", "Wraps PCM bytes into a UDP payload.\nAdds sequence number for loss detection.\nAdds timestamp for jitter measurement.\nPacket size = 1024 × 2 = 2048 bytes"),
        "tx":     ("UDP TRANSMIT",  "Sends packet as a UDP datagram over IP.\nUDP is connectionless — no handshake.\nFaster than TCP but no retransmission.\nDest: IP:PORT of receiver"),
        "ch":     ("CHANNEL / NETWORK",
                   "The physical/wireless medium between\nsender and receiver.\n\nEffects simulated here:\n• Additive White Gaussian Noise (AWGN)\n• Packet loss (random drop)\n• Propagation delay (latency)\n• Bandwidth limiting (low-pass filter)"),
        "rx":     ("UDP RECEIVE",   "Receives incoming UDP datagrams on\na bound socket port.\nExtract raw bytes from payload.\nRecord arrival time for jitter calc."),
        "depack": ("DEPACKETIZATION","Strips UDP header, reads sequence\nnumber to detect out-of-order or\nmissing packets.\nMissing = increment packets_lost counter."),
        "decode": ("PCM DECODING",  "Converts Int16 bytes back to float32.\nReverses the encoder: divide by 32768.\nApplies any channel effects (noise/BW).\nOutput range: –1.0 … +1.0"),
        "buf":    ("JITTER BUFFER", "Re-orders packets using sequence numbers.\nHolds a small delay buffer to absorb\nnetwork jitter (timing variation).\nTrades latency for smooth playback."),
        "dac":    ("DAC  (Digital→Analog Converter)",
                   "Converts Int16 digital samples back to\na smooth analog voltage waveform.\nSample rate: 16,000 Hz\nReconstructs audio up to 8 kHz."),
        "postamp":("POST-AMPLIFIER","Volume control and final low-pass filter.\nRemoves quantization noise above 8 kHz.\nDrives loudspeaker with sufficient power."),
        "spk":    ("SPEAKER",       "Converts electrical signal back to\nsound pressure waves via voice coil\nand cone diaphragm.\nCompletes the transmission chain."),
    }

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.t = 0.0
        self.selected = None
        self.packets = []   # animated travelling packets: {frac, arrow_idx, ok, lifetime}
        self._spawn_timer = 0.0
        self.setMinimumHeight(460)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self._hovered = None
        # layout cache rebuilt on resize
        self._layout = {}   # id → QRectF
        self._arrow_paths = []  # list of (from_pt, to_pt, label, arrow_idx)
        self._w = self._h = 0

    # ── geometry ─────────────────────────────────────────────────────────────

    def _build_layout(self, W, H):
        if W == self._w and H == self._h:
            return
        self._w, self._h = W, H
        # three rows: sender(top), channel(mid), receiver(bottom)
        pad_x, pad_y = 20, 18
        row_h = (H - pad_y * 4) // 3
        # 7 columns for sender/receiver, channel sits in middle
        n_cols = 7
        col_w = (W - pad_x * 2) // n_cols
        bw = int(col_w * 0.82)
        bh = int(row_h * 0.72)

        def rect(row, col):
            cx = pad_x + col * col_w + col_w // 2
            cy = pad_y + row * (row_h + pad_y) + row_h // 2
            return QRectF(cx - bw//2, cy - bh//2, bw, bh)

        # channel block spans 3 cols in middle row, centred at col 3
        ch_cx = pad_x + 3 * col_w + col_w // 2
        ch_cy = pad_y + 1 * (row_h + pad_y) + row_h // 2
        ch_w = int(col_w * 2.2)
        ch_h = int(row_h * 0.72)

        self._layout = {}
        for sid, lbl, sub, row, col, col_hex in self.STAGES:
            if sid == "ch":
                self._layout[sid] = QRectF(ch_cx - ch_w//2, ch_cy - ch_h//2, ch_w, ch_h)
            else:
                self._layout[sid] = rect(row, col)

        # build arrow endpoint list
        self._arrow_paths = []
        id_map = {s[0]: s for s in self.STAGES}
        for fi, (fid, tid, lbl) in enumerate(self.ARROWS):
            fr = self._layout[fid]
            tr = self._layout[tid]
            fc = QPointF(fr.center())
            tc = QPointF(tr.center())
            # pick nearest edge
            fp, tp = self._edge_pts(fr, tr, fc, tc)
            self._arrow_paths.append((fp, tp, lbl, fi))

    def _edge_pts(self, fr, tr, fc, tc):
        dx, dy = tc.x()-fc.x(), tc.y()-fc.y()
        # from-rect exit
        if abs(dx) > abs(dy):
            fx = fr.right() if dx > 0 else fr.left()
            fy = fc.y()
            tx = tr.left() if dx > 0 else tr.right()
            ty = tc.y()
        else:
            fx = fc.x()
            fy = fr.bottom() if dy > 0 else fr.top()
            tx = tc.x()
            ty = tr.top() if dy > 0 else tr.bottom()
        return QPointF(fx, fy), QPointF(tx, ty)

    # ── packet spawning ───────────────────────────────────────────────────────

    def _tick_packets(self, dt):
        # Only spawn new packets when there is real audio energy
        has_sound = (self.engine.transmission_active and
                     self.engine.current_input_level > 0.002)
        if has_sound:
            self._spawn_timer += dt
            if self._spawn_timer >= 0.10:
                self._spawn_timer = 0.0
                ok = random.random() > self.engine.packet_loss
                for fi in range(len(self.ARROWS)):
                    if random.random() < 0.45:
                        self.packets.append({'frac': 0.0, 'arrow': fi, 'ok': ok, 'life': 1.0})
        else:
            self._spawn_timer = 0.0
        # Always advance and expire existing in-flight packets
        speed = 0.7 if has_sound else 0.5
        dead = []
        for p in self.packets:
            p['frac'] += dt * speed
            if p['frac'] >= 1.0:
                dead.append(p)
        for p in dead:
            self.packets.remove(p)

    # ── paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        W, H = self.width(), self.height()
        self._build_layout(W, H)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        # background
        bg = QLinearGradient(0, 0, 0, H)
        bg.setColorAt(0, QColor("#060a14"))
        bg.setColorAt(1, QColor("#070d1a"))
        p.fillRect(0, 0, W, H, bg)

        # faint grid
        pen = QPen(QColor(30, 55, 90, 40), 1)
        p.setPen(pen)
        for gx in range(0, W, 40):
            p.drawLine(gx, 0, gx, H)
        for gy in range(0, H, 40):
            p.drawLine(0, gy, W, gy)

        # row labels
        self._draw_row_labels(p, W, H)

        # arrows (behind blocks)
        for fp, tp, lbl, fi in self._arrow_paths:
            self._draw_arrow(p, fp, tp, lbl, fi)

        # travelling packets on arrows
        for pk in self.packets:
            fi = pk['arrow']
            if fi >= len(self._arrow_paths):
                continue
            fp, tp, _, _ = self._arrow_paths[fi]
            x = fp.x() + (tp.x()-fp.x()) * pk['frac']
            y = fp.y() + (tp.y()-fp.y()) * pk['frac']
            col = QColor("#00ff88") if pk['ok'] else QColor("#ff2244")
            col.setAlphaF(0.85)
            p.setBrush(QBrush(col))
            p.setPen(Qt2.NoPen)
            p.drawEllipse(QPointF(x, y), 5, 5)
            # inner dot
            inner = QColor("white"); inner.setAlphaF(0.6)
            p.setBrush(QBrush(inner))
            p.drawEllipse(QPointF(x, y), 2, 2)

        # blocks (on top)
        for sid, lbl, sub, row, col, col_hex in self.STAGES:
            rect = self._layout[sid]
            self._draw_block(p, sid, lbl, sub, rect, col_hex)

        # detail panel if block selected
        if self.selected and self.selected in self.DETAIL:
            self._draw_detail(p, W, H)

        p.end()

    def _draw_row_labels(self, p, W, H):
        pad_y = 18
        row_h = (H - pad_y * 4) // 3
        labels = [("▶  SENDER", "#00ff88"), ("⬡  CHANNEL", "#ff6644"), ("◀  RECEIVER", "#00ffcc")]
        fnt = QFont("Consolas", 8, QFont.Bold)
        p.setFont(fnt)
        for i, (txt, col) in enumerate(labels):
            cy = pad_y + i * (row_h + pad_y) + row_h // 2
            p.setPen(QPen(QColor(col), 1))
            p.drawText(QRectF(4, cy - row_h//2, 14, row_h), Qt2.AlignVCenter | Qt2.AlignHCenter, txt[0])

    def _draw_arrow(self, p, fp, tp, label, idx):
        active = self.engine.transmission_active
        col = QColor("#1a4488" if not active else "#2266cc")
        pen = QPen(col, 2 if active else 1, Qt2.SolidLine)
        p.setPen(pen)
        p.setBrush(Qt2.NoBrush)

        # draw line
        p.drawLine(fp, tp)

        # arrowhead
        dx, dy = tp.x()-fp.x(), tp.y()-fp.y()
        length = max(math.hypot(dx, dy), 1)
        ux, uy = dx/length, dy/length
        aw = 8
        ax1 = tp.x() - uw1*aw*1.5 - uy*aw*0.5 if False else tp.x() - ux*9 - uy*4
        ay1 = tp.y() - uy*9 + ux*4
        ax2 = tp.x() - ux*9 + uy*4
        ay2 = tp.y() - uy*9 - ux*4
        p.setBrush(QBrush(col))
        poly = QPolygonF([tp, QPointF(ax1, ay1), QPointF(ax2, ay2)])
        p.drawPolygon(poly)

        # label
        if label:
            mx, my = (fp.x()+tp.x())/2, (fp.y()+tp.y())/2
            fnt = QFont("Consolas", 6)
            p.setFont(fnt)
            lc = QColor("#334466" if not active else "#4488aa")
            p.setPen(QPen(lc, 1))
            p.drawText(QRectF(mx-30, my-14, 60, 28), Qt2.AlignCenter, label)

    def _draw_block(self, p, sid, label, sub, rect, col_hex):
        active = self.engine.transmission_active
        is_sel = self.selected == sid
        is_hov = self._hovered == sid
        base = QColor(col_hex)

        # background fill
        if is_sel:
            fill = QColor(col_hex); fill.setAlphaF(0.25)
        elif is_hov:
            fill = QColor(col_hex); fill.setAlphaF(0.15)
        else:
            fill = QColor(8, 15, 30, 210)
        p.setBrush(QBrush(fill))

        # border
        border_w = 2.5 if is_sel else (1.8 if is_hov else 1.2)
        if active:
            pulse = 0.55 + 0.45 * math.sin(self.t * 3.0 + hash(sid) * 0.7)
            bc = QColor(col_hex)
            bc.setAlphaF(0.5 + 0.5 * pulse if active else 0.4)
        else:
            bc = QColor(col_hex); bc.setAlphaF(0.3)
        p.setPen(QPen(bc, border_w))
        p.drawRoundedRect(rect, 8, 8)

        # glow ring when active
        if active:
            glow_c = QColor(col_hex); glow_c.setAlphaF(0.08)
            p.setBrush(QBrush(glow_c))
            p.setPen(Qt2.NoPen)
            gr = rect.adjusted(-4, -4, 4, 4)
            p.drawRoundedRect(gr, 11, 11)

        # label text
        fnt_main = QFont("Consolas", 8, QFont.Bold)
        p.setFont(fnt_main)
        tc = QColor(col_hex) if active else QColor(col_hex).darker(140)
        tc.setAlphaF(1.0 if active else 0.7)
        p.setPen(QPen(tc, 1))
        label_rect = QRectF(rect.x(), rect.y()+4, rect.width(), rect.height()*0.38)
        p.drawText(label_rect, Qt2.AlignHCenter | Qt2.AlignVCenter, label)

        # sub label
        fnt_sub = QFont("Consolas", 6)
        p.setFont(fnt_sub)
        sc = QColor(col_hex); sc.setAlphaF(0.55 if not active else 0.75)
        p.setPen(QPen(sc, 1))
        sub_rect = QRectF(rect.x()+2, rect.y()+rect.height()*0.40, rect.width()-4, rect.height()*0.35)
        p.drawText(sub_rect, Qt2.AlignHCenter | Qt2.AlignVCenter, sub)

        # mini waveform / meter inside block
        if active:
            self._draw_mini_signal(p, sid, rect)

        # click hint
        hint_c = QColor(col_hex); hint_c.setAlphaF(0.35)
        fnt_hint = QFont("Consolas", 5)
        p.setFont(fnt_hint)
        p.setPen(QPen(hint_c, 1))
        p.drawText(QRectF(rect.x(), rect.bottom()-11, rect.width(), 11),
                   Qt2.AlignHCenter | Qt2.AlignVCenter, "click for detail")

    def _draw_mini_signal(self, p, sid, rect):
        """Draw a tiny waveform or level bar inside a block."""
        bx = rect.x() + 4
        by = rect.y() + rect.height() * 0.76
        bw = rect.width() - 8
        bh = rect.height() * 0.14
        mid_y = by + bh / 2

        wave_sids = {"mic", "preamp", "adc", "frame", "encode", "pack"}
        buf_sids  = {"decode", "buf", "dac", "postamp", "spk", "rx", "depack"}

        if sid in wave_sids and len(self.engine.raw_buffer) > 0:
            samples = self.engine.raw_buffer[-1]
            step = max(1, len(samples) // int(bw))
            pts = []
            for i in range(0, min(len(samples), int(bw)*step), step):
                frac = i / max(len(samples)-1, 1)
                x = bx + frac * bw
                y = mid_y - (samples[i] / 32768.0) * bh * 0.45
                pts.append(QPointF(x, y))
            if len(pts) > 1:
                col = QColor("#00ff88"); col.setAlphaF(0.7)
                p.setPen(QPen(col, 1.2))
                p.setBrush(Qt2.NoBrush)
                path = QPainterPath()
                path.moveTo(pts[0])
                for pt in pts[1:]:
                    path.lineTo(pt)
                p.drawPath(path)

        elif sid in buf_sids and len(self.engine.output_buffer) > 0:
            samples = self.engine.output_buffer[-1]
            step = max(1, len(samples) // int(bw))
            pts = []
            for i in range(0, min(len(samples), int(bw)*step), step):
                frac = i / max(len(samples)-1, 1)
                x = bx + frac * bw
                y = mid_y - (samples[i] / 32768.0) * bh * 0.45
                pts.append(QPointF(x, y))
            if len(pts) > 1:
                col = QColor("#00ccff"); col.setAlphaF(0.7)
                p.setPen(QPen(col, 1.2))
                p.setBrush(Qt2.NoBrush)
                path = QPainterPath()
                path.moveTo(pts[0])
                for pt in pts[1:]:
                    path.lineTo(pt)
                p.drawPath(path)

        elif sid == "tx":
            # show sent pkt count as bar
            sent = min(self.engine.packets_sent / max(self.engine.packets_sent, 1), 1.0)
            bar_w = bw * min(1.0, (self.engine.packets_sent % 50) / 50.0)
            col = QColor("#cc44ff"); col.setAlphaF(0.55)
            p.setBrush(QBrush(col)); p.setPen(Qt2.NoPen)
            p.drawRoundedRect(QRectF(bx, by, bar_w, bh), 2, 2)

        elif sid == "ch":
            # show noise + loss levels as dual bars
            nw = bw * self.engine.noise_level
            lw = bw * self.engine.packet_loss * 2
            if nw > 0:
                nc = QColor("#ff4444"); nc.setAlphaF(0.5)
                p.setBrush(QBrush(nc)); p.setPen(Qt2.NoPen)
                p.drawRoundedRect(QRectF(bx, by, nw, bh*0.4), 1, 1)
            if lw > 0:
                lc = QColor("#ff8800"); lc.setAlphaF(0.5)
                p.setBrush(QBrush(lc)); p.setPen(Qt2.NoPen)
                p.drawRoundedRect(QRectF(bx, by+bh*0.5, lw, bh*0.4), 1, 1)

    def _draw_detail(self, p, W, H):
        """Overlay a semi-transparent detail card at bottom of widget."""
        sid = self.selected
        title, body = self.DETAIL[sid]
        # find color
        col_hex = "#00ccff"
        for s in self.STAGES:
            if s[0] == sid:
                col_hex = s[5]; break

        panel_h = 160
        panel_rect = QRectF(10, H - panel_h - 8, W - 20, panel_h)
        # shadow
        shadow = QColor(0, 0, 0, 140)
        p.setBrush(QBrush(shadow)); p.setPen(Qt2.NoPen)
        p.drawRoundedRect(panel_rect.adjusted(3, 3, 3, 3), 10, 10)
        # background
        bg_col = QColor(7, 14, 28, 230)
        p.setBrush(QBrush(bg_col))
        border_col = QColor(col_hex); border_col.setAlphaF(0.7)
        p.setPen(QPen(border_col, 1.5))
        p.drawRoundedRect(panel_rect, 10, 10)
        # title
        fnt_t = QFont("Consolas", 9, QFont.Bold)
        p.setFont(fnt_t)
        p.setPen(QPen(QColor(col_hex), 1))
        p.drawText(QRectF(panel_rect.x()+12, panel_rect.y()+8, panel_rect.width()-40, 22),
                   Qt2.AlignLeft | Qt2.AlignVCenter, "▌ " + title)
        # close hint
        fnt_c = QFont("Consolas", 7)
        p.setFont(fnt_c)
        p.setPen(QPen(QColor("#334466"), 1))
        p.drawText(QRectF(panel_rect.right()-60, panel_rect.y()+8, 55, 16),
                   Qt2.AlignRight | Qt2.AlignVCenter, "[click to close]")
        # body
        fnt_b = QFont("Consolas", 7)
        p.setFont(fnt_b)
        bc = QColor(col_hex); bc.setAlphaF(0.75)
        p.setPen(QPen(bc, 1))
        body_rect = QRectF(panel_rect.x()+12, panel_rect.y()+34, panel_rect.width()-24, panel_h-42)
        p.drawText(body_rect, Qt2.AlignLeft | Qt2.TextWordWrap, body)

        # live stats overlay for relevant blocks
        active = self.engine.transmission_active
        if active:
            stats = self._get_live_stats(sid)
            if stats:
                fnt_s = QFont("Consolas", 7, QFont.Bold)
                p.setFont(fnt_s)
                sx = panel_rect.right() - 160
                sy = panel_rect.y() + 34
                for i, (k, v) in enumerate(stats):
                    kc = QColor("#334466"); vc = QColor(col_hex); vc.setAlphaF(0.9)
                    p.setPen(QPen(kc, 1))
                    p.drawText(QRectF(sx, sy + i*18, 90, 16), Qt2.AlignRight, k + " :")
                    p.setPen(QPen(vc, 1))
                    p.drawText(QRectF(sx+95, sy + i*18, 65, 16), Qt2.AlignLeft, v)

    def _get_live_stats(self, sid):
        e = self.engine
        if sid in ("mic","preamp","adc","frame","encode","pack","tx"):
            return [
                ("In Level",  f"{e.current_input_level:.4f}"),
                ("Pkts Sent", str(e.packets_sent)),
                ("Rate",      "16 kHz / 16-bit"),
                ("Frame",     f"{CHUNK} smp / {CHUNK/RATE*1000:.0f} ms"),
            ]
        elif sid == "ch":
            return [
                ("Noise",     f"{e.noise_level:.3f}"),
                ("Pkt Loss",  f"{e.packet_loss*100:.1f} %"),
                ("Latency",   f"{e.latency_ms} ms"),
                ("Bandwidth", f"{e.bandwidth_hz} Hz"),
            ]
        elif sid in ("rx","depack","decode","buf","dac","postamp","spk"):
            loss_pct = (e.packets_lost/max(e.packets_sent,1)*100)
            return [
                ("Out Level", f"{e.current_output_level:.4f}"),
                ("Pkts Recv", str(e.packets_received)),
                ("Pkts Lost", f"{e.packets_lost} ({loss_pct:.1f}%)"),
                ("Rate",      "16 kHz / 16-bit"),
            ]
        return []

    # ── interaction ───────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        pos = event.pos()
        for sid, *_ in self.STAGES:
            if sid in self._layout and self._layout[sid].contains(pos.x(), pos.y()):
                self.selected = None if self.selected == sid else sid
                self.update()
                return
        self.selected = None
        self.update()

    def mouseMoveEvent(self, event):
        pos = event.pos()
        prev = self._hovered
        self._hovered = None
        for sid, *_ in self.STAGES:
            if sid in self._layout and self._layout[sid].contains(pos.x(), pos.y()):
                self._hovered = sid
                break
        if self._hovered != prev:
            self.setCursor(Qt2.PointingHandCursor if self._hovered else Qt2.ArrowCursor)
            self.update()

    def tick(self, dt):
        self.t += dt * 60
        self._tick_packets(dt)


# ─────────────────────────────────────────────────────────────────────────────
#  WAVEFORM COMPARISON WIDGET  (Qt2D, 3 lanes side-by-side)
# ─────────────────────────────────────────────────────────────────────────────
class WaveformGLWidget(QWidget):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.t = 0.0
        self.setMinimumHeight(160)

    def paintEvent(self, event):
        W, H = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bg = QLinearGradient(0,0,0,H)
        bg.setColorAt(0, QColor("#060a14")); bg.setColorAt(1, QColor("#070d1a"))
        p.fillRect(0, 0, W, H, bg)

        lanes = [
            (self.engine.raw_buffer,       "#00ff88", "RAW INPUT"),
            (self.engine.processed_buffer, "#ff4466", "AFTER CHANNEL EFFECTS"),
            (self.engine.output_buffer,    "#ffaa22", "OUTPUT / PLAYBACK"),
        ]
        lw = W // 3
        for i, (buf, col_hex, lbl) in enumerate(lanes):
            lx = i * lw
            self._draw_lane(p, buf, col_hex, lbl, lx, 0, lw, H)
            if i > 0:
                p.setPen(QPen(QColor(30,55,90,80), 1))
                p.drawLine(lx, 0, lx, H)
        p.end()

    def _draw_lane(self, p, buf, col_hex, lbl, lx, ly, lw, lh):
        mid = ly + lh // 2
        # bg
        lane_bg = QColor(col_hex); lane_bg.setAlphaF(0.04)
        p.fillRect(lx, ly, lw, lh, lane_bg)
        # zero line
        p.setPen(QPen(QColor(col_hex).darker(200), 1, Qt2.DashLine))
        p.drawLine(lx+4, mid, lx+lw-4, mid)
        # label
        fnt = QFont("Consolas", 7, QFont.Bold)
        p.setFont(fnt); lc = QColor(col_hex); lc.setAlphaF(0.7)
        p.setPen(QPen(lc, 1))
        p.drawText(lx+6, ly+13, lbl)
        # waveform
        if len(buf) > 0:
            samples = buf[-1]
            n = min(len(samples), lw - 8)
            step = max(1, len(samples) // n)
            pts = []
            for i in range(0, min(len(samples), n*step), step):
                frac = i / max(len(samples)-1, 1)
                x = lx + 4 + frac * (lw-8)
                val = float(samples[min(i,len(samples)-1)]) / 32768.0
                y = mid + val * (lh*0.38)
                pts.append(QPointF(x, y))
            if len(pts) > 1:
                wc = QColor(col_hex); wc.setAlphaF(0.9)
                p.setPen(QPen(wc, 1.5))
                p.setBrush(Qt2.NoBrush)
                path = QPainterPath()
                path.moveTo(pts[0])
                for pt in pts[1:]:
                    path.lineTo(pt)
                p.drawPath(path)
        else:
            p.setPen(QPen(QColor(col_hex).darker(180), 1, Qt2.DashLine))
            p.drawText(lx+lw//4, mid+4, "no signal")

    def tick(self, dt):
        self.t += dt


# ─────────────────────────────────────────────────────────────────────────────
#  SPECTRUM + PACKET FLOW  in one panel using Qt Painter
# ─────────────────────────────────────────────────────────────────────────────
class SpectrumGLWidget(QWidget):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.t = 0.0
        self.bar_heights = np.zeros(48)
        self.setMinimumHeight(160)

    def paintEvent(self, event):
        W, H = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bg = QLinearGradient(0,0,0,H)
        bg.setColorAt(0, QColor("#060a14")); bg.setColorAt(1, QColor("#070d1a"))
        p.fillRect(0, 0, W, H, bg)

        num_bars = 48
        if len(self.engine.raw_buffer) > 0:
            samples = self.engine.raw_buffer[-1].astype(np.float32)
            fft = np.abs(np.fft.rfft(samples))[:num_bars]
            if len(fft) < num_bars:
                fft = np.pad(fft, (0, num_bars-len(fft)))
            mx = max(fft.max(), 1.0)
            self.bar_heights = self.bar_heights * 0.65 + (fft/mx) * 0.35
        else:
            self.bar_heights *= 0.95

        margin = 10
        bar_zone_h = H - 40
        bar_full_w = (W - margin*2) / num_bars
        bar_w = max(bar_full_w * 0.7, 2)

        for i in range(num_bars):
            h = self.bar_heights[i] * bar_zone_h
            x = margin + i * bar_full_w + (bar_full_w - bar_w)/2
            y = margin + bar_zone_h - h
            hue_f = i / num_bars
            r = int(255*(0.5+0.5*math.sin(hue_f*math.pi*2 + self.t*2)))
            g = int(255*(0.5+0.5*math.sin(hue_f*math.pi*2 + 2.094 + self.t*1.4)))
            b_v = int(255*(0.5+0.5*math.sin(hue_f*math.pi*2 + 4.189 + self.t)))
            grad = QLinearGradient(x, y, x, y+h)
            top_c = QColor(r, g, b_v, 220)
            bot_c = QColor(r//3, g//3, b_v//3, 80)
            grad.setColorAt(0, top_c); grad.setColorAt(1, bot_c)
            p.setBrush(QBrush(grad)); p.setPen(Qt2.NoPen)
            p.drawRoundedRect(QRectF(x, y, bar_w, h), 2, 2)

        # axis labels
        fnt = QFont("Consolas", 6)
        p.setFont(fnt); p.setPen(QPen(QColor("#334466"), 1))
        p.drawText(margin, H-4, "0 Hz")
        p.drawText(W//2-10, H-4, f"{RATE//4} Hz")
        p.drawText(W-50, H-4, f"{RATE//2} Hz")

        fnt2 = QFont("Consolas", 7, QFont.Bold)
        p.setFont(fnt2); p.setPen(QPen(QColor("#cc44ff"), 1))
        p.drawText(margin, margin+10, "FREQUENCY SPECTRUM  (FFT)")
        p.end()

    def tick(self, dt):
        self.t += dt * 2


class PacketFlowGLWidget(QWidget):
    """Horizontal timeline of packets: green=ok, red=lost, with byte counts."""
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.t = 0.0
        self.setMinimumHeight(80)

    def paintEvent(self, event):
        W, H = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bg = QLinearGradient(0,0,0,H)
        bg.setColorAt(0, QColor("#060a14")); bg.setColorAt(1, QColor("#070d1a"))
        p.fillRect(0, 0, W, H, bg)

        events = list(self.engine.packet_events)
        fnt = QFont("Consolas", 7, QFont.Bold)
        p.setFont(fnt)

        # title
        p.setPen(QPen(QColor("#4488cc"), 1))
        p.drawText(8, 14, "PACKET TIMELINE  (● = delivered  ✕ = lost)")

        if not events:
            p.setPen(QPen(QColor("#223344"), 1))
            p.drawText(W//3, H//2+4, "waiting for packets...")
            p.end()
            return

        n = len(events)
        pkt_w = max(6, min(14, (W - 20) // max(n, 1)))
        total_w = n * pkt_w
        start_x = max(10, W - total_w - 10)
        cy = H // 2 + 4

        # pipe line
        p.setPen(QPen(QColor("#1a3355"), 2))
        p.drawLine(start_x - 4, cy, start_x + total_w + 4, cy)

        # arrows at ends
        p.setPen(QPen(QColor("#224466"), 1))
        p.drawText(start_x-26, cy+4, "TX")
        p.drawText(start_x + total_w + 6, cy+4, "RX")

        for i, (status, ts) in enumerate(events):
            x = start_x + i * pkt_w + pkt_w//2
            pulse = 0.5 + 0.5*math.sin(self.t*4 + i*0.4)
            if status == "ok":
                col = QColor(0, int(180+75*pulse), int(80+60*pulse), 230)
                sym = "●"
            else:
                col = QColor(int(200+55*pulse), int(20+20*pulse), int(20+20*pulse), 220)
                sym = "✕"
            p.setPen(QPen(col, 1))
            p.setBrush(QBrush(col))
            p.drawEllipse(QPointF(x, cy), 4, 4)

        # stats bar
        total = max(n, 1)
        lost = sum(1 for s, _ in events if s == "lost")
        ok = total - lost
        bar_y = cy + 16
        bar_h = 6
        ok_w = int((W-20) * ok/total)
        ok_c = QColor("#00aa55"); ok_c.setAlphaF(0.7)
        lo_c = QColor("#ff2244"); lo_c.setAlphaF(0.7)
        p.setBrush(QBrush(ok_c)); p.setPen(Qt2.NoPen)
        p.drawRoundedRect(QRectF(10, bar_y, ok_w, bar_h), 2, 2)
        p.setBrush(QBrush(lo_c))
        p.drawRoundedRect(QRectF(10+ok_w, bar_y, W-20-ok_w, bar_h), 2, 2)

        fnt2 = QFont("Consolas", 6)
        p.setFont(fnt2)
        p.setPen(QPen(QColor("#00aa55"), 1))
        p.drawText(10, bar_y + bar_h + 10, f"✓ {ok} delivered  ({ok/total*100:.0f}%)")
        p.setPen(QPen(QColor("#ff4466"), 1))
        p.drawText(W//2, bar_y + bar_h + 10, f"✕ {lost} lost  ({lost/total*100:.0f}%)")
        p.end()

    def tick(self, dt):
        self.t += dt * 3


class NeonLabel(QLabel):
    def __init__(self, text, color="#00ffaa", size=11, parent=None):
        super().__init__(text, parent)
        self.setFont(QFont("Consolas", size, QFont.Bold))
        self.setStyleSheet(f"color: {color}; background: transparent;")


class GlowButton(QPushButton):
    def __init__(self, text, color="#00ffaa", parent=None):
        super().__init__(text, parent)
        self.setFont(QFont("Consolas", 11, QFont.Bold))
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(42)
        self.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(20,40,60,220), stop:1 rgba(10,20,35,240));
                color: {color};
                border: 2px solid {color};
                border-radius: 8px;
                padding: 8px 20px;
                font-family: Consolas; font-size: 12px; font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(30,60,90,230), stop:1 rgba(15,35,55,240));
            }}
            QPushButton:pressed {{
                background: rgba(40,80,120,240);
            }}
            QPushButton:disabled {{
                background: rgba(15,20,30,200);
                color: rgba(100,100,120,150);
                border: 1px solid rgba(60,60,80,100);
            }}
        """)


class NeonSlider(QWidget):
    valueChanged = pyqtSignal(float)

    def __init__(self, label, min_val, max_val, default, fmt="{:.2f}", color="#00ccff", parent=None):
        super().__init__(parent)
        self.fmt = fmt
        self.min_val = min_val
        self.max_val = max_val
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        top = QHBoxLayout()
        self.lbl = NeonLabel(label, color, 9)
        self.val_label = NeonLabel(fmt.format(default), color, 9)
        top.addWidget(self.lbl)
        top.addStretch()
        top.addWidget(self.val_label)
        layout.addLayout(top)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.setValue(int((default - min_val) / max(max_val - min_val, 1e-9) * 1000))
        self.slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: rgba(10,20,40,200); height: 6px; border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {color}; width: 16px; height: 16px;
                margin: -5px 0; border-radius: 8px; border: 2px solid rgba(255,255,255,80);
            }}
            QSlider::sub-page:horizontal {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {color}, stop:1 rgba(0,100,180,150));
                border-radius: 3px;
            }}
        """)
        self.slider.valueChanged.connect(self._on_change)
        layout.addWidget(self.slider)

    def _on_change(self, val):
        real = self.min_val + (val / 1000.0) * (self.max_val - self.min_val)
        self.val_label.setText(self.fmt.format(real))
        self.valueChanged.emit(real)

    def value(self):
        return self.min_val + (self.slider.value() / 1000.0) * (self.max_val - self.min_val)


class NeonGroupBox(QGroupBox):
    def __init__(self, title, color="#4488cc", parent=None):
        super().__init__(title, parent)
        self.setStyleSheet(f"""
            QGroupBox {{
                background: rgba(8,12,22,200); border: 1px solid {color};
                border-radius: 10px; margin-top: 14px; padding-top: 18px;
                font-family: Consolas; font-size: 10px; font-weight: bold; color: {color};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; left: 15px; padding: 0 8px; color: {color};
            }}
        """)


class VoiceCallApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.engine = AudioEngine()
        self.is_running = False
        self.setWindowTitle("VOICE CALL TRANSMISSION SIMULATOR")
        self.setMinimumSize(1300, 850)
        self.setStyleSheet("""
            QMainWindow { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 #060a14, stop:0.5 #0a1020, stop:1 #060a14); }
            QComboBox { background: rgba(15,25,45,220); color: #00ccff;
                border: 1px solid #1a3355; border-radius: 6px; padding: 6px 12px;
                font-family: Consolas; font-size: 11px; }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox QAbstractItemView { background: #0a1525; color: #00ccff;
                selection-background-color: #1a3555; border: 1px solid #1a3355; }
            QLineEdit { background: rgba(10,18,35,220); color: #00ffaa;
                border: 1px solid #1a3355; border-radius: 6px; padding: 6px 10px;
                font-family: Consolas; font-size: 11px; }
            QLineEdit:focus { border: 1px solid #00ccff; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        header = QHBoxLayout()
        header.addWidget(NeonLabel("VOICE CALL TRANSMISSION SIMULATOR", "#00ffaa", 16))
        header.addStretch()
        self.status_label = NeonLabel("IDLE", "#556688", 12)
        header.addWidget(self.status_label)
        main_layout.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(6)

        left_panel = QWidget()
        left_panel.setFixedWidth(300)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        mode_group = NeonGroupBox("TRANSMISSION MODE", "#00ffaa")
        mode_lay = QVBoxLayout(mode_group)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Loopback (Local Test)", "Network Send", "Network Receive", "Full Duplex (Real Call)"])
        mode_lay.addWidget(self.mode_combo)
        left_layout.addWidget(mode_group)

        net_group = NeonGroupBox("NETWORK CONFIG", "#00ccff")
        net_lay = QVBoxLayout(net_group)
        net_lay.addWidget(NeonLabel("Target IP", "#00ccff", 9))
        self.ip_input = QLineEdit("127.0.0.1")
        net_lay.addWidget(self.ip_input)
        net_lay.addWidget(NeonLabel("Port", "#00ccff", 9))
        self.port_input = QLineEdit("50007")
        net_lay.addWidget(self.port_input)
        left_layout.addWidget(net_group)

        fx_group = NeonGroupBox("CHANNEL EFFECTS", "#ff6644")
        fx_lay = QVBoxLayout(fx_group)
        self.noise_slider = NeonSlider("Noise Level", 0, 1, 0, "{:.2f}", "#ff4466")
        self.noise_slider.valueChanged.connect(lambda v: setattr(self.engine, 'noise_level', v))
        fx_lay.addWidget(self.noise_slider)
        self.latency_slider = NeonSlider("Latency (ms)", 0, 500, 0, "{:.0f} ms", "#ffaa00")
        self.latency_slider.valueChanged.connect(lambda v: setattr(self.engine, 'latency_ms', int(v)))
        fx_lay.addWidget(self.latency_slider)
        self.loss_slider = NeonSlider("Packet Loss", 0, 0.5, 0, "{:.0%}", "#ff2244")
        self.loss_slider.valueChanged.connect(lambda v: setattr(self.engine, 'packet_loss', v))
        fx_lay.addWidget(self.loss_slider)
        self.bw_slider = NeonSlider("Bandwidth (Hz)", 500, 8000, 8000, "{:.0f} Hz", "#cc44ff")
        self.bw_slider.valueChanged.connect(lambda v: setattr(self.engine, 'bandwidth_hz', v))
        fx_lay.addWidget(self.bw_slider)
        left_layout.addWidget(fx_group)

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(6)
        self.start_btn = GlowButton("START CALL", "#00ff88")
        self.start_btn.clicked.connect(self._start_call)
        btn_layout.addWidget(self.start_btn)
        self.stop_btn = GlowButton("STOP CALL", "#ff4444")
        self.stop_btn.clicked.connect(self._stop_call)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_btn)
        left_layout.addLayout(btn_layout)

        stats_group = NeonGroupBox("LIVE STATS", "#4488cc")
        stats_lay = QGridLayout(stats_group)
        self.stat_labels = {}
        for name, row in [("Packets Sent", 0), ("Packets Received", 1), ("Packets Lost", 2),
                          ("Input Level", 3), ("Output Level", 4)]:
            stats_lay.addWidget(NeonLabel(name, "#557799", 9), row, 0)
            val = NeonLabel("0", "#00ccff", 10)
            stats_lay.addWidget(val, row, 1)
            self.stat_labels[name] = val
        left_layout.addWidget(stats_group)

        mobile_group = NeonGroupBox("MOBILE PHONES", "#ff9900")
        mob_lay = QVBoxLayout(mobile_group)
        local_ip = get_local_ip()
        self.mobile_server = MobileServer(self.engine)
        self.mobile_server.start()
        ip_label = NeonLabel(f"https://{local_ip}:{WEB_PORT}", "#ffcc00", 11)
        ip_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        mob_lay.addWidget(NeonLabel("Open on phone browser:", "#aa7700", 9))
        mob_lay.addWidget(ip_label)
        mob_lay.addWidget(NeonLabel("Phone & PC must be on same WiFi", "#665533", 8))
        mob_lay.addWidget(NeonLabel("Accept the certificate warning!", "#ff6633", 8))
        self.mobile_count_label = NeonLabel("Connected: 0", "#ff9900", 9)
        mob_lay.addWidget(self.mobile_count_label)
        left_layout.addWidget(mobile_group)

        left_layout.addStretch()
        body.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        right_layout.addWidget(NeonLabel("TRANSMISSION BLOCK DIAGRAM  — click any block for details", "#00ffaa", 9))
        self.pipeline_gl = BlockDiagramWidget(self.engine)
        self.pipeline_gl.setStyleSheet("border: 1px solid #1a2a44; border-radius: 8px;")
        right_layout.addWidget(self.pipeline_gl, 5)

        mid_row = QHBoxLayout()
        mid_row.setSpacing(4)
        wcont = QWidget()
        wl = QVBoxLayout(wcont)
        wl.setContentsMargins(0,0,0,0)
        wl.setSpacing(0)
        wl.addWidget(NeonLabel("WAVEFORM MONITOR  (raw / channel / output)", "#00ff88", 9))
        self.waveform_gl = WaveformGLWidget(self.engine)
        self.waveform_gl.setStyleSheet("border: 1px solid #1a2a44; border-radius: 8px;")
        wl.addWidget(self.waveform_gl)
        mid_row.addWidget(wcont, 3)

        scont = QWidget()
        sl = QVBoxLayout(scont)
        sl.setContentsMargins(0,0,0,0)
        sl.setSpacing(0)
        sl.addWidget(NeonLabel("FREQUENCY SPECTRUM  (FFT)", "#cc44ff", 9))
        self.spectrum_gl = SpectrumGLWidget(self.engine)
        self.spectrum_gl.setStyleSheet("border: 1px solid #1a2a44; border-radius: 8px;")
        sl.addWidget(self.spectrum_gl)
        mid_row.addWidget(scont, 2)
        right_layout.addLayout(mid_row, 2)

        right_layout.addWidget(NeonLabel("PACKET DELIVERY TIMELINE", "#4488aa", 9))
        self.packet_gl = PacketFlowGLWidget(self.engine)
        self.packet_gl.setStyleSheet("border: 1px solid #1a2a44; border-radius: 8px;")
        right_layout.addWidget(self.packet_gl, 1)

        body.addWidget(right_panel, 1)
        main_layout.addLayout(body, 1)

        self.render_timer = QTimer()
        self.render_timer.timeout.connect(self._tick)
        self.render_timer.start(33)

    def _start_call(self):
        mode_idx = self.mode_combo.currentIndex()
        ip = self.ip_input.text().strip()
        try:
            port = int(self.port_input.text().strip())
        except ValueError:
            return
        self.engine.port = port
        try:
            if mode_idx == 0:
                self.engine.start_loopback()
            elif mode_idx == 1:
                self.engine.start_network_send(ip)
            elif mode_idx == 2:
                self.engine.start_network_recv()
            elif mode_idx == 3:
                self.engine.start_full_duplex(ip)
        except Exception as e:
            print(f"Error: {e}")
            return
        self.is_running = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText(f"ACTIVE - {self.mode_combo.currentText().upper()}")
        self.status_label.setStyleSheet("color: #00ff66; background: transparent;")

    def _stop_call(self):
        self.engine.stop()
        self.is_running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("IDLE")
        self.status_label.setStyleSheet("color: #556688; background: transparent;")

    def _tick(self):
        dt = 0.033
        self.pipeline_gl.tick(dt)
        self.pipeline_gl.update()
        self.waveform_gl.tick(dt)
        self.waveform_gl.update()
        self.spectrum_gl.tick(dt)
        self.spectrum_gl.update()
        self.packet_gl.tick(dt)
        self.packet_gl.update()
        self.stat_labels["Packets Sent"].setText(str(self.engine.packets_sent))
        self.stat_labels["Packets Received"].setText(str(self.engine.packets_received))
        self.stat_labels["Packets Lost"].setText(str(self.engine.packets_lost))
        self.stat_labels["Input Level"].setText(f"{self.engine.current_input_level:.4f}")
        self.stat_labels["Output Level"].setText(f"{self.engine.current_output_level:.4f}")
        mc = len(self.mobile_server.clients) if hasattr(self, 'mobile_server') else 0
        self.mobile_count_label.setText(f"Connected: {mc}")

    def closeEvent(self, event):
        self.engine.stop()
        if hasattr(self, 'mobile_server'):
            self.mobile_server.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    dark = QPalette()
    dark.setColor(QPalette.Window, QColor(6, 10, 20))
    dark.setColor(QPalette.WindowText, QColor(150, 200, 220))
    dark.setColor(QPalette.Base, QColor(10, 18, 35))
    dark.setColor(QPalette.Text, QColor(0, 255, 170))
    dark.setColor(QPalette.Button, QColor(15, 25, 45))
    dark.setColor(QPalette.ButtonText, QColor(0, 200, 255))
    dark.setColor(QPalette.Highlight, QColor(0, 120, 200))
    app.setPalette(dark)
    window = VoiceCallApp()
    window.show()
    sys.exit(app.exec_())
