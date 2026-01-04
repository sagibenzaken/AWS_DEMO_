from flask import Flask, request, render_template, redirect, url_for, session, flash
import os, secrets, subprocess

class S3WebApp:
    def __init__(self, s3_class):
        self._ensure_certs()
        self.app = Flask(__name__)
        self.app.secret_key = secrets.token_hex(32)
        self.S3Class = s3_class
        self._setup_routes()

    def _ensure_certs(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.cert, self.key = os.path.join(base_dir, 'cert.pem'), os.path.join(base_dir, 'key.pem')
        if not os.path.exists(self.cert):
            subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:4096", "-nodes", 
                           "-out", self.cert, "-keyout", self.key, "-days", "365", 
                           "-subj", "/CN=localhost"], check=True)

    def _get_worker(self):
        return self.S3Class(session.get('access'), session.get('secret'), session.get('region'))

    def _setup_routes(self):
        @self.app.route('/login', methods=['GET', 'POST'])
        def login():
            if request.method == 'POST':
                session.update({'access': request.form.get('access'), 'secret': request.form.get('secret'),
                                'region': request.form.get('region'), 'bucket': request.form.get('bucket')})
                return redirect(url_for('index'))
            return render_template('login.html')

        @self.app.route('/')
        def index():
            if 'access' not in session: return redirect(url_for('login'))
            try:
                worker = self._get_worker()
                _, files = worker.list_files(session['bucket'])
                versioning = worker.get_versioning_status(session['bucket'])
                return render_template('index.html', files=files, bucket_name=session['bucket'], versioning=versioning)
            except Exception as e:
                flash(f"Error: {str(e)}")
                return render_template('index.html', files=[], bucket_name="Error", versioning="Unknown")

        @self.app.route('/upload', methods=['POST'])
        def upload_file():
            file = request.files.get('file')
            if file:
                filename = file.filename.lower()
                # Task 1: Auto-Prefix Logic
                if filename.endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    prefix = "images/"
                elif filename.endswith(('.pdf', '.doc', '.docx', '.txt')):
                    prefix = "documents/"
                else:
                    prefix = "others/"
                
                try:
                    full_key = f"{prefix}{file.filename}"
                    self._get_worker().upload_file(session['bucket'], file, full_key)
                    flash(f"Auto-categorized as {prefix}")
                except Exception as e: flash(f"Upload Error: {str(e)}")
            return redirect(url_for('index'))

        @self.app.route('/set_versioning', methods=['POST'])
        def set_versioning():
            target = request.form.get('status')
            self._get_worker().set_versioning(session['bucket'], target)
            flash(f"Versioning updated: {target}")
            return redirect(url_for('index'))

        @self.app.route('/apply_policy')
        def apply_policy():
            try:
                self._get_worker().apply_lifecycle(session['bucket'])
                flash("30-Day Policy Applied Successfully")
            except Exception as e: flash(f"Policy Error: {str(e)}")
            return redirect(url_for('index'))

        @self.app.route('/history/<path:filename>')
        def file_history(filename):
            try:
                v_list = self._get_worker().get_file_versions(session['bucket'], filename)
                return render_template('history.html', filename=filename, versions=v_list)
            except Exception as e:
                flash(f"History Error: {str(e)}")
                return redirect(url_for('index'))

        @self.app.route('/download/<path:filename>')
        def download_file(filename):
            return redirect(self._get_worker().get_url(session['bucket'], filename))

        @self.app.route('/delete/<path:filename>', methods=['POST'])
        def delete_file(filename):
            self._get_worker().delete_object(session['bucket'], filename)
            flash(f"Deleted {filename}")
            return redirect(url_for('index'))

        @self.app.route('/logout')
        def logout():
            session.clear()
            return redirect(url_for('login'))

    def start(self, host='0.0.0.0', port=443):
        self.app.run(host=host, port=port, ssl_context=(self.cert, self.key), debug=True)