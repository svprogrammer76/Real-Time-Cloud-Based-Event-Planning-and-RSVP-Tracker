"""Real-Time Cloud Event RSVP Tracker: local runnable FastAPI implementation."""
import os, time, json, base64, hashlib, hmac, secrets, re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, String, Integer, ForeignKey, UniqueConstraint, Text, DateTime, Boolean, func, and_, text, event as sqlalchemy_event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session, sessionmaker
import httpx

ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')
URL=os.getenv('DATABASE_URL',f"sqlite:///{ROOT/'events.db'}")
engine=create_engine(URL,connect_args={'check_same_thread':False} if URL.startswith('sqlite') else {})
if URL.startswith('sqlite'):
    @sqlalchemy_event.listens_for(engine,'connect')
    def enable_sqlite_foreign_keys(connection,record):
        cursor=connection.cursor();cursor.execute('PRAGMA foreign_keys=ON');cursor.close()
SessionLocal=sessionmaker(engine,expire_on_commit=False)
SECRET=os.getenv('APP_SECRET','local-demo-secret-change-before-deployment')
def utcnow():return datetime.now(timezone.utc)
def parse_deadline(value):
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result
class Base(DeclarativeBase): pass
class User(Base):
    __tablename__='users'; id:Mapped[int]=mapped_column(primary_key=True); email:Mapped[str]=mapped_column(String(254),unique=True,index=True); username:Mapped[str]=mapped_column(String(50),unique=True); name:Mapped[str]=mapped_column(String(80)); password:Mapped[Optional[str]]=mapped_column(String(200),nullable=True); role:Mapped[str]=mapped_column(String(20))
class Event(Base):
    __tablename__='events'; id:Mapped[int]=mapped_column(primary_key=True); organizer_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True); name:Mapped[str]=mapped_column(String(120)); description:Mapped[str]=mapped_column(Text,default=''); date:Mapped[str]=mapped_column(String(10)); time:Mapped[str]=mapped_column(String(5)); venue:Mapped[str]=mapped_column(String(200)); capacity:Mapped[int]=mapped_column(Integer); deadline:Mapped[str]=mapped_column(String(40)); status:Mapped[str]=mapped_column(String(20),default='PUBLISHED'); event_type:Mapped[str]=mapped_column(String(50),default='OTHER'); end_time:Mapped[str]=mapped_column(String(5),default=''); online_link:Mapped[str]=mapped_column(String(500),default=''); updated_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow)
class RSVP(Base):
    __tablename__='rsvps'; __table_args__=(UniqueConstraint('event_id','user_id',name='uq_event_user'),); id:Mapped[int]=mapped_column(primary_key=True); event_id:Mapped[int]=mapped_column(ForeignKey('events.id'),index=True); user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True); status:Mapped[str]=mapped_column(String(20)); updated_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow)
class Announcement(Base):
    __tablename__='announcements'; id:Mapped[int]=mapped_column(primary_key=True); event_id:Mapped[int]=mapped_column(ForeignKey('events.id')); title:Mapped[str]=mapped_column(String(120)); message:Mapped[str]=mapped_column(Text); created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow)
class Waitlist(Base):
    __tablename__='waitlist'; __table_args__=(UniqueConstraint('event_id','user_id',name='uq_waitlist_event_user'),); id:Mapped[int]=mapped_column(primary_key=True); event_id:Mapped[int]=mapped_column(ForeignKey('events.id'),index=True); user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True); joined_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow); status:Mapped[str]=mapped_column(String(20),default='WAITING')
class Invitation(Base):
    __tablename__='invitations'; __table_args__=(UniqueConstraint('event_id','email',name='uq_invite_event_email'),); id:Mapped[int]=mapped_column(primary_key=True); event_id:Mapped[int]=mapped_column(ForeignKey('events.id'),index=True); email:Mapped[str]=mapped_column(String(254)); created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow)
