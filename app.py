"""Single-server central database. All authorization and prize decisions happen here."""
import os, sqlite3, secrets, json, time, io, csv, re
from hashlib import sha256
from pathlib import Path
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, request, jsonify, g, send_from_directory, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image, ImageOps, UnidentifiedImageError
from content import HOUSES, QUESTIONS, PRIZES, score

app=Flask(__name__,static_folder='static')
app.config.update(MAX_CONTENT_LENGTH=16*1024*1024,DATA_DIR=os.environ.get('DATA_DIR','./data'),COOKIE_SECURE=os.environ.get('COOKIE_SECURE','0')=='1')
Image.MAX_IMAGE_PIXELS=24_000_000

def now(): return datetime.now(timezone.utc).isoformat()
def db():
 if 'db' not in g:
  g.db=sqlite3.connect(Path(app.config['DATA_DIR'])/'reading.db',timeout=30,isolation_level=None)
  g.db.row_factory=sqlite3.Row
  g.db.execute('PRAGMA foreign_keys=ON')
 return g.db
@app.teardown_appcontext
def close(_):
 if 'db' in g: g.db.close()
def init():
 Path(app.config['DATA_DIR'],'uploads').mkdir(parents=True,exist_ok=True)
 db().executescript(Path(__file__).with_name('schema.sql').read_text())
 db().execute("INSERT OR IGNORE INTO activities VALUES ('reading-1','บ้านเวทมนตร์รักการอ่าน',0,0)")
 for i,h in enumerate(HOUSES): db().execute('INSERT OR IGNORE INTO houses VALUES (?,?)',(i,json.dumps(h,ensure_ascii=False)))
 for i,p in enumerate(PRIZES,1): db().execute('INSERT OR IGNORE INTO prizes VALUES (?,?)',(i,p))

def fail(msg,status=400): return jsonify(error=msg),status
def data(): return request.get_json(silent=True) or {}
def textval(d,k,maxlen=200,required=True):
 v=d.get(k,'')
 if not isinstance(v,str) or len(v)>maxlen or (required and not v.strip()): raise ValueError('กรุณาตรวจสอบช่อง '+k)
 return v.strip()
def user():
 token=request.cookies.get('reading_session','')
 return db().execute('SELECT u.*,s.csrf FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?',(token,time.time())).fetchone()
def auth(teacher=False):
 def deco(fn):
  @wraps(fn)
  def wrapper(*a,**kw):
   g.user=user()
   if not g.user: return fail('กรุณาเข้าสู่ระบบ',401)
   if teacher and g.user['role']!='teacher': return fail('สำหรับครูผู้ดูแลเท่านั้น',403)
   if request.method!='GET' and not secrets.compare_digest(request.headers.get('X-CSRF-Token',''),g.user['csrf']): return fail('กรุณาโหลดหน้าใหม่แล้วลองอีกครั้ง',403)
   return fn(*a,**kw)
  return wrapper
 return deco
@app.before_request
def same_origin():
 if request.method not in ('GET','HEAD','OPTIONS'):
  origin=request.headers.get('Origin')
  if origin and origin!=request.host_url.rstrip('/'): return fail('ไม่อนุญาตคำขอข้ามเว็บไซต์',403)
@app.after_request
def headers(r):
 r.headers['X-Content-Type-Options']='nosniff'
 r.headers['X-Frame-Options']='DENY'
 r.headers['Referrer-Policy']='same-origin'
 r.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
 if request.path.startswith('/api'): r.headers['Cache-Control']='no-store'
 return r
