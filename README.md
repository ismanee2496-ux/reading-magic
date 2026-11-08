# บ้านเวทมนตร์รักการอ่าน

เว็บแอปภาษาไทยสำหรับนักเรียนมัธยมต้น ลงทะเบียน → แบบทดสอบ 12 ข้อ → คัดบ้าน → แชร์หนังสือพร้อมรูป → หมุนวงล้อ → ตั๋วรางวัล พร้อมห้องครู

**สถานะส่งมอบ:** โค้ดทำงานร่วมกับฐานข้อมูลจริงเมื่อรันเซิร์ฟเวอร์ ไม่ได้เชื่อมบัญชีโฮสติ้งของครูหรือเผยแพร่เว็บไซต์ออนไลน์ให้แล้ว ไม่มีข้อมูลนักเรียนหรือรหัสครูตัวอย่างฝังมา ต้องสร้างบัญชีครูและรหัสเข้าร่วมก่อนใช้งาน

## 1. เริ่มเร็วด้วย Docker

ติดตั้ง Docker พร้อม Compose บนเครื่องที่ใช้รัน แยก ZIP แล้วเปิด Terminal ในโฟลเดอร์ที่มี `compose.yaml`

```sh
docker compose up --build -d
docker compose exec reading python manage.py teacher teacher01 --name "ครูอิส"
```

ระบบถามรหัสผ่านสองครั้ง ใช้อย่างน้อย 10 ตัวอักษร ไม่แสดงรหัสผ่านใน Terminal ไม่ต้องแก้ซอร์สโค้ดเพื่อใส่รหัสครู

1. เปิด `http://localhost:8000`
2. เข้าสู่ระบบด้วยรหัสสมาชิก `teacher01` และรหัสผ่านที่เพิ่งตั้ง
3. ไป **ห้องครู** สร้างรหัสเข้าร่วมให้รหัสนักเรียนแต่ละคน
4. มอบรหัสเข้าร่วมให้เจ้าของรหัสนักเรียนเป็นการส่วนตัว นักเรียนเลือกลิงก์ลงทะเบียนครั้งแรก
5. แก้ชื่อของสมนาคุณช่อง 2–9 ก่อนเปิดวงล้อครั้งแรก
6. นักเรียนตอบครบ 12 ข้อ ถ้าเสมอจะมีคำถามเลือกเฉพาะแนวที่เสมอ
7. นักเรียนแชร์หนังสือ แล้วครูเปิดช่วงหมุนวงล้อจากห้องครู
8. นักเรียนหมุน รับตั๋ว บันทึก PNG หรือแคปหน้าจอ ครูตรวจรหัสตั๋วแล้วกดยืนยันมอบรางวัล

หากเปิดเครื่องเดียวกันเป็นหลายบัญชี ใช้หน้าต่างไม่ระบุตัวตนหรือคนละเบราว์เซอร์ แต่ละแท็บของเบราว์เซอร์เดียวกันใช้ session เดียวกัน

## 2. นำไฟล์ขึ้น GitHub

สร้าง repository ใหม่ แล้วอัปโหลด **ไฟล์ข้างในโฟลเดอร์ reading-magic** ให้ `app.py`, `Dockerfile`, `requirements.txt` และ `static/` อยู่ที่ราก repository ไม่ต้องอัปโหลด ZIP ทั้งก้อนเป็นไฟล์เดียว หากใช้ Git:

```sh
git init
git add .
git commit -m "Create reading magic application"
git branch -M main
git remote add origin https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY.git
git push -u origin main
```

แทน `YOUR_ACCOUNT` และ `YOUR_REPOSITORY` ด้วยของจริง การยืนยันตัวตน GitHub ใช้เครื่องมือ Git ของครู อย่าวาง token ในไฟล์เว็บ

**GitHub เก็บโค้ด ส่วนเซิร์ฟเวอร์รันเว็บแอป** GitHub Pages ไม่รองรับ Python backend จึงใช้ Pages อย่างเดียวกับโครงการนี้ไม่ได้ ดูเอกสาร [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site)

## 3. ทำให้หลายอุปกรณ์ใช้งานข้อมูลกลางเดียวกัน

เลือกเซิร์ฟเวอร์/VPS หรือบริการโฮสต์ Docker ที่ให้พื้นที่ถาวรและเข้า Terminal ได้ โครงการนี้เหมาะกับหนึ่งโรงเรียนที่รันเซิร์ฟเวอร์หนึ่งชุด ไม่ใช้ serverless filesystem ชั่วคราว ไม่ขยายหลาย instance ที่แยกไฟล์ฐานข้อมูลกัน

### วิธีบนเซิร์ฟเวอร์ Docker

