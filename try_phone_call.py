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


class PipelineGLWidget(QGLWidget):
    def __init__(self, engine, parent=None):
        fmt = QSurfaceFormat()
        fmt.setSamples(4)
        QSurfaceFormat.setDefaultFormat(fmt)
        super().__init__(parent)
        self.engine = engine
        self.t = 0.0
        self.rotation_y = 0.0
        self.rotation_x = 15.0
        self.zoom = -12.0
        self.mouse_last = None
        self.particles = []
        for _ in range(80):
            self.particles.append({
                'pos': [random.uniform(-6, 6), random.uniform(-0.5, 0.5), random.uniform(-0.5, 0.5)],
                'vel': [random.uniform(0.02, 0.08), 0, 0],
                'phase': random.uniform(0, math.pi * 2),
                'size': random.uniform(0.03, 0.08),
                'color': [random.uniform(0, 1), random.uniform(0.5, 1), 1.0]
            })
        self.setMinimumHeight(220)

    def initializeGL(self):
        glClearColor(0.02, 0.02, 0.06, 1.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        glLightfv(GL_LIGHT0, GL_POSITION, [5, 5, 10, 1])
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.15, 0.15, 0.2, 1])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8, 0.85, 1.0, 1])
        glLightfv(GL_LIGHT0, GL_SPECULAR, [1, 1, 1, 1])
        glEnable(GL_LINE_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)

    def resizeGL(self, w, h):
        glViewport(0, 0, w, max(h, 1))
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, w / max(h, 1), 0.1, 100)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        self.t += 0.03
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glTranslatef(0, -0.5, self.zoom)
        glRotatef(self.rotation_x, 1, 0, 0)
        glRotatef(self.rotation_y, 0, 1, 0)

        self._draw_grid()
        self._draw_pipeline_nodes()
        self._draw_connections()
        if self.engine.transmission_active:
            self._draw_particles()
            self._draw_wave_tube()
        self._draw_data_sphere()

    def _draw_grid(self):
        glDisable(GL_LIGHTING)
        glBegin(GL_LINES)
        for i in range(-10, 11):
            alpha = 0.08 + 0.03 * math.sin(self.t + i * 0.3)
            glColor4f(0.1, 0.3, 0.5, alpha)
            glVertex3f(i, -2, -10)
            glVertex3f(i, -2, 10)
            glVertex3f(-10, -2, i)
            glVertex3f(10, -2, i)
        glEnd()
        glEnable(GL_LIGHTING)

    def _draw_pipeline_nodes(self):
        stages = ["MIC", "ADC", "ENCODE", "TX", "CHANNEL", "RX", "DECODE", "DAC", "SPEAKER"]
        colors = [
            (0, 1, 0.5), (0, 0.8, 1), (1, 0.6, 0), (1, 0.3, 0.6),
            (1, 0, 0.4), (1, 0.3, 0.6), (1, 0.6, 0), (0, 0.8, 1), (0, 1, 0.5)
        ]
        n = len(stages)
        spacing = 12.0 / (n - 1)
        start_x = -6.0

        for i, (name, col) in enumerate(zip(stages, colors)):
            x = start_x + i * spacing
            pulse = 0.5 + 0.5 * math.sin(self.t * 2 + i * 0.7) if self.engine.transmission_active else 0.3
            glPushMatrix()
            glTranslatef(x, 0, 0)
            bob = 0.15 * math.sin(self.t * 1.5 + i * 0.9) if self.engine.transmission_active else 0
            glTranslatef(0, bob, 0)
            scale = 0.35 + 0.08 * pulse
            glScalef(scale, scale, scale)
            r, g, b = col[0] * pulse, col[1] * pulse, col[2] * pulse
            glColor4f(r, g, b, 0.9)
            quad = gluNewQuadric()
            gluQuadricNormals(quad, GLU_SMOOTH)
            gluSphere(quad, 1.0, 16, 16)
            gluDeleteQuadric(quad)
            glColor4f(r * 0.3, g * 0.3, b * 0.3, 0.2)
            glScalef(1.4, 1.4, 1.4)
            glDisable(GL_LIGHTING)
            glLineWidth(1.0)
            edges = [
                -1,-1,-1, 1,-1,-1, 1,-1,-1, 1,1,-1, 1,1,-1, -1,1,-1, -1,1,-1, -1,-1,-1,
                -1,-1,1, 1,-1,1, 1,-1,1, 1,1,1, 1,1,1, -1,1,1, -1,1,1, -1,-1,1,
                -1,-1,-1, -1,-1,1, 1,-1,-1, 1,-1,1, 1,1,-1, 1,1,1, -1,1,-1, -1,1,1
            ]
            glBegin(GL_LINES)
            for j in range(0, len(edges), 3):
                glVertex3f(edges[j], edges[j+1], edges[j+2])
            glEnd()
            glEnable(GL_LIGHTING)
            glPopMatrix()

    def _draw_connections(self):
        glDisable(GL_LIGHTING)
        n = 9
        spacing = 12.0 / (n - 1)
        start_x = -6.0
        active = self.engine.transmission_active

        for i in range(n - 1):
            x1 = start_x + i * spacing + 0.5
            x2 = start_x + (i + 1) * spacing - 0.5
            segments = 20
            glLineWidth(2.0 if active else 1.0)
            glBegin(GL_LINE_STRIP)
            for s in range(segments + 1):
                frac = s / segments
                x = x1 + frac * (x2 - x1)
                if active:
                    y = 0.1 * math.sin(self.t * 4 + x * 2 + i)
                    pulse = 0.5 + 0.5 * math.sin(self.t * 3 - frac * math.pi * 2 + i)
                    glColor4f(0.2 + 0.6 * pulse, 0.5 + 0.5 * pulse, 1.0, 0.6 * pulse + 0.2)
                else:
                    y = 0
                    glColor4f(0.1, 0.2, 0.4, 0.3)
                glVertex3f(x, y, 0)
            glEnd()
        glEnable(GL_LIGHTING)

    def _draw_particles(self):
        glDisable(GL_LIGHTING)
        for p in self.particles:
            p['pos'][0] += p['vel'][0]
            p['pos'][1] = 0.3 * math.sin(self.t * 2 + p['phase'])
            p['pos'][2] = 0.3 * math.cos(self.t * 1.5 + p['phase'])
            if p['pos'][0] > 7:
                p['pos'][0] = -7
                p['phase'] = random.uniform(0, math.pi * 2)
            glow = 0.5 + 0.5 * math.sin(self.t * 3 + p['phase'])
            glPushMatrix()
            glTranslatef(*p['pos'])
            glColor4f(p['color'][0] * glow, p['color'][1] * glow, p['color'][2], 0.8)
            q = gluNewQuadric()
            gluSphere(q, p['size'], 8, 8)
            gluDeleteQuadric(q)
            glPopMatrix()
        glEnable(GL_LIGHTING)

    def _draw_wave_tube(self):
        glDisable(GL_LIGHTING)
        if len(self.engine.raw_buffer) < 1:
            return
        samples = self.engine.raw_buffer[-1]
        step = max(1, len(samples) // 100)
        glLineWidth(2.0)
        glBegin(GL_LINE_STRIP)
        for i in range(0, min(len(samples), 100 * step), step):
            frac = i / max(100 * step, 1)
            x = -6 + frac * 12
            y = -1.5 + (samples[min(i, len(samples)-1)] / 32768.0) * 0.8
            hue = frac * math.pi * 2 + self.t
            glColor4f(
                0.5 + 0.5 * math.sin(hue),
                0.5 + 0.5 * math.sin(hue + 2.094),
                0.5 + 0.5 * math.sin(hue + 4.189), 0.8
            )
            glVertex3f(x, y, 0.5)
        glEnd()
        glEnable(GL_LIGHTING)

    def _draw_data_sphere(self):
        if not self.engine.transmission_active:
            return
        level = min(self.engine.current_input_level * 8, 1.0)
        glPushMatrix()
        glTranslatef(0, 2.2, 0)
        glRotatef(self.t * 30, 0, 1, 0)
        glRotatef(self.t * 15, 1, 0, 0)
        glColor4f(0.1 + level * 0.8, 0.4 + level * 0.6, 1.0, 0.3 + level * 0.4)
        q = gluNewQuadric()
        gluQuadricDrawStyle(q, GLU_LINE)
        gluQuadricNormals(q, GLU_SMOOTH)
        radius = 0.4 + level * 0.3
        gluSphere(q, radius, 16, 16)
        gluDeleteQuadric(q)
        glColor4f(0.2 + level, 0.6 + level * 0.4, 1.0, 0.15)
        q2 = gluNewQuadric()
        gluSphere(q2, radius * 1.3, 12, 12)
        gluDeleteQuadric(q2)
        glDisable(GL_LIGHTING)
        glLineWidth(1.0)
        for r_idx in range(3):
            glBegin(GL_LINE_LOOP)
            ring_r = radius * (1.5 + r_idx * 0.3) + 0.1 * math.sin(self.t * 2 + r_idx)
            for a in range(36):
                angle = math.radians(a * 10)
                rx = ring_r * math.cos(angle)
                ry = ring_r * math.sin(angle) * math.cos(math.radians(r_idx * 60 + self.t * 20))
                rz = ring_r * math.sin(angle) * math.sin(math.radians(r_idx * 60 + self.t * 20))
                glColor4f(0.3, 0.7, 1.0, 0.3 + 0.2 * math.sin(self.t + angle))
                glVertex3f(rx, ry, rz)
            glEnd()
        glEnable(GL_LIGHTING)
        glPopMatrix()

    def mousePressEvent(self, event):
        self.mouse_last = event.pos()

    def mouseMoveEvent(self, event):
        if self.mouse_last:
            dx = event.x() - self.mouse_last.x()
            dy = event.y() - self.mouse_last.y()
            self.rotation_y += dx * 0.5
            self.rotation_x += dy * 0.3
            self.rotation_x = max(-60, min(60, self.rotation_x))
            self.mouse_last = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        self.mouse_last = None

    def wheelEvent(self, event):
        delta = event.angleDelta().y() / 120
        self.zoom += delta * 0.5
        self.zoom = max(-30, min(-5, self.zoom))
        self.update()


class WaveformGLWidget(QGLWidget):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.t = 0.0
        self.setMinimumHeight(180)

    def initializeGL(self):
        glClearColor(0.015, 0.015, 0.04, 1.0)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE)
        glEnable(GL_LINE_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)

    def resizeGL(self, w, h):
        glViewport(0, 0, w, max(h, 1))
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(-1, 1, -1, 1, -1, 1)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        self.t += 0.03
        glClear(GL_COLOR_BUFFER_BIT)
        glLoadIdentity()
        self._draw_bg_grid()
        self._draw_waveform(self.engine.raw_buffer, 0.45, (0, 1, 0.55), "INPUT")
        self._draw_waveform(self.engine.processed_buffer, 0.0, (1.0, 0.1, 0.4), "CHANNEL")
        self._draw_waveform(self.engine.output_buffer, -0.45, (1.0, 0.45, 0.15), "OUTPUT")

    def _draw_bg_grid(self):
        glLineWidth(0.5)
        glBegin(GL_LINES)
        for i in range(21):
            x = -1 + i * 0.1
            glColor4f(0.1, 0.15, 0.25, 0.15 + 0.05 * math.sin(self.t + i * 0.3))
            glVertex2f(x, -1)
            glVertex2f(x, 1)
        for i in range(21):
            y = -1 + i * 0.1
            glColor4f(0.1, 0.15, 0.25, 0.15)
            glVertex2f(-1, y)
            glVertex2f(1, y)
        glEnd()

    def _draw_waveform(self, buffer, y_center, color, label):
        r, g, b = color
        glColor4f(r * 0.15, g * 0.15, b * 0.15, 0.3)
        glBegin(GL_QUADS)
        glVertex2f(-0.98, y_center - 0.14)
        glVertex2f(0.98, y_center - 0.14)
        glVertex2f(0.98, y_center + 0.14)
        glVertex2f(-0.98, y_center + 0.14)
        glEnd()

        glLineWidth(1.0)
        glColor4f(r * 0.3, g * 0.3, b * 0.3, 0.4)
        glBegin(GL_LINES)
        glVertex2f(-0.98, y_center)
        glVertex2f(0.98, y_center)
        glEnd()

        if len(buffer) > 0:
            samples = buffer[-1]
            num_points = min(len(samples), 300)
            step = max(1, len(samples) // num_points)
            glLineWidth(2.0)
            glBegin(GL_LINE_STRIP)
            for i in range(0, min(len(samples), num_points * step), step):
                frac = i / max(num_points * step, 1)
                x = -0.96 + frac * 1.92
                val = samples[min(i, len(samples)-1)] / 32768.0
                y = y_center + val * 0.12
                glow = 0.6 + 0.4 * math.sin(self.t * 3 + frac * 10)
                glColor4f(r * glow, g * glow, b * glow, 0.9)
                glVertex2f(x, y)
            glEnd()


class SpectrumGLWidget(QGLWidget):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.t = 0.0
        self.bar_heights = np.zeros(64)
        self.setMinimumHeight(170)

    def initializeGL(self):
        glClearColor(0.015, 0.015, 0.04, 1.0)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        glLightfv(GL_LIGHT0, GL_POSITION, [0, 5, 5, 1])
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.2, 0.2, 0.3, 1])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.7, 0.7, 0.9, 1])

    def resizeGL(self, w, h):
        glViewport(0, 0, w, max(h, 1))
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, w / max(h, 1), 0.1, 50)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        self.t += 0.03
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glTranslatef(0, -1.5, -8)
        glRotatef(25, 1, 0, 0)
        glRotatef(self.t * 5, 0, 1, 0)

        num_bars = 64
        if len(self.engine.raw_buffer) > 0:
            samples = self.engine.raw_buffer[-1]
            fft = np.abs(np.fft.rfft(samples))[:num_bars]
            if len(fft) < num_bars:
                fft = np.pad(fft, (0, num_bars - len(fft)))
            max_val = max(fft.max(), 1)
            target = fft / max_val
            self.bar_heights = self.bar_heights * 0.7 + target * 0.3
        else:
            self.bar_heights *= 0.95

        glDisable(GL_LIGHTING)
        glBegin(GL_LINES)
        for i in range(-8, 9):
            alpha = 0.06 + 0.02 * math.sin(self.t + i * 0.5)
            glColor4f(0.15, 0.25, 0.4, alpha)
            glVertex3f(i, 0, -8)
            glVertex3f(i, 0, 8)
            glVertex3f(-8, 0, i)
            glVertex3f(8, 0, i)
        glEnd()
        glEnable(GL_LIGHTING)

        bar_width = 0.12
        total_w = num_bars * bar_width * 1.5
        start_x = -total_w / 2

        for i in range(num_bars):
            h = max(self.bar_heights[i] * 3, 0.02)
            x = start_x + i * bar_width * 1.5
            hue = i / num_bars
            r = 0.5 + 0.5 * math.sin(hue * math.pi * 2 + self.t)
            g = 0.5 + 0.5 * math.sin(hue * math.pi * 2 + 2.094 + self.t * 0.7)
            b = 0.5 + 0.5 * math.sin(hue * math.pi * 2 + 4.189 + self.t * 0.5)
            glColor4f(r, g, b, 0.85)
            glPushMatrix()
            glTranslatef(x, h / 2, 0)
            glScalef(bar_width, h, bar_width)
            self._draw_cube()
            glPopMatrix()

    def _draw_cube(self):
        glBegin(GL_QUADS)
        for normal, verts in [
            ((0,1,0), [(-1,1,-1),(1,1,-1),(1,1,1),(-1,1,1)]),
            ((0,-1,0), [(-1,-1,1),(1,-1,1),(1,-1,-1),(-1,-1,-1)]),
            ((0,0,1), [(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]),
            ((0,0,-1), [(1,-1,-1),(-1,-1,-1),(-1,1,-1),(1,1,-1)]),
            ((1,0,0), [(1,-1,-1),(1,-1,1),(1,1,1),(1,1,-1)]),
            ((-1,0,0), [(-1,-1,1),(-1,-1,-1),(-1,1,-1),(-1,1,1)]),
        ]:
            glNormal3fv(normal)
            for v in verts:
                glVertex3fv([c * 0.5 for c in v])
        glEnd()


class PacketFlowGLWidget(QGLWidget):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.t = 0.0
        self.setMinimumHeight(100)

    def initializeGL(self):
        glClearColor(0.015, 0.015, 0.04, 1.0)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE)
        glEnable(GL_DEPTH_TEST)

    def resizeGL(self, w, h):
        glViewport(0, 0, w, max(h, 1))
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(35, w / max(h, 1), 0.1, 50)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        self.t += 0.03
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glTranslatef(0, 0, -10)
        glRotatef(10, 1, 0, 0)

        events = list(self.engine.packet_events)
        if not events:
            return

        spacing = min(0.2, 12.0 / max(len(events), 1))
        start_x = -len(events) * spacing / 2

        for i, (status, _) in enumerate(events):
            x = start_x + i * spacing
            if status == "ok":
                r, g, b = 0.0, 1.0, 0.5
            else:
                r, g, b = 1.0, 0.15, 0.2
            pulse = 0.5 + 0.5 * math.sin(self.t * 4 + i * 0.3)
            glPushMatrix()
            glTranslatef(x, 0.2 * math.sin(self.t + i * 0.3), 0)
            glColor4f(r * pulse, g * pulse, b * pulse, 0.8)
            q = gluNewQuadric()
            gluSphere(q, 0.06 + 0.02 * pulse, 8, 8)
            gluDeleteQuadric(q)
            glPopMatrix()


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

        right_layout.addWidget(NeonLabel("3D PIPELINE VIEW  (drag to rotate, scroll to zoom)", "#4488aa", 9))
        self.pipeline_gl = PipelineGLWidget(self.engine)
        self.pipeline_gl.setStyleSheet("border: 1px solid #1a2a44; border-radius: 8px;")
        right_layout.addWidget(self.pipeline_gl, 3)

        mid_row = QHBoxLayout()
        mid_row.setSpacing(4)
        wcont = QWidget()
        wl = QVBoxLayout(wcont)
        wl.setContentsMargins(0,0,0,0)
        wl.setSpacing(0)
        wl.addWidget(NeonLabel("WAVEFORM MONITOR", "#00ff88", 9))
        self.waveform_gl = WaveformGLWidget(self.engine)
        self.waveform_gl.setStyleSheet("border: 1px solid #1a2a44; border-radius: 8px;")
        wl.addWidget(self.waveform_gl)
        mid_row.addWidget(wcont, 3)

        scont = QWidget()
        sl = QVBoxLayout(scont)
        sl.setContentsMargins(0,0,0,0)
        sl.setSpacing(0)
        sl.addWidget(NeonLabel("3D SPECTRUM ANALYZER", "#cc44ff", 9))
        self.spectrum_gl = SpectrumGLWidget(self.engine)
        self.spectrum_gl.setStyleSheet("border: 1px solid #1a2a44; border-radius: 8px;")
        sl.addWidget(self.spectrum_gl)
        mid_row.addWidget(scont, 2)
        right_layout.addLayout(mid_row, 2)

        right_layout.addWidget(NeonLabel("PACKET FLOW VISUALIZATION", "#4488aa", 9))
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
        self.pipeline_gl.update()
        self.waveform_gl.update()
        self.spectrum_gl.update()
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