class Notification(Base):
    __tablename__='notifications'; id:Mapped[int]=mapped_column(primary_key=True); user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True); event_id:Mapped[int]=mapped_column(ForeignKey('events.id'),index=True); kind:Mapped[str]=mapped_column(String(40)); message:Mapped[str]=mapped_column(String(500)); is_read:Mapped[bool]=mapped_column(Boolean,default=False); created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow)
class RevokedToken(Base):
    __tablename__='revoked_tokens'; id:Mapped[int]=mapped_column(primary_key=True); signature:Mapped[str]=mapped_column(String(100),unique=True); expires_at:Mapped[int]=mapped_column(Integer)
Base.metadata.create_all(engine)
# SQLAlchemy create_all does not alter existing PostgreSQL tables. Keep profile
# columns required by the ORM present on older Supabase schemas.
if engine.dialect.name=='postgresql':
    with engine.begin() as conn:
        conn.exec_driver_sql('ALTER TABLE public.users ADD COLUMN IF NOT EXISTS username VARCHAR(50)')
        conn.exec_driver_sql("UPDATE public.users SET username = 'legacy_' || id::text WHERE username IS NULL")
        conn.exec_driver_sql('ALTER TABLE public.users ALTER COLUMN username SET NOT NULL')
        conn.exec_driver_sql('ALTER TABLE public.users ADD COLUMN IF NOT EXISTS password VARCHAR(200)')
        conn.exec_driver_sql("ALTER TABLE public.users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'ATTENDEE'")
