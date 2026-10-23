import pytest
from app.config import Settings

def test_config_validation(monkeypatch, tmp_path):
    monkeypatch.setenv('BOT_TOKEN','token'); monkeypatch.setenv('OWNER_ID','42'); monkeypatch.setenv('ADMIN_IDS','7,8'); monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'db'))
    s=Settings.from_env(); assert s.is_admin(42) and s.is_admin(7) and not s.is_admin(9)

def test_missing_token(monkeypatch):
    monkeypatch.delenv('BOT_TOKEN', raising=False); monkeypatch.setenv('OWNER_ID','42')
    with pytest.raises(ValueError): Settings.from_env()