1. นำ repository ลงเซิร์ฟเวอร์ แล้วรัน `docker compose up --build -d`
2. รันคำสั่งสร้างครูจากข้อ 1 บนเซิร์ฟเวอร์นี้ บัญชีในเครื่องทดสอบไม่ได้ตามขึ้นอัตโนมัติ
3. ตั้งโดเมนมายังเซิร์ฟเวอร์ และตั้ง HTTPS reverse proxy เช่น Caddy หรือ nginx ให้ส่งคำขอไปพอร์ต 8000 โดยรักษา Host/Origin เดิม
4. สร้างไฟล์ `.env` บนเซิร์ฟเวอร์ ใส่ `COOKIE_SECURE=1` แล้วรัน `docker compose up -d` อีกครั้ง ใช้ค่านี้เมื่อเข้าผ่าน HTTPS แล้วเท่านั้น
5. ปิดการเข้าถึงพอร์ตฐานข้อมูล/ไฟล์โดยตรง โครงการไม่ต้องเปิดพอร์ต SQLite ใด ๆ หน้าเว็บและ API อยู่โดเมนเดียวกัน
6. เปิด URL HTTPS เดียวกันจากมือถือ แท็บเล็ต และคอมพิวเตอร์ ทุกเครื่องจะอ่านข้อมูลจากเซิร์ฟเวอร์เดียวกัน
7. ทดสอบรายการใน `TESTING.md` ก่อนเชิญนักเรียน

### หากใช้บริการโฮสต์ที่เชื่อม GitHub

- เลือก build จาก `Dockerfile` ที่ราก repository
- ติด persistent disk/volume ที่ `/data` ให้ UID 10001 อ่านเขียนได้
- ตั้ง `DATA_DIR=/data`, `COOKIE_SECURE=1` และใช้พอร์ตจากตัวแปร `PORT` (ค่าเริ่มต้น 8000)
- รัน 1 instance / 1 replica; ภายในมี Gunicorn 1 worker / 8 threads
- ให้บริการจัด HTTPS และตรวจว่า `GET /api/config` ตอบ JSON
- ใช้ Terminal ของ container รัน `python manage.py teacher teacher01 --name "ครูอิส"`
- ห้ามใส่ข้อมูลนักเรียน รหัสผ่าน หรือไฟล์ฐานข้อมูลไว้ใน repository

ไฟล์ `.env.example` เป็นตัวอย่างเท่านั้น แอปอ่าน environment ที่ระบบรันส่งให้ ไม่โหลด `.env` เอง ยกเว้น Compose ซึ่งอ่านไฟล์นี้ให้ตามปกติ `.env.example` ไม่ต้องมี Firebase API key เพราะใช้ฐานข้อมูล SQL กลางของเซิร์ฟเวอร์

## 4. ทางเลือก: รัน Python โดยไม่ใช้ Docker

Python 3.12 ขึ้นไป:

```sh
python -m venv .venv
```

เปิด virtual environment:

- Windows PowerShell: `.venv\Scripts\Activate.ps1`
- macOS/Linux: `source .venv/bin/activate`

จากนั้น:

```sh
python -m pip install -r requirements.txt
python manage.py teacher teacher01 --name "ครูอิส"
python app.py
```

เปิด `http://localhost:8000` ใช้การรันนี้เพื่อทดลองในเครื่อง สำหรับ production Linux ให้ใช้ Gunicorn หลัง HTTPS reverse proxy:

```sh
gunicorn --workers 1 --threads 8 --bind 0.0.0.0:8000 --timeout 60 app:app
```

