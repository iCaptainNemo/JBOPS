#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Find what was added TFRAME ago and not watched using Tautulli.
"""

import requests
import sys
import time
import os
from plexapi.server import CONFIG
from datetime import datetime

# Extract Tautulli settings
TAUTULLI_APIKEY = CONFIG.data['auth'].get('tautulli_apikey')
TAUTULLI_URL = CONFIG.data['auth'].get('tautulli_baseurl')

# Extract local file settings
LOCAL_ROOT_DIRECTORY = CONFIG.data['auth'].get('local_root_directory')
RELATIVE_PATH_PREFIX = CONFIG.data['auth'].get('relative_path_prefix')

# Hardcoded values if config variables are empty
if not LOCAL_ROOT_DIRECTORY:
    LOCAL_ROOT_DIRECTORY = ''
if not RELATIVE_PATH_PREFIX:
    RELATIVE_PATH_PREFIX = ''

# Prompt user for the number of days to look back, default to 30 days if no input
days_input = input("Enter the number of days to look back (default is 30): ").strip()
try:
    days = int(days_input) if days_input else 30
except ValueError:
    print("Invalid input. Using default value of 30 days.")
    days = 30

# Convert days to seconds
TFRAME = days * 86400  # Number of seconds in the given days
TODAY = time.time()

# Additional input prompt to select the operator
operator_choice = input("Enter the filter operator (<= or >=): ").strip()
if operator_choice not in ("<=", ">="):
    print("Invalid operator choice. Defaulting to <=.")
    operator_choice = "<="

def get_library_names():
    """
    Get a list of library sections and ids on the PMS.
    """
    payload = {'apikey': TAUTULLI_APIKEY, 'cmd': 'get_libraries_table'}
    try:
        r = requests.get(TAUTULLI_URL.rstrip('/') + '/api/v2', params=payload)
        response = r.json()
        return response['response']['data']['data']
    except Exception as e:
        sys.stderr.write(f"Tautulli API 'get_libraries_table' request failed: {e}.")
        return []

# Get library names from Tautulli
libraries = get_library_names()
LIBRARY_NAMES = [lib['section_name'] for lib in libraries]

# Display available libraries and prompt the user to select one or more
print("\nAvailable Libraries:")
for i, lib_name in enumerate(LIBRARY_NAMES, start=1):
    print(f"{i}. {lib_name}")

selected_libs_input = input("Enter the library numbers to check, separated by commas (e.g., 1,3): ")
selected_libs_indices = [int(x.strip()) - 1 for x in selected_libs_input.split(',') if x.strip().isdigit()]

# Filter libraries based on user selection
LIBRARY_NAMES = [LIBRARY_NAMES[i] for i in selected_libs_indices if 0 <= i < len(LIBRARY_NAMES)]

class LIBINFO(object):
    def __init__(self, data=None):
        d = data or {}
        self.added_at = d['added_at']
        self.parent_rating_key = d['parent_rating_key']
        self.play_count = d['play_count']
        self.title = d['title']
        self.rating_key = d['rating_key']
        self.media_type = d['media_type']

class METAINFO(object):
    def __init__(self, data=None):
        d = data or {}
        self.added_at = d['added_at']
        self.parent_rating_key = d['parent_rating_key']
        self.title = d['title']
        self.rating_key = d['rating_key']
        self.media_type = d['media_type']
        self.grandparent_title = d['grandparent_title']
        media_info = d['media_info'][0]
        parts = media_info['parts'][0]
        self.file_size = parts['file_size']
        self.file = parts['file']

# Display function to group items by days or months since added
def display_unwatched_items(items):
    grouped_items = {}
    current_time = int(datetime.now().timestamp())

    for item in items:
        if operator_choice == "<=":
            days_since_added = (current_time - int(item['added_at'])) // 86400  # 86400 seconds in a day
            grouped_items.setdefault(days_since_added, []).append(item)
        else:
            # Group by month if operator is >=
            added_date = datetime.fromtimestamp(int(item['added_at']))
            month_key = added_date.strftime("%Y-%m")
            grouped_items.setdefault(month_key, []).append(item)

    if operator_choice == "<=":
        for days, group in sorted(grouped_items.items()):
            added_date = datetime.fromtimestamp(int(group[0]['added_at'])).strftime("%a %b %d")
            print(f"\nItems not watched within {days} days, added {added_date}:")
            for item in group:
                print(f"  {item['file']}")
    else:
        for month, group in sorted(grouped_items.items()):
            print(f"\nItems not watched within month {month}:")
            for item in group:
                print(f"  {item['file']}")

def get_new_rating_keys(rating_key, media_type):
    payload = {'apikey': TAUTULLI_APIKEY,
               'cmd': 'get_new_rating_keys',
               'rating_key': rating_key,
               'media_type': media_type}
    try:
        r = requests.get(TAUTULLI_URL.rstrip('/') + '/api/v2', params=payload)
        response = r.json()
        res_data = response['response']['data']
        if '0' not in res_data:
            return []
        show = res_data['0']
        episode_lst = [episode['rating_key'] for _, season in show['children'].items() for _, episode in
                       season['children'].items()]
        return episode_lst
    except Exception as e:
        sys.stderr.write(f"Tautulli API 'get_new_rating_keys' request failed: {e}.")
        return []

def get_metadata(rating_key):
    payload = {'apikey': TAUTULLI_APIKEY,
               'rating_key': rating_key,
               'cmd': 'get_metadata',
               'media_info': True}
    try:
        r = requests.get(TAUTULLI_URL.rstrip('/') + '/api/v2', params=payload)
        response = r.json()
        res_data = response['response']['data']
        return METAINFO(data=res_data)
    except Exception:
        return None

# Function to get library media info and filter based on play count and added_at using selected operator
def get_library_media_info(section_id):
    payload = {
        'apikey': TAUTULLI_APIKEY,
        'section_id': section_id,
        'cmd': 'get_library_media_info',
        'length': 10000,
        'refresh': 'true'  # Force refresh of the media info
    }
    try:
        r = requests.get(TAUTULLI_URL.rstrip('/') + '/api/v2', params=payload)
        response = r.json()
        if 'response' not in response or 'data' not in response['response']:
            return []
        res_data = response['response']['data']['data']
        if operator_choice == "<=":
            filtered_items = [
                LIBINFO(data=d)
                for d in res_data
                if (d['play_count'] is None or d['play_count'] == 0) and (TODAY - int(d['added_at'])) <= TFRAME
            ]
        else:
            filtered_items = [
                LIBINFO(data=d)
                for d in res_data
                if (d['play_count'] is None or d['play_count'] == 0) and (TODAY - int(d['added_at'])) >= TFRAME
            ]
        return filtered_items
    except Exception as e:
        sys.stderr.write(f"Tautulli API 'get_library_media_info' request failed: {e}.\n")
        return []

def get_libraries_table():
    payload = {'apikey': TAUTULLI_APIKEY,
               'cmd': 'get_libraries_table'}
    try:
        r = requests.get(TAUTULLI_URL.rstrip('/') + '/api/v2', params=payload)
        response = r.json()
        res_data = response['response']['data']['data']
        return [d['section_id'] for d in res_data if d['section_name'] in LIBRARY_NAMES]
    except Exception as e:
        sys.stderr.write(f"Tautulli API 'get_libraries_table' request failed: {e}.")
        return []

def delete_files(tmp_lst):
    del_file = input('Delete all unwatched files? (yes/no/all): ').strip().lower()
    if del_file == 'all':
        for x in tmp_lst:
            print(f"Removing {x}")
            os.remove(x)
    elif del_file.startswith('y'):
        for x in tmp_lst:
            del_individual = input(f"Delete {x}? (yes/no): ").strip().lower()
            if del_individual.startswith('y'):
                print(f"Removing {x}")
                os.remove(x)
            else:
                print(f"Skipping {x}")
    else:
        print('Ok. doing nothing.')

def check_local_file_exists(library_name, file_path):
    if not LOCAL_ROOT_DIRECTORY or not RELATIVE_PATH_PREFIX:
        return False

    relative_path = file_path.replace(RELATIVE_PATH_PREFIX, '')
    local_file_path = os.path.join(LOCAL_ROOT_DIRECTORY, library_name, relative_path)
    
    # Debugging statement
    print(f"Checking local file: {local_file_path}")
    
    return os.path.exists(local_file_path)

show_lst = []
path_lst = []
glt = [lib for lib in get_libraries_table()]

for i in glt:
    try:
        gglm = get_library_media_info(i)
        for x in gglm:
            try:
                if x.media_type in ['show', 'episode']:
                    show_lst += get_new_rating_keys(x.rating_key, x.media_type)
                else:
                    show_lst += [int(x.rating_key)]
            except Exception as e:
                print(f"Rating_key failed: {e}")

    except Exception as e:
        print(f"Library media info failed: {e}")

unwatched_items = []

for i in sorted(show_lst, reverse=True):
    try:
        x = get_metadata(str(i))
        if x:
            unwatched_items.append({
                'title': x.title,
                'rating_key': x.rating_key,
                'added_at': x.added_at,
                'file': x.file,
                'grandparent_title': x.grandparent_title,
                'media_type': x.media_type
            })
            path_lst.append(x.file)
        else:
            print(f"Metadata retrieval failed for rating_key: {i}")
    except Exception as e:
        print(f"Metadata failed. Likely end of range: {e}")

# Display unwatched items
display_unwatched_items(unwatched_items)

# Prompt user if they want to check against local files only
check_local_files = input("\nDo you want to filter the results based on local files only? (yes/no): ").strip().lower()
if check_local_files.startswith('y'):
    found_items = []
    not_found_items = []
    for item in unwatched_items:
        if check_local_file_exists(item['grandparent_title'], item['file']):
            found_items.append(item)
        else:
            not_found_items.append(item)
    
    print("\nFiltered results based on local files:")
    display_unwatched_items(found_items)

delete_files(path_lst)