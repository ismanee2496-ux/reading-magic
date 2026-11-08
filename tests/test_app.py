import sys,io,json,threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from app import app,db,init,now
from content import score
from werkzeug.security import generate_password_hash
from PIL import Image

@pytest.fixture
def env(tmp_path):
 app.config.update(TESTING=True,DATA_DIR=str(tmp_path),COOKIE_SECURE=False)
 with app.app_context():
  init()
  db().execute("INSERT INTO users(id,student_id,name,classroom,number,password,role,created) VALUES ('teacher','teacher','ครู','ครู','0',?,'teacher',?)",(generate_password_hash('teacher-password'),now()))
 yield app

def client(env,sid='1001'):
 c=env.test_client()
 with env.app_context():db().execute('INSERT INTO invites VALUES (?,?,0)',('invite-'+sid,sid))
 r=c.post('/api/register',json=dict(student_id=sid,name='นักอ่าน '+sid,classroom='ม.1/2',number='1',password='test-password',code='invite-'+sid));assert r.status_code==200
 u=c.get('/api/me').json['user'];return c,{'X-CSRF-Token':u['csrf']}
def teacher(env):
 c=env.test_client();assert c.post('/api/login',json={'student_id':'teacher','password':'teacher-password'}).status_code==200
 return c,{'X-CSRF-Token':c.get('/api/me').json['user']['csrf']}
def sorted_user(env,sid='1001'):
 c,h=client(env,sid);assert c.post('/api/quiz',json={'answers':[0]*12},headers=h).json['house']==0;return c,h
def publish(c,h,pid='post-1234567890abcdef',images=None):
 return c.put('/api/posts/'+pid,json=dict(title='หนังสือหนึ่งเล่ม',author='ผู้เขียน',genre='การ์ตูน',summary='เรื่องย่อ',learned='ได้เรียนรู้',recommend='',rating=5,consent=True,images=images or []),headers=h)
def unlock(env,c,h):
 assert publish(c,h).status_code==200
 t,th=teacher(env);assert t.post('/api/admin/settings',json={'is_open':True},headers=th).status_code==200
 return t,th

def test_registration_login_and_recovery(env):
 c,h=client(env);assert c.post('/api/register',json={}).status_code==400
 assert c.post('/api/logout',headers=h).status_code==200
 assert c.get('/api/me').json['user'] is None
 assert c.post('/api/login',json=dict(student_id='1001',password='wrong')).status_code==401
 assert c.post('/api/login',json=dict(student_id='1001',password='test-password')).status_code==200
 c2=env.test_client();c2.post('/api/login',json=dict(student_id='1001',password='test-password'));assert c2.get('/api/me').json['user']['name']=='นักอ่าน 1001'
 with env.app_context():assert db().execute("SELECT password FROM users WHERE student_id='1001'").fetchone()[0]!='test-password'
def test_quiz_tie_and_immutability(env):
 c,h=client(env);a=[0,1,2,3]*3
 assert c.post('/api/quiz',json={'answers':a},headers=h).json['tied']==[0,1,2,3]
 assert c.post('/api/quiz',json={'answers':a,'tie':2},headers=h).json['house']==2
 assert c.post('/api/quiz',json={'answers':[0]*12},headers=h).json['house']==2
 assert c.get('/api/me').json['user']['house']==2
 assert c.post('/api/quiz',json={'answers':[True]*12},headers=h).status_code==400
 assert score([0]*6+[1]*6,3)[2] is None

def test_posts_public_privacy_edit_and_upload(env):
 c,h=sorted_user(env);assert publish(c,h).status_code==200
 c2,h2=sorted_user(env,'1002');assert c2.delete('/api/posts/post-1234567890abcdef',headers=h2).status_code==404
 assert publish(c2,h2).status_code==403
 out=env.test_client().get('/api/posts').json
 assert out['stats'][0]['members']==2
 assert 'student_id' not in json.dumps(out)
 im=Image.new('RGB',(50,50),'red');buf=io.BytesIO();im.save(buf,'PNG');buf.seek(0)
 r=c.post('/api/uploads',data={'image':(buf,'cover.png','image/png')},headers=h);assert r.status_code==200
 iid=r.json['id'];assert env.test_client().get('/media/'+iid).status_code==404
 assert publish(c,h,images=[iid]).status_code==200
 assert env.test_client().get('/media/'+iid).status_code==200
 assert c.post('/api/uploads',data={'image':(io.BytesIO(b'bad'),'x.png','image/png')},headers=h).status_code==400
 assert c.post('/api/uploads',data={'image':(io.BytesIO(b'x'*(5*1024*1024+1)),'x.png','image/png')},headers=h).status_code==400
 assert c.delete('/api/posts/post-1234567890abcdef',headers=h).status_code==200
 assert env.test_client().get('/api/posts').json['posts']==[]

