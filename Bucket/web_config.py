import os
import secrets
import subprocess
from dotenv import load_dotenv
from flask import Flask, request, render_template, redirect, url_for, session, flash
from datetime import timedelta

load_dotenv()

class S3WebApp:
    def __init__(self, s3_class):
        self._ensure_certs()
        self.app = Flask(__name__)
        
        secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(32)
        if not os.getenv("SECRET_KEY"):
            with open(".env", "a") as f: f.write(f"\nSECRET_KEY={secret_key}")
        
        self.app.secret_key = secret_key
        self.app.permanent_session_lifetime = timedelta(days=30)
        self.S3Class = s3_class
        self._setup_routes()

    def _ensure_certs(self):
        if not os.path.exists('cert.pem'):
            subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:4096", "-nodes", 
                           "-out", "cert.pem", "-keyout", "key.pem", "-days", "365", 
                           "-subj", "/CN=localhost"], check=True)

    def _get_worker(self):
        return self.S3Class(session.get('access'), session.get('secret'), session.get('region'))

    def _setup_routes(self):
        @self.app.route('/login', methods=['GET', 'POST'])
        def login():
            if request.method == 'POST':
                access = request.form.get('access')
                secret = request.form.get('secret')
                region = request.form.get('region')
                bucket = request.form.get('bucket')

                # VALIDATION: Check if region matches bucket
                temp_worker = self.S3Class(access, secret, region)
                actual = temp_worker.get_actual_region(bucket)

                if not actual:
                    return "Error: Could not find bucket or access denied. Check keys and name."
                if actual != region:
                    return f"Error: Bucket is in {actual}, but you entered {region}. Please fix and retry."

                session['access'], session['secret'], session['region'], session['bucket'] = access, secret, region, bucket
                return redirect(url_for('index'))
            return render_template('login.html')

        @self.app.route('/')
        def index():
            if 'access' not in session: return redirect(url_for('login'))
            try:
                worker = self._get_worker()
                files = worker.list_files(session['bucket'])
                return render_template('index.html', files=files, bucket=session['bucket'])
            except Exception as e:
                return f"AWS Error: {str(e)} <br><a href='/logout'>Logout</a>"

        @self.app.route('/upload', methods=['POST'])
        def upload():
            f = request.files.get('file')
            if f and 'access' in session:
                self._get_worker().upload(session['bucket'], f, f.filename, f.content_type)
            return redirect(url_for('index'))

        @self.app.route('/download/<path:filename>')
        def download(filename):
            if 'access' in session:
                url = self._get_worker().get_url(session['bucket'], filename)
                return redirect(url)
            return redirect(url_for('login'))

        @self.app.route('/delete/<path:filename>')
        def delete(filename):
            if 'access' in session:
                self._get_worker().delete(session['bucket'], filename)
            return redirect(url_for('index'))

        @self.app.route('/logout')
        def logout():
            session.clear()
            return redirect(url_for('login'))

    def start(self):
        self.app.run(host='0.0.0.0', port=443, ssl_context=('cert.pem', 'key.pem'))