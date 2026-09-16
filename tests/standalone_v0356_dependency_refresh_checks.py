from pathlib import Path
R=Path(__file__).resolve().parents[1]
req=(R/"requirements.txt").read_text()
cfg=(R/"movie_catalogue/config.py").read_text()
assert "Flask==3.1.3" in req
assert "Flask-WTF==1.3.0" in req
assert "gunicorn==26.2.0" in req
assert "requests==2.34.2" in req
assert "Flask-Login==0.6.3" in req
assert 'APP_VERSION = "0.3.68"' in cfg
print("v0.3.56 dependency refresh checks: PASS")