# create_all does not add columns to an existing local database; apply safe additive SQLite migrations.
if engine.dialect.name=='sqlite':
    with engine.begin() as conn:
        columns={row[1] for row in conn.exec_driver_sql('PRAGMA table_info(events)').all()}
        for name,definition in {'event_type':"VARCHAR(50) NOT NULL DEFAULT 'OTHER'",'end_time':"VARCHAR(5) NOT NULL DEFAULT ''",'online_link':"VARCHAR(500) NOT NULL DEFAULT ''",'updated_at':"DATETIME"}.items():
            if name not in columns: conn.exec_driver_sql(f'ALTER TABLE events ADD COLUMN {name} {definition}')
        for table,name,definition in [('rsvps','updated_at','DATETIME'),('announcements','created_at','DATETIME')]:
            known={row[1] for row in conn.exec_driver_sql(f'PRAGMA table_info({table})').all()}
            if name not in known: conn.exec_driver_sql(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')
app=FastAPI(title='Real-Time Cloud Event RSVP Tracker')
origins=[item.strip() for item in os.getenv('CORS_ORIGINS','http://127.0.0.1:8000,http://localhost:8000').split(',') if item.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_methods=['GET','POST','PUT','DELETE'],allow_headers=['Authorization','Content-Type'])
def dbdep():
    db=SessionLocal()
    try: yield db
    finally: db.close()
def hashpw(p):
    salt=secrets.token_bytes(16); return base64.b64encode(salt).decode()+':'+base64.b64encode(hashlib.pbkdf2_hmac('sha256',p.encode(),salt,260000)).decode()
def validpw(p,s):
    try:
        a,b=s.split(':'); actual=hashlib.pbkdf2_hmac('sha256',p.encode(),base64.b64decode(a),260000)
        return hmac.compare_digest(actual,base64.b64decode(b))
    except Exception:return False
def make_username(email,user_id=None):
    base=re.sub(r'[^a-z0-9]+','',email.split('@',1)[0].lower())[:10] or 'user'
    suffix=re.sub(r'[^a-f0-9]','',str(user_id or secrets.token_hex(4)).lower())[:8]
    return f'{base}_{suffix}'[:20]
def issue(uid):
    p=base64.urlsafe_b64encode(json.dumps({'uid':uid,'exp':time.time()+86400,'jti':secrets.token_urlsafe(16)}).encode()).decode().rstrip('='); sig=base64.urlsafe_b64encode(hmac.new(SECRET.encode(),p.encode(),hashlib.sha256).digest()).decode().rstrip('='); return p+'.'+sig
def auth(authorization:Optional[str]=Header(None),db:Session=Depends(dbdep)):
    raw=authorization.removeprefix('Bearer ') if authorization else ''
    if raw.count('.')==2 and os.getenv('SUPABASE_URL') and os.getenv('SUPABASE_ANON_KEY'):
        try:
            with httpx.Client(timeout=5) as client:
                response=client.get(os.getenv('SUPABASE_URL').rstrip('/')+'/auth/v1/user',headers={'apikey':os.getenv('SUPABASE_ANON_KEY'),'Authorization':f'Bearer {raw}'})
        except httpx.HTTPError as error:
            raise HTTPException(503,'Could not reach Supabase Auth') from error
        if response.status_code!=200:raise HTTPException(401,'Supabase session is invalid or expired')
        try:
            identity=response.json(); email=identity.get('email')
        except (ValueError,AttributeError):
            raise HTTPException(401,'Supabase returned an invalid user profile')
        if not email:raise HTTPException(401,'Supabase account has no email address')
        u=db.query(User).filter(func.lower(User.email)==email.lower()).first()
        if not u:
            metadata=identity.get('user_metadata') or {}; role=str(metadata.get('role','ATTENDEE')).upper()
            if role not in ('ATTENDEE','ORGANIZER'):role='ATTENDEE'
            u=User(email=email.lower(),username=make_username(email,identity.get('id')),name=str(metadata.get('full_name') or email.split('@')[0])[:80],password=None,role=role)
            db.add(u);db.commit();db.refresh(u)
        return u
    try:
        p,s=raw.split('.'); want=base64.urlsafe_b64encode(hmac.new(SECRET.encode(),p.encode(),hashlib.sha256).digest()).decode().rstrip('=')
        if not hmac.compare_digest(s,want): raise ValueError()
        data=json.loads(base64.urlsafe_b64decode(p+'='*(-len(p)%4)))
        if data['exp']<time.time(): raise ValueError()
        if db.query(RevokedToken).filter_by(signature=s).first():raise ValueError()
        u=db.get(User,data['uid'])
        if not u: raise ValueError()
        return u
    except Exception: raise HTTPException(401,'Sign in required')
class Register(BaseModel): name:str=Field(min_length=1,max_length=80); email:str=Field(min_length=5,max_length=254); password:str=Field(min_length=10,max_length=128); role:str='ATTENDEE'
class Login(BaseModel): email:str; password:str
class EventIn(BaseModel): name:str=Field(min_length=3,max_length=120); description:str=Field(default='',max_length=3000); date:str; time:str; end_time:str=''; venue:str=Field(min_length=1,max_length=200); capacity:int=Field(gt=0,le=100000); deadline:str; event_type:str='OTHER'; online_link:str=''
class RSVPIn(BaseModel): status:str
class AnnouncementIn(BaseModel): title:str=Field(min_length=2,max_length=120); message:str=Field(min_length=1,max_length=3000)
class InviteIn(BaseModel): emails:list[str]=Field(min_length=1,max_length=200)
class ReadIn(BaseModel): is_read:bool=True
class WaitlistIn(BaseModel): join:bool=True
@app.get('/')
def home():
    built=ROOT/'frontend'/'dist'/'index.html'
    return FileResponse(built if built.exists() else ROOT/'frontend'/'index.html')
@app.get('/config.json')
def public_config():
    return JSONResponse({'supabaseUrl':os.getenv('SUPABASE_URL'),'supabaseAnonKey':os.getenv('SUPABASE_ANON_KEY')})
@app.get('/style.css')
def stylesheet():return FileResponse(ROOT/'frontend'/'style.css',media_type='text/css')
@app.get('/app.js')
def javascript():return FileResponse(ROOT/'frontend'/'app.js',media_type='application/javascript')
if (ROOT/'frontend'/'dist'/'assets').exists():
    app.mount('/assets',StaticFiles(directory=ROOT/'frontend'/'dist'/'assets'),name='assets')
@app.get('/health')
def health(db:Session=Depends(dbdep)):
    try:db.execute(text('SELECT 1'))
    except Exception:raise HTTPException(503,'Database unavailable')
    return {'ok':True,'database':'reachable'}
@app.post('/api/register',status_code=201)
def register(x:Register,db:Session=Depends(dbdep)):
    role=x.role.upper()
    if role not in ('ATTENDEE','ORGANIZER'):raise HTTPException(422,'Invalid role')
    email=x.email.strip().lower()
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',email):raise HTTPException(422,'Enter a valid email address')
    if db.query(User).filter(func.lower(User.email)==email).first():raise HTTPException(409,'Email is already registered')
    u=User(name=x.name.strip(),email=email,username=make_username(email),password=hashpw(x.password),role=role);db.add(u);db.commit();db.refresh(u);return {'token':issue(u.id),'user':{'id':u.id,'name':u.name,'role':role}}
@app.post('/api/login')
def login(x:Login,db:Session=Depends(dbdep)):
    u=db.query(User).filter(func.lower(User.email)==x.email.strip().lower()).first()
    if not u or not validpw(x.password,u.password):raise HTTPException(401,'Incorrect email or password')
    return {'token':issue(u.id),'user':{'id':u.id,'name':u.name,'role':u.role}}
@app.post('/api/logout')
def logout(authorization:Optional[str]=Header(None),u:User=Depends(auth),db:Session=Depends(dbdep)):
    raw=authorization.removeprefix('Bearer ');signature=raw.rsplit('.',1)[-1]
    payload=raw.split('.',1)[0];data=json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4)))
    if not db.query(RevokedToken).filter_by(signature=signature).first():db.add(RevokedToken(signature=signature,expires_at=int(data['exp'])));db.commit()
    return {'logged_out':True}
