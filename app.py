import subprocess
import os
import requests
from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)

# הגדרות ברירת מחדל מהסביבה
DEFAULT_N = int(os.environ.get('CPU_CORES', 1))
DEFAULT_T = int(os.environ.get('STRESS_TIME', 60))

def get_aws_public_ip():
    """שולף את ה-Public IP האמיתי של ה-Instance מתוך ה-Metadata של AWS (IMDSv2)"""
    try:
        # שלב 1: השגת Token זמני (נדרש ב-AWS עבור אבטחה)
        token_url = "http://169.254.169.254/latest/api/token"
        token_headers = {"X-aws-ec2-metadata-token-ttl-seconds": "21600"}
        token_response = requests.put(token_url, headers=token_headers, timeout=1)
        
        if token_response.status_code == 200:
            token = token_response.text
            # שלב 2: שליפת הכתובת הציבורית באמצעות ה-Token שקיבלנו
            ip_url = "http://169.254.169.254/latest/meta-data/public-ipv4"
            ip_headers = {"X-aws-ec2-metadata-token": token}
            public_ip = requests.get(ip_url, headers=ip_headers, timeout=1).text
            return public_ip
        return "IP Fetch Error"
    except Exception:
        # גיבוי: אם השרת לא ב-AWS או שיש חסימה, נסה שירות חיצוני
        try:
            return requests.get('https://ifconfig.me', timeout=2).text.strip()
        except:
            return "Local/Unknown IP"

# --- ממשק המשתמש (HTML) ---

HOME_UI = """
<!DOCTYPE html>
<html>
<head>
    <title>AWS Management Portal</title>
    <style>
        body { 
            margin: 0; height: 100vh; display: flex; justify-content: center; align-items: center;
            background: url('https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1920&q=80') no-repeat center center fixed; 
            background-size: cover; font-family: 'Segoe UI', sans-serif;
        }
        .container { 
            background: rgba(0, 0, 0, 0.85); backdrop-filter: blur(15px); padding: 50px; 
            border-radius: 20px; border: 2px solid #1e90ff; box-shadow: 0 0 30px rgba(30, 144, 255, 0.5);
            text-align: center; width: 600px;
        }
        h1 { color: #00ffcc; text-shadow: 0 0 15px #00ffcc; margin-bottom: 40px; text-transform: uppercase; font-size: 2.5rem; letter-spacing: 2px; }
        .options { display: flex; justify-content: space-around; gap: 20px; }
        .card { 
            background: rgba(255, 255, 255, 0.05); border: 1px solid #1e90ff; padding: 25px;
            border-radius: 15px; width: 220px; cursor: pointer; transition: all 0.4s ease;
        }
        .card:hover { transform: translateY(-10px); background: rgba(30, 144, 255, 0.2); box-shadow: 0 0 20px #1e90ff; border-color: #00ffcc; }
        .card img { width: 80px; margin-bottom: 15px; filter: drop-shadow(0 0 5px #1e90ff); }
        .card h3 { color: #fff; margin: 10px 0; }
        .card p { color: #aaa; font-size: 14px; }
        .ip-footer { margin-top: 30px; color: #1e90ff; font-weight: bold; font-size: 1.2rem; }
    </style>
</head>
<body>
    <div class="container">
        <h1>WELCOME TO AWS WORLD</h1>
        <div class="options">
            <div class="card" onclick="location.href='/s3'">
                <img src="https://cdn-icons-png.flaticon.com/512/3752/3752538.png" alt="S3">
                <h3>S3 Bucket</h3>
                <p>Manage your cloud storage and files.</p>
            </div>
            <div class="card" onclick="location.href='/stressor'">
                <img src="https://cdn-icons-png.flaticon.com/512/900/900139.png" alt="CPU">
                <h3>CPU Stressor</h3>
                <p>Run performance tests on your instance.</p>
            </div>
        </div>
        <div class="ip-footer">Host IP: {{ ip }}</div>
    </div>
</body>
</html>
"""

