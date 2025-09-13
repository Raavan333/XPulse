# Filename: xpulse_fixed_timezone.py
# Requires: pip install flask pandas openpyxl plotly pytz

from flask import Flask, render_template_string, request, redirect
import pandas as pd
from datetime import datetime, timedelta
import os
import pytz

app = Flask(__name__)

# -----------------------
# Config / Constants
# -----------------------
EXCEL_FILE = "tasks.xlsx"
BASE_XP = 50
WEEKLY_TOKEN_LIMIT = 1
MONTHLY_XP_TOKEN_LIMIT = 1
MAX_STREAK_BONUS = 0.5  # 50% cap on streak bonus
TOKEN_XP_VALUE = 200    # 1 token = 200 XP

# Timezone setup
IST = pytz.timezone('Asia/Kolkata')

def get_ist_now():
    """Get current time in IST"""
    return datetime.now(IST)

def get_ist_today():
    """Get current date in IST"""
    return get_ist_now().date()

# -----------------------
# HTML Template (Dark Theme)
# -----------------------
HTML_TEMPLATE = """ 
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>XPulse</title>
<style>
body { font-family: 'Consolas', monospace; margin:0; padding:0; background:#1e1e1e; color:#d4d4d4; }
header { padding:20px; text-align:center; font-size:2em; font-weight:bold; color:#61dafb; }
#stats { display:flex; justify-content:space-around; padding:15px; flex-wrap:wrap; }
.stat-card { background:#2d2d2d; padding:10px 20px; border-radius:8px; text-align:center; flex:1; margin:5px;}
.task-board { display:flex; justify-content:space-around; padding:20px; flex-wrap:wrap; }
.column { background: #2d2d2d; border-radius:10px; padding:10px; width:45%; min-height:200px; margin:5px; }
.task { background: #3c3c3c; margin:5px; padding:8px; border-radius:5px; cursor:pointer; display:flex; justify-content:space-between; }
.task button { background:#61dafb; color:#1e1e1e; border:none; border-radius:4px; cursor:pointer; }
textarea, input[type=datetime-local] { width:90%; padding:5px; border-radius:4px; border:none; margin-bottom:5px; }
button.add-btn { background:#0db39e; color:#fff; padding:8px 12px; border:none; border-radius:5px; cursor:pointer; }
#charts { display:flex; justify-content:space-around; flex-wrap:wrap; padding:10px; }
canvas { background:#2d2d2d; border-radius:8px; }
#bonus-panel, #weekly-reminder { background: #2d2d2d; padding:15px; margin:10px; border-radius:10px; }
.priority-selector { display: inline-flex; justify-content: flex-start; align-items: center; gap: 20px; padding: 5px 0; }
.priority-item { display: flex; align-items: center; }
.priority-circle { width:15px; height:15px; border-radius:50%; margin-right: 8px; }
.debug-info { background: #2d2d2d; padding: 10px; margin: 10px; border-radius: 5px; font-size: 0.8em; color: #888; }
</style>
</head>
<body>
<header>XPulse 🔥</header>

<!-- Debug info to show current dates -->
<div class="debug-info">
  <strong>Debug Info:</strong> Current IST Time: {{current_ist_time}} | Week Start: {{week_start_debug}} | Week End: {{week_end_debug}}
</div>

<div id="stats">
  <div class="stat-card">
    <h4>✅ Completed</h4>
    <p>{{completed_count}}</p>
  </div>
  <div class="stat-card">
    <h4>⏳ Pending</h4>
    <p>{{pending_count}}</p>
  </div>
  <div class="stat-card">
    <h4>💎 XP Earned</h4>
    <p>{{total_xp}}</p>
  </div>
  <div class="stat-card">
    <h4>🎫 Tokens</h4>
    <p>{{tokens_available}}</p>
  </div>
  <div class="stat-card">
    <h4>🔥 Streak</h4>
    <p>{{streak}}</p>
  </div>
</div>

<div id="charts">
  <div><canvas id="pieChart" width="200" height="200"></canvas></div>
  <div><canvas id="barChart" width="400" height="200"></canvas></div>
</div>

{% if show_weekly_reminder %}
<div id="weekly-reminder">
<h3>🌟 Add New Task (Sat/Sun)</h3>
<form method="POST" action="/add_task">
<textarea name="task_text" placeholder="Task description" required></textarea><br>

<!-- Priority Radio Buttons with color indicators -->
<div class="priority-selector">
  <div class="priority-item">
    <input type="radio" id="low" name="priority" value="Low" checked>
    <label for="low" style="color:#2ecc71;">
      <span class="priority-circle" style="background-color:#2ecc71;"></span> Low
    </label>
  </div>
  <div class="priority-item">
    <input type="radio" id="medium" name="priority" value="Medium">
    <label for="medium" style="color:#f39c12;">
      <span class="priority-circle" style="background-color:#f39c12;"></span> Medium
    </label>
  </div>
  <div class="priority-item">
    <input type="radio" id="high" name="priority" value="High">
    <label for="high" style="color:#e74c3c;">
      <span class="priority-circle" style="background-color:#e74c3c;"></span> High
    </label>
  </div>
</div>
<br>
<label>Custom Due Date (optional):</label>
<input type="datetime-local" name="due_date"><br>
<button type="submit" class="add-btn">Add Task</button>
</form>
</div>
{% endif %}

<div class="task-board">
  <div class="column"><h3>Pending</h3>
  {% for t in pending %}
    <div class="task" style="border-left:5px solid {{t.color}}; background-color: {{ t.priority_color }}">
      <span>{{t.text}} (XP: {{t.xp}})</span>
      <form method="POST" action="/complete_task" style="display:inline;">
        <input type="hidden" name="task_id" value="{{t.id}}">
        <button type="submit">✔</button>
      </form>
    </div>
  {% endfor %}
  </div>
  <div class="column"><h3>Done</h3>
  {% for t in done %}
    <div class="task" style="border-left:5px solid #2ecc71;">
      <span>{{t.text}} (XP: {{t.xp}})</span>
    </div>
  {% endfor %}
  </div>
</div>

{% if show_bonus_panel %}
<div id="bonus-panel">
<h3>🎉 Bonus / Early Finish Tasks</h3>
<form method="POST" action="/add_bonus">
<textarea name="task_text" placeholder="Bonus task" required></textarea><br>
<label>Custom Due Date (optional):</label>
<input type="datetime-local" name="due_date"><br>
<button type="submit" class="add-btn">Add Bonus Task</button>
</form>
</div>
{% endif %}

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
var pieData = {{ pie_data }};
var barData = {{ bar_data }};
new Chart(document.getElementById("pieChart"), {type:'pie',data:{labels:['Done','Pending'],datasets:[{data:pieData,backgroundColor:['#2ecc71','#e74c3c']}]},options:{}});
new Chart(document.getElementById("barChart"), {type:'bar',data:{labels:['Sun','Mon','Tue','Wed','Thu','Fri','Sat'],datasets:[{label:'Prev Week',data:barData.prev,backgroundColor:'#3498db'},{label:'This Week',data:barData.curr,backgroundColor:'#f1c40f'}]},options:{scales:{y:{beginAtZero:true}}}});
</script>
</body>
</html>
"""

