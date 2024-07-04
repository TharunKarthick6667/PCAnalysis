import streamlit as st
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
import pandas as pd
import time
import os
import zipfile
from io import BytesIO

# Initialize connection to Azure Blob Storage
connect_str = "DefaultEndpointsProtocol=https;AccountName=20320mdsplacement0025;AccountKey=wIWrRFbdwqN9FVHCux3GQPk+y5QczAJlVP07a9KSsPJCNhd1aT835hkpGYLBpL2yjDXHbGyeG1Tk+AStHEUxUw==;EndpointSuffix=core.windows.net"
blob_service_client = BlobServiceClient.from_connection_string(connect_str)
container_name = "placements-2024"
archive_container = "archive"
reject_container = "reject"

# Define user roles
USER_ROLE_UPLOADER = "Uploader"
USER_ROLE_ACCESSOR = "Accessor"
USER_ROLE_MANAGER = "Manager"

def get_user_role(email):
    # Simulated user roles based on email (replace with actual authentication logic)
    if email == "uploader@example.com":
        return USER_ROLE_UPLOADER
    elif email == "accessor@example.com":
        return USER_ROLE_ACCESSOR
    elif email == "manager@example.com":
        return USER_ROLE_MANAGER
    else:
        return None

def check_file_exists(container_client, blob_name):
    try:
        container_client.get_blob_client(blob_name).get_blob_properties()
        return True
    except:
        return False

def upload_file(container_client, file, blob_name):
    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(file, overwrite=True)

def list_files(container_client, prefix):
    blobs = container_client.list_blobs(name_starts_with=prefix)
    return [blob.name for blob in blobs]

def list_roll_numbers(container_client, department):
    blobs = container_client.list_blobs(name_starts_with=department)
    roll_numbers = set()
    for blob in blobs:
        roll_number = blob.name.split('/')[1]
        roll_numbers.add(roll_number)
    return sorted(list(roll_numbers))

def move_blob(source_client, dest_client, blob_name, new_blob_name):
    source_blob = source_client.get_blob_client(blob_name)
    dest_blob = dest_client.get_blob_client(new_blob_name)
    copy = dest_blob.start_copy_from_url(source_blob.url)

    while True:
        props = dest_blob.get_blob_properties()
        if props.copy.status == 'success':
            source_blob.delete_blob()
            break
        time.sleep(1)

def log_rejection(roll_number, file_name, reason):
    try:
        df = pd.read_excel("rejections_log.xlsx")
    except FileNotFoundError:
        df = pd.DataFrame(columns=["Roll Number", "File Name", "Reason"])
    new_entry = pd.DataFrame([[roll_number, file_name, reason]], columns=["Roll Number", "File Name", "Reason"])
    df = pd.concat([df, new_entry], ignore_index=True)
    df.to_excel("rejections_log.xlsx", index=False)

def download_blob_as_bytes(container_client, blob_name):
    blob_client = container_client.get_blob_client(blob_name)
    stream = BytesIO()
    blob_client.download_blob().readinto(stream)
    stream.seek(0)
    return stream

def create_zip(files):
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zip_file:
        for file_name, file_stream in files:
            zip_file.writestr(file_name, file_stream.read())
    zip_buffer.seek(0)
    return zip_buffer

def display_timer(duration):
    timer_placeholder = st.empty()
    for i in range(duration, 0, -1):
        timer_placeholder.write(f"Please wait... {i} seconds remaining")
        time.sleep(1)
    timer_placeholder.empty()

def login_page():
    st.title("Login")

    # Simulated user credentials for demonstration
    valid_credentials = {
        "uploader@example.com": {"password": "uploader123", "role": USER_ROLE_UPLOADER},
        "accessor@example.com": {"password": "accessor456", "role": USER_ROLE_ACCESSOR},
        "manager@example.com": {"password": "manager789", "role": USER_ROLE_MANAGER}
    }

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        if username in valid_credentials:
            if password == valid_credentials[username]["password"]:
                st.success("Logged in successfully!")
                # Set session state variables
                st.session_state.user_email = username
                st.session_state.user_role = valid_credentials[username]["role"]
                return True
            else:
                st.error("Incorrect password. Please try again.")
        else:
            st.error("User does not exist. Please try again.")
    
    return False

def uploader_page():
    st.title("Uploader Page")
    department_list = ['Msc., Software Systems','Msc., Data Science','Msc., Decision and Computing Sciences','Msc., Artificial Intelligence and Machine Learning']
    
    if 'department' not in st.session_state:
        st.session_state.department = department_list[0]
    if 'roll_number' not in st.session_state:
        st.session_state.roll_number = ""
    if 'file' not in st.session_state:
        st.session_state.file = None

    department = st.selectbox("Select Department :", department_list, index=department_list.index(st.session_state.department))
    roll_number = st.text_input("Enter Roll Number", value=st.session_state.roll_number)
    file = st.file_uploader("Upload File", type=["csv", "xlsx", "txt"], key="file_uploader")
    
    if file is not None:
        st.session_state.file = file

    file_exists = False

    if st.session_state.file and roll_number:
        blob_name = f"{department}/{roll_number}/{st.session_state.file.name}"
        container_client = blob_service_client.get_container_client(container_name)
        file_exists = check_file_exists(container_client, blob_name)
        
        if file_exists:
            st.warning("File already exists. Check the box below to replace it.")
            replace = st.checkbox("Replace existing file?")
        else:
            replace = True  # Automatically set to True if file does not exist

    if st.button("Upload") and roll_number and st.session_state.file:
        blob_name = f"{department}/{roll_number}/{st.session_state.file.name}"
        container_client = blob_service_client.get_container_client(container_name)
        
        if file_exists and replace:
            display_timer(3)  # Display a 3-second timer
            upload_file(container_client, st.session_state.file, blob_name)
            st.success("File replaced successfully.")
        elif not file_exists:
            display_timer(3)  # Display a 3-second timer
            upload_file(container_client, st.session_state.file, blob_name)
            st.success("File uploaded successfully.")
        elif file_exists and not replace:
            st.info("File upload canceled.")
        
        # Reset inputs and file state after upload
        st.session_state.department = department_list[0]
        st.session_state.roll_number = ""
        st.session_state.file = None

