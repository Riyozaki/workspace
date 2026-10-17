import pytest
from aira_local import engine


def test_missing_model_reports_error_without_partial_ready_state(tmp_path,monkeypatch):
 monkeypatch.setattr(engine,'MODEL',tmp_path/'missing.gguf');model=engine.LocalLanguageModel()
 with pytest.raises(FileNotFoundError):model.load()
 assert model.status=='error';assert model.model is None;assert model.error


def test_corrupt_model_rejected_by_hash_before_native_parser(tmp_path,monkeypatch):
 p=tmp_path/'wrong.gguf';p.write_bytes(b'GGUF definitely not trusted weights')
 monkeypatch.setattr(engine,'MODEL',p);model=engine.LocalLanguageModel()
 with pytest.raises(ValueError,match='SHA-256'):model.load()
 assert model.status=='error';assert model.model is None