# -----------------------
# Helper Functions
# -----------------------

@app.route("/", methods=["GET"])
def index():
    df = load_tasks()
    today = get_ist_now()
    week_start = get_week_start(today)
    week_str = week_start.strftime('%Y-%m-%d')
    
    # Debug info
    week_end = week_start + timedelta(days=6, hours=23, minutes=59)
    
    # Pending and Done tasks for current week
    pending = df[(df['WeekStart']==week_str) & (df['Status']=='Pending')]
    done = df[(df['WeekStart']==week_str) & (df['Status']=='Completed')]
    
    # Convert tasks into list of dicts for the template
    pending_tasks_list = []
    done_tasks_list = []
    
    for _, row in pending.iterrows():
        pending_tasks_list.append({
            'id': row['TaskID'],
            'text': row['TaskText'],
            'xp': row['XP'],
            'priority_color': get_priority_color(row['Priority']),
            'color': calculate_urgency(datetime.strptime(row['Deadline'], "%Y-%m-%d %H:%M"))
        })

    for _, row in done.iterrows():
        done_tasks_list.append({
            'id': row['TaskID'],
            'text': row['TaskText'],
            'xp': row['XP'],
            'priority_color': get_priority_color(row['Priority']),
            'color': "#2ecc71"  # green for completed
        })
    
    # Determine if we should show weekly reminder (Saturday or Sunday)
    show_weekly_reminder = should_show_weekly_reminder(today)
    
    # Determine if we should show bonus panel
    show_bonus_panel = should_show_bonus_panel(today, pending_tasks_list)
    
    return render_template_string(HTML_TEMPLATE, 
                                  completed_count=len(done),
                                  pending_count=len(pending),
                                  total_xp=calculate_total_xp(done, pending),
                                  tokens_available=calculate_tokens_available(),
                                  streak=calculate_streak(done),
                                  show_weekly_reminder=show_weekly_reminder,
                                  pending=pending_tasks_list,
                                  done=done_tasks_list,
                                  show_bonus_panel=show_bonus_panel,
                                  pie_data=[len(done), len(pending)],
                                  bar_data=calculate_weekly_xp_data(df, week_start),
                                  current_ist_time=today.strftime('%Y-%m-%d %H:%M:%S IST'),
                                  week_start_debug=week_start.strftime('%Y-%m-%d'),
                                  week_end_debug=week_end.strftime('%Y-%m-%d'))

