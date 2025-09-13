# Filename: xpulse_final.py
# Requires: pip install flask pandas openpyxl plotly

from flask import Flask, render_template_string, request, redirect
import pandas as pd
from datetime import datetime, timedelta
import os

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
</style>
</head>
<body>
<header>XPulse 🔥</header>

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
<label>Custom Due Date (optional):</label>
<input type="datetime-local" name="due_date"><br>
<button type="submit" class="add-btn">Add Task</button>
</form>
</div>
{% endif %}

<div class="task-board">
  <div class="column"><h3>Pending</h3>
  {% for t in pending %}
    <div class="task" style="border-left:5px solid {{t.color}}">
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
    today = datetime.today()
    week_start = get_week_start(today)
    week_str = week_start.strftime('%Y-%m-%d')
    
    # Pending and Done tasks
    pending = df[(df['WeekStart']==week_str) & (df['Status']=='Pending')]
    done = df[(df['WeekStart']==week_str) & (df['Status']=='Done')]
    
    # Prepare pending tasks list for template
    pending_tasks_list = []
    for _, row in pending.iterrows():
        deadline_dt = pd.to_datetime(row['Deadline'])
        pending_tasks_list.append({
            "id": row['TaskID'],
            "text": row['TaskText'],
            "xp": row['XP'],
            "color": calculate_urgency(deadline_dt)
        })
        
    done_tasks_list = []
    for _, row in done.iterrows():
        done_tasks_list.append({
            "id": row['TaskID'],
            "text": row['TaskText'],
            "xp": row['XP']
        })
    
    # Charts
    pie_data = calculate_pie(df, week_start)
    bar_data = calculate_bar(df)
    
    # Metrics
    completed_count = len(done)
    pending_count = len(pending)
    total_xp = df[(df['WeekStart']==week_str) & (df['Status']=='Done')]['XP'].sum()
    
    # Placeholder token and streak values
    tokens_available = 0
    streak = 0
    show_weekly_reminder = True
    show_bonus_panel = False
    
    return render_template_string(
        HTML_TEMPLATE,
        pending=pending_tasks_list,
        done=done_tasks_list,
        pie_data=pie_data,
        bar_data=bar_data,
        completed_count=completed_count,
        pending_count=pending_count,
        total_xp=total_xp,
        tokens_available=tokens_available,
        streak=streak,
        show_weekly_reminder=show_weekly_reminder,
        show_bonus_panel=show_bonus_panel
    )
def load_tasks():
    if not os.path.exists(EXCEL_FILE):
        cols = ["WeekStart","DateAdded","TaskID","TaskText","Status","Deadline","Priority","XP","StreakWeek","TokenEarned"]
        pd.DataFrame(columns=cols).to_excel(EXCEL_FILE,index=False)
    return pd.read_excel(EXCEL_FILE)

def save_tasks(df):
    df.to_excel(EXCEL_FILE,index=False)

def get_week_start(date):
    return date - timedelta(days=date.weekday())

def generate_task_id(df, week_start):
    existing = df[df['WeekStart']==week_start.strftime('%Y-%m-%d')]['TaskID'].tolist()
    idx = 1
    while f"{week_start.strftime('%Y-%m-%d')}-{idx:03d}" in existing:
        idx +=1
    return f"{week_start.strftime('%Y-%m-%d')}-{idx:03d}"

def calculate_urgency(deadline):
    days_left = max(0,(deadline - datetime.now()).days)
    if days_left<=1: return "red"
    if days_left<=3: return "yellow"
    return "green"

def calculate_task_xp(base_xp, deadline, streak):
    days_left = max(0,(deadline - datetime.now()).days)
    decay_factor = (days_left+1)/7
    streak_factor = min(1 + 0.1*streak, 1 + MAX_STREAK_BONUS)
    return int(base_xp * decay_factor * streak_factor)

def calculate_pie(df, week_start):
    week_str = week_start.strftime('%Y-%m-%d')
    done = len(df[(df['WeekStart']==week_str) & (df['Status']=='Done')])
    pending = len(df[(df['WeekStart']==week_str) & (df['Status']=='Pending')])
    return [done,pending]

def calculate_bar(df):
    today = datetime.today()
    curr_start = get_week_start(today)
    prev_start = curr_start - timedelta(days=7)
    prev_counts = []
    curr_counts = []
    for i in range(7):
        prev_day = prev_start + timedelta(days=i)
        curr_day = curr_start + timedelta(days=i)
        prev_counts.append(len(df[df['DateAdded']==prev_day.strftime('%Y-%m-%d')]))
        curr_counts.append(len(df[df['DateAdded']==curr_day.strftime('%Y-%m-%d')]))
    return {"prev":prev_counts,"curr":curr_counts}
@app.route("/add_task", methods=["POST"])
def add_task():
    df = load_tasks()
    today = datetime.now()
    week_start = get_week_start(today)
    
    task_text = request.form["task_text"]
    due_date_input = request.form.get("due_date")
    
    if due_date_input:
        deadline = datetime.strptime(due_date_input, "%Y-%m-%dT%H:%M")
    else:
        # Default: Saturday 23:59 of this week
        deadline = week_start + timedelta(days=5, hours=23, minutes=59)
    
    task_id = generate_task_id(df, week_start)
    
    new_task = {
        "WeekStart": week_start.strftime("%Y-%m-%d"),
        "DateAdded": today.strftime("%Y-%m-%d"),
        "TaskID": task_id,
        "TaskText": task_text,
        "Status": "Pending",
        "Deadline": deadline.strftime("%Y-%m-%d %H:%M"),
        "Priority": "Medium",
        "XP": BASE_XP,
        "StreakWeek": 0,
        "TokenEarned": 0
    }
    
    df = pd.concat([df, pd.DataFrame([new_task])], ignore_index=True)
    save_tasks(df)
    return redirect("/")
if __name__=="__main__":
    app.run(debug=True)