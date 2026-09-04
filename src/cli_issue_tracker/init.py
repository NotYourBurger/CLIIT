import os
from cli_issue_tracker.storage import issues_dir

def init():
    
    path = issues_dir()
    if os.path.isdir(path):
        print("Project is already Initialized")
        return
    else:
        os.mkdir(path)
    print("Feel free to explore .issues folder")