# -----------------------
# Add Task (POST)
# -----------------------

@app.route("/add_task", methods=["POST"])
def add_task():
    df = load_tasks()
    today = get_ist_now()
    
    # Get the start of the current week (Sunday)
    week_start = get_week_start(today)
    
    # Priority & Task Details
    priority = request.form.get("priority", "Medium")
    task_text = request.form["task_text"]
    
    # Custom Due Date (if provided)
    due_date_input = request.form.get("due_date")
    
    if due_date_input:
        deadline = datetime.strptime(due_date_input, "%Y-%m-%dT%H:%M")
        # Convert to IST if needed
        deadline = IST.localize(deadline)
    else:
        # Default deadline: Saturday at 23:59 of this week
        deadline = week_start + timedelta(days=6, hours=23, minutes=59)
        deadline = IST.localize(deadline.replace(tzinfo=None))
    
    # Generate Task ID
    task_id = generate_task_id(df, week_start)
    
    # New task creation
    new_task = {
        "WeekStart": week_start.strftime("%Y-%m-%d"),
        "DateAdded": today.strftime("%Y-%m-%d"),
        "TaskID": task_id,
        "TaskText": task_text,
        "Status": "Pending",
        "Deadline": deadline.strftime("%Y-%m-%d %H:%M"),
        "Priority": priority,
        "XP": BASE_XP,
        "StreakWeek": 0,
        "TokenEarned": 0
    }
    
    # Save task to DataFrame
    df = pd.concat([df, pd.DataFrame([new_task])], ignore_index=True)
    save_tasks(df)
    
    return redirect("/")

@app.route("/complete_task", methods=["POST"])
def complete_task():
    df = load_tasks()
    task_id = request.form["task_id"]
    
    # Find and update the task
    mask = df['TaskID'] == task_id
    if mask.any():
        df.loc[mask, 'Status'] = 'Completed'
        df.loc[mask, 'DateCompleted'] = get_ist_now().strftime("%Y-%m-%d %H:%M")
        save_tasks(df)
    
    return redirect("/")

@app.route("/add_bonus", methods=["POST"])
def add_bonus():
    df = load_tasks()
    today = get_ist_now()
    
    # Get the start of the current week (Sunday)
    week_start = get_week_start(today)
    
    task_text = request.form["task_text"]
    
    # Custom Due Date (if provided)
    due_date_input = request.form.get("due_date")
    
    if due_date_input:
        deadline = datetime.strptime(due_date_input, "%Y-%m-%dT%H:%M")
        deadline = IST.localize(deadline)
    else:
        # Default deadline: Saturday at 23:59 of this week
        deadline = week_start + timedelta(days=6, hours=23, minutes=59)
        deadline = IST.localize(deadline.replace(tzinfo=None))
    
    # Generate Task ID
    task_id = generate_task_id(df, week_start)
    
    # Bonus task creation
    new_task = {
        "WeekStart": week_start.strftime("%Y-%m-%d"),
        "DateAdded": today.strftime("%Y-%m-%d"),
        "TaskID": task_id,
        "TaskText": f"[BONUS] {task_text}",
        "Status": "Pending",
        "Deadline": deadline.strftime("%Y-%m-%d %H:%M"),
        "Priority": "Medium",
        "XP": int(BASE_XP * 1.5),
        "StreakWeek": 0,
        "TokenEarned": 0
    }
    
    # Save task to DataFrame
    df = pd.concat([df, pd.DataFrame([new_task])], ignore_index=True)
    save_tasks(df)
    
    return redirect("/")

