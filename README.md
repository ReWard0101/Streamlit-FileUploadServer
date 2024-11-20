# Streamlit File Upload Server

FastAPI-powered file upload server with Streamlit frontend.

## Features

- Uploads will be streamed directly to disk, no RAM overhead
- Rate limiting (same as st.file_uploader())
- Automatic 24h cleanup
- Cleanup at start/stop

## Install

```bash
pip install -r requirements.txt
```

## Usage

```bash
streamlit run main.py
# Increase max upload size (default 200MB):
streamlit run main.py -- --server.maxUploadSize 400
```

Or in `.streamlit/config.toml`:
```toml
[server]
maxUploadSize = 400
```

## Technical Details

- Upload server: FastAPI on port 8000
- Storage: `/tmp/streamlit_uploads`
- Rate limit: 1 upload per 2 seconds
- Preview: First 5 rows/lines
- Supports: `.csv`, `.xlsx`, `.gz`, `.json`


## Files

```
main.py                 # Streamlit app
modules/
  upload_server.py      # FastAPI server
requirements.txt
```

## License

MIT