@app.get('/api/me')
def me(u:User=Depends(auth)):return {'id':u.id,'name':u.name,'email':u.email,'role':u.role}
def counts(db,e):
    d=dict(db.query(RSVP.status,func.count(RSVP.id)).filter_by(event_id=e.id).group_by(RSVP.status).all());g=d.get('GOING',0)
    waiting=db.query(Waitlist).filter_by(event_id=e.id,status='WAITING').count()
    return {'going':g,'maybe':d.get('MAYBE',0),'not_going':d.get('NOT_GOING',0),'available':max(0,e.capacity-g),'full':g>=e.capacity,'waitlist':waiting}
def view(db,e,viewer_id=None):
    org=db.get(User,e.organizer_id);current=counts(db,e);status='FULL' if current['full'] and e.status=='PUBLISHED' else e.status
    my_status=db.query(RSVP.status).filter_by(event_id=e.id,user_id=viewer_id).scalar() if viewer_id else None
    return {'id':e.id,'organizer_id':e.organizer_id,'organizer':org.name,'name':e.name,'description':e.description,'date':e.date,'time':e.time,'end_time':e.end_time,'venue':e.venue,'online_link':e.online_link,'event_type':e.event_type,'deadline':e.deadline,'capacity':e.capacity,'status':status,'updated_at':e.updated_at.isoformat() if e.updated_at else None,'my_status':my_status,**current}
@app.get('/api/events')
def events(u:User=Depends(auth),db:Session=Depends(dbdep)):return [view(db,e,u.id) for e in db.query(Event).filter(Event.status=='PUBLISHED').order_by(Event.date,Event.time).all()]
@app.post('/api/events',status_code=201)
def create_event(x:EventIn,u:User=Depends(auth),db:Session=Depends(dbdep)):
    if u.role!='ORGANIZER':raise HTTPException(403,'Organizer role required')
    try:
        event_date=datetime.strptime(x.date,'%Y-%m-%d').date(); start=datetime.strptime(x.time,'%H:%M'); deadline=parse_deadline(x.deadline)
        if x.end_time and datetime.strptime(x.end_time,'%H:%M')<=start: raise ValueError()
    except ValueError:raise HTTPException(422,'Use YYYY-MM-DD date, HH:MM time, ISO deadline')
    if x.date<datetime.now().date().isoformat():raise HTTPException(422,'Event date must not be in the past')
    if deadline<=datetime.now(timezone.utc):raise HTTPException(422,'Registration deadline must be in the future')
    if not x.event_type.strip():raise HTTPException(422,'Event type is required')
    if x.online_link and not x.online_link.lower().startswith(('https://','http://')):raise HTTPException(422,'Online meeting URL must use HTTP or HTTPS')
    e=Event(organizer_id=u.id,**x.model_dump());db.add(e);db.commit();db.refresh(e);return view(db,e)
