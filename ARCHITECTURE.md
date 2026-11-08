# โครงสร้างระบบและสิทธิ์

เลือก Flask + SQLite + ระบบไฟล์บน persistent volume เพราะยกขึ้น GitHub และติดตั้งด้วย Docker ได้ครบทั้ง API และข้อมูล ไม่มี Firebase project หรือ cloud credential ที่ต้องส่งให้ผู้พัฒนา ทุกอุปกรณ์เชื่อม HTTPS เซิร์ฟเวอร์กลางเดียวกัน SQLite ไม่อยู่ในโทรศัพท์และไม่ใช้ localStorage เก็บข้อมูลจริง

## ตาราง

| ตาราง | ความสัมพันธ์/ข้อมูล |
|---|---|
| users | รหัสสมาชิก unique, password hash, ชื่อ/ห้อง/เลขที่, role, house |
| houses | บ้านทั้ง 4 และรายละเอียด JSON; content.py เป็นต้นฉบับเนื้อหาตายตัว |
| invites | รหัสสุ่มเฉพาะ student_id, ใช้ครั้งเดียวแบบ transaction |
| sessions | token สุ่ม, CSRF, อายุ 7 วัน, user_id |
| quizResults | user_id unique, คำตอบครบ, คะแนน 4 บ้าน, คำตอบตัดสิน, บ้าน |
| bookPosts | เจ้าของ, ข้อมูลหนังสือ JSON, hidden, วันสร้าง/แก้ไข |
| images | เจ้าของและ id รูป; ไฟล์จริงอยู่ uploads |
| activities | กิจกรรม reading-1, ชื่อ, เปิด/ปิด, เคยเปิดแล้วหรือไม่ |
| prizes | ช่อง 1–9 และชื่อปัจจุบัน |
| spins | unique(activity_id,user_id), ช่องสุ่มจาก secrets.randbelow(9) |
| tickets | code unique, spin_id unique, snapshot, เวลาออก/รับ, ผู้ยืนยัน |
| auth_attempts | จำกัดความถี่ login/register ต่อ IP + บัญชี 15 ครั้งใน 15 นาที |

## สิทธิ์

| ผู้ใช้ | อ่านได้ | เขียนได้ |
|---|---|---|
| ไม่เข้าสู่ระบบ | บ้าน/คำถาม/รางวัล/กิจกรรม, โพสต์ที่เผยแพร่, จำนวนรวม | login/register ที่ตรวจรหัสเข้าร่วม |
| นักเรียน | สาธารณะ + ข้อมูลบัญชี/โพสต์/ตั๋วของตัวเอง | โพสต์/รูปของตัวเอง; ส่งคำตอบให้เซิร์ฟเวอร์คำนวณ; ขอใช้สิทธิ์หมุน |
| ครู | นักเรียน, โพสต์ซ่อน, ตั๋ว, รหัสเข้าร่วม, CSV | สร้างรหัสเข้าร่วม, ซ่อน/คืนโพสต์, ชื่อรางวัลก่อนเปิด, เปิดปิด, ยืนยันรับ |
| ผู้ดูแลเซิร์ฟเวอร์ | ไฟล์ระบบตามสิทธิ์เครื่อง | สร้างครู/รีเซ็ตรหัสผ่าน/backup ผ่าน CLI |

ไม่มี direct database endpoint นักเรียนส่ง house/role/คะแนน/ผลรางวัล/สถานะรับเพื่อเปลี่ยนเองไม่ได้ แอปไม่เชื่อค่า user_id จาก browser ในการเขียน ใช้ session ปัจจุบันเสมอ การ query ใช้ parameter binding และ UI escape HTML ข้อมูลผู้ใช้

## API

- GET /api/config — เนื้อหาสาธารณะและสถานะกิจกรรม
- POST /api/register, /api/login — Authentication จริง รหัสผ่าน hash ด้วย Werkzeug scrypt
- GET /api/me — บัญชี/โพสต์/ตั๋วของ session; ไม่เข้าสู่ระบบได้ user=null
- POST /api/logout — ยกเลิก session ปัจจุบัน
- POST /api/quiz — 12 house indexes คำนวณฝั่งเซิร์ฟเวอร์; เมื่อเสมอคืน tied ให้ UI ถามเพิ่ม
- GET /api/posts — ข้อมูลสาธารณะไม่รวมรหัสนักเรียน/ห้อง/เลขที่/ข้อมูลบัญชี
- PUT /api/posts/:id — เพิ่ม/แก้ของตน; id คงเดิมเมื่อ retry ป้องกันสร้างซ้ำ
- DELETE /api/posts/:id — ลบของตน
- POST /api/uploads — ตรวจ MIME/เนื้อหาจริง/ขนาด <=5 MB; ย่อ 1600px และแปลง WebP ลบ EXIF
- GET /media/:id — รูป published อ่านสาธารณะ; รูป draft/hidden อ่านได้เฉพาะเจ้าของหรือครู
- POST /api/spin — เรียกตั๋วเดิม หรือสร้างผล+ตั๋ว transaction เดียว
- GET /api/admin — ข้อมูลห้องครู
- POST /api/admin/invites, /settings, /moderate, /redeem — ครูพร้อม CSRF
- GET /api/admin/export — CSV ครู, BOM ภาษาไทย, ป้องกัน spreadsheet formula injection

