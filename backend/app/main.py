from datetime import datetime, timezone
import secrets

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import create_token, hash_password, verify_password, decode_token
from app.config import settings
from app.database import Base, engine, get_db
from app.models import User, License, Device, Preset

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.APP_NAME)
templates = Jinja2Templates(directory="app/templates")


def get_current_user_from_header(request: Request, db: Session):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.replace("Bearer ", "").strip()
    data = decode_token(token)
    if not data:
        return None
    user = db.query(User).filter(User.email == data.get("sub")).first()
    return user


def require_admin(request: Request, db: Session):
    token = request.cookies.get("admin_token")
    if not token:
        return None
    data = decode_token(token)
    if not data:
        return None
    user = db.query(User).filter(User.email == data.get("sub"), User.role == "admin").first()
    return user


def generate_key(prefix: str = "FRAME") -> str:
    body = secrets.token_hex(8).upper()
    return f"{prefix}-{body[:4]}-{body[4:8]}-{body[8:12]}-{body[12:16]}"


@app.get("/", response_class=HTMLResponse)
def home():
    return RedirectResponse("/admin")


@app.get("/health")
def health():
    return {"ok": True, "app": settings.APP_NAME}


@app.post("/api/auth/login")
def api_login(payload: dict, db: Session = Depends(get_db)):
    email = (payload.get("email") or "").lower().strip()
    password = payload.get("password") or ""

    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Login inválido")

    token = create_token(user.email, user.role)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "name": user.name,
            "email": user.email,
            "role": user.role
        }
    }


@app.post("/api/client/activate")
def api_activate(payload: dict, request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_header(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Token inválido")

    key = (payload.get("license_key") or "").upper().strip()
    hwid_hash = (payload.get("hwid_hash") or "").strip()
    machine_name = payload.get("machine_name")
    gpu_name = payload.get("gpu_name")

    if not key or not hwid_hash:
        raise HTTPException(status_code=400, detail="Chave e HWID são obrigatórios")

    license_obj = db.query(License).filter(License.key == key, License.is_active == True).first()
    if not license_obj:
        raise HTTPException(status_code=403, detail="Chave inválida ou inativa")

    if license_obj.user_id is None:
        license_obj.user_id = user.id
        db.commit()
        db.refresh(license_obj)

    if license_obj.user_id != user.id:
        raise HTTPException(status_code=403, detail="Esta chave pertence a outro usuário")

    existing = db.query(Device).filter(
        Device.license_id == license_obj.id,
        Device.hwid_hash == hwid_hash
    ).first()

    if not existing:
        count = db.query(Device).filter(Device.license_id == license_obj.id).count()
        if count >= license_obj.max_devices:
            raise HTTPException(status_code=403, detail="Limite de dispositivos atingido")
        existing = Device(
            license_id=license_obj.id,
            hwid_hash=hwid_hash,
            machine_name=machine_name,
            gpu_name=gpu_name
        )
        db.add(existing)
    else:
        existing.machine_name = machine_name
        existing.gpu_name = gpu_name

    db.commit()

    return {
        "ok": True,
        "plan": license_obj.plan,
        "max_devices": license_obj.max_devices,
        "device_id": existing.id,
        "message": "Booster desbloqueado"
    }


@app.get("/api/client/me")
def api_me(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_header(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Token inválido")

    licenses = db.query(License).filter(License.user_id == user.id, License.is_active == True).all()
    return {
        "user": {"name": user.name, "email": user.email, "role": user.role},
        "licenses": [
            {
                "key": l.key,
                "plan": l.plan,
                "max_devices": l.max_devices,
                "devices": len(l.devices)
            }
            for l in licenses
        ]
    }


@app.get("/api/client/presets")
def api_presets(game: str = "pubg", request: Request = None, db: Session = Depends(get_db)):
    user = get_current_user_from_header(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Token inválido")

    presets = db.query(Preset).filter(Preset.game == game, Preset.is_active == True).all()

    return {
        "game": game,
        "presets": [
            {
                "name": p.name,
                "slug": p.slug,
                "description": p.description,
                "plan_required": p.plan_required,
                "config": p.config
            }
            for p in presets
        ]
    }


@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/admin/login")
def admin_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email.lower().strip(), User.role == "admin").first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Login inválido"})

    token = create_token(user.email, user.role)
    resp = RedirectResponse("/admin", status_code=302)
    resp.set_cookie("admin_token", token, httponly=True, samesite="lax")
    return resp


@app.get("/admin/logout")
def admin_logout():
    resp = RedirectResponse("/admin/login", status_code=302)
    resp.delete_cookie("admin_token")
    return resp


@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)

    stats = {
        "users": db.query(User).count(),
        "licenses": db.query(License).count(),
        "devices": db.query(Device).count(),
        "presets": db.query(Preset).count()
    }

    recent_licenses = db.query(License).order_by(License.id.desc()).limit(10).all()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "admin": admin,
        "stats": stats,
        "licenses": recent_licenses
    })


@app.get("/admin/users", response_class=HTMLResponse)
def admin_users(request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)

    users = db.query(User).order_by(User.id.desc()).all()
    return templates.TemplateResponse("users.html", {"request": request, "users": users})


@app.post("/admin/users/create")
def admin_create_user(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("customer"),
    db: Session = Depends(get_db)
):
    admin = require_admin(request, db)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)

    exists = db.query(User).filter(User.email == email.lower().strip()).first()
    if exists:
        return RedirectResponse("/admin/users?error=email_exists", status_code=302)

    user = User(
        name=name.strip(),
        email=email.lower().strip(),
        password_hash=hash_password(password),
        role=role,
        is_active=True
    )
    db.add(user)
    db.commit()
    return RedirectResponse("/admin/users", status_code=302)