@app.errorhandler(ValueError)
def invalid(e): return fail(str(e))
@app.errorhandler(413)
def large(e): return fail('รูปหรือคำขอใหญ่เกินไป กรุณาเลือกรูปไม่เกิน 5 MB ต่อรูป',413)
@app.errorhandler(sqlite3.IntegrityError)
def conflict(e): return fail('ข้อมูลนี้ถูกใช้แล้ว กรุณาตรวจสอบแล้วลองใหม่',409)
@app.errorhandler(500)
def internal(e): return fail('ระบบขัดข้อง กรุณาลองใหม่ ข้อมูลที่บันทึกแล้วจะยังอยู่',500)
@app.get('/')
def home(): return app.send_static_file('index.html')
@app.get('/api/config')
def config(): return jsonify(houses=HOUSES,questions=QUESTIONS,activity=dict(db().execute('SELECT * FROM activities').fetchone()),prizes=[dict(r) for r in db().execute('SELECT * FROM prizes ORDER BY number')])
def issue(uid):
 token=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(24)
 db().execute('INSERT INTO sessions VALUES (?,?,?,?)',(token,uid,csrf,time.time()+7*86400))
 r=jsonify(ok=True)
 r.set_cookie('reading_session',token,httponly=True,secure=app.config['COOKIE_SECURE'],samesite='Lax',max_age=7*86400)
 return r

def throttle(key):
 t=time.time(); row=db().execute('SELECT * FROM auth_attempts WHERE key=?',(key,)).fetchone()
 if row and row['until']>t and row['count']>=15: return False
 db().execute('INSERT INTO auth_attempts VALUES (?,1,?) ON CONFLICT(key) DO UPDATE SET count=CASE WHEN until<? THEN 1 ELSE count+1 END, until=CASE WHEN until<? THEN excluded.until ELSE until END',(key,t+900,t,t))
 return True
@app.post('/api/register')
def register():
 if not throttle('register:'+request.remote_addr+':'+sha256(str(data().get('student_id','')).encode()).hexdigest()): return fail('ลองบ่อยเกินไป กรุณารอ 15 นาที',429)
 d=data(); sid=textval(d,'student_id',50); name=textval(d,'name',80); classroom=textval(d,'classroom',30); number=textval(d,'number',10); password=textval(d,'password',200); code=textval(d,'code',100)
 if len(password)<10: return fail('รหัสผ่านต้องมีอย่างน้อย 10 ตัวอักษร')
 hashed=generate_password_hash(password); uid=secrets.token_hex(16); c=db(); c.execute('BEGIN IMMEDIATE')
 try:
  invite=c.execute('SELECT * FROM invites WHERE code=? AND student_id=? AND used=0',(code,sid)).fetchone()
  if not invite: c.rollback(); return fail('รหัสเข้าร่วมไม่ถูกต้องหรือถูกใช้แล้ว')
  c.execute('INSERT INTO users(id,student_id,name,classroom,number,password,created) VALUES (?,?,?,?,?,?,?)',(uid,sid,name,classroom,number,hashed,now()))
  c.execute('UPDATE invites SET used=1 WHERE code=?',(code,)); c.commit()
 except Exception: c.rollback(); raise
 return issue(uid)
@app.post('/api/login')
def login():
 if not throttle('login:'+request.remote_addr+':'+sha256(str(data().get('student_id','')).encode()).hexdigest()): return fail('ลองบ่อยเกินไป กรุณารอ 15 นาที',429)
 d=data(); u=db().execute('SELECT * FROM users WHERE student_id=?',(textval(d,'student_id',50),)).fetchone()
 # Run a password hash even for nonexistent accounts.
 hashed=u['password'] if u else generate_password_hash('unavailable-account')
 valid=check_password_hash(hashed,textval(d,'password',200))
 if not u or not valid: return fail('รหัสสมาชิกหรือรหัสผ่านไม่ถูกต้อง',401)
 return issue(u['id'])
@app.post('/api/logout')
@auth()
def logout():
 db().execute('DELETE FROM sessions WHERE token=?',(request.cookies.get('reading_session'),)); r=jsonify(ok=True); r.delete_cookie('reading_session'); return r

def ticket_for(uid):
 r=db().execute('SELECT t.* FROM tickets t JOIN spins s ON s.id=t.spin_id WHERE s.user_id=? AND s.activity_id=?',(uid,'reading-1')).fetchone()
 return dict(r) if r else None
