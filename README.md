# PixShare

**PixShare** is a full-stack photo sharing web application built with **Flask**, **SQLite**, and **Vanilla JavaScript**. Users can upload, explore, rate, and comment on images. Creators/admins can manage content and users.

---

## Features

- Browse and search images by title, caption, location, and people.
- Upload images with metadata (title, caption, location, people).
- Rate images and leave comments.
- Creator/Admin dashboard to manage users and images.
- JWT-based authentication and role-based access control.
- Responsive UI with HTML, CSS, and JavaScript.

---

## Tech Stack

- **Backend:** Flask, Python, SQLite
- **Frontend:** HTML, CSS, JavaScript
- **Authentication:** JWT
- **Containerization:** Docker, Docker Compose


## Installation

1. Clone the repository:
git clone https://github.com/Mujeeb117/PIXSHARE-APP.git
cd PIXSHARE-APP

2. Create a Python virtual environment:
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

3.Install backend dependencies:
pip install -r backend/requirements.txt

# Usage

1. Start the backend server:
python backend/app.py

2. Open frontend:
Open frontend/index.html in your browser


# Or use Docker Compose to run both services:
docker-compose up --build


