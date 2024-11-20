import streamlit as st
from modules.upload_server import FileUploadServer
import pandas as pd
from pathlib import Path
from datetime import datetime
import gzip

def init_states():
    if 'initialized' not in st.session_state:
        st.session_state.update({
            'upload_server_initialized': False,
            'last_file_name': None,
            'temp_file_path': None, 
            'file_type': None,
            'upload_complete': False,
            'initialized': True
        })

def handle_file_selection():
    """Handles file selection from uploaded files directory."""
    upload_dir = Path('/tmp/streamlit_uploads')
    upload_dir.mkdir(exist_ok=True)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("Press Refresh File List when upload is complete and then select your file.")
    with col2:
        if st.button("🔄 Refresh File List"):
            st.rerun()

    files = [
        {
            'path': str(file),
            'name': file.name,
            'size': round(file.stat().st_size / (1024 * 1024), 2),
            'modified': datetime.fromtimestamp(file.stat().st_mtime)
        }
        for file in upload_dir.glob('*.*')
        if (datetime.now().timestamp() - file.stat().st_mtime) <= 86400
    ]

    if not files:
        st.info("No recent files found. Please upload a file first.")
        return False

    file_df = pd.DataFrame(files)
    file_df['Select'] = False
    file_df['Modified'] = file_df['modified'].dt.strftime('%Y-%m-%d %H:%M:%S')
    file_df['Size (MB)'] = file_df['size']

    selected_indices = st.data_editor(
        file_df[['name', 'Size (MB)', 'Modified', 'Select']],
        hide_index=True,
        column_config={
            "Select": st.column_config.CheckboxColumn(
                "Select",
                help="Select file to process",
                default=False
            )
        },
        disabled=['name', 'Size (MB)', 'Modified']
    )

    selected_files = selected_indices[selected_indices['Select']]['name'].tolist()

    if len(selected_files) > 1:
        st.warning("Please select only one file.")
        return False

    if len(selected_files) == 1:
        selected_file = selected_files[0]
        selected_path = next(f['path'] for f in files if f['name'] == selected_file)

        extension_to_type = {
            '.csv': "text/csv",
            '.xlsx': "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            '.gz': "application/gzip",
            '.json': "application/json"
        }

        file_extension = Path(selected_file).suffix.lower()
        file_type = extension_to_type.get(file_extension, "text/plain")

        st.session_state.update({
            'last_file_name': selected_file,
            'temp_file_path': selected_path,
            'file_type': file_type,
            'upload_complete': True
        })

        st.success(f"✅ Selected file: {selected_file}")
        return True

    return False

def preview_file(file_path, file_type):
    try:
        preview_rows = 5
        
        if file_type == "application/gzip":
            with gzip.open(file_path, 'rt') as f:
                if str(file_path).endswith('.csv.gz'):
                    df = pd.read_csv(f, nrows=preview_rows)
                    st.dataframe(df, use_container_width=True)
                else:
                    lines = [next(f) for _ in range(preview_rows)]
                    st.code('\n'.join(lines))
                return
                    
        elif file_type == "text/csv":
            df = pd.read_csv(file_path, nrows=preview_rows)
        elif file_type == "application/json":
            df = pd.read_json(file_path, nrows=preview_rows)
        elif file_type.startswith("application/vnd.openxmlformats-officedocument.spreadsheetml"):
            df = pd.read_excel(file_path, nrows=preview_rows)
        else:
            with open(file_path, 'r') as f:
                lines = [next(f) for _ in range(preview_rows)]
            st.code('\n'.join(lines))
            return

        st.dataframe(df, use_container_width=True)
                
    except Exception as e:
        st.error(f"Error previewing file: {str(e)}")

def main():
    st.title("File Upload and Preview")
    
    init_states()

    if not st.session_state.upload_server_initialized:
        upload_server = FileUploadServer(port=8000)
        upload_server.start()
        st.session_state.upload_server_initialized = True

    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        server_ip = s.getsockname()[0]
    finally:
        s.close()

    st.write("Upload your file (CSV, XLSX, GZ, or JSON):")
    st.components.v1.html(
        f"""<iframe src="http://{server_ip}:8000/upload" 
        height="260" style="width: 100%; border: none;"></iframe>""", 
        height=250
    )

    st.divider()
    
    if handle_file_selection():
        with st.spinner("Loading file preview..."):
            preview_file(
                Path(st.session_state.temp_file_path),
                st.session_state.file_type
            )

if __name__ == "__main__":
    main()