@app.get('/api/events/{eid}')
def get_event(eid:int,u:User=Depends(auth),db:Session=Depends(dbdep)):
    e=db.get(Event,eid)
    if not e or e.status=='CANCELLED':raise HTTPException(404,'Event not found')
    return view(db,e,u.id)
@app.put('/api/events/{eid}')
def update_event(eid:int,x:EventIn,u:User=Depends(auth),db:Session=Depends(dbdep)):
    e=db.get(Event,eid)
    if not e:raise HTTPException(404,'Event not found')
    if e.organizer_id!=u.id:raise HTTPException(403,'Only the organizer can edit this event')
    old_capacity=e.capacity
    if x.capacity<counts(db,e)['going']:raise HTTPException(409,'Capacity cannot be lower than current Going RSVPs')
    try:
        event_date=datetime.strptime(x.date,'%Y-%m-%d').date();start=datetime.strptime(x.time,'%H:%M');deadline=parse_deadline(x.deadline)
        if x.end_time and datetime.strptime(x.end_time,'%H:%M')<=start:raise ValueError()
    except ValueError:raise HTTPException(422,'Invalid date, time or deadline')
    if deadline<=datetime.now(timezone.utc):raise HTTPException(422,'Registration deadline must be in the future')
    if x.online_link and not x.online_link.lower().startswith(('https://','http://')):raise HTTPException(422,'Online meeting URL must use HTTP or HTTPS')
    changed_fields=[key for key in ('date','time','end_time','venue','online_link') if getattr(e,key)!=getattr(x,key)]
    for key,value in x.model_dump().items():setattr(e,key,value)
    if x.capacity>old_capacity:
        while counts(db,e)['going']<e.capacity and counts(db,e)['waitlist']:
            if not promote_waitlisted(db,e):break
    e.updated_at=utcnow()
    if changed_fields:
        message=f'{e.name} details changed: '+', '.join(changed_fields)+'. Check the event page for the latest information.'
        recipients={row.user_id for row in db.query(RSVP).filter_by(event_id=eid).all()}
        for invitation in db.query(Invitation).filter_by(event_id=eid).all():
            attendee=db.query(User).filter(func.lower(User.email)==invitation.email).first()
            if attendee:recipients.add(attendee.id)
        for user_id in recipients:notify(db,user_id,eid,'EVENT_UPDATED',message)
    db.commit();return view(db,e,u.id)
@app.delete('/api/events/{eid}')
def cancel_event(eid:int,u:User=Depends(auth),db:Session=Depends(dbdep)):
    e=db.get(Event,eid)
    if not e:raise HTTPException(404,'Event not found')
    if e.organizer_id!=u.id:raise HTTPException(403,'Only the organizer can cancel this event')
    e.status='CANCELLED'
    for r in db.query(RSVP).filter_by(event_id=eid).all():notify(db,r.user_id,eid,'EVENT_CANCELLED',f'{e.name} was cancelled.')
    db.commit();return {'status':'CANCELLED'}
