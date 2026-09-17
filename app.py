from flask import Flask, render_template, jsonify, request
import requests
import re
from bs4 import BeautifulSoup
import os
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# 預設的 5 組 MAC 綁定
mac_list = [
    "079C838279B9BFE1",
    "83DD49312D281A8D",
    "B6D9B61C06F642A9",
    "328F9DCA1C4C757F",
    "DE2AEA2BBAB57BD0"
]

@app.route('/')
def index():
    return render_template('index.html', macs=mac_list)

@app.route('/update_macs', methods=['POST'])
def update_macs():
    global mac_list
    data = request.json
    if 'macs' in data and isinstance(data['macs'], list):
        mac_list = [m.strip() for m in data['macs'][:5]]
        while len(mac_list) < 5:
            mac_list.append("")
        return jsonify({"status": "success", "macs": mac_list})
    return jsonify({"status": "error", "message": "Invalid data"}), 400

def fetch_single_mac(args):
    i, mac = args
    if not mac:
        return {
            "index": i + 1, "mac": "", "status": "未設定 MAC",
            "rssi": "-", "rsrp": "-", "sinr": "-"
        }
        
    url = f"http://realtrack236.brickcom.com:8086/data_log?mac={mac}&use_hours=on&hours=24"
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        # 設定 6 秒逾時
        resp = requests.get(url, headers=headers, timeout=6)
        
        if resp.status_code == 200:
            html_content = resp.text
            soup = BeautifulSoup(html_content, 'html.parser')
            
            rssi, rsrp, sinr = "-", "-", "-"
            found = False
            
            for td in soup.find_all(['td', 'div', 'pre', 'span']):
                text = td.get_text()
                if 'rssi' in text.lower() and 'rsrp' in text.lower():
                    rssi_m = re.search(r'["\\]*rssi["\\]*\s*[:=]\s*([-0-9.]+)', text, re.IGNORECASE)
                    rsrp_m = re.search(r'["\\]*rsrp["\\]*\s*[:=]\s*([-0-9.]+)', text, re.IGNORECASE)
                    sinr_m = re.search(r'["\\]*sinr["\\]*\s*[:=]\s*([-0-9.]+)', text, re.IGNORECASE)
                    
                    if rssi_m or rsrp_m or sinr_m:
                        rssi = rssi_m.group(1) if rssi_m else "-"
                        rsrp = rsrp_m.group(1) if rsrp_m else "-"
                        sinr = sinr_m.group(1) if sinr_m else "-"
                        found = True
                        break
            
            if found:
                return {
                    "index": i + 1, "mac": mac, "status": "連線正常",
                    "rssi": rssi, "rsrp": rsrp, "sinr": sinr
                }
            else:
                return {
                    "index": i + 1, "mac": mac, "status": "無有效 Payload",
                    "rssi": "-", "rsrp": "-", "sinr": "-"
                }
        else:
            return {
                "index": i + 1, "mac": mac, "status": f"HTTP {resp.status_code}",
                "rssi": "-", "rsrp": "-", "sinr": "-"
            }
    except Exception as e:
        return {
            "index": i + 1, "mac": mac, "status": "連線逾時",
            "rssi": "-", "rsrp": "-", "sinr": "-"
        }

@app.route('/get_data')
def get_data():
    # 使用多執行緒同時抓取 5 台機器，大幅縮短回應時間，避免 502 逾時
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(fetch_single_mac, enumerate(mac_list)))
        
    return jsonify(results)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)