@app.get('/api/me')
def me():
 u=user()
 if not u: return jsonify(user=None)
 keys=['id','student_id','name','classroom','number','house','role','csrf']
 return jsonify(user={k:u[k] for k in keys},posts=[postdict(p) for p in db().execute('SELECT p.*,u.name,u.house FROM bookPosts p JOIN users u ON u.id=p.user_id WHERE user_id=? ORDER BY p.created DESC',(u['id'],))],ticket=ticket_for(u['id']))
@app.post('/api/quiz')
@auth()
def quiz():
 d=data(); scores,tied,house=score(d.get('answers'),d.get('tie'))
 if house is None: return jsonify(tied=tied,scores=scores)
 c=db(); c.execute('BEGIN IMMEDIATE')
 try:
  old=c.execute('SELECT house FROM users WHERE id=?',(g.user['id'],)).fetchone()['house']
  if old is not None: c.rollback(); return jsonify(house=old)
  c.execute('INSERT INTO quizResults VALUES (?,?,?,?,?)',(g.user['id'],json.dumps(d['answers']),json.dumps(scores),d.get('tie'),house))
  c.execute('UPDATE users SET house=? WHERE id=?',(house,g.user['id'])); c.commit()
 except Exception: c.rollback(); raise
 return jsonify(house=house)

def postdict(p):
 return dict(id=p['id'],user_id=p['user_id'],name=p['name'],house=p['house'],hidden=bool(p['hidden']),created=p['created'],**json.loads(p['body']))
@app.get('/api/posts')
def posts():
 rows=db().execute('SELECT p.*,u.name,u.house FROM bookPosts p JOIN users u ON u.id=p.user_id WHERE hidden=0 ORDER BY p.created DESC LIMIT 1000')
 return jsonify(posts=[postdict(p) for p in rows],stats=[dict(house=i,members=db().execute('SELECT count(*) FROM users WHERE house=?',(i,)).fetchone()[0],books=db().execute('SELECT count(*) FROM bookPosts p JOIN users u ON u.id=p.user_id WHERE u.house=? AND p.hidden=0',(i,)).fetchone()[0]) for i in range(4)])
@app.post('/api/uploads')
@auth()
def upload():
 f=request.files.get('image')
 if not f or f.mimetype not in ('image/jpeg','image/png','image/webp'): return fail('รองรับ JPG, PNG และ WebP เท่านั้น')
 raw=f.read(5*1024*1024+1)
 if len(raw)>5*1024*1024: return fail('รูปต้องไม่เกิน 5 MB')
 if db().execute('SELECT count(*) FROM images WHERE user_id=?',(g.user['id'],)).fetchone()[0]>=100: return fail('พื้นที่รูปเต็ม กรุณาติดต่อครู')
 try:
  im=Image.open(io.BytesIO(raw))
  if im.format not in ('JPEG','PNG','WEBP'): return fail('ไฟล์ไม่ใช่รูปที่รองรับ')
  im.load(); im=ImageOps.exif_transpose(im); im.thumbnail((1600,1600)); im=im.convert('RGB')
 except (UnidentifiedImageError,OSError,Image.DecompressionBombError,Image.DecompressionBombWarning): return fail('อ่านรูปไม่ได้ หรือรูปมีขนาดความละเอียดสูงเกินไป')
 iid=secrets.token_hex(16)+'.webp'; im.save(Path(app.config['DATA_DIR'],'uploads',iid),'WEBP',quality=82)
 db().execute('INSERT INTO images VALUES (?,?,?)',(iid,g.user['id'],'image/webp'))
 return jsonify(id=iid)
@app.get('/media/<name>')
def media(name):
 # Only published images are public. Draft images require the owner's session.
 row=db().execute('SELECT user_id FROM images WHERE id=?',(name,)).fetchone()
 if not row: return fail('ไม่พบรูป',404)
 visible=any(name in json.loads(p['body']).get('images',[]) for p in db().execute('SELECT body FROM bookPosts WHERE hidden=0'))
 u=user()
 if not visible and (not u or (u['id']!=row['user_id'] and u['role']!='teacher')): return fail('ไม่พบรูป',404)
 return send_from_directory(Path(app.config['DATA_DIR']).resolve()/'uploads',name,mimetype='image/webp')
