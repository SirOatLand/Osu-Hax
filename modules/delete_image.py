import os, glob
folders = folder_names=['img1', 'img2', 'img3', 'img4']

for folder in folders:
    files = glob.glob(f'./screenshot/{folder}/*')
    for f in files:
        os.remove(f)