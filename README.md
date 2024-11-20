# Streamlit File Upload Server

FastAPI-powered file upload server with Streamlit frontend.

## Example of RAM overhead
Using st.file_uploader on a 1.2GB File:
![mrpof_plot_streamlit_file_uploader](https://github.com/user-attachments/assets/1ec909fd-8bca-45a0-9d55-4cd5dd525eb3)

Using this fastapi upload server on a 1.2GB File:
![mprof_plot_direct_upload](https://github.com/user-attachments/assets/90c78a98-8f35-4fe8-aad4-c162a5230fea)


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
