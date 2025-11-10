# 🧠 Derived Mind – Conversation Analysis System

## 🚀 Setup & Run Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/<your-username>/derived-mind.git
cd derived-mind
```

### 2. Create and Activate Virtual Environment
```
pip install -r requirements.txt
```

### 3. Install Dependencies
```
python -m venv venv
venv\Scripts\activate        # On Windows
# or
source venv/bin/activate     # On macOS/Linux
```

### 4. Run Database Migrations
```
python manage.py makemigrations
python manage.py migrate
```

### 5. Start the Development Server
```
python manage.py runserver
```

### Background Task (Analytics Updater)

The project uses Django Background Tasks to analyze conversations automatically.

Start the Background Task Runner

Open a new terminal (while the server is running) and execute:
```
python manage.py process_tasks
```
This will continuously run background jobs such as updating analytics every night.

### API Endpoints Overview

| Endpoint   | Method | Description                                 |
| ---------  | ------ | ------------------------------------------- |
| `/upload`  | `POST` | Upload new conversation data in JSON format |
| `/report`  | `GET`  | Fetch all analyzed conversation reports     |
| `/analyse` | `POST` | To analyse a conversation manually          |


### Notes

The analytics updater runs automatically for newly added conversations.

Ensure both the Django server and the background task process are running simultaneously.