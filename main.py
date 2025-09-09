# Filename: xpulse.py
# Requires: pip install flask pandas openpyxl plotly

from flask import Flask, render_template_string, request, redirect
import pandas as pd
from datetime import datetime, timedelta
import os
import random

app = Flask(__name__)

# Excel file path
EXCEL_FILE = "tasks.xlsx"

# Constants
MAX_WEEKLY_TOKENS = 2
MAX_MONTHLY_TOKENS = 5
XP_PENALTY_ROLLOVER = 0.2  # 20% penalty

# HTML template (internal CSS + JS included)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>XPulse</title>
<style>
body { font-family: Arial; margin: 0; padding: 0; background: linear-gradient(120deg,#2980b9,#6dd5fa); color:#fff; }
header { padding: 20px; text-align:center; font-size:2em; font-weight:bold; }
#stats { padding: 20px; display:flex; justify-content:space-around; }
.task-board { display:flex; justify-content:space-around; padding:20px; }
.column { background: rgba(255,255,255,0.1); border-radius:10px; padding:10px; width:30%; min-height:200px; }
.task { background: rgba(255,255,255,0.2); margin:5px; padding:5px; border-radius:5px; cursor:pointer; transition: transform 0.2s; }
.task:hover { transform: scale(1.05); }
button { padding:5px 10px; margin-top:5px; cursor:pointer; border:none; border-radius:5px; }
#bonus-panel, #weekly-reminder { background: rgba(0,0,0,0.3); padding:15px; margin:10px; border-radius:10px; }
canvas { background: rgba(255,255,255,0.1); border-radius:10px; }
</style>
</head>
<body>
<header>XPulse 🔥</header>

<div id="stats">
  <div>
    <h3>Progress</h3>
    <canvas id="pieChart" width="150" height="150"></canvas>
  </div>
  <div>
    <h3>Week Comparison</h3>
    <canvas id="barChart" width="200" height="150"></canvas>
  </div>
</div>

{% if show_weekly_reminder %}
<div id="weekly-reminder">
<h3>🌟 New week, new goals!</h3>
<form method="POST" action="/add_task">
<textarea name="task_text" required></textarea><br>
<button type="submit">Add Task</button>
</form>
</div>
{% endif %}

<div class="task-board">
  <div class="column"><h3>Pending</h3>
  {% for t in pending %}<div class="task">{{t}}</div>{% endfor %}</div>
  <div class="column"><h3>In Progress</h3>
  {% for t in inprogress %}<div class="task">{{t}}</div>{% endfor %}</div>
  <div class="column"><h3>Done</h3>
  {% for t in done %}<div class="task">{{t}}</div>{% endfor %}</div>
</div>

{% if show_bonus_panel %}
<div id="bonus-panel">
<h3>🎉 Early Finish! Add tasks for remaining days:</h3>
<form method="POST" action="/add_bonus">
<textarea name="task_text" required></textarea><br>
<button type="submit">Add Bonus Task</button>
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

# ----------------------
# Helper functions
# ----------------------
def load_tasks():
    if not os.path.exists(EXCEL_FILE):
        df = pd.DataFrame(columns=["WeekStart","DateAdded","TaskNumber","TaskText","Status","Deadline","Priority","Notes","XP"])
        df.to_excel(EXCEL_FILE,index=False)
    df = pd.read_excel(EXCEL_FILE)
    return df

def save_tasks(df):
    df.to_excel(EXCEL_FILE,index=False)

def get_week_start(date):
    return date - timedelta(days=date.weekday())

def assign_task_number(df, week_start):
    week_tasks = df[df['WeekStart']==week_start]
    return len(week_tasks)+1

def pending_tasks(df, week_start):
    return df[(df['WeekStart']==week_start) & (df['Status']=='Pending')]['TaskText'].tolist()

def inprogress_tasks(df, week_start):
    return df[(df['WeekStart']==week_start) & (df['Status']=='InProgress')]['TaskText'].tolist()

def done_tasks(df, week_start):
    return df[(df['WeekStart']==week_start) & (df['Status']=='Completed')]['TaskText'].tolist()

def calculate_pie(df, week_start):
    done = len(df[(df['WeekStart']==week_start) & (df['Status']=='Completed')])
    pending = len(df[(df['WeekStart']==week_start) & (df['Status']!='Completed')])
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
        prev_counts.append(len(df[(df['DateAdded']==prev_day.strftime('%Y-%m-%d'))]))
        curr_counts.append(len(df[(df['DateAdded']==curr_day.strftime('%Y-%m-%d'))]))
    return {"prev":prev_counts,"curr":curr_counts}

# ----------------------
# Routes
# ----------------------
@app.route("/", methods=["GET"])
def index():
    df = load_tasks()
    today = datetime.today()
    week_start = get_week_start(today)
    show_weekly_reminder = not any(df['WeekStart']==week_start)
    pending = pending_tasks(df, week_start)
    inprogress = inprogress_tasks(df, week_start)
    done = done_tasks(df, week_start)
    pie_data = calculate_pie(df, week_start)
    bar_data = calculate_bar(df)
    
    # Show bonus panel if all tasks done
    show_bonus_panel = len(pending)==0 and len(inprogress)==0 and len(done)>0 and not show_weekly_reminder

    return render_template_string(HTML_TEMPLATE,
                                  pending=pending,
                                  inprogress=inprogress,
                                  done=done,
                                  pie_data=pie_data,
                                  bar_data=bar_data,
                                  show_weekly_reminder=show_weekly_reminder,
                                  show_bonus_panel=show_bonus_panel)

@app.route("/add_task", methods=["POST"])
def add_task():
    df = load_tasks()
    today = datetime.today()
    week_start = get_week_start(today)
    task_text = request.form["task_text"]
    task_number = assign_task_number(df, week_start)
    new_task = {
        "WeekStart": week_start,
        "DateAdded": today,
        "TaskNumber": task_number,
        "TaskText": task_text,
        "Status": "Pending",
        "Deadline": week_start+timedelta(days=6),
        "Priority": "Medium",
        "Notes": "",
        "XP": 50
    }
    df = df.append(new_task, ignore_index=True)
    save_tasks(df)
    return redirect("/")

@app.route("/add_bonus", methods=["POST"])
def add_bonus():
    df = load_tasks()
    today = datetime.today()
    week_start = get_week_start(today)
    task_text = request.form["task_text"]
    task_number = assign_task_number(df, week_start)
    new_task = {
        "WeekStart": week_start,
        "DateAdded": today,
        "TaskNumber": task_number,
        "TaskText": task_text,
        "Status": "Pending",
        "Deadline": week_start+timedelta(days=6),
        "Priority": "Medium",
        "Notes": "Bonus task",
        "XP": 50
    }
    df = df.append(new_task, ignore_index=True)
    save_tasks(df)
    return redirect("/")

# ----------------------
# Run
# ----------------------
if __name__=="__main__":
    app.run(debug=True)
