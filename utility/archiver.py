import os
import zipfile
import subprocess
from plexapi.server import CONFIG

# Extract archive settings
ARCHIVE_PATH = CONFIG.data['archive'].get('archive_path', os.getcwd())
S3_BUCKET = CONFIG.data['archive'].get('s3_bucket', 'my-bucket')
RCLONE_PATH = CONFIG.data['archive'].get('rclone_path', '~/bin/rclone')
RCLONE_URL = CONFIG.data['archive'].get('rclone_url', '127.0.0.1:1234')

def archive_files(items, archive_path=ARCHIVE_PATH):
    """
    Archive the given files into a zip file.

    Parameters
    ----------
    items (list): List of items to be archived.
    archive_path (str): Path to the archive location.

    Returns
    -------
    None
    """
    archive_file = os.path.join(archive_path, "archived_media.zip")
    
    with zipfile.ZipFile(archive_file, 'w') as archive:
        for item in items:
            if os.path.exists(item):
                archive.write(item, os.path.basename(item))
                print(f"Archived: {item}")
            else:
                print(f"File not found: {item}")

    print(f"Archive created at: {archive_file}")

def archive_to_s3(items, s3_bucket=S3_BUCKET, s3_path='', rclone_path=RCLONE_PATH):
    """
    Archive the given files to AWS S3 using rclone.

    Parameters
    ----------
    items (list): List of items to be archived.
    s3_bucket (str): S3 bucket name.
    s3_path (str): Path in the S3 bucket.
    rclone_path (str): Path to the rclone executable.

    Returns
    -------
    None
    """
    for item in items:
        if os.path.exists(item):
            command = f'{rclone_path} moveto "{item}" {s3_bucket}:{s3_path} -P'
            subprocess.run(command, shell=True, check=True)
            print(f"Uploaded: {item} to {s3_bucket}:{s3_path}")
        else:
            print(f"File not found: {item}")

def refresh_rclone_cache(rclone_url=RCLONE_URL):
    """
    Refresh the rclone cache.

    Parameters
    ----------
    rclone_url (str): URL for the rclone remote control.

    Returns
    -------
    None
    """
    if rclone_url:
        command = f'rclone rc --url {rclone_url} vfs/refresh recursive=true'
        subprocess.run(command, shell=True, check=True)
        print("Rclone cache refreshed.")
    else:
        print("Rclone URL not set. Skipping cache refresh.")