STRESS_UI = """
<!DOCTYPE html>
<html>
<head>
    <title>CPU Stressor</title>
    <style>
        body { 
            margin: 0; height: 100vh; display: flex; justify-content: center; align-items: center;
            background: url('https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=1920&q=80') no-repeat center center fixed; 
            background-size: cover; font-family: 'Segoe UI', sans-serif;
        }
        .container { 
            background: rgba(0, 0, 0, 0.8); backdrop-filter: blur(12px); padding: 40px; 
            border-radius: 15px; border: 2px solid #1e90ff; box-shadow: 0 0 25px rgba(30, 144, 255, 0.4); 
            width: 380px; color: white; text-align: center;
        }
        .back-btn { position: absolute; top: 20px; left: 20px; color: #00ffcc; text-decoration: none; font-weight: bold; border: 1px solid #00ffcc; padding: 8px 15px; border-radius: 5px; }
        h2 { color: #00ffcc; text-shadow: 0 0 10px #00ffcc; text-transform: uppercase; }
        .public-ip { color: #1e90ff; font-size: 1.4rem; font-weight: bold; margin-bottom: 30px; }
        label { display: block; margin-bottom: 8px; color: #00ffcc; text-align: left; }
        input { width: 100%; padding: 12px; margin-bottom: 25px; border: 1px solid #1e90ff; border-radius: 5px; background: rgba(20, 20, 20, 0.95); color: #00ffcc; font-size: 18px; }
        .btn-execute { width: 100%; padding: 15px; border: none; border-radius: 5px; cursor: pointer; font-weight: 900; font-size: 18px; text-transform: uppercase; background: #1e90ff; color: white; transition: 0.3s; }
        .btn-execute:hover { background: #00ffcc; color: black; box-shadow: 0 0 20px #00ffcc; }
    </style>
</head>
<body>
    <a href="/" class="back-btn"><- BACK TO HOME</a>
    <div class="container">
        <h2>CPU Stressor</h2>
        <div class="public-ip">I AM {{ ip }}</div>
        <form action="/execute" method="get">
            <label>CORES (N):</label>
            <input type="number" name="n" value="{{ n }}" min="1" required>
            <label>TIME (SECONDS):</label>
            <input type="number" name="t" value="{{ t }}" min="1" required>
            <button type="submit" class="btn-execute">EXECUTE STRESS</button>
        </form>
    </div>
</body>
</html>
"""

S3_UI = """
<!DOCTYPE html>
<html>
<head>
    <title>S3 Management</title>
    <style>
        body { margin: 0; height: 100vh; display: flex; justify-content: center; align-items: center; background: radial-gradient(circle, #1a1a1a, #000); font-family: 'Segoe UI', sans-serif; color: white; }
        .container { background: rgba(255, 255, 255, 0.05); border: 2px solid #1e90ff; padding: 50px; border-radius: 20px; text-align: center; width: 500px; box-shadow: 0 0 30px rgba(30, 144, 255, 0.3); }
        .back-btn { position: absolute; top: 20px; left: 20px; color: #00ffcc; text-decoration: none; font-weight: bold; border: 1px solid #00ffcc; padding: 8px 15px; border-radius: 5px; }
        h2 { color: #1e90ff; text-transform: uppercase; letter-spacing: 2px; }
        .cloud-icon { font-size: 80px; margin-bottom: 20px; }
        .button-group { display: flex; gap: 15px; justify-content: center; margin-top: 20px; }
        .btn-s3 { padding: 12px 25px; border: 1px solid #1e90ff; border-radius: 5px; background: transparent; color: #1e90ff; font-weight: bold; cursor: pointer; transition: 0.3s; }
        .btn-s3:hover { background: #1e90ff; color: white; }
    </style>
</head>
<body>
    <a href="/" class="back-btn"><- BACK TO HOME</a>
    <div class="container">
        <div class="cloud-icon">☁️</div>
        <h2>S3 Storage Portal</h2>
        <p>This module is under development. Future integration will allow S3 file management.</p>
        <div class="button-group">
            <button class="btn-s3" onclick="alert('Coming Soon!')">UPLOAD</button>
            <button class="btn-s3" onclick="alert('Coming Soon!')">DOWNLOAD</button>
        </div>
    </div>
</body>
</html>
"""

# --- פונקציות ניתוב (Routes) ---

@app.route('/')
def home():
    return render_template_string(HOME_UI, ip=get_aws_public_ip())

@app.route('/stressor')
def stressor_page():
    return render_template_string(STRESS_UI, n=DEFAULT_N, t=DEFAULT_T, ip=get_aws_public_ip())

@app.route('/s3')
def s3_page():
    return render_template_string(S3_UI)

@app.route('/execute', methods=['GET'])
def execute():
    try:
        n = request.args.get('n', DEFAULT_N)
        t = request.args.get('t', DEFAULT_T)
        
        # פקודת עומס מבוססת stress-ng
        command = [
            "stress-ng", 
            "--cpu", str(n), 
            "--cpu-method", "matrixprod", 
            "--timeout", f"{t}s"
        ]
        
        # הרצה ברקע
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        return jsonify({
            "status": "Stress Started", 
            "cores": n, 
            "duration": f"{t}s",
            "host": get_aws_public_ip()
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # הרצה על פורט 80 עבור ה-Load Balancer
    app.run(host='0.0.0.0', port=8080)