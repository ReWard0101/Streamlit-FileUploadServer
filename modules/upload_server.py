from fastapi import FastAPI, File, UploadFile, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import threading
import atexit
import uvicorn
import logging
import asyncio
import os
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from werkzeug.utils import secure_filename

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FileUploadServer:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, port=8000):
        if not hasattr(self, 'initialized'):
            # Get Streamlit's max upload size
            try:
                import streamlit as st
                max_size = st._config.get_option('server.maxUploadSize')
                self.max_file_size = max_size * 1024 * 1024  # Convert MB to bytes
            except:
                self.max_file_size = 200 * 1024 * 1024  # Default 200MB
                
            logger.info(f"Max upload size set to: {self.max_file_size / (1024*1024):.0f}MB")
            
            self.upload_cooldown = 2
            self.last_upload = {}
            
            @asynccontextmanager
            async def lifespan_handler(app: FastAPI):
                self.cleanup_task = asyncio.create_task(self.cleanup_old_files())
                await self.cleanup_upload_dir()
                yield
                self.cleanup_task.cancel()
                await self.cleanup_upload_dir()
            
            self.app = FastAPI(lifespan=lifespan_handler)
            
            self.app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
            
            self.upload_dir = Path('/tmp/streamlit_uploads')
            self.upload_dir.mkdir(exist_ok=True)
            
            self.port = port
            self.server_thread = None
            self.setup_routes()
            self.initialized = True
            
            atexit.register(self.stop)
            
            logger.info(f"FileUploadServer initialized with upload directory: {self.upload_dir}")

    async def cleanup_old_files(self):
        """Background task to clean up old files"""
        while True:
            try:
                current_time = datetime.now()
                for file in self.upload_dir.glob('*'):
                    file_age = current_time - datetime.fromtimestamp(file.stat().st_mtime)
                    if file_age > timedelta(hours=24):
                        file.unlink()
                        logger.info(f"Cleaned up old file: {file}")
                await asyncio.sleep(3600)  # Check every hour
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
                await asyncio.sleep(300)  # Retry in 5 minutes

    def setup_routes(self):
        """Setup FastAPI routes"""
        @self.app.get("/")
        async def root():
            return {"message": "File Upload Server is running"}

        @self.app.get("/upload", response_class=HTMLResponse)
        async def get_upload_page():
            """HTML page with upload form"""
            return """
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    * {
                        box-sizing: border-box;
                        margin: 0;
                        padding: 0;
                    }

                    body {
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                        padding: 16px;
                        background-color: #ffffff;
                        color: #1a1a1a;
                    }

                    .upload-form {
                        background: #ffffff;
                        border: 2px dashed #e0e0e0;
                        border-radius: 12px;
                        padding: 24px;
                        transition: border-color 0.3s ease;
                    }

                    .upload-form:hover {
                        border-color: #2196F3;
                    }

                    .file-input-container {
                        margin-bottom: 16px;
                        display: flex;
                        gap: 12px;
                        align-items: center;
                    }

                    .file-input {
                        display: none;
                    }

                    .file-input-label {
                        background-color: #f5f5f5;
                        color: #1a1a1a;
                        padding: 10px 16px;
                        border-radius: 8px;
                        cursor: pointer;
                        font-size: 14px;
                        border: 1px solid #e0e0e0;
                        transition: all 0.2s ease;
                    }

                    .file-input-label:hover {
                        background-color: #eeeeee;
                        border-color: #2196F3;
                    }

                    .file-name {
                        color: #666;
                        font-size: 14px;
                        margin-left: 8px;
                        white-space: nowrap;
                        overflow: hidden;
                        text-overflow: ellipsis;
                        max-width: 200px;
                    }

                    .upload-button {
                        background-color: #2196F3;
                        color: white;
                        border: none;
                        padding: 10px 20px;
                        border-radius: 8px;
                        cursor: pointer;
                        font-size: 14px;
                        font-weight: 500;
                        transition: all 0.2s ease;
                        width: 120px;
                    }

                    .upload-button:hover {
                        background-color: #1976D2;
                        transform: translateY(-1px);
                        box-shadow: 0 2px 4px rgba(33, 150, 243, 0.2);
                    }

                    .upload-button:disabled {
                        background-color: #e0e0e0;
                        cursor: not-allowed;
                        transform: none;
                        box-shadow: none;
                    }

                    .progress-container {
                        margin-top: 16px;
                    }

                    .progress {
                        display: none;
                        width: 100%;
                        height: 6px;
                        background-color: #f5f5f5;
                        border-radius: 3px;
                        overflow: hidden;
                        margin: 8px 0;
                        box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.1);
                    }

                    .progress-bar {
                        width: 0%;
                        height: 100%;
                        background-color: #2196F3;
                        transition: width 0.2s ease;
                    }

                    #uploadStatus {
                        font-size: 14px;
                        color: #666;
                        margin-top: 8px;
                        min-height: 20px;
                    }

                    .success {
                        color: #4CAF50;
                    }

                    .error {
                        color: #f44336;
                    }

                    .spinner {
                        display: none;
                        width: 16px;
                        height: 16px;
                        border: 2px solid #f3f3f3;
                        border-top: 2px solid #2196F3;
                        border-radius: 50%;
                        animation: spin 1s linear infinite;
                        margin-right: 8px;
                        vertical-align: middle;
                    }

                    @keyframes spin {
                        0% { transform: rotate(0deg); }
                        100% { transform: rotate(360deg); }
                    }
                </style>
            </head>
            <body>
                <div class="upload-form">
                    <form id="uploadForm" enctype="multipart/form-data">
                        <div class="file-input-container">
                            <input type="file" id="fileInput" name="file" class="file-input" 
                                   accept=".csv,.xlsx,.gz,.json" required>
                            <label for="fileInput" class="file-input-label">Choose File</label>
                            <span class="file-name"></span>
                        </div>
                        <button type="submit" class="upload-button" disabled>
                            <span class="spinner"></span>
                            <span class="button-text">Upload</span>
                        </button>
                    </form>
                    <div class="progress-container">
                        <div class="progress">
                            <div class="progress-bar"></div>
                        </div>
                        <div id="uploadStatus"></div>
                    </div>
                </div>

                <script>
                    const fileInput = document.getElementById('fileInput');
                    const uploadButton = document.querySelector('.upload-button');
                    const buttonText = document.querySelector('.button-text');
                    const spinner = document.querySelector('.spinner');
                    const fileName = document.querySelector('.file-name');
                    const form = document.getElementById('uploadForm');
                    const progress = document.querySelector('.progress');
                    const progressBar = document.querySelector('.progress-bar');
                    const uploadStatus = document.getElementById('uploadStatus');

                    fileInput.addEventListener('change', function(e) {
                        const file = e.target.files[0];
                        if (file) {
                            fileName.textContent = file.name;
                            uploadButton.disabled = false;
                            uploadStatus.textContent = '';
                            uploadStatus.className = '';
                        } else {
                            fileName.textContent = '';
                            uploadButton.disabled = true;
                        }
                    });

                    form.addEventListener('submit', function(e) {
                        e.preventDefault();
                        
                        const file = fileInput.files[0];
                        if (!file) return;
                        
                        const formData = new FormData();
                        formData.append('file', file);
                        
                        progress.style.display = 'block';
                        progressBar.style.width = '0%';
                        uploadButton.disabled = true;
                        spinner.style.display = 'inline-block';
                        buttonText.textContent = 'Uploading...';
                        uploadStatus.textContent = 'Preparing upload...';
                        uploadStatus.className = '';
                        
                        const xhr = new XMLHttpRequest();
                        
                        xhr.upload.addEventListener('progress', function(e) {
                            if (e.lengthComputable) {
                                const percentComplete = (e.loaded / e.total) * 100;
                                progressBar.style.width = percentComplete + '%';
                                uploadStatus.textContent = `Uploading: ${Math.round(percentComplete)}%`;
                            }
                        });
                        
                        xhr.addEventListener('load', function() {
                            spinner.style.display = 'none';
                            buttonText.textContent = 'Upload';
                            
                            if (xhr.status === 200) {
                                const result = JSON.parse(xhr.responseText);
                                uploadStatus.textContent = `Upload successful! File: ${result.filename} (${result.size_mb} MB)`;
                                uploadStatus.className = 'success';
                                fileInput.value = '';
                                fileName.textContent = '';
                                uploadButton.disabled = true;
                                
                                window.parent.postMessage({
                                    type: 'upload_complete',
                                    data: result
                                }, '*');
                            } else {
                                uploadStatus.textContent = xhr.responseText ? JSON.parse(xhr.responseText).detail : 'Upload failed';
                                uploadStatus.className = 'error';
                                progressBar.style.backgroundColor = '#f44336';
                                uploadButton.disabled = false;
                            }
                        });
                        
                        xhr.addEventListener('error', function() {
                            spinner.style.display = 'none';
                            buttonText.textContent = 'Upload';
                            uploadStatus.textContent = 'Upload failed';
                            uploadStatus.className = 'error';
                            progressBar.style.backgroundColor = '#f44336';
                            uploadButton.disabled = false;
                        });
                        
                        xhr.open('POST', '/upload', true);
                        xhr.send(formData);
                    });
                </script>
            </body>
            </html>
            """

        @self.app.post("/upload")
        async def upload_file(request: Request, file: UploadFile = File(...)):
            """Handle file upload with optimized chunk size"""
            client_ip = request.client.host
            
            # Rate limiting check
            now = datetime.now()
            if client_ip in self.last_upload:
                time_since_last = (now - self.last_upload[client_ip]).total_seconds()
                if time_since_last < self.upload_cooldown:
                    raise HTTPException(status_code=429, detail="Too many uploads. Please wait.")
            
            # Increased chunk size for better performance
            CHUNK_SIZE = 1024 * 1024  # 1MB chunks
            
            safe_filename = secure_filename(file.filename)
            temp_file = self.upload_dir / safe_filename
            counter = 1
            while temp_file.exists():
                name, ext = os.path.splitext(safe_filename)
                temp_file = self.upload_dir / f"{name}_{counter}{ext}"
                counter += 1
            
            try:
                size = 0
                with temp_file.open("wb") as buffer:
                    # Use shutil for faster copying
                    while chunk := await file.read(CHUNK_SIZE):
                        size += len(chunk)
                        if size > self.max_file_size:
                            temp_file.unlink()
                            raise HTTPException(status_code=413, 
                                            detail=f"File too large. Maximum size is {self.max_file_size/(1024*1024):.0f}MB")
                        buffer.write(chunk)

                self.last_upload[client_ip] = now
                
                extension = temp_file.suffix.lower()
                content_type = file.content_type or {
                    '.csv': "text/csv",
                    '.xlsx': "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    '.gz': "application/gzip",
                    '.json': "application/json"
                }.get(extension, "application/octet-stream")
                
                return {
                    "filename": file.filename,
                    "temp_path": str(temp_file),
                    "file_extension": extension,
                    "size_mb": round(size / (1024 * 1024), 2),
                    "content_type": content_type
                }
                
            except Exception as e:
                if temp_file.exists():
                    temp_file.unlink()
                logger.error(f"Upload error: {str(e)}")
                if isinstance(e, HTTPException):
                    raise
                raise HTTPException(status_code=500, detail=str(e))

    def start(self):
        """Start the FastAPI server in a separate thread"""
        if not self.server_thread or not self.server_thread.is_alive():
            def run_server():
                logger.info(f"Starting server on port {self.port}")
                uvicorn.run(self.app, host="0.0.0.0", port=self.port)

            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self.server_thread.start()
            logger.info("Server thread started")

    def stop(self):
        """Stop the server and clean up temp files"""
        logger.info("Stopping server and cleaning up")
        try:
            current_time = datetime.now().timestamp()
            for file in self.upload_dir.glob('*'):
                if current_time - file.stat().st_mtime > 86400:  # 24 hours
                    try:
                        file.unlink()
                        logger.info(f"Cleaned up old file: {file}")
                    except Exception as e:
                        logger.error(f"Error deleting file {file}: {e}")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

    async def cleanup_upload_dir(self):
        """Clean up all files in the upload directory"""
        logger.info("Cleaning up temporary upload directory")
        try:
            for file in self.upload_dir.glob('*'):
                if file.is_file():
                    file.unlink()
                    logger.info(f"Deleted file: {file}")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def __del__(self):
        """Ensure cleanup runs on object destruction"""
        self.stop()