ตั้ง `DATA_DIR` เป็นไดเรกทอรีถาวรที่เขียนได้ และ `COOKIE_SECURE=1` ผ่าน environment ของ service manager ดู [Flask production](https://flask.palletsprojects.com/en/stable/deploying/) Gunicorn ไม่รองรับ Windows โดยตรง ให้ใช้ Docker บน Windows สำหรับการรันแบบ production

## 5. หน้าจอและความสามารถ

| หน้า | ความสามารถ |
|---|---|
| หน้าแรก | ปราสาทวาด SVG, บ้านทั้ง 4, ความคืบหน้า, ลดภาพเคลื่อนไหว |
| เข้าสู่ระบบ | รหัสสมาชิกและรหัสผ่าน; ลงทะเบียนต้องใช้รหัสเข้าร่วมผูกนักเรียนรายคน |
| คัดสรร | สถานการณ์ 12 ข้อ ทีละข้อ ย้อนกลับได้ สลับตัวเลือก ถามตัดสินคะแนนเสมอ บันทึกฝั่งเซิร์ฟเวอร์ |
| บ้านของฉัน | ชื่อบ้านพร้อมแนว, คำขวัญ, จำนวนจริง, หนังสือของฉันและหนังสือของบ้าน |
| แชร์หนังสือ | ข้อมูลจำเป็นครบ, 1–5 ดาว, ไม่เกิน 3 รูป, ดูตัวอย่าง, ฉบับร่างในเครื่อง, แก้ไข/ลบของตน |
| ห้องสมุด | สาธารณะ, ทุกบ้าน/กรองบ้าน, ค้นชื่อ/ผู้เขียน/ผู้แชร์, กรองแนว, เรียงใหม่/ชื่อ |
| วงล้อ | 9 ช่องเท่ากัน, สุ่มที่เซิร์ฟเวอร์, ตรวจเงื่อนไขจริง, หนึ่งสิทธิ์ต่อกิจกรรม |
| ตั๋ว | สำเนารางวัล ณ เวลาออก, เวลาไทย, รหัสเฉพาะ, สถานะรับจริง, PNG ฟอนต์ไทยในโครงการ |
| ห้องครู | นักเรียน/กรองสถานะ, รหัสเข้าร่วม, ชื่อรางวัล, เปิดปิดวงล้อ, ซ่อนโพสต์, ตรวจ/รับตั๋ว, CSV UTF-8 BOM |

รางวัลชนะเลิศมีเพียงหนึ่ง **ประเภท** คือ “ดูดวงกับแฮรรี่น็อต” โอกาส 1/9 ต่อคน จึงมีผู้ชนะหลายคนได้ ระบบล็อกชื่อรางวัลเมื่อเปิดกิจกรรมครั้งแรก แม้ครูปิดกิจกรรมภายหลังก็แก้ไม่ได้ ตั๋วเดิมเก็บชื่อรางวัลแยกเป็น snapshot

## 6. โครงสร้างโครงการ

```text
app.py                 API, sessions, permissions, transactions, image processing
content.py             บ้านทั้ง 4, คำถาม 12 ข้อ, mapping, score, ชื่อรางวัล
schema.sql             ตารางและ unique constraints
manage.py              สร้างครู/รหัสเข้าร่วม/รีเซ็ตรหัสผ่าน/สำรองฐานข้อมูล
static/index.html      โครงหน้าเว็บ
static/app.js          เส้นทางหน้าจอและการโต้ตอบ
static/style.css       Responsive 360px ขึ้นไปและ reduced motion
static/fonts/          Noto Sans Thai พร้อมใบอนุญาต OFL
requirements*.txt      dependencies สำหรับรัน/ทดสอบ
Dockerfile             production container
compose.yaml           ตัวรันพร้อม volume ถาวร
.env.example           ตัวอย่าง environment ไม่มีข้อมูลลับ
.github/workflows/     ชุดทดสอบเมื่อ push GitHub
TESTING.md             ผลทดสอบและรายการตรวจในเบราว์เซอร์
ARCHITECTURE.md        ตาราง/API/สิทธิ์/ข้อจำกัด
```

## 7. ดูแลและสำรองข้อมูล

สร้างรหัสเข้าร่วมจาก CLI ได้เช่นกัน:

```sh
docker compose exec reading python manage.py invite 12345
```

ลืมรหัสผ่าน: ครูตรวจตัวตนนักเรียนก่อน แล้วผู้ดูแลเซิร์ฟเวอร์รัน:

```sh
docker compose exec reading python manage.py reset 12345
```

การ reset จะยกเลิก session เดิมทุกเครื่อง ไม่มีการกู้ผ่านอีเมลในเวอร์ชันนี้

สำรอง SQLite ด้วย online backup API:

```sh
docker compose exec reading python manage.py backup --output /data/reading-backup.db
docker compose cp reading:/data/reading-backup.db ./reading-backup.db
```

ต้องสำรอง `/data/uploads` ควบคู่กัน เก็บนอกเซิร์ฟเวอร์และจำกัดสิทธิ์ผู้เข้าถึง สำหรับชุดสำรองที่มีฐานข้อมูลและรูปตรงเวลาเดียวกัน ให้ปิดกิจกรรมและหยุดการเขียนชั่วคราว หรือหยุด container แล้ว snapshot volume ทั้งก้อน

**ห้ามใช้ `docker compose down -v` ถ้ายังต้องการข้อมูลเดิม** เพราะจะลบ volume การอัปเดตด้วย `docker compose up --build -d` ไม่ลบ named volume อย่าส่งไฟล์ฐานข้อมูล/รูปนักเรียนขึ้น GitHub

## 8. สิ่งที่ต้องตั้งค่าจริงก่อนใช้

- repository GitHub ของครู
- เซิร์ฟเวอร์และพื้นที่เก็บข้อมูลถาวร
- URL/โดเมนและ HTTPS พร้อม `COOKIE_SECURE=1`
- บัญชีครูและรหัสผ่านที่สร้างเอง
- รหัสนักเรียนและรหัสเข้าร่วมรายคน
- ชื่อของสมนาคุณและช่วงเวลาเปิดหมุน
- การสำรองข้อมูลและตรวจรายการใน TESTING.md

ไม่มีค่าลับที่ต้องใส่ใน JavaScript และไม่มีบริการภายนอกเรียกเก็บเงินที่โค้ดนี้สมัครให้อัตโนมัติ