def test_csrf_and_admin_permissions(env):
 c,h=client(env);assert c.post('/api/quiz',json={'answers':[0]*12}).status_code==403
 assert c.get('/api/admin').status_code==403
 assert c.post('/api/login',json={},headers={'Origin':'https://evil.example'}).status_code==403
 assert env.test_client().post('/api/spin').status_code==401

def test_locked_spin_and_moderation(env):
 c,h=client(env);t,th=teacher(env);t.post('/api/admin/settings',json={'is_open':True},headers=th)
 assert c.post('/api/spin',headers=h).status_code==400
 c.post('/api/quiz',json={'answers':[0]*12},headers=h);assert c.post('/api/spin',headers=h).status_code==400
 publish(c,h);t.post('/api/admin/moderate',json={'id':'post-1234567890abcdef','hidden':True},headers=th)
 assert env.test_client().get('/api/posts').json['posts']==[]
 assert c.post('/api/spin',headers=h).status_code==400
 t.post('/api/admin/moderate',json={'id':'post-1234567890abcdef','hidden':False},headers=th)
 assert c.post('/api/spin',headers=h).status_code==200

def test_concurrent_spin_and_snapshot_redeem(env):
 c,h=sorted_user(env);t,th=unlock(env,c,h)
 token=c.get_cookie('reading_session').value
 barrier=threading.Barrier(2)
 def spin():
  cc=env.test_client();cc.set_cookie('reading_session',token);barrier.wait();r=cc.post('/api/spin',headers=h);assert r.status_code==200;return r.json['ticket']
 with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:spin(),range(2)))
 assert results[0]['code']==results[1]['code']
 ticket=results[0];assert c.post('/api/spin',headers=h).json['ticket']['code']==ticket['code']
 assert c.get('/api/me').json['ticket']['code']==ticket['code']
 snap=json.loads(ticket['snapshot']);assert snap['number'] in range(1,10)
 assert t.post('/api/admin/settings',json={'prizes':['ใหม่']*8},headers=th).status_code==400
 assert t.post('/api/admin/settings',json={'is_open':False},headers=th).status_code==200
 assert c.post('/api/spin',headers=h).json['ticket']['snapshot']==ticket['snapshot']
 code=ticket['code'];assert t.post('/api/admin/redeem',json={'code':code},headers=th).status_code==200
 assert t.post('/api/admin/redeem',json={'code':code},headers=th).status_code==409
 assert c.get('/api/me').json['ticket']['redeemed']
 with env.app_context():assert db().execute('SELECT count(*) FROM spins').fetchone()[0]==1
 assert t.get('/api/admin/export').data.startswith(b'\xef\xbb\xbf')

def test_settings_before_launch(env):
 t,h=teacher(env);assert t.post('/api/admin/settings',json={'prizes':['ทดสอบ']*8},headers=h).status_code==200
 assert t.get('/api/config').json['prizes'][0]['name']=='ดูดวงกับแฮรรี่น็อต'
 assert t.post('/api/admin/settings',json={'is_open':True},headers=h).status_code==200
 assert t.post('/api/admin/settings',json={'is_open':False},headers=h).status_code==200
 assert t.post('/api/admin/settings',json={'prizes':['แก้']*8},headers=h).status_code==400

def test_duplicate_invite_concurrent(env):
 with env.app_context():db().execute("INSERT INTO invites VALUES ('single-code','2000',0)")
 def reg(_):
  return env.test_client().post('/api/register',json=dict(student_id='2000',name='ซ้ำ',classroom='1/1',number='1',password='test-password',code='single-code')).status_code
 with ThreadPoolExecutor(2) as pool:results=list(pool.map(reg,range(2)))
 assert sorted(results)==[200,400]
