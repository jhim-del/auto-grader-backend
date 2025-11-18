from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
import os
import zipfile
import csv
import io
from datetime import datetime
import json
import statistics

# Import grading engine
from grading_engine import grade_submission

app = FastAPI(title="Auto-Grader API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup with Railway Volume support
DATA_DIR = os.getenv("DATA_DIR", ".")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "auto_grader.db")
print(f"[DB] Database path: {DB_PATH}")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Competitions table
    c.execute('''CREATE TABLE IF NOT EXISTS competitions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  description TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Assignments table
    c.execute('''CREATE TABLE IF NOT EXISTS assignments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  competition_id INTEGER,
                  name TEXT NOT NULL,
                  prompt TEXT NOT NULL,
                  FOREIGN KEY (competition_id) REFERENCES competitions(id))''')
    
    # Participants table
    c.execute('''CREATE TABLE IF NOT EXISTS participants
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  competition_id INTEGER,
                  name TEXT NOT NULL,
                  email TEXT,
                  student_id TEXT,
                  FOREIGN KEY (competition_id) REFERENCES competitions(id))''')
    
    # Submissions table
    c.execute('''CREATE TABLE IF NOT EXISTS submissions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  competition_id INTEGER,
                  participant_id INTEGER,
                  assignment_id INTEGER,
                  prompt_text TEXT,
                  submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  status TEXT DEFAULT 'pending',
                  score REAL,
                  feedback TEXT,
                  grading_details TEXT,
                  FOREIGN KEY (competition_id) REFERENCES competitions(id),
                  FOREIGN KEY (participant_id) REFERENCES participants(id),
                  FOREIGN KEY (assignment_id) REFERENCES assignments(id))''')
    
    conn.commit()
    conn.close()

init_db()

# Pydantic models
class Competition(BaseModel):
    name: str
    description: Optional[str] = None

class Assignment(BaseModel):
    name: str
    prompt: str

class ParticipantUpload(BaseModel):
    name: str
    email: Optional[str] = None
    student_id: Optional[str] = None

# Helper functions
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ==================== COMPETITION ENDPOINTS ====================

@app.get("/")
async def root():
    return {"message": "Auto-Grader API", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/competitions")
async def create_competition(comp: Competition):
    """Create a new competition"""
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO competitions (name, description) VALUES (?, ?)",
              (comp.name, comp.description))
    comp_id = c.lastrowid
    conn.commit()
    conn.close()
    return {"id": comp_id, "name": comp.name, "description": comp.description}

@app.get("/competitions")
async def list_competitions():
    """List all competitions"""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM competitions ORDER BY created_at DESC")
    competitions = [dict(row) for row in c.fetchall()]
    conn.close()
    return competitions

@app.get("/competitions/{competition_id}")
async def get_competition(competition_id: int):
    """Get competition details"""
    conn = get_db()
    c = conn.cursor()
    
    # Get competition
    c.execute("SELECT * FROM competitions WHERE id = ?", (competition_id,))
    comp = c.fetchone()
    if not comp:
        conn.close()
        raise HTTPException(status_code=404, detail="Competition not found")
    
    # Get assignments
    c.execute("SELECT * FROM assignments WHERE competition_id = ?", (competition_id,))
    assignments = [dict(row) for row in c.fetchall()]
    
    # Get participants
    c.execute("SELECT * FROM participants WHERE competition_id = ?", (competition_id,))
    participants = [dict(row) for row in c.fetchall()]
    
    # Get submissions
    c.execute("SELECT * FROM submissions WHERE competition_id = ?", (competition_id,))
    submissions = [dict(row) for row in c.fetchall()]
    
    conn.close()
    
    return {
        **dict(comp),
        "assignments": assignments,
        "participants": participants,
        "submissions": submissions
    }

# ==================== ASSIGNMENT ENDPOINTS ====================

@app.post("/competitions/{competition_id}/assignments")
async def create_assignment(competition_id: int, assignment: Assignment):
    """Create assignment for competition"""
    conn = get_db()
    c = conn.cursor()
    
    # Verify competition exists
    c.execute("SELECT id FROM competitions WHERE id = ?", (competition_id,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Competition not found")
    
    c.execute("INSERT INTO assignments (competition_id, name, prompt) VALUES (?, ?, ?)",
              (competition_id, assignment.name, assignment.prompt))
    assignment_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return {"id": assignment_id, "name": assignment.name, "prompt": assignment.prompt}

@app.get("/competitions/{competition_id}/assignments")
async def get_assignments(competition_id: int):
    """Get all assignments for competition"""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM assignments WHERE competition_id = ?", (competition_id,))
    assignments = [dict(row) for row in c.fetchall()]
    conn.close()
    return assignments

# ==================== PARTICIPANT ENDPOINTS ====================

@app.post("/competitions/{competition_id}/participants/upload")
async def upload_participants(competition_id: int, file: UploadFile = File(...)):
    """Upload participants from CSV file"""
    conn = get_db()
    c = conn.cursor()
    
    # Verify competition exists
    c.execute("SELECT id FROM competitions WHERE id = ?", (competition_id,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Competition not found")
    
    # Read CSV
    content = await file.read()
    csv_file = io.StringIO(content.decode('utf-8'))
    reader = csv.DictReader(csv_file)
    
    participants_added = 0
    for row in reader:
        name = row.get('name') or row.get('이름')
        email = row.get('email') or row.get('이메일')
        student_id = row.get('student_id') or row.get('학번')
        
        if name:
            c.execute("""INSERT INTO participants (competition_id, name, email, student_id)
                        VALUES (?, ?, ?, ?)""",
                     (competition_id, name, email, student_id))
            participants_added += 1
    
    conn.commit()
    conn.close()
    
    return {"message": f"{participants_added} participants added successfully"}

@app.get("/competitions/{competition_id}/participants")
async def get_participants(competition_id: int):
    """Get all participants for competition"""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM participants WHERE competition_id = ?", (competition_id,))
    participants = [dict(row) for row in c.fetchall()]
    conn.close()
    return participants

# ==================== SUBMISSION ENDPOINTS ====================

@app.post("/competitions/{competition_id}/submissions/upload")
async def upload_submissions(competition_id: int, file: UploadFile = File(...)):
    """Upload submissions from ZIP file"""
    conn = get_db()
    c = conn.cursor()
    
    # Verify competition exists
    c.execute("SELECT id FROM competitions WHERE id = ?", (competition_id,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Competition not found")
    
    # Get assignments
    c.execute("SELECT * FROM assignments WHERE competition_id = ?", (competition_id,))
    assignments = {row['name']: dict(row) for row in c.fetchall()}
    
    # Get participants
    c.execute("SELECT * FROM participants WHERE competition_id = ?", (competition_id,))
    participants = {row['name']: dict(row) for row in c.fetchall()}
    
    # Read ZIP file
    content = await file.read()
    zip_file = zipfile.ZipFile(io.BytesIO(content))
    
    submissions_added = 0
    skipped = []
    
    for file_name in zip_file.namelist():
        # Try to decode filename (handle Korean filenames)
        try:
            # Try UTF-8 first
            decoded_name = file_name
        except:
            try:
                # Try CP949 (Korean Windows encoding)
                decoded_name = file_name.encode('cp437').decode('utf-8')
            except:
                decoded_name = file_name
        
        if decoded_name.endswith('.txt'):
            # Parse filename: participantname_assignmentname.txt
            base_name = os.path.splitext(decoded_name)[0]
            parts = base_name.split('_')
            
            if len(parts) >= 2:
                participant_name = parts[0]
                assignment_name = '_'.join(parts[1:])
                
                # Find participant and assignment
                participant = participants.get(participant_name)
                assignment = assignments.get(assignment_name)
                
                if participant and assignment:
                    # Read prompt text
                    prompt_text = zip_file.read(file_name).decode('utf-8')
                    
                    # Insert submission
                    c.execute("""INSERT INTO submissions 
                                (competition_id, participant_id, assignment_id, prompt_text, status)
                                VALUES (?, ?, ?, ?, 'pending')""",
                             (competition_id, participant['id'], assignment['id'], prompt_text))
                    submissions_added += 1
                else:
                    skipped.append(f"{participant_name}_{assignment_name} (participant: {participant_name in participants}, assignment: {assignment_name in assignments})")
    
    conn.commit()
    conn.close()
    
    result = {"message": f"{submissions_added} submissions uploaded successfully"}
    if skipped:
        result["skipped"] = skipped
    return result

@app.get("/competitions/{competition_id}/submissions")
async def get_submissions(competition_id: int):
    """Get all submissions for competition"""
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT s.*, p.name as participant_name, a.name as assignment_name
        FROM submissions s
        JOIN participants p ON s.participant_id = p.id
        JOIN assignments a ON s.assignment_id = a.id
        WHERE s.competition_id = ?
        ORDER BY s.submitted_at DESC
    """, (competition_id,))
    submissions = [dict(row) for row in c.fetchall()]
    conn.close()
    return submissions

# ==================== GRADING ENDPOINTS ====================

async def grade_all_submissions_background(competition_id: int):
    """Background task to grade all pending submissions"""
    print(f"[GRADING] Background task started for competition {competition_id}")
    
    conn = get_db()
    c = conn.cursor()
    
    # Get all pending submissions
    c.execute("""
        SELECT s.*, a.prompt as assignment_prompt
        FROM submissions s
        JOIN assignments a ON s.assignment_id = a.id
        WHERE s.competition_id = ? AND s.status = 'pending'
    """, (competition_id,))
    
    submissions = c.fetchall()
    total = len(submissions)
    
    print(f"[GRADING] Found {total} pending submissions")
    
    for idx, submission in enumerate(submissions, 1):
        submission_id = submission['id']
        
        print(f"[GRADING] Processing {idx}/{total}: submission_id={submission_id}")
        
        # Update status to grading
        c.execute("UPDATE submissions SET status = 'grading' WHERE id = ?", (submission_id,))
        conn.commit()
        
        try:
            # Grade submission
            result = grade_submission(
                task_prompt=submission['assignment_prompt'],
                user_prompt=submission['prompt_text']
            )
            
            # Update with results
            c.execute("""
                UPDATE submissions 
                SET status = 'completed', 
                    score = ?, 
                    feedback = ?,
                    grading_details = ?
                WHERE id = ?
            """, (result['average_score'], result['feedback'], 
                  json.dumps(result['detailed_scores']), submission_id))
            
            print(f"[GRADING] ✓ Completed {idx}/{total}: score={result['average_score']}")
            
        except Exception as e:
            print(f"[GRADING_ERROR] ✗ Failed {idx}/{total}: {str(e)}")
            c.execute("""
                UPDATE submissions 
                SET status = 'error', 
                    feedback = ?
                WHERE id = ?
            """, (f"Grading failed: {str(e)}", submission_id))
        
        conn.commit()
    
    conn.close()
    print(f"[GRADING] Background task completed for competition {competition_id}")

@app.post("/competitions/{competition_id}/grade")
async def start_grading(competition_id: int, background_tasks: BackgroundTasks):
    """Start grading all pending submissions"""
    conn = get_db()
    c = conn.cursor()
    
    # Verify competition exists
    c.execute("SELECT id FROM competitions WHERE id = ?", (competition_id,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Competition not found")
    
    # Count pending submissions
    c.execute("SELECT COUNT(*) as count FROM submissions WHERE competition_id = ? AND status = 'pending'",
              (competition_id,))
    count = c.fetchone()['count']
    conn.close()
    
    if count == 0:
        return {"message": "No pending submissions to grade"}
    
    # Start background grading
    background_tasks.add_task(grade_all_submissions_background, competition_id)
    
    return {"message": f"Grading started for {count} submissions"}

@app.get("/competitions/{competition_id}/grading-status")
async def get_grading_status(competition_id: int):
    """Get grading progress"""
    conn = get_db()
    c = conn.cursor()
    
    c.execute("""
        SELECT status, COUNT(*) as count
        FROM submissions
        WHERE competition_id = ?
        GROUP BY status
    """, (competition_id,))
    
    status_counts = {row['status']: row['count'] for row in c.fetchall()}
    conn.close()
    
    total = sum(status_counts.values())
    
    return {
        "total": total,
        "pending": status_counts.get('pending', 0),
        "grading": status_counts.get('grading', 0),
        "completed": status_counts.get('completed', 0),
        "error": status_counts.get('error', 0)
    }

# ==================== LEADERBOARD ENDPOINTS ====================

@app.get("/competitions/{competition_id}/leaderboard")
async def get_leaderboard(competition_id: int):
    """Get competition leaderboard"""
    conn = get_db()
    c = conn.cursor()
    
    c.execute("""
        SELECT 
            p.id,
            p.name,
            p.email,
            p.student_id,
            AVG(s.score) as average_score,
            COUNT(s.id) as submission_count,
            SUM(CASE WHEN s.status = 'completed' THEN 1 ELSE 0 END) as graded_count
        FROM participants p
        LEFT JOIN submissions s ON p.id = s.participant_id AND s.competition_id = ?
        WHERE p.competition_id = ?
        GROUP BY p.id, p.name, p.email, p.student_id
        ORDER BY average_score DESC NULLS LAST
    """, (competition_id, competition_id))
    
    leaderboard = []
    rank = 1
    for row in c.fetchall():
        entry = dict(row)
        entry['rank'] = rank if entry['average_score'] is not None else None
        leaderboard.append(entry)
        if entry['average_score'] is not None:
            rank += 1
    
    conn.close()
    return leaderboard

# ==================== ANALYSIS REPORT ENDPOINTS ====================

@app.get("/competitions/{competition_id}/report")
async def generate_report(competition_id: int):
    """Generate analysis report for competition"""
    conn = get_db()
    c = conn.cursor()
    
    # Get competition info
    c.execute("SELECT * FROM competitions WHERE id = ?", (competition_id,))
    competition = c.fetchone()
    if not competition:
        conn.close()
        raise HTTPException(status_code=404, detail="Competition not found")
    
    # Get all completed submissions with details
    c.execute("""
        SELECT 
            s.*,
            p.name as participant_name,
            a.name as assignment_name
        FROM submissions s
        JOIN participants p ON s.participant_id = p.id
        JOIN assignments a ON s.assignment_id = a.id
        WHERE s.competition_id = ? AND s.status = 'completed'
    """, (competition_id,))
    
    submissions = [dict(row) for row in c.fetchall()]
    
    if not submissions:
        conn.close()
        return {
            "message": "No completed submissions yet",
            "statistics": None
        }
    
    # Calculate overall statistics
    scores = [s['score'] for s in submissions if s['score'] is not None]
    
    overall_stats = {
        "total_submissions": len(submissions),
        "mean_score": round(statistics.mean(scores), 2) if scores else 0,
        "median_score": round(statistics.median(scores), 2) if scores else 0,
        "std_dev": round(statistics.stdev(scores), 2) if len(scores) > 1 else 0,
        "min_score": round(min(scores), 2) if scores else 0,
        "max_score": round(max(scores), 2) if scores else 0
    }
    
    # Assignment-wise analysis
    c.execute("""
        SELECT 
            a.name as assignment_name,
            COUNT(s.id) as submission_count,
            AVG(s.score) as avg_score,
            MIN(s.score) as min_score,
            MAX(s.score) as max_score
        FROM assignments a
        LEFT JOIN submissions s ON a.id = s.assignment_id AND s.status = 'completed'
        WHERE a.competition_id = ?
        GROUP BY a.id, a.name
    """, (competition_id,))
    
    assignment_stats = [dict(row) for row in c.fetchall()]
    for stat in assignment_stats:
        if stat['avg_score']:
            stat['avg_score'] = round(stat['avg_score'], 2)
        if stat['min_score']:
            stat['min_score'] = round(stat['min_score'], 2)
        if stat['max_score']:
            stat['max_score'] = round(stat['max_score'], 2)
    
    # Top performers
    c.execute("""
        SELECT 
            p.name,
            AVG(s.score) as avg_score,
            COUNT(s.id) as submission_count
        FROM participants p
        JOIN submissions s ON p.id = s.participant_id AND s.status = 'completed'
        WHERE s.competition_id = ?
        GROUP BY p.id, p.name
        ORDER BY avg_score DESC
        LIMIT 10
    """, (competition_id,))
    
    top_performers = [dict(row) for row in c.fetchall()]
    for performer in top_performers:
        performer['avg_score'] = round(performer['avg_score'], 2)
    
    # Score distribution (bins)
    score_bins = {
        "0-20": 0,
        "21-40": 0,
        "41-60": 0,
        "61-80": 0,
        "81-100": 0
    }
    
    for score in scores:
        if score <= 20:
            score_bins["0-20"] += 1
        elif score <= 40:
            score_bins["21-40"] += 1
        elif score <= 60:
            score_bins["41-60"] += 1
        elif score <= 80:
            score_bins["61-80"] += 1
        else:
            score_bins["81-100"] += 1
    
    conn.close()
    
    return {
        "competition": dict(competition),
        "overall_statistics": overall_stats,
        "assignment_statistics": assignment_stats,
        "top_performers": top_performers,
        "score_distribution": score_bins,
        "generated_at": datetime.now().isoformat()
    }

# ==================== STATIC FILES & FRONTEND ====================

# Create static directory if it doesn't exist
os.makedirs("static", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/app", response_class=HTMLResponse)
async def serve_frontend():
    """Serve frontend application"""
    static_index = os.path.join("static", "index.html")
    if os.path.exists(static_index):
        return FileResponse(static_index)
    else:
        # Return a simple message if index.html doesn't exist yet
        return HTMLResponse("""
        <html>
            <head><title>Auto-Grader</title></head>
            <body style="font-family: sans-serif; padding: 2rem; text-align: center;">
                <h1>🚀 Auto-Grader Platform</h1>
                <p>프론트엔드 파일을 업로드 중입니다...</p>
                <p>잠시 후 다시 시도해주세요.</p>
                <hr>
                <p><a href="/docs">API 문서 보기</a></p>
            </body>
        </html>
        """)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