def file_manager_page():
    st.title("File Manager Page")
    department_list = ['Msc., Software Systems','Msc., Data Science','Msc., Decision and Computing Sciences','Msc., Artificial Intelligence and Machine Learning']
    department = st.selectbox("Select Department:", department_list)
    container_client = blob_service_client.get_container_client(container_name)
    roll_numbers = list_roll_numbers(container_client, department)
    
    if not roll_numbers:
        st.write("No pending files for approval")
        return

    roll_number = st.selectbox("Select Roll Number:", roll_numbers)
    file_list = list_files(container_client, f"{department}/{roll_number}")
    
    if file_list:
        st.write("Files:")
        for file_path in file_list:
            file_name = os.path.basename(file_path)
            st.write(file_name)
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button(f"Accept", key=f"accept_{file_path}"):
                    new_blob_name = f"{department}/{roll_number}/{file_name}"
                    archive_client = blob_service_client.get_container_client(archive_container)
                    display_timer(3)  # Display a 3-second timer
                    move_blob(container_client, archive_client, file_path, new_blob_name)
                    st.success(f"File {file_name} moved to archive.")
                    st.experimental_rerun()
            with col2:
                reject_reason_key = f"reason_{file_path}"
                if st.button(f"Reject", key=f"reject_{file_path}"):
                    st.session_state[reject_reason_key] = ""
                if reject_reason_key in st.session_state:
                    st.text_input(f"Enter rejection reason for {file_name}", key=reject_reason_key)
                    if st.button(f"Confirm Rejection {file_name}", key=f"confirm_{file_path}"):
                        reason = st.session_state[reject_reason_key]
                        if reason:
                            new_blob_name = f"{department}/{roll_number}/{file_name}"
                            reject_client = blob_service_client.get_container_client(reject_container)
                            display_timer(3)  # Display a 3-second timer
                            move_blob(container_client, reject_client, file_path, new_blob_name)
                            log_rejection(roll_number, file_name, reason)
                            st.success(f"File {file_name} moved to reject with reason: {reason}")
                            st.experimental_rerun()
                        else:
                            st.error("Please enter a rejection reason before confirming.")
    else:
        st.write("No pending files for approval.")

def view_and_download_files_page():
    st.title("View and Download Files Page")
    department_list = ['Msc., Software Systems','Msc., Data Science','Msc., Decision and Computing Sciences','Msc., Artificial Intelligence and Machine Learning']
    department = st.selectbox("Select Department:", department_list)
    container_client = blob_service_client.get_container_client(archive_container)
    roll_numbers = list_roll_numbers(container_client, department)
    
    if not roll_numbers:
        st.write("No files found for downloading.")
        return

    roll_number = st.selectbox("Select Roll Number:", roll_numbers)
    file_list = list_files(container_client, f"{department}/{roll_number}")
    
    if file_list:
        st.write("Files:")
        selected_files = st.multiselect("Select files to download", file_list)
        selected_file_names = [os.path.basename(file_path) for file_path in selected_files]

        if st.button("Download Selected Files as ZIP"):
            if selected_files:
                files_to_zip = [(os.path.basename(file_path), download_blob_as_bytes(container_client, file_path)) for file_path in selected_files]
                zip_buffer = create_zip(files_to_zip)
                st.download_button(label="Download ZIP", data=zip_buffer, file_name=f"{department}_{roll_number}.zip")
                st.experimental_rerun()
            else:
                st.warning("No files selected for download.")

        for file_path in selected_files:
            file_name = os.path.basename(file_path)
            file_stream = download_blob_as_bytes(container_client, file_path)
            st.download_button(label=f"Download {file_name}", data=file_stream, file_name=file_name)
            st.experimental_rerun()
    else:
        st.write("No files found for the selected roll number.")

def main():
    st.sidebar.title("Navigation")

    if 'user_email' not in st.session_state:
        # If user is not logged in, show login page
        if login_page():
            st.experimental_rerun()
        return

    # Determine authenticated user role
    user_role = get_user_role(st.session_state.user_email)

    # Example of using user role for access control
    if user_role == USER_ROLE_UPLOADER:
        # Display only "Upload Files" page
        page = st.sidebar.selectbox("Go to", ["📤Upload Files"])
    elif user_role == USER_ROLE_ACCESSOR:
        # Display "Upload Files" and "View and Download Files" pages
        page = st.sidebar.selectbox("Go to", ["📤Upload Files", "📥View and Download Files"])
    elif user_role == USER_ROLE_MANAGER:
        # Display all pages
        page = st.sidebar.selectbox("Go to", ["📤Upload Files", "📁Manage Files", "📥View and Download Files"])

    # Render selected page based on user's role and selected option
    if page == "📤Upload Files":
        uploader_page()
    elif page == "📁Manage Files":
        file_manager_page()
    elif page == "📥View and Download Files":
        view_and_download_files_page()

    # Logout button
    if st.sidebar.button("Logout"):
        st.session_state.clear()  # Clear all session state variables
        st.experimental_rerun()

if __name__ == "__main__":
    main()