# -----------------------
# Utility Functions
# -----------------------

def load_tasks():
    if os.path.exists(EXCEL_FILE):
        df = pd.read_excel(EXCEL_FILE)
        if 'DateCompleted' not in df.columns:
            df['DateCompleted'] = ''
        return df
    else:
        return pd.DataFrame(columns=['WeekStart', 'DateAdded', 'TaskID', 'TaskText', 'Status', 'Deadline', 'Priority', 'XP', 'StreakWeek', 'TokenEarned', 'DateCompleted'])

def save_tasks(df):
    df.to_excel(EXCEL_FILE, index=False)

def calculate_urgency(deadline):
    now = get_ist_now().replace(tzinfo=None)  # Remove timezone for comparison
    if deadline < now:
        return '#e74c3c'  # Red if overdue
    elif (deadline - now).days <= 1:
        return "#f39c12"  # Yellow if due soon
    else:
        return '#2ecc71'  # Green if not urgent

def get_priority_color(priority):
    colors = {
        "Low": "#2ecc71",      # green
        "Medium": "#f39c12",   # orange
        "High": "#e74c3c"      # red
    }
    return colors.get(priority, "#3c3c3c")

def calculate_total_xp(done, pending):
    done_xp = done['XP'].sum() if len(done) > 0 else 0
    pending_xp = pending['XP'].sum() if len(pending) > 0 else 0
    return done_xp + pending_xp

def calculate_tokens_available():
    if not os.path.exists(EXCEL_FILE):
        return 0  # No file, so no tokens
    
    df = pd.read_excel(EXCEL_FILE)
    if 'TokenEarned' not in df.columns:
        return 0  # No token info column
    
    # Consider tokens from completed tasks only
    completed_tokens = df[df['Status'] == 'Completed']['TokenEarned']
    
    if completed_tokens.empty:
        return 0
    
    # Return the sum or max tokens earned (choose your logic)
    total_tokens = completed_tokens.sum()
    return total_tokens


def calculate_streak(done):
    return len(done)

def calculate_weekly_xp_data(df, week_start):
    current_week_xp = df[df['WeekStart'] == week_start.strftime('%Y-%m-%d')]['XP'].sum()
    previous_week_start = (week_start - timedelta(days=7)).strftime('%Y-%m-%d')
    previous_week_xp = df[df['WeekStart'] == previous_week_start]['XP'].sum()
    
    return {
        'prev': [0, 0, 0, 0, 0, 0, previous_week_xp],
        'curr': [0, 0, 0, 0, 0, 0, current_week_xp]
    }

def generate_task_id(df, week_start):
    week_tasks = df[df['WeekStart'] == week_start.strftime('%Y-%m-%d')]
    task_count = len(week_tasks) + 1
    task_id = f"{week_start.strftime('%Y-%m-%d')}-{task_count}"
    return task_id

def get_week_start(date):
    """Returns the start of the week (Sunday) for the given date in IST."""
    # Make sure we're working with a timezone-naive datetime for calculation
    if hasattr(date, 'tzinfo') and date.tzinfo is not None:
        date = date.replace(tzinfo=None)
    
    # Calculate days since Sunday
    days_since_sunday = (date.weekday() + 1) % 7
    start_of_week = date - timedelta(days=days_since_sunday)
    # Reset to start of day
    return start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)

def should_show_weekly_reminder(today):
    """Show weekly reminder only on Saturday and Sunday"""
    return today.weekday() in [5, 6]  # Saturday=5, Sunday=6

def should_show_bonus_panel(today, pending_tasks):
    """Show bonus panel only when:
       1. It's Monday to Friday (weekday 0 to 4)
       2. All tasks are completed (no pending tasks)
    """
    is_weekday = today.weekday() in range(0, 5)  # Monday=0,... Friday=4
    no_pending_tasks = len(pending_tasks) == 0
    return is_weekday and no_pending_tasks


if __name__ == "__main__":
    app.run(debug=True)
