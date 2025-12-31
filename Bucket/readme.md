# Secure S3 Web Manager

A lightweight, secure, and fully automated Flask-based file manager for Amazon S3. This tool allows users to manage S3 buckets via a web interface without hardcoding sensitive credentials.

## Features
- Zero-Configuration Setup: Automatically generates SSL certificates and Flask secret keys on first run.
- Session-Based Authentication: No AWS keys are stored on the server. Users login with their own credentials.
- Dynamic Worker Model: Creates on-the-fly S3 connections for every user request.
- Full File Management: Upload, download, delete, and live-search files in your bucket.
- HTTPS by Default: Enforces secure connections via automatically generated self-signed certificates.

## Installation

### 1. Clone the repository
```bash
git clone <your-repo-link>
cd <your-repo-folder>

## To run
sudo ./venv/bin/python3 bucket.py