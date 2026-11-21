from app.cache import Cache


def test_values_survive_a_new_cache_instance(tmp_path):
    db = tmp_path / "data" / "cache.db"
    Cache(db).put("analysis", "abc", {"summary": "आवाज़ अच्छी है", "ok": True})

    assert Cache(db).get("analysis", "abc") == {"summary": "आवाज़ अच्छी है", "ok": True}


def test_missing_keys_and_other_namespaces_are_misses(tmp_path):
    cache = Cache(tmp_path / "cache.db")
    cache.put("analysis", "abc", {"x": 1})

    assert cache.get("analysis", "zzz") is None
    assert cache.get("reply", "abc") is None


def test_put_overwrites_existing_value(tmp_path):
    cache = Cache(tmp_path / "cache.db")
    cache.put("reply", "k", {"reply": "old"})
    cache.put("reply", "k", {"reply": "new"})

    assert cache.get("reply", "k") == {"reply": "new"}