## การใช้สิทธิ์พร้อมกัน

SQLite `BEGIN IMMEDIATE` จอง write lock ก่อนตรวจตั๋วเก่าและเงื่อนไข เมื่อมีสองแท็บเรียกพร้อมกัน คำขอแรกสร้าง spin และ ticket แล้ว commit คำขอที่สองจะอ่านตั๋วเดิมจากฐานข้อมูล มี UNIQUE(activity_id,user_id) ป้องกันอีกชั้น ทั้งผลและตั๋วอยู่ใน transaction เดียวกัน ถ้า error จะ rollback ไม่เสียสิทธิ์ หากเครือข่ายขาดหลัง commit การ retry คืนผลเดิมก่อนตรวจช่วงเปิดปิดกิจกรรม

UI รับผลจากเซิร์ฟเวอร์ก่อนหมุน CSS วงล้อ ช่องเริ่มต้นมีศูนย์กลาง `(number-1)*40+20` องศาจากด้านบนแบบตามเข็มนาฬิกา จึงหมุน `2160-center` องศาให้ตรงลูกศร ไม่ใช้ Math.random ตัดสินรางวัล

ตั๋วใช้ random code 64 บิตพร้อม unique constraint, snapshot ชื่อ/บ้าน/กิจกรรม/รางวัล เวลา UTC ในฐานข้อมูล แสดง Asia/Bangkok ทั้งเว็บและ PNG การยืนยันรับใช้ conditional UPDATE WHERE redeemed IS NULL เป็นคำสั่ง atomic

## ความปลอดภัยและขอบเขตการใช้งาน

- session อยู่ในฐานข้อมูล Cookie HttpOnly/SameSite=Lax และ Secure เมื่อเปิด HTTPS
- ไม่เก็บ password plaintext หรือ secret ครูใน frontend
- ทุก write หลัง login ต้องมี CSRF token; ตรวจ Origin สำหรับ write ทั้งหมด
- CSP จำกัดสคริปต์/ฟอนต์/รูปที่จำเป็น; ไม่มี third-party analytics หรือ CDN
- รหัสเข้าร่วมต้องผูกนักเรียนตรงกันและใช้ได้ครั้งเดียว
- session หมดอายุ 7 วัน; reset ผ่าน CLI ลบ sessions ทั้งหมดของบัญชี
- ค่า classroom/number ตอนลงทะเบียนกรอกโดยนักเรียน ครูควรตรวจรายชื่อก่อนใช้ผลทางการ
- โพสต์อ่านสาธารณะ ใช้ชื่อแสดงที่ไม่เปิดเผยข้อมูลส่วนตัวตามความเหมาะสม
- ไม่มีแชต ความคิดเห็น อีเมลยืนยัน หรือ social login ในเวอร์ชันนี้
- หนึ่งกิจกรรมต่อ installation ในเวอร์ชันนี้ schema เตรียม activity_id แต่ยังไม่มีหน้าสร้างกิจกรรมใหม่ อย่าลบ spins เพื่อล้างสิทธิ์ระหว่างกิจกรรม
- ฉบับร่างเก็บใน localStorage **เฉพาะเครื่องและบัญชีนั้น** ไม่ซิงก์ข้ามเครื่อง; โพสต์จริง/บ้าน/ตั๋วอยู่กลางทั้งหมด คำตอบคัดสรรที่ยังไม่ส่งไม่บันทึกข้ามเครื่อง
- รูปที่อัปโหลดแต่ยังไม่เผยแพร่คงอยู่ จำกัด 100 รูปต่อบัญชี; ยังไม่มีเครื่องมือล้างรูปที่ไม่ใช้งานอัตโนมัติ
- ห้องสมุดดึงไม่เกิน 1,000 โพสต์ล่าสุด ไม่มี pagination สำหรับคลังขนาดใหญ่มาก
- ไม่มี realtime push เมื่อมีคนโพสต์ใหม่ ให้รีเฟรชหรือเปิดหน้าห้องสมุดอีกครั้ง
- SQLite เหมาะกับ single server/volume ต้องเปลี่ยนไป PostgreSQL + object storage ก่อนขยายหลาย replicas
- อย่าเชื่อค่าจาก PNG เพื่อมอบของรางวัล ให้ครูตรวจรหัสและสถานะกับฐานข้อมูลเสมอ
- rate limit ผูก IP + hash รหัสสมาชิก จึงไม่ล็อกทุกบัญชีในห้องเรียนที่ใช้ Wi-Fi เดียวกัน หากเปิดสาธารณะขนาดใหญ่ ควรเพิ่ม edge rate limiter และตั้ง trusted proxy ตามโครงสร้างจริง