@app.route('/api/posts/<pid>',methods=['PUT','DELETE'])
@auth()
def mutate_post(pid):
 p=db().execute('SELECT * FROM bookPosts WHERE id=? AND user_id=?',(pid,g.user['id'])).fetchone()
 if request.method=='DELETE':
  if not p: return fail('ไม่พบโพสต์ของคุณ',404)
  db().execute('DELETE FROM bookPosts WHERE id=?',(pid,)); return jsonify(ok=True)
 if g.user['house'] is None: return fail('กรุณาค้นพบบ้านก่อนแชร์')
 if not re.fullmatch(r'[a-zA-Z0-9-]{16,80}',pid): return fail('รหัสโพสต์ไม่ถูกต้อง')
 d=data(); body={k:textval(d,k,n,k not in ('author','recommend')) for k,n in [('title',150),('author',100),('genre',80),('summary',3000),('learned',2000),('recommend',500)]}
 if type(d.get('rating')) is not int or d['rating'] not in range(1,6) or d.get('consent') is not True: return fail('กรุณาให้ดาวและยืนยันก่อนส่ง')
 imgs=d.get('images',[])
 if not isinstance(imgs,list) or len(imgs)>3 or any(not isinstance(i,str) or not db().execute('SELECT 1 FROM images WHERE id=? AND user_id=?',(i,g.user['id'])).fetchone() for i in imgs): return fail('รูปไม่ถูกต้อง')
 body.update(rating=d['rating'],images=imgs)
 if not p and db().execute('SELECT 1 FROM bookPosts WHERE id=?',(pid,)).fetchone(): return fail('คุณแก้ไขโพสต์นี้ไม่ได้',403)
 changed=db().execute('INSERT INTO bookPosts VALUES (?,?,?,0,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body,updated=excluded.updated WHERE bookPosts.user_id=excluded.user_id',(pid,g.user['id'],json.dumps(body,ensure_ascii=False),now(),now())).rowcount
 if not changed: return fail('คุณแก้ไขโพสต์นี้ไม่ได้',403)
 return jsonify(ok=True,id=pid)
@app.post('/api/spin')
@auth()
def spin():
 c=db(); c.execute('BEGIN IMMEDIATE')
 try:
  old=ticket_for(g.user['id'])
  if old: c.commit(); return jsonify(ticket=old)
  a=c.execute('SELECT * FROM activities').fetchone()
  if not a['is_open']: c.rollback(); return fail('ครูยังไม่เปิดช่วงหมุนวงล้อ')
  u=c.execute('SELECT * FROM users WHERE id=?',(g.user['id'],)).fetchone()
  if u['house'] is None or not c.execute('SELECT 1 FROM bookPosts WHERE user_id=? AND hidden=0',(u['id'],)).fetchone(): c.rollback(); return fail('ต้องค้นพบบ้านและเผยแพร่หนังสือก่อน')
  n=secrets.randbelow(9)+1; sid=secrets.token_hex(16); code='READ-'+secrets.token_hex(8).upper()
  prize=c.execute('SELECT name FROM prizes WHERE number=?',(n,)).fetchone()[0]
  snapshot=dict(name=u['name'],house=u['house'],number=n,prize=prize,activity=a['name'])
  c.execute('INSERT INTO spins VALUES (?,?,?,?)',(sid,a['id'],u['id'],n))
  c.execute('INSERT INTO tickets VALUES (?,?,?,?,NULL,NULL)',(code,sid,json.dumps(snapshot,ensure_ascii=False),now()))
  c.commit(); return jsonify(ticket=ticket_for(u['id']))
 except Exception: c.rollback(); raise
