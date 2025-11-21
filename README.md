# Client task manager

A lightweight Flask app to manage client tasks with monthly planning and billing summaries.

## Features
- Track tasks by client with statuses: planned, doing, to review, reviewing, published.
- Plan work by month and optional scheduled date.
- View tasks grouped by planned month.
- Billing view shows tasks published in a given month.

## Preview locally
1. (Optional) Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the server:
   ```bash
   python app.py
   ```
   The Flask app listens on `http://0.0.0.0:5000` by default.
4. Visit the UI at http://localhost:5000.
   - Use the form at the top to create tasks for a client and month.
   - Update status inline to move tasks through planned → doing → to review → reviewing → published.
   - Open the **Billing** link in the navbar to see tasks completed in a selected month.

The SQLite database file (`tasks.db`) is created automatically in the project root; delete it to start fresh.
