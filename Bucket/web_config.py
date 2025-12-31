import os
import secrets
import subprocess
from dotenv import load_dotenv
from flask import Flask, request, render_template, redirect, url_for, session
from datetime import timedelta

load_dotenv()

class S3WebApp:
    def __init__(self, s3_class):
        self._ensure_certs()
        self.app = Flask(__name__)
        
        secret_key = os.getenv("SECRET_KEY")
        if not secret_key:
            secret_key = secrets.token_hex(32)
            with open(".env", "a") as f:
                f.write(f"\nSECRET_KEY={secret_key}")
        
        self.app.secret_key = secret_key
        self.app.permanent_session_lifetime = timedelta(days=30)
        self.S3Class = s3_class
        self._setup_routes()

    def _ensure_certs(self):
        if not os.path.exists('cert.pem') or not os.path.exists('key.pem'):
            cmd = [
                "openssl", "req", "-x509", "-newkey", "rsa:4096", 
                "-nodes", "-out", "cert.pem", "-keyout", "key.pem", 
                "-days", "365", "-subj", "/CN=localhost"
            ]
            subprocess.run(cmd, check=True)

    def _get_worker(self):
        return self.S3Class(
            session.get('access'), 
            session.get('secret'), 
            session.get('region')
        )

    def _setup_routes(self):
        @self.app.route('/login', methods=['GET', 'POST'])
        def login():
            if request.method == 'POST':
                session.permanent = True if request.form.get('remember') else False
                session['access'] = request.form.get('access')
                session['secret'] = request.form.get('secret')
                session['region'] = request.form.get('region')
                session['bucket'] = request.form.get('bucket')
                return redirect(url_for('index'))
            return render_template('login.html')

        @self.app.route('/')
        def index():
            if 'access' not in session:
                return redirect(url_for('login'))
            try:
                worker = self._get_worker()
                files = worker.list_files(session['bucket'])
                return render_template('index.html', files=files, bucket=session['bucket'])
            except Exception as e:
                return f"AWS Error: {str(e)} <br><a href='/logout'>Reset Login</a>"

        @self.app.route('/upload', methods=['POST'])
        def upload():
            f = request.files.get('file')
            if f and 'access' in session:
                worker = self._get_worker()
                worker.upload(session['bucket'], f, f.filename, f.content_type)
            return redirect(url_for('index'))

        @self.app.route('/download/<path:filename>')
        def download(filename):
            if 'access' in session:
                worker = self._get_worker()
                url = worker.get_url(session['bucket'], filename)
                return redirect(url)
            return redirect(url_for('login'))

        @self.app.route('/delete/<path:filename>')
        def delete(filename):
            if 'access' in session:
                worker = self._get_worker()
                worker.delete(session['bucket'], filename)
            return redirect(url_for('index'))

        @self.app.route('/logout')
        def logout():
            session.clear()
            return redirect(url_for('login'))

    def start(self):
        self.app.run(host='0.0.0.0', port=443, ssl_context=('cert.pem', 'key.pem'))