@app.post('/api/events/{eid}/invitations',status_code=201)
def invite(eid:int,x:InviteIn,u:User=Depends(auth),db:Session=Depends(dbdep)):
    e=db.get(Event,eid)
    if not e:raise HTTPException(404,'Event not found')
    if e.organizer_id!=u.id:raise HTTPException(403,'Only the organizer can invite attendees')
    inserted=0
    for raw in x.emails:
        email=raw.strip().lower()
        if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',email):raise HTTPException(422,'Every invite must be an email address')
        if not db.query(Invitation).filter_by(event_id=eid,email=email).first():db.add(Invitation(event_id=eid,email=email));inserted+=1
        attendee=db.query(User).filter(func.lower(User.email)==email).first()
        if attendee and not db.query(RSVP).filter_by(event_id=eid,user_id=attendee.id).first():notify(db,attendee.id,eid,'EVENT_INVITATION',f'You were invited to {e.name}.')
    db.commit();return {'invited':inserted,'total_invited':db.query(Invitation).filter_by(event_id=eid).count()}
def notify(db,user_id,event_id,kind,message):
    db.add(Notification(user_id=user_id,event_id=event_id,kind=kind,message=message))
def promote_waitlisted(db,e):
    if counts(db,e)['going']>=e.capacity:return None
    first=db.query(Waitlist).filter_by(event_id=e.id,status='WAITING').order_by(Waitlist.joined_at,Waitlist.id).first()
    if not first:return None
    first.status='PROMOTED'
    current=db.query(RSVP).filter_by(event_id=e.id,user_id=first.user_id).first()
    if current:current.status='GOING';current.updated_at=utcnow()
    else:db.add(RSVP(event_id=e.id,user_id=first.user_id,status='GOING'))
    notify(db,first.user_id,e.id,'WAITLIST_PROMOTED',f'A seat opened for {e.name}; you are now Going.')
    return first.user_id
@app.put('/api/events/{eid}/rsvp')
def rsvp(eid:int,x:RSVPIn,u:User=Depends(auth),db:Session=Depends(dbdep)):
    s=x.status.upper()
    if s not in ('GOING','MAYBE','NOT_GOING'):raise HTTPException(422,'Invalid RSVP status')
    e=db.get(Event,eid)
    if not e:raise HTTPException(404,'Event not found')
    if e.status!='PUBLISHED':raise HTTPException(409,'Event is not accepting RSVPs')
    if parse_deadline(e.deadline)<datetime.now(timezone.utc):raise HTTPException(409,'Registration deadline passed')
    try:
        if db.bind.dialect.name=='sqlite':db.connection().exec_driver_sql('BEGIN IMMEDIATE')
        old=db.query(RSVP).filter_by(event_id=eid,user_id=u.id).first()
        previous=old.status if old else None
        if s=='GOING' and previous!='GOING' and counts(db,e)['going']>=e.capacity:raise HTTPException(409,'Event is full')
        if old:old.status=s;old.updated_at=utcnow()
        else:db.add(RSVP(event_id=eid,user_id=u.id,status=s))
        if previous!=s:notify(db,u.id,eid,'RSVP_CONFIRMATION',f'Your response for {e.name} is {s.replace("_"," ").title()}.')
        if previous=='GOING' and s!='GOING':promote_waitlisted(db,e)
        if s=='GOING':
            queued=db.query(Waitlist).filter_by(event_id=eid,user_id=u.id,status='WAITING').first()
            if queued:queued.status='PROMOTED'
        db.commit()
    except Exception:db.rollback();raise
    return {'status':s,'counts':counts(db,e)}
@app.delete('/api/events/{eid}/rsvp')
def cancel_rsvp(eid:int,u:User=Depends(auth),db:Session=Depends(dbdep)):
    e=db.get(Event,eid)
    if not e:raise HTTPException(404,'Event not found')
    r=db.query(RSVP).filter_by(event_id=eid,user_id=u.id).first()
    if not r:raise HTTPException(404,'Your RSVP was not found')
    was_going=r.status=='GOING';db.delete(r)
    if was_going:promote_waitlisted(db,e)
    db.commit();return {'cancelled':True,'counts':counts(db,e)}
