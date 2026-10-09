"""Exercise route logic against an isolated SQLite database without network ports."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import app as project

@pytest.fixture
def db():
    path=Path(__file__).parent/f".test-{uuid.uuid4().hex}.db"
    engine=create_engine(f"sqlite:///{path}",connect_args={"check_same_thread":False})
    project.Base.metadata.create_all(engine)
    session=sessionmaker(engine,expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close();engine.dispose();path.unlink(missing_ok=True)

def account(db,name,role="ATTENDEE"):
    result=project.register(project.Register(name=name,email=f"{name}@test.example",password="correct-horse-battery",role=role),db)
    return db.get(project.User,result["user"]["id"]),result["token"]

def event_data(capacity=1,deadline=None):
    return project.EventIn(name="Cloud Workshop",description="Synthetic demo",date="2030-08-01",time="10:00",venue="Online",capacity=capacity,deadline=deadline or (datetime.now(timezone.utc)+timedelta(days=3)).isoformat())

def publish(db,host,capacity=1):
    return project.create_event(event_data(capacity),host,db)["id"]

def test_frontend_assets_exist(db):
    assert "Gather" in (project.ROOT/"frontend"/"index.html").read_text(encoding="utf-8")
    assert "stylesheet" in (project.ROOT/"frontend"/"index.html").read_text(encoding="utf-8")
    assert (project.ROOT/"frontend"/"style.css").is_file()
    assert (project.ROOT/"frontend"/"app.js").is_file()
    assert project.health(db)=={'ok':True,'database':'reachable'}
    assert Path(project.home().path)==project.ROOT/'frontend'/'index.html'
    assert Path(project.stylesheet().path)==project.ROOT/'frontend'/'style.css'
    assert Path(project.javascript().path)==project.ROOT/'frontend'/'app.js'

def test_registration_login_roles_and_duplicate(db):
    guest,token=account(db,"guest")
    assert project.login(project.Login(email=guest.email,password="correct-horse-battery"),db)["user"]["role"]=="ATTENDEE"
    with pytest.raises(HTTPException) as error:
        project.create_event(event_data(),guest,db)
    assert error.value.status_code==403
    with pytest.raises(HTTPException) as error:
        project.register(project.Register(name="duplicate",email="GUEST@test.example",password="correct-horse-battery"),db)
    assert error.value.status_code==409
    assert project.issue(guest.id)==token or project.auth("Bearer "+token,db) is guest
    project.logout("Bearer "+token,guest,db)
    with pytest.raises(HTTPException):project.auth("Bearer "+token,db)

def test_expired_token_is_rejected(db):
    guest,_=account(db,"expired")
    payload=project.base64.urlsafe_b64encode(project.json.dumps({'uid':guest.id,'exp':0,'jti':'expired'}).encode()).decode().rstrip('=')
    signature=project.base64.urlsafe_b64encode(project.hmac.new(project.SECRET.encode(),payload.encode(),project.hashlib.sha256).digest()).decode().rstrip('=')
    with pytest.raises(HTTPException) as error:project.auth(f'Bearer {payload}.{signature}',db)
    assert error.value.status_code==401

def test_rsvp_update_capacity_unique_and_counts(db):
    host,_=account(db,"host","ORGANIZER");guest,_=account(db,"guest");other,_=account(db,"other");eid=publish(db,host)
    assert project.rsvp(eid,project.RSVPIn(status="GOING"),guest,db)["counts"]["going"]==1
    result=project.rsvp(eid,project.RSVPIn(status="MAYBE"),guest,db)
    assert result["counts"]["going"]==0 and result["counts"]["maybe"]==1
    project.rsvp(eid,project.RSVPIn(status="GOING"),other,db)
    with pytest.raises(HTTPException) as error:
        project.rsvp(eid,project.RSVPIn(status="GOING"),guest,db)
    assert error.value.status_code==409
    assert db.query(project.RSVP).filter_by(event_id=eid,user_id=guest.id).count()==1

def test_deadline_and_invalid_rsvp(db):
    host,_=account(db,"host","ORGANIZER");guest,_=account(db,"guest")
    eid=publish(db,host,2);db.get(project.Event,eid).deadline=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat();db.commit()
    with pytest.raises(HTTPException) as error:
        project.rsvp(eid,project.RSVPIn(status="GOING"),guest,db)
    assert error.value.status_code==409
    eid=publish(db,host,2)
    with pytest.raises(HTTPException) as error:
        project.rsvp(eid,project.RSVPIn(status="INVALID"),guest,db)
    assert error.value.status_code==422
    assert project.parse_deadline('2030-01-01T12:00:00').tzinfo==timezone.utc

def test_announcement_ownership_and_analytics(db):
    host,_=account(db,"host","ORGANIZER");stranger,_=account(db,"stranger","ORGANIZER");guest,_=account(db,"guest");eid=publish(db,host,3)
    item=project.AnnouncementIn(title="Venue update",message="Now online")
    with pytest.raises(HTTPException) as error:
        project.announce(eid,item,stranger,db)
    assert error.value.status_code==403
    assert project.announce(eid,item,host,db)=={"ok":True}
    assert project.get_announcements(eid,guest,db)[0]["title"]=="Venue update"
    project.rsvp(eid,project.RSVPIn(status="GOING"),guest,db)
    assert project.analytics(host,db)["going"]==1
    detail=project.event_analytics(eid,host,db)
    assert detail["going"]==1 and detail["capacity_utilization"]==33.3 and detail["available_seats"]==2

def test_event_edit_cancel_and_permission(db):
    host,_=account(db,"host","ORGANIZER");other,_=account(db,"other","ORGANIZER");guest,_=account(db,"guest");eid=publish(db,host,4)
    project.rsvp(eid,project.RSVPIn(status="GOING"),guest,db)
    with pytest.raises(HTTPException) as error:project.update_event(eid,event_data(4),other,db)
    assert error.value.status_code==403
    changed=event_data(5);changed.name="Updated Cloud Workshop";changed.venue="Updated venue"
    assert project.update_event(eid,changed,host,db)["name"]=="Updated Cloud Workshop"
    assert project.notifications(guest,db)[0]['kind']=='EVENT_UPDATED'
    assert project.send_reminder(eid,host,db)['notified']==1
    assert project.notifications(guest,db)[0]['kind']=='EVENT_REMINDER'
    assert project.cancel_event(eid,host,db)["status"]=="CANCELLED"
    with pytest.raises(HTTPException) as error:project.get_event(eid,other,db)
    assert error.value.status_code==404

def test_waitlist_fifo_promotion_and_notification(db):
    host,_=account(db,"host","ORGANIZER");first,_=account(db,"first");second,_=account(db,"second");eid=publish(db,host,1)
    project.rsvp(eid,project.RSVPIn(status="GOING"),first,db)
    assert project.join_waitlist(eid,project.WaitlistIn(),second,db)["position"]==1
    project.cancel_rsvp(eid,first,db)
    assert db.query(project.RSVP).filter_by(event_id=eid,user_id=second.id).one().status=="GOING"
    assert project.notifications(second,db)[0]["kind"]=="WAITLIST_PROMOTED"

def test_invites_announcement_notifications_and_read_ownership(db):
    host,_=account(db,"host","ORGANIZER");guest,_=account(db,"guest");outsider,_=account(db,"outsider");eid=publish(db,host,3)
    assert project.invite(eid,project.InviteIn(emails=[guest.email,"new@test.example"]),host,db)["invited"]==2
    project.announce(eid,project.AnnouncementIn(title="Venue",message="Room 12"),host,db)
    note=project.notifications(guest,db)[0]
    assert note["kind"]=="ANNOUNCEMENT"
    with pytest.raises(HTTPException) as error:project.mark_notification(note["id"],project.ReadIn(),outsider,db)
    assert error.value.status_code==403
    assert project.mark_notification(note["id"],project.ReadIn(),guest,db)["is_read"] is True
    project.rsvp(eid,project.RSVPIn(status="MAYBE"),guest,db)
    project.rsvp(eid,project.RSVPIn(status="GOING"),outsider,db)
    metrics=project.event_analytics(eid,host,db)
    assert metrics["responses"]==2 and metrics["invited_responses"]==1 and metrics["response_rate"]==50
    assert next(n for n in project.notifications(guest,db) if n['id']==note['id'])['is_read'] is True

def test_cancelled_event_rejects_new_rsvp(db):
    host,_=account(db,"host","ORGANIZER");guest,_=account(db,"guest");eid=publish(db,host)
    project.cancel_event(eid,host,db)
    with pytest.raises(HTTPException) as error:project.rsvp(eid,project.RSVPIn(status="GOING"),guest,db)
    assert error.value.status_code==409

def test_two_attendees_compete_for_last_seat():
    path=Path(__file__).parent/f".race-{uuid.uuid4().hex}.db"
    engine=create_engine(f"sqlite:///{path}",connect_args={"check_same_thread":False,"timeout":10})
    project.Base.metadata.create_all(engine);sessions=sessionmaker(engine,expire_on_commit=False)
    try:
        setup=sessions();host,_=account(setup,"race-host","ORGANIZER");a,_=account(setup,"race-a");b,_=account(setup,"race-b");eid=publish(setup,host,1);ids=(a.id,b.id);setup.close()
        gate=Barrier(2)
        def attempt(uid):
            session=sessions();user=session.get(project.User,uid);gate.wait()
            try:
                project.rsvp(eid,project.RSVPIn(status="GOING"),user,session);return 200
            except HTTPException as error:return error.status_code
            finally:session.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,ids))
        assert sorted(results)==[200,409]
        check=sessions();assert check.query(project.RSVP).filter_by(event_id=eid,status="GOING").count()==1;check.close()
    finally:
        engine.dispose();path.unlink(missing_ok=True)