@app.get('/api/admin')
@auth(True)
def admin():
 users=[dict(r) for r in db().execute("SELECT id,student_id,name,classroom,number,house,(SELECT count(*) FROM bookPosts WHERE user_id=u.id AND hidden=0) posts,(SELECT count(*) FROM spins WHERE user_id=u.id) spun FROM users u WHERE role='student' ORDER BY classroom,number")]
 return jsonify(users=users,posts=[postdict(p) for p in db().execute('SELECT p.*,u.name,u.house FROM bookPosts p JOIN users u ON u.id=p.user_id ORDER BY created DESC')],tickets=[dict(r) for r in db().execute('SELECT * FROM tickets ORDER BY created DESC')],invites=[dict(r) for r in db().execute('SELECT * FROM invites ORDER BY student_id')])
@app.post('/api/admin/invites')
@auth(True)
def invites():
 sid=textval(data(),'student_id',50); code=secrets.token_urlsafe(12)
 db().execute('INSERT INTO invites VALUES (?,?,0)',(code,sid)); return jsonify(code=code)
@app.post('/api/admin/settings')
@auth(True)
def settings():
 d=data(); c=db(); c.execute('BEGIN IMMEDIATE')
 try:
  a=c.execute('SELECT * FROM activities').fetchone()
  if 'prizes' in d:
   if a['started']: c.rollback(); return fail('แก้ชื่อของสมนาคุณได้เฉพาะก่อนเปิดกิจกรรมครั้งแรก')
   names=d['prizes']
   if not isinstance(names,list) or len(names)!=8 or any(not isinstance(x,str) or not x.strip() or len(x)>100 for x in names): c.rollback(); return fail('กรุณากรอกของสมนาคุณครบ 8 รายการ')
   for n,name in enumerate(names,2): c.execute('UPDATE prizes SET name=? WHERE number=?',(name.strip(),n))
  if 'is_open' in d:
   if type(d['is_open']) is not bool: c.rollback(); return fail('สถานะไม่ถูกต้อง')
   c.execute('UPDATE activities SET is_open=?,started=MAX(started,?)',(int(d['is_open']),int(d['is_open'])))
  c.commit()
 except Exception: c.rollback(); raise
 return jsonify(ok=True)
@app.post('/api/admin/moderate')
@auth(True)
def moderate():
 d=data()
 if type(d.get('hidden')) is not bool: return fail('สถานะไม่ถูกต้อง')
 r=db().execute('UPDATE bookPosts SET hidden=? WHERE id=?',(int(d['hidden']),textval(d,'id',80)))
 if not r.rowcount: return fail('ไม่พบโพสต์',404)
 return jsonify(ok=True)
@app.post('/api/admin/redeem')
@auth(True)
def redeem():
 code=textval(data(),'code',100)
 changed=db().execute('UPDATE tickets SET redeemed=?,redeemed_by=? WHERE code=? AND redeemed IS NULL',(now(),g.user['id'],code)).rowcount
 if not changed: return fail('ไม่พบตั๋ว หรือรับของรางวัลแล้ว',409)
 return jsonify(ok=True)
@app.get('/api/admin/export')
@auth(True)
def export():
 buf=io.StringIO(); w=csv.writer(buf); w.writerow(['ชื่อ','ห้อง','เลขที่','รหัสสมาชิก','บ้าน','รหัสตั๋ว','รางวัล','รับรางวัลแล้ว'])
 for u in db().execute("SELECT * FROM users WHERE role='student'"):
  t=ticket_for(u['id']); s=json.loads(t['snapshot']) if t else {}
  row=[u['name'],u['classroom'],u['number'],u['student_id'],HOUSES[u['house']]['name'] if u['house'] is not None else '',t['code'] if t else '',s.get('prize',''),bool(t and t['redeemed'])]
  w.writerow(["'"+str(v) if str(v).startswith(('=','+','-','@','\t','\r')) else v for v in row])
 r=make_response('\ufeff'+buf.getvalue()); r.headers['Content-Type']='text/csv; charset=utf-8'; r.headers['Content-Disposition']='attachment; filename=reading-summary.csv'; return r
with app.app_context(): init()
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.environ.get('PORT',8000)),debug=False)