@app.get("/admin/licenses", response_class=HTMLResponse)
def admin_licenses(request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)

    licenses = db.query(License).order_by(License.id.desc()).all()
    users = db.query(User).filter(User.role == "customer").order_by(User.name.asc()).all()
    return templates.TemplateResponse("licenses.html", {
        "request": request,
        "licenses": licenses,
        "users": users
    })


@app.post("/admin/licenses/create")
def admin_create_license(
    request: Request,
    plan: str = Form("basic"),
    max_devices: int = Form(1),
    user_id: str = Form(""),
    db: Session = Depends(get_db)
):
    admin = require_admin(request, db)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)

    user_value = int(user_id) if user_id else None
    license_obj = License(
        key=generate_key("BOOST"),
        plan=plan,
        max_devices=max_devices,
        user_id=user_value,
        is_active=True
    )
    db.add(license_obj)
    db.commit()
    return RedirectResponse("/admin/licenses", status_code=302)


@app.post("/admin/licenses/toggle/{license_id}")
def admin_toggle_license(license_id: int, request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)

    license_obj = db.query(License).filter(License.id == license_id).first()
    if license_obj:
        license_obj.is_active = not license_obj.is_active
        db.commit()
    return RedirectResponse("/admin/licenses", status_code=302)


@app.post("/admin/licenses/reset_devices/{license_id}")
def admin_reset_devices(license_id: int, request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)

    db.query(Device).filter(Device.license_id == license_id).delete()
    db.commit()
    return RedirectResponse("/admin/licenses", status_code=302)


@app.get("/admin/presets", response_class=HTMLResponse)
def admin_presets(request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)

    presets = db.query(Preset).order_by(Preset.id.desc()).all()
    return templates.TemplateResponse("presets.html", {"request": request, "presets": presets})


@app.post("/admin/presets/create")
def admin_create_preset(
    request: Request,
    game: str = Form("pubg"),
    name: str = Form(...),
    slug: str = Form(...),
    plan_required: str = Form("basic"),
    description: str = Form(""),
    config_json: str = Form(...),
    db: Session = Depends(get_db)
):
    admin = require_admin(request, db)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)

    try:
        config = json_loads(config_json)
    except Exception:
        return RedirectResponse("/admin/presets?error=invalid_json", status_code=302)

    preset = Preset(
        game=game,
        name=name,
        slug=slug,
        plan_required=plan_required,
        description=description,
        config=config,
        is_active=True
    )
    db.add(preset)
    db.commit()
    return RedirectResponse("/admin/presets", status_code=302)


def json_loads(value: str):
    import json
    return json.loads(value)


@app.post("/admin/presets/toggle/{preset_id}")
def admin_toggle_preset(preset_id: int, request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)

    preset = db.query(Preset).filter(Preset.id == preset_id).first()
    if preset:
        preset.is_active = not preset.is_active
        db.commit()
    return RedirectResponse("/admin/presets", status_code=302)
