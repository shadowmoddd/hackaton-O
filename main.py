import uuid, random
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import engine as E

app = FastAPI(); S = {}
class Q(BaseModel):
    sid: str = ""; text: str = ""; dest: str = ""; kind: str = ""; code: str = ""

def view(x): return dict(sid=x["sid"],state={k:v for k,v in x["s"].items() if k!="explicit"},assume=E.assumptions(x["s"]),
                          dest=x.get("dest"),plan=x.get("plan"),mock=True)

@app.post("/api/start")
def start(q: Q):
    s = E.parse(q.text); x = dict(sid=uuid.uuid4().hex[:8],s=s); S[x["sid"]] = x
    r = view(x); r["top"] = E.rank(s); return r

@app.post("/api/select")
def select(q: Q):
    x = S[q.sid]; x["dest"] = q.dest; x["packs"] = E.packages(x["s"],E.dest_by_name(q.dest))
    r = view(x); r["packs"] = x["packs"]; return r

@app.post("/api/choose")
def choose(q: Q):
    x = S[q.sid]; x["plan"] = x["packs"][q.kind]; return view(x)

@app.post("/api/fix")
def fix(q: Q):
    x = S[q.sid]; E.apply_fix(x["s"],x["plan"],E.dest_by_name(x["dest"]),q.code); return view(x)

@app.post("/api/replan")
def replan(q: Q):
    x = S[q.sid]; s2,new,ch,diff = E.replan(x["s"],x["plan"],E.dest_by_name(x["dest"]),q.text)
    x["s"],x["plan"] = s2,new; r = view(x); r["changes"],r["diff"] = ch,diff; return r

@app.post("/api/pay")
def pay(q: Q):
    x = S[q.sid]; x["order"] = "OSTR-"+str(random.randint(100000,999999)); r = view(x); r["order"] = x["order"]; return r

@app.get("/")
def index(): return FileResponse("static/index.html")