@app.post('/api/events/{eid}/waitlist',status_code=201)
def join_waitlist(eid:int,x:WaitlistIn,u:User=Depends(auth),db:Session=Depends(dbdep)):
    e=db.get(Event,eid)
    if not e or e.status!='PUBLISHED':raise HTTPException(404,'Event not available')
    if parse_deadline(e.deadline)<datetime.now(timezone.utc):raise HTTPException(409,'Registration deadline passed')
    if not counts(db,e)['full']:raise HTTPException(409,'Event has available seats; RSVP Going instead')
    existing=db.query(Waitlist).filter_by(event_id=eid,user_id=u.id).first()
    if existing and existing.status=='WAITING':
        ordered=db.query(Waitlist).filter_by(event_id=eid,status='WAITING').order_by(Waitlist.joined_at,Waitlist.id).all()
        return {'position':next(i for i,item in enumerate(ordered,1) if item.id==existing.id),'status':'WAITING'}
    if db.query(RSVP).filter_by(event_id=eid,user_id=u.id).first():raise HTTPException(409,'You already have an RSVP for this event')
    item=Waitlist(event_id=eid,user_id=u.id);db.add(item);db.commit();db.refresh(item)
    ordered=db.query(Waitlist).filter_by(event_id=eid,status='WAITING').order_by(Waitlist.joined_at,Waitlist.id).all()
    position=next(i for i,row in enumerate(ordered,1) if row.id==item.id)
    return {'position':position,'status':'WAITING'}
@app.delete('/api/events/{eid}/waitlist')
def leave_waitlist(eid:int,u:User=Depends(auth),db:Session=Depends(dbdep)):
    item=db.query(Waitlist).filter_by(event_id=eid,user_id=u.id,status='WAITING').first()
    if not item:raise HTTPException(404,'Active waitlist entry not found')
    item.status='LEFT';db.commit();return {'left':True}
@app.get('/api/rsvps/me')
def my_rsvps(u:User=Depends(auth),db:Session=Depends(dbdep)):
    rows=db.query(RSVP).filter_by(user_id=u.id).order_by(RSVP.updated_at.desc()).all()
    return [{'status':r.status,'updated_at':r.updated_at.isoformat() if r.updated_at else None,'event':view(db,db.get(Event,r.event_id),u.id)} for r in rows]
@app.get('/api/events/{eid}/rsvps')
def event_rsvps(eid:int,u:User=Depends(auth),db:Session=Depends(dbdep)):
    e=db.get(Event,eid)
    if not e:raise HTTPException(404,'Event not found')
    if e.organizer_id!=u.id:raise HTTPException(403,'Organizer access required')
    rows=db.query(RSVP).filter_by(event_id=eid).all()
    return {'counts':counts(db,e),'attendees':[{'name':db.get(User,r.user_id).name,'email':db.get(User,r.user_id).email,'status':r.status} for r in rows],'waitlist':[{'name':db.get(User,w.user_id).name,'position':i+1} for i,w in enumerate(db.query(Waitlist).filter_by(event_id=eid,status='WAITING').order_by(Waitlist.joined_at).all())]}
@app.post('/api/events/{eid}/announcements',status_code=201)
def announce(eid:int,x:AnnouncementIn,u:User=Depends(auth),db:Session=Depends(dbdep)):
    e=db.get(Event,eid)
    if not e:raise HTTPException(404,'Event not found')
    if e.organizer_id!=u.id:raise HTTPException(403,'Event owner only')
    a=Announcement(event_id=eid,**x.model_dump());db.add(a)
    for r in db.query(RSVP).filter_by(event_id=eid).all():notify(db,r.user_id,eid,'ANNOUNCEMENT',f'{x.title}: {x.message[:400]}')
    for invitation in db.query(Invitation).filter_by(event_id=eid).all():
        attendee=db.query(User).filter(func.lower(User.email)==invitation.email).first()
        if attendee and not db.query(RSVP).filter_by(event_id=eid,user_id=attendee.id).first():notify(db,attendee.id,eid,'ANNOUNCEMENT',f'{x.title}: {x.message[:400]}')
    db.commit();return {'ok':True}
