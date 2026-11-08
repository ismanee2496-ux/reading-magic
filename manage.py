"""Administrative CLI, never exposed to the browser. Passwords entered via getpass."""
import argparse,getpass,secrets,json
from app import app,db,now
from werkzeug.security import generate_password_hash
p=argparse.ArgumentParser(description='จัดการบ้านเวทมนตร์รักการอ่าน')
p.add_argument('command',choices=['teacher','invite','reset','backup'])
p.add_argument('student_id',nargs='?')
p.add_argument('--name',default='ครูผู้ดูแล')
p.add_argument('--output',default='reading-backup.db')
a=p.parse_args()
with app.app_context():
 if a.command=='backup':
  import sqlite3
  target=sqlite3.connect(a.output);db().backup(target);target.close();print('สำรองฐานข้อมูลแล้ว ต้องคัดลอกโฟลเดอร์ uploads ด้วย')
 elif not a.student_id: p.error('กรุณาระบุรหัสสมาชิก')
 elif a.command=='invite':
  code=secrets.token_urlsafe(12);db().execute('INSERT INTO invites VALUES (?,?,0)',(code,a.student_id));print('รหัสเข้าร่วม:',code)
 else:
  password=getpass.getpass('รหัสผ่านใหม่ (อย่างน้อย 10 ตัว): ')
  if len(password)<10: raise SystemExit('รหัสผ่านสั้นเกินไป')
  confirm=getpass.getpass('ยืนยันรหัสผ่าน: ')
  if password!=confirm: raise SystemExit('รหัสผ่านไม่ตรงกัน')
  hashed=generate_password_hash(password)
  if a.command=='teacher':
   db().execute("INSERT INTO users(id,student_id,name,classroom,number,password,role,created) VALUES (?,?,?,'ครู','0',?,'teacher',?)",(secrets.token_hex(16),a.student_id,a.name,hashed,now()));print('สร้างบัญชีครูแล้ว')
  else:
   u=db().execute('SELECT id FROM users WHERE student_id=?',(a.student_id,)).fetchone()
   if not u: raise SystemExit('ไม่พบรหัสสมาชิก')
   db().execute('UPDATE users SET password=? WHERE id=?',(hashed,u['id']));db().execute('DELETE FROM sessions WHERE user_id=?',(u['id'],));print('รีเซ็ตรหัสผ่านและออกจากระบบทุกอุปกรณ์แล้ว')
