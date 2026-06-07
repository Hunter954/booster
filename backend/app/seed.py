import json
from app.auth import hash_password
from app.config import settings
from app.database import Base, engine, SessionLocal
from app.models import User, License, Preset

Base.metadata.create_all(bind=engine)

db = SessionLocal()

admin = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
if not admin:
    admin = User(
        name="Administrador",
        email=settings.ADMIN_EMAIL,
        password_hash=hash_password(settings.ADMIN_PASSWORD),
        role="admin",
        is_active=True
    )
    db.add(admin)
    db.commit()

test_user = db.query(User).filter(User.email == "cliente@teste.com").first()
if not test_user:
    test_user = User(
        name="Cliente Teste",
        email="cliente@teste.com",
        password_hash=hash_password("123456"),
        role="customer",
        is_active=True
    )
    db.add(test_user)
    db.commit()
    db.refresh(test_user)

test_license = db.query(License).filter(License.key == "BOOST-TESTE-2026").first()
if not test_license:
    test_license = License(
        key="BOOST-TESTE-2026",
        plan="pro",
        max_devices=1,
        user_id=test_user.id,
        is_active=True
    )
    db.add(test_license)

preset = db.query(Preset).filter(Preset.slug == "pubg-competitive-safe").first()
if not preset:
    config = {
        "windows": {
            "power_plan": "high_performance",
            "disable_game_dvr": True,
            "enable_game_mode": True,
            "clean_temp": True,
            "set_process_priority": {
                "process": "TslGame.exe",
                "priority": "high"
            },
            "stop_services": [
                "SysMain",
                "WSearch",
                "DiagTrack",
                "MapsBroker",
                "XblAuthManager",
                "XblGameSave",
                "XboxNetApiSvc"
            ],
            "never_close_processes": [
                "Discord.exe",
                "chrome.exe",
                "msedge.exe",
                "brave.exe",
                "opera.exe",
                "firefox.exe"
            ]
        },
        "nvidia": {
            "mode": "prepared_only",
            "profile_target": "TslGame.exe",
            "settings": {
                "Image Scaling": "Off",
                "FXAA": "Off",
                "Antialiasing Gamma Correction": "Off",
                "Antialiasing Mode": "Off",
                "Antialiasing Transparency": "Off",
                "Triple Buffering": "Off",
                "CUDA GPUs": "All",
                "DSR Factors": "Off",
                "Anisotropic Filtering": "Application-controlled",
                "Texture Filtering Negative LOD Bias": "Clamp",
                "Texture Filtering Anisotropic Sample Optimization": "On",
                "Texture Filtering Trilinear Optimization": "On",
                "Texture Filtering Quality": "High performance",
                "OpenGL Rendering GPU": "Detected NVIDIA GPU",
                "Power Management Mode": "Prefer maximum performance",
                "Low Latency Mode": "Off",
                "MFAA": "Off",
                "Vulkan/OpenGL Present Method": "Auto",
                "Ambient Occlusion": "Off",
                "Threaded Optimization": "Auto",
                "VR Pre-rendered Frames": "1",
                "Vertical Sync": "Use the 3D application setting",
                "Shader Cache Size": "Driver default",
                "Max Frame Rate": "Off",
                "Preferred Refresh Rate": "Application-controlled",
                "Background Application Max Frame Rate": "Off",
                "Scaling Mode": "Full-screen",
                "Perform Scaling On": "GPU",
                "Override Scaling Mode": "On"
            }
        }
    }

    preset = Preset(
        game="pubg",
        name="PUBG Competitivo Seguro",
        slug="pubg-competitive-safe",
        plan_required="basic",
        description="Preset seguro: não fecha Discord/navegador e não altera arquivos do jogo.",
        config=config,
        is_active=True
    )
    db.add(preset)

db.commit()
db.close()

print("Seed finalizado.")
print("Admin:", settings.ADMIN_EMAIL)
print("Cliente teste: cliente@teste.com / 123456")
print("Chave teste: BOOST-TESTE-2026")
