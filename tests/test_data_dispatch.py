"""app/data.py が DB_BACKEND の値に応じて正しく委譲することのテスト。

app.database.DB_BACKEND は本来モジュール読み込み時に一度だけ決まる定数だが、
app.data 側は毎回 database.DB_BACKEND を参照しているため、
テストでは対象の属性を直接書き換えることで切り替えを再現できる。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app import data, database


def test_get_product_dispatches_to_mysql_store_when_mysql():
    with patch.object(database, "DB_BACKEND", "mysql"):
        with patch("app.mysql_store.get_product", return_value="from-mysql") as mocked:
            result = data.get_product("prod-001")

    mocked.assert_called_once_with("prod-001")
    assert result == "from-mysql"


def test_get_product_dispatches_to_sqlite_store_when_sqlite():
    with patch.object(database, "DB_BACKEND", "sqlite"):
        with patch("app.sqlite_store.get_product", return_value="from-sqlite") as mocked:
            result = data.get_product("prod-001")

    mocked.assert_called_once_with("prod-001")
    assert result == "from-sqlite"


def test_get_product_uses_in_memory_store_when_memory():
    with patch.object(database, "DB_BACKEND", "memory"):
        result = data.get_product("prod-001")

    # インメモリのダミーデータがそのまま返る。
    assert result is not None
    assert result.product_id == "prod-001"


@pytest.mark.parametrize(
    "env, expected",
    [
        ({"DB_BACKEND": "sqlite"}, "sqlite"),
        ({"DB_BACKEND": "MySQL"}, "mysql"),
        ({"DB_BACKEND": "memory", "USE_MYSQL": "true"}, "memory"),  # DB_BACKENDが優先
        ({"USE_MYSQL": "true"}, "mysql"),  # 旧設定との互換
        ({}, "memory"),
    ],
)
def test_resolve_backend(monkeypatch, env, expected):
    monkeypatch.delenv("DB_BACKEND", raising=False)
    monkeypatch.delenv("USE_MYSQL", raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert database._resolve_backend() == expected


def test_resolve_backend_rejects_unknown_value(monkeypatch):
    monkeypatch.setenv("DB_BACKEND", "postgres")
    with pytest.raises(ValueError):
        database._resolve_backend()
