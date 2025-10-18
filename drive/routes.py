import os
import json
from flask import Flask, render_template, request, redirect, url_for
from googleapiclient.discovery import build
from flask import Blueprint
app = Blueprint('drive', __name__, template_folder='templates')

API_KEY = "Enter your google drive api key"
DRIVE_SERVICE = build('drive', 'v3', developerKey=API_KEY)
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


DATABASE_FILE = 'gdrive_folders.json'

def load_folders():
    """Loads saved folders from the JSON file."""
    if not os.path.exists(DATABASE_FILE):
        with open(DATABASE_FILE, 'w') as f:
            json.dump([], f)
        return []
    with open(DATABASE_FILE, 'r') as f:
        return json.load(f)

def save_folders(folders):
    """Saves folders to the JSON file."""
    with open(DATABASE_FILE, 'w') as f:
        json.dump(folders, f, indent=4)

def list_folder_public(folder_id):
    """Lists the contents of a public Google Drive folder."""
    try:
        query = f"'{folder_id}' in parents and trashed=false"
        response = DRIVE_SERVICE.files().list(
            q=query,
            fields="files(id, name, mimeType, webContentLink, webViewLink)"
        ).execute()

        items = []
        for item in response.get('files', []):
            item_data = {
                "name": item["name"],
                "id": item["id"],
                "mime_type": item["mimeType"],
                "is_folder": item["mimeType"] == "application/vnd.google-apps.folder",
                "link": item.get('webViewLink')
            }
            items.append(item_data)
        return items
    except Exception as e:
        print(f"Error listing folder contents: {e}")
        return None

def find_folder_by_id(folder_id, folders):
    """Finds a folder in the list by its ID."""
    for folder in folders:
        if folder['folder_id'] == folder_id:
            return folder
    return None

@app.route("/edit_folder/<folder_id>", methods=["POST"])
def edit_folder(folder_id):
    """Handles renaming a saved folder."""
    new_name = request.form.get("new_folder_name")
    
    if not new_name:
        return redirect(url_for('drive.index'))

    folders = load_folders()
    folder = find_folder_by_id(folder_id, folders)

    if folder:
        # Update the name and save back to the JSON file
        folder['folder_name'] = new_name
        save_folders(folders)
        return redirect(url_for('drive.index'))
    
    return "Folder not found in saved list.", 404
@app.route("/delete_folder/<folder_id>", methods=["POST"])
def delete_folder(folder_id):
    """Handles deleting a saved folder entry from the JSON database."""
    folders = load_folders()
    
    # Use list comprehension to create a new list excluding the folder to delete
    updated_folders = [folder for folder in folders if folder['folder_id'] != folder_id]
    
    # Check if the list size changed (meaning an entry was deleted)
    if len(updated_folders) < len(folders):
        save_folders(updated_folders)
    
    return redirect(url_for('drive.index'))


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        folder_url = request.form.get("folder_url")
        if folder_url:
            try:
                folder_id = folder_url.split('/')[-1]
                folders = load_folders()

                if not find_folder_by_id(folder_id, folders):
                    folder_name_request = DRIVE_SERVICE.files().get(fileId=folder_id, fields='name').execute()
                    folder_name = folder_name_request.get('name')
                    folders.append({"folder_id": folder_id, "folder_name": folder_name})
                    save_folders(folders)
                
                return redirect(url_for('drive.display_folder', folder_id=folder_id))
            except Exception as e:
                return f"Error: {e}. Please ensure the URL is correct and the folder is public."
    
    saved_folders = load_folders()
    return render_template("index.html", saved_folders=saved_folders)

@app.route("/folder/<folder_id>")
def display_folder(folder_id):
    folder_contents = list_folder_public(folder_id)
    if folder_contents is None:
        return "Folder not found or is not public.", 404
    
    saved_folders = load_folders()
    folder = find_folder_by_id(folder_id, saved_folders)
    if folder:
        folder_name = folder['folder_name']
    else:
        # Fallback in case folder is not in JSON file
        folder_name_request = DRIVE_SERVICE.files().get(fileId=folder_id, fields='name').execute()
        folder_name = folder_name_request.get('name')
        
    return render_template("display_folder.html", folder_name=folder_name, folder_contents=folder_contents, folder_id=folder_id)

@app.route("/<path:search_path>")
def fuzzy_search(search_path):
    parts = search_path.strip("/").split("/")
    saved_folders = load_folders()

    if not parts:
        return redirect(url_for('drive.index'))

    # Step 1: Start with top-level fuzzy match from saved folders
    current_folder = None
    matched_folder_id = None

    # Fuzzy match the first part with saved folder names
    folder_name_part = parts[0].lower()
    matched_folders = [folder for folder in saved_folders if folder_name_part in folder['folder_name'].lower()]

    if not matched_folders:
        return "No matching top-level folder found.", 404

    # Start from first match
    current_folder = matched_folders[0]
    matched_folder_id = current_folder['folder_id']

    # Step 2: Iterate deeper into subfolders/files
    for i in range(1, len(parts)):
        segment = parts[i].lower()
        contents = list_folder_public(matched_folder_id)

        if not contents:
            return f"No contents found in folder: {current_folder['folder_name']}", 404

        # Try to match this segment as a folder
        folder_matches = [
            item for item in contents
            if item['is_folder'] and segment in item['name'].lower()
        ]

        if folder_matches:
            # Go one level deeper into this matched subfolder
            current_folder = folder_matches[0]
            matched_folder_id = current_folder['id']
            continue

        # If not a folder match, try to match files instead
        file_matches = [
            item for item in contents
            if not item['is_folder'] and segment in item['name'].lower()
        ]

        if len(file_matches) == 1:
            return redirect(file_matches[0]['link'])
        elif len(file_matches) > 1:
            return render_template("search_results.html", search_results=file_matches, search_query=search_path)
        else:
            return f"No file or folder found matching: {segment}", 404

    # If all segments matched folders, display the last matched folder
    folder_contents = list_folder_public(matched_folder_id)
    folder_name = current_folder['name'] if current_folder else "Folder"

    return render_template("display_folder.html", folder_name=folder_name, folder_contents=folder_contents, folder_id=matched_folder_id)
