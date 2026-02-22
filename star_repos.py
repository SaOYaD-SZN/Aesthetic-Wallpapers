"""Script to mass-star popular GitHub repositories.

Requirements:
    pip install requests

Usage:
    python star_repos.py
    Enter your GitHub username and a Personal Access Token with the 'public_repo' scope when prompted.
"""
import requests
from getpass import getpass

username = input("GitHub username: ")
token = getpass("Personal access token (with public_repo scope): ")

repos = [
    "torvalds/linux",
    "octocat/Hello-World",
    "github/gitignore",
    "microsoft/vscode",
    "facebook/react",
    "vuejs/vue",
    "angular/angular",
    "tensorflow/tensorflow",
    "twbs/bootstrap",
    "ohmyzsh/ohmyzsh",
    "freeCodeCamp/freeCodeCamp",
    "sindresorhus/awesome",
    "kamranahmedse/developer-roadmap",
    "EbookFoundation/free-programming-books",
    "jwasham/coding-interview-university",
    "donnemartin/system-design-primer",
]

headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github.v3+json"
}

for repo in repos:
    url = f"https://api.github.com/user/starred/{repo}"
    r = requests.put(url, headers=headers)
    if r.status_code == 204:
        print(f"✅ Starred {repo}")
    else:
        print(f"❌ Failed to star {repo}: {r.status_code} - {r.text}")