@app.post('/api/events/{eid}/reminders',status_code=201)
def send_reminder(eid:int,u:User=Depends(auth),db:Session=Depends(dbdep)):
    e=db.get(Event,eid)
    if not e:raise HTTPException(404,'Event not found')
    if e.organizer_id!=u.id:raise HTTPException(403,'Only the organizer can send reminders')
    recipients={row.user_id for row in db.query(RSVP).filter_by(event_id=eid).all()}
    for invitation in db.query(Invitation).filter_by(event_id=eid).all():
        attendee=db.query(User).filter(func.lower(User.email)==invitation.email).first()
        if attendee:recipients.add(attendee.id)
    for user_id in recipients:notify(db,user_id,eid,'EVENT_REMINDER',f'Reminder: {e.name} is scheduled for {e.date} at {e.time}.')
    db.commit();return {'notified':len(recipients)}
@app.get('/api/events/{eid}/announcements')
def get_announcements(eid:int,u:User=Depends(auth),db:Session=Depends(dbdep)):
    return [{'title':a.title,'message':a.message,'created_at':a.created_at.isoformat() if a.created_at else None} for a in db.query(Announcement).filter_by(event_id=eid).order_by(Announcement.id.desc()).all()]
@app.get('/api/notifications')
def notifications(u:User=Depends(auth),db:Session=Depends(dbdep)):
    return [{'id':n.id,'event_id':n.event_id,'kind':n.kind,'message':n.message,'is_read':n.is_read,'created_at':n.created_at.isoformat()} for n in db.query(Notification).filter_by(user_id=u.id).order_by(Notification.created_at.desc()).limit(100).all()]
@app.put('/api/notifications/{nid}/read')
def mark_notification(nid:int,x:ReadIn,u:User=Depends(auth),db:Session=Depends(dbdep)):
    n=db.get(Notification,nid)
    if not n:raise HTTPException(404,'Notification not found')
    if n.user_id!=u.id:raise HTTPException(403,'Notification belongs to another user')
    n.is_read=x.is_read;db.commit();return {'id':nid,'is_read':n.is_read}
@app.get('/api/analytics')
def analytics(u:User=Depends(auth),db:Session=Depends(dbdep)):
    es=db.query(Event).filter_by(organizer_id=u.id).all(); allc=[counts(db,e) for e in es]
    return {'events':len(es),'going':sum(x['going'] for x in allc),'maybe':sum(x['maybe'] for x in allc),'not_going':sum(x['not_going'] for x in allc)}
@app.get('/api/events/{eid}/analytics')
def event_analytics(eid:int,u:User=Depends(auth),db:Session=Depends(dbdep)):
    e=db.get(Event,eid)
    if not e:raise HTTPException(404,'Event not found')
    if e.organizer_id!=u.id:raise HTTPException(403,'Organizer access required')
    c=counts(db,e);invited=db.query(Invitation).filter_by(event_id=eid).count();responded=c['going']+c['maybe']+c['not_going']
    invited_responses=db.query(RSVP.user_id).join(User,User.id==RSVP.user_id).join(Invitation,and_(Invitation.event_id==RSVP.event_id,func.lower(Invitation.email)==func.lower(User.email))).filter(RSVP.event_id==eid).distinct().count()
    growth=[]
    for r in db.query(RSVP).filter_by(event_id=eid).order_by(RSVP.updated_at).all():
        day=r.updated_at.date().isoformat() if r.updated_at else 'unknown'
        item=next((x for x in growth if x['date']==day),None)
        if item:item['responses']+=1
        else:growth.append({'date':day,'responses':1})
    return {'event_id':eid,'invited':invited,'responses':responded,'invited_responses':invited_responses,'going':c['going'],'maybe':c['maybe'],'not_going':c['not_going'],'response_rate':round(invited_responses*100/invited,1) if invited else None,'capacity_utilization':round(c['going']*100/e.capacity,1),'available_seats':c['available'],'waitlist_size':c['waitlist'],'rsvp_growth':growth}
