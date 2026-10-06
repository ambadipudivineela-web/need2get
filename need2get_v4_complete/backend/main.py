from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
import sqlite3, math, re, uuid, io

DB="need2get.db"
app=FastAPI(title="Need2Get Complete MVP",version="4.0")
app.add_middleware(CORSMiddleware,allow_origins=["http://127.0.0.1:5500","http://localhost:5500"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])

def db():
    c=sqlite3.connect(DB,check_same_thread=False); c.row_factory=sqlite3.Row; return c

def init():
    c=db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS merchants(id INTEGER PRIMARY KEY,name TEXT,lat REAL,lon REAL,reliability REAL,open_now INTEGER);
    CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY,name TEXT,category TEXT,material TEXT,color TEXT,size_value REAL,size_unit TEXT,use_case TEXT,synonyms TEXT);
    CREATE TABLE IF NOT EXISTS inventory(id INTEGER PRIMARY KEY,merchant_id INTEGER,product_id INTEGER,quantity INTEGER,price REAL,confirmed INTEGER,updated_at TEXT);
    CREATE TABLE IF NOT EXISTS reservations(id TEXT PRIMARY KEY,merchant_id INTEGER,product_id INTEGER,lat REAL,lon REAL,status TEXT,otp TEXT,created_at TEXT,expires_at TEXT,merchant_confirmed INTEGER);
    CREATE TABLE IF NOT EXISTS journeys(id TEXT PRIMARY KEY,reservation_id TEXT,status TEXT,lat REAL,lon REAL,eta REAL,started_at TEXT,updated_at TEXT);
    """)
    if c.execute("SELECT COUNT(*) n FROM merchants").fetchone()["n"]==0:
        now=datetime.now(timezone.utc).isoformat()
        c.executemany("INSERT INTO merchants VALUES(?,?,?,?,?,?)",[
            (1,"Sri Sai Electronics",17.9780,79.5980,.94,1),(2,"ABC Electricals",17.9840,79.5900,.88,1),(3,"Ravi Hardware",17.9700,79.6100,.91,1),(4,"Metro Plumbing",17.9900,79.6030,.90,1)])
        c.executemany("INSERT INTO products VALUES(?,?,?,?,?,?,?,?,?)",[
            (1,"12V 2A Adapter","adapter","electronic","black",12,"volt","electronics","charger,12v,2a,power adapter"),
            (2,"A4 Drawing Sheets","paper","paper","white",4,"a4","drawing","a4,sheets,drawing paper"),
            (3,"15 inch Blue PVC Water Pipe","pipe","PVC","blue",15,"inch","water","pipe,pipes,blue pipe,water pipe,pvc pipe"),
            (4,"20 inch Red PVC Pipe","pipe","PVC","red",20,"inch","water","pipe,pipes,red pipe,pvc pipe"),
            (5,"1 meter Blue PVC Water Pipe","pipe","PVC","blue",1,"meter","water","pipe,pipes,blue pipe,water pipe,pvc pipe"),
            (6,"15 inch Blue GI Pipe","pipe","GI","blue",15,"inch","water","pipe,blue pipe,gi pipe")])
        c.executemany("INSERT INTO inventory VALUES(?,?,?,?,?,?,?)",[
            (1,1,1,5,450,1,now),(2,2,1,2,475,1,now),(3,3,1,1,500,1,now),
            (4,3,2,20,120,1,now),(5,1,3,1,180,1,now),(6,2,4,4,210,1,now),(7,4,5,2,260,1,now),(8,3,6,2,310,1,now)])
        c.commit()
    c.close()
init()

class Search(BaseModel): query:str; lat:float=17.978; lon:float=79.598
class Reserve(BaseModel): merchant_id:int; product_id:int; lat:float; lon:float
class Loc(BaseModel): lat:float; lon:float
class Confirm(BaseModel): reservation_id:str; approved:bool=True
class Compete(BaseModel): reservation_id:str

def dist(a,b,c,d):
    R=6371;p1=math.radians(a);p2=math.radians(c);dp=math.radians(c-a);dl=math.radians(d-b)
    x=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R*2*math.atan2(math.sqrt(x),math.sqrt(1-x))
def parse(q):
    s=q.lower(); a={"raw":q,"category":None,"color":None,"material":None,"size_value":None,"size_unit":None,"use_case":None}
    for x in ["blue","red","green","black","white","yellow"]:
        if x in s:a["color"]=x;break
    for x in ["pvc","gi","steel","metal","plastic","rubber","wood"]:
        if x in s:a["material"]=x;break
    if "pipe" in s:a["category"]="pipe"
    elif "adapter" in s:a["category"]="adapter"
    elif "sheet" in s:a["category"]="paper"
    if "water" in s or "plumbing" in s:a["use_case"]="water"
    m=re.search(r"(\d+(?:\.\d+)?)\s*(inch|inches|in|meter|meters|m|cm|mm|volt|v)\b",s)
    if m:
        u=m.group(2);u={"in":"inch","inches":"inch","meters":"meter","m":"meter","v":"volt"}.get(u,u)
        a["size_value"]=float(m.group(1));a["size_unit"]=u
    return a
def score(a,p):
    z=0
    if a["category"]:
        z += 45 if (a["category"]==p["category"] or (a["category"]=="pipe" and "pipe" in p["category"])) else -20
    if a["color"]: z += 18 if a["color"]==p["color"] else -8
    if a["material"]: z += 15 if a["material"].lower()==p["material"].lower() else -8
    if a["use_case"]: z += 10 if a["use_case"]==p["use_case"] else -3
    if a["size_value"] is not None:
        if a["size_unit"]==p["size_unit"]:
            z += 12 if a["size_value"]==p["size_value"] else max(0,8-abs(a["size_value"]-p["size_value"]))
        else:z-=12
    toks=re.findall(r"[a-z0-9]+",a["raw"].lower()); hay=(p["product_name"]+" "+p["synonyms"]).lower()
    z+=min(15,sum(2 for t in toks if len(t)>1 and t in hay))
    return z

@app.get("/api/health")
def health(): return {"ok":True,"version":"4.0"}

@app.get("/api/suggest")
def suggest(q:str=""):
    q=q.lower().strip(); c=db(); rows=c.execute("SELECT name FROM products").fetchall(); c.close()
    vals=[r["name"] for r in rows]
    vals += ["pipe","blue pipe","PVC pipe","water pipe","15 inch blue pipe","12V 2A adapter"]
    return {"suggestions":list(dict.fromkeys([x for x in vals if q in x.lower()]))[:8] if q else []}

@app.post("/api/search")
def search(r:Search):
    a=parse(r.query);c=db(); rows=c.execute("""SELECT i.*,m.name shop_name,m.lat shop_lat,m.lon shop_lon,m.reliability,m.open_now,
    p.name product_name,p.category,p.material,p.color,p.size_value,p.size_unit,p.use_case,p.synonyms
    FROM inventory i JOIN merchants m ON m.id=i.merchant_id JOIN products p ON p.id=i.product_id WHERE i.quantity>0""").fetchall();out=[]
    for x in rows:
        s=score(a,dict(x))
        if s<5:continue
        d=dist(r.lat,r.lon,x["shop_lat"],x["shop_lon"]); eta=max(2,round(d/.45))
        ob=round(min(99,max(1,s*.55+x["reliability"]*10+(12 if x["confirmed"] else 0)+min(5,x["quantity"])*2+(10 if x["open_now"] else -20)-d*1.2)))
        out.append({**{k:x[k] for k in ["merchant_id","product_id","shop_name","product_name","category","material","color","size_value","size_unit","use_case","quantity","price","shop_lat","shop_lon"]},"distance_km":round(d,2),"eta_min":eta,"obtainability":ob,"label":"Very likely" if ob>=80 else ("Likely" if ob>=60 else "Possible")})
    c.close();out.sort(key=lambda x:(-x["obtainability"],x["distance_km"]));return {"need":a,"count":len(out),"results":out[:20]}

@app.post("/api/reserve")
def reserve(r:Reserve):
    c=db();c.execute("BEGIN IMMEDIATE")
    inv=c.execute("SELECT * FROM inventory WHERE merchant_id=? AND product_id=? AND quantity>0",(r.merchant_id,r.product_id)).fetchone()
    active=c.execute("SELECT * FROM reservations WHERE merchant_id=? AND product_id=? AND status IN ('PENDING_CONFIRMATION','CONFIRMED') AND expires_at>?",
                     (r.merchant_id,r.product_id,datetime.now(timezone.utc).isoformat())).fetchone()
    if not inv or active:
        c.rollback();c.close();raise HTTPException(409,"Reserved — another customer is currently requesting/on the way.")
    rid=str(uuid.uuid4());otp=str(100000+uuid.uuid4().int%900000);now=datetime.now(timezone.utc);exp=now+timedelta(minutes=20)
    c.execute("UPDATE inventory SET quantity=quantity-1 WHERE id=?",(inv["id"],))
    c.execute("INSERT INTO reservations VALUES(?,?,?,?,?,?,?,?,?,?)",(rid,r.merchant_id,r.product_id,r.lat,r.lon,"PENDING_CONFIRMATION",otp,now.isoformat(),exp.isoformat(),0))
    c.commit();c.close()
    return {"reservation_id":rid,"status":"PENDING_CONFIRMATION","otp":otp,"expires_at":exp.isoformat(),"message":"Request sent to merchant. Stock is temporarily held."}

@app.post("/api/merchant/confirm")
def merchant_confirm(r:Confirm):
    c=db();row=c.execute("SELECT * FROM reservations WHERE id=?",(r.reservation_id,)).fetchone()
    if not row:c.close();raise HTTPException(404,"Reservation not found")
    if not r.approved:
        c.execute("UPDATE reservations SET status='CANCELLED' WHERE id=?",(r.reservation_id,))
        c.execute("UPDATE inventory SET quantity=quantity+1 WHERE merchant_id=? AND product_id=?",(row["merchant_id"],row["product_id"]))
        c.commit();c.close();return {"status":"CANCELLED","message":"Merchant rejected. Stock released."}
    c.execute("UPDATE reservations SET status='CONFIRMED',merchant_confirmed=1 WHERE id=?",(r.reservation_id,));c.commit();c.close()
    return {"status":"CONFIRMED","message":"Merchant confirmed. Stock is locked for this customer."}

@app.get("/api/merchant/pending")
def pending():
    c=db();rows=c.execute("""SELECT r.*,m.name shop_name,p.name product_name FROM reservations r JOIN merchants m ON m.id=r.merchant_id
    JOIN products p ON p.id=r.product_id WHERE r.status='PENDING_CONFIRMATION' ORDER BY r.created_at DESC""").fetchall();c.close();return {"requests":[dict(x) for x in rows]}

@app.post("/api/journey/start")
def start(rid:str,r:Loc):
    c=db();x=c.execute("SELECT r.*,m.name shop_name,m.lat slat,m.lon slon,p.name product_name FROM reservations r JOIN merchants m ON m.id=r.merchant_id JOIN products p ON p.id=r.product_id WHERE r.id=? AND r.status='CONFIRMED'",(rid,)).fetchone()
    if not x:c.close();raise HTTPException(409,"Merchant confirmation required before journey.")
    jid=str(uuid.uuid4());d=dist(r.lat,r.lon,x["slat"],x["slon"]);eta=max(1,round(d/.45));now=datetime.now(timezone.utc).isoformat()
    c.execute("INSERT INTO journeys VALUES(?,?,?,?,?,?,?,?)",(jid,rid,"TRAVELLING",r.lat,r.lon,eta,now,now));c.commit();c.close()
    return {"journey_id":jid,"status":"TRAVELLING","eta_min":eta,"distance_km":round(d,2),"shop_name":x["shop_name"],"product_name":x["product_name"],"shop_lat":x["slat"],"shop_lon":x["slon"]}

@app.patch("/api/journey/{jid}")
def move(jid:str,r:Loc):
    c=db();x=c.execute("""SELECT j.*,m.lat slat,m.lon slon FROM journeys j JOIN reservations r ON r.id=j.reservation_id JOIN merchants m ON m.id=r.merchant_id WHERE j.id=?""",(jid,)).fetchone()
    if not x:c.close();raise HTTPException(404,"Journey not found")
    d=dist(r.lat,r.lon,x["slat"],x["slon"]);eta=max(1,round(d/.45));st="ARRIVED" if d<.08 else "TRAVELLING";now=datetime.now(timezone.utc).isoformat()
    c.execute("UPDATE journeys SET lat=?,lon=?,eta=?,status=?,updated_at=? WHERE id=?",(r.lat,r.lon,eta,st,now,jid));c.commit();c.close()
    return {"status":st,"distance_km":round(d,2),"eta_min":eta}

@app.get("/api/journey/{jid}")
def getjourney(jid:str):
    c=db();x=c.execute("SELECT * FROM journeys WHERE id=?",(jid,)).fetchone();c.close()
    if not x:raise HTTPException(404,"Journey not found")
    return dict(x)

@app.get("/api/merchant/live")
def live():
    c=db();rows=c.execute("""SELECT j.*,m.name shop_name,p.name product_name FROM journeys j JOIN reservations r ON r.id=j.reservation_id
    JOIN merchants m ON m.id=r.merchant_id JOIN products p ON p.id=r.product_id WHERE j.status IN ('TRAVELLING','ARRIVED')""").fetchall();c.close();return {"journeys":[dict(x) for x in rows]}

@app.post("/api/failure/{rid}")
def failure(rid:str):
    c=db();r=c.execute("SELECT * FROM reservations WHERE id=?",(rid,)).fetchone()
    if not r:c.close();raise HTTPException(404,"Reservation not found")
    c.execute("UPDATE reservations SET status='FAILED' WHERE id=?",(rid,));c.execute("UPDATE journeys SET status='AT_RISK' WHERE reservation_id=?",(rid,))
    # find alternatives of same product/category; never expose reserved/sold stock
    alts=c.execute("""SELECT i.*,m.name shop_name,m.lat shop_lat,m.lon shop_lon,p.name product_name
    FROM inventory i JOIN merchants m ON m.id=i.merchant_id JOIN products p ON p.id=i.product_id
    WHERE i.product_id=? AND i.quantity>0 AND i.merchant_id<>? AND m.open_now=1""",(r["product_id"],r["merchant_id"])).fetchall()
    c.commit();c.close()
    return {"status":"AT_RISK","message":"Original stock failed. Alternatives found.","alternatives":[dict(a) for a in alts]}

@app.post("/api/arrival")
def arrival(rid:str,otp:str):
    c=db();r=c.execute("SELECT * FROM reservations WHERE id=?",(rid,)).fetchone()
    if not r or r["otp"]!=otp:c.close();raise HTTPException(400,"Invalid reservation or OTP")
    c.execute("UPDATE reservations SET status='FULFILLED' WHERE id=?",(rid,));c.execute("UPDATE journeys SET status='SUCCESS' WHERE reservation_id=?",(rid,));c.commit();c.close()
    return {"status":"FULFILLED","message":"Purchase/acquisition successfully confirmed."}

@app.post("/api/image/analyze")
async def image(file:UploadFile=File(...)):
    data=await file.read()
    try:
        from PIL import Image
        im=Image.open(io.BytesIO(data)).convert("RGB").resize((60,60));px=list(im.getdata());avg=tuple(sum(p[i] for p in px)//len(px) for i in range(3));rr,gg,bb=avg
        color="blue" if bb>rr*1.15 and bb>gg*1.05 else ("red" if rr>gg*1.25 and rr>bb*1.25 else ("green" if gg>rr*1.2 and gg>bb*1.1 else "unknown"))
        return {"detected_color":color,"suggested_query":(color+" pipe" if color!="unknown" else "pipe"),"mode":"camera-demo","message":"Photo received. This local demo uses visual color as a signal; a production vision model can add exact product/material/size recognition."}
    except Exception:return {"detected_color":"unknown","suggested_query":"pipe","mode":"camera-demo"}

@app.get("/api/reset")
def reset():
    c=db();c.execute("DELETE FROM reservations");c.execute("DELETE FROM journeys")
    c.execute("UPDATE inventory SET quantity=CASE id WHEN 1 THEN 5 WHEN 2 THEN 2 WHEN 3 THEN 1 WHEN 4 THEN 20 WHEN 5 THEN 1 WHEN 6 THEN 4 WHEN 7 THEN 2 WHEN 8 THEN 2 END")
    c.commit();c.close();return {"ok":True}
