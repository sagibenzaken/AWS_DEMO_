import subprocess
import os
import requests
from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)

# Administrator Defaults
DEFAULT_N = int(os.environ.get('CPU_CORES', 1))
DEFAULT_T = int(os.environ.get('STRESS_TIME', 60))

def get_public_ip():
    """Fetches the actual public IP address of the EC2 instance."""
    try:
        return requests.get('https://ifconfig.me', timeout=2).text.strip()
    except:
        return "34.228.29.61"

# --- UI with Nature Background and Unique Neon Colors ---
HTML_UI = """
<!DOCTYPE html>
<html>
<head>
    <title>CPU Stressor (stress-ng)</title>
    <style>
        body { 
            margin: 0;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            background: url('https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=1920&q=80') no-repeat center center fixed; 
            background-size: cover;
            font-family: 'Segoe UI', sans-serif;
        }
        .container { 
            background: rgba(0, 0, 0, 0.75); 
            backdrop-filter: blur(12px);
            padding: 40px; 
            border-radius: 15px; 
            border: 2px solid #00ffcc; 
            box-shadow: 0 0 25px rgba(0, 255, 204, 0.4); 
            width: 380px;
            color: white;
            text-align: center;
        }
        h2 { 
            color: #00ffcc; 
            text-shadow: 0 0 10px rgba(0, 255, 204, 0.8);
            margin-bottom: 5px; 
            font-size: 2.2rem;
            letter-spacing: 2px;
            text-transform: uppercase;
        }
        .public-ip { 
            color: #ff00ff; 
            font-size: 1.4rem; 
            font-weight: bold; 
            margin-bottom: 30px;
            text-shadow: 0 0 8px rgba(255, 0, 255, 0.6);
        }
        label { 
            display: block; 
            margin-bottom: 8px; 
            font-weight: bold; 
            color: #00ffcc;
            text-align: left;
            font-size: 0.9rem;
        }
        input { 
            width: 100%; 
            padding: 12px; 
            margin-bottom: 25px; 
            border: 1px solid #00ffcc;
            border-radius: 5px; 
            box-sizing: border-box;
            background: rgba(20, 20, 20, 0.95); 
            color: #00ffcc; 
            font-size: 18px;
            font-weight: bold;
            outline: none;
        }
        button { 
            width: 100%; 
            padding: 15px; 
            background: #ff00ff; 
            color: black; 
            border: none; 
            border-radius: 5px; 
            cursor: pointer; 
            font-weight: 900; 
            font-size: 20px;
            text-transform: uppercase;
            transition: all 0.3s ease;
        }
        button:hover { 
            background: #00ffcc;
            box-shadow: 0 0 20px #00ffcc;
        }
        .footer { 
            font-size: 12px; 
            color: #777; 
            margin-top: 20px; 
        }
    </style>
</head>
<body>
    <div class="container">
        <h2>CPU Stressor</h2>
        <div class="public-ip">I AM {{ ip }}</div>
        
        <form action="/execute" method="get">
            <label>CORES (N):</label>
            <input type="number" name="n" value="{{ n }}" min="1" required>
            
            <label>TIME IN SECONDS (T):</label>
            <input type="number" name="t" value="{{ t }}" min="1" required>
            
            <button type="submit">EXECUTE</button>
        </form>
        <div class="footer">STRESS-NG | AWS EC2 | DEFAULTS: N={{ n }}, T={{ t }}</div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    """Renders the UI with dynamic public IP"""
    return render_template_string(HTML_UI, n=DEFAULT_N, t=DEFAULT_T, ip=get_public_ip())

@app.route('/execute', methods=['GET'])
def execute():
    """Triggers the stress-ng background process"""
    try:
        n = request.args.get('n', DEFAULT_N)
        t = request.args.get('t', DEFAULT_T)
        command = ["stress-ng", "--cpu", str(n), "--timeout", f"{t}s"]
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        return jsonify({
            "status": "Background Execution Started",
            "host": f"I AM {get_public_ip()}",
            "message": f"Stressing {n} core(s) for {t} seconds."
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)