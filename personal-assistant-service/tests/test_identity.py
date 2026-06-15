"""Tests for outbound identity helpers."""

from __future__ import annotations

from app import identity


def test_get_gitee_provider_name_defaults(monkeypatch):
    monkeypatch.setattr(identity, "_service_config", {})

    assert identity.get_gitee_provider_name() == "gitee-provider"


def test_get_gitee_provider_name_reads_config(monkeypatch):
    monkeypatch.setattr(
        identity,
        "_service_config",
        {"identity": {"gitee": {"provider_name": "custom-gitee-provider"}}},
    )

    assert identity.get_gitee_provider_name() == "custom-gitee-provider"


def test_get_iam_users_readonly_config_defaults(monkeypatch):
    monkeypatch.setattr(identity, "_service_config", {})

    assert identity.get_iam_users_readonly_config() == {
        "provider_name": "iam-users-readonly",
        "agency_session_name": "personal-assistant-iam-users-readonly",
        "region": "cn-southwest-2",
        "endpoint": "https://iam.cn-southwest-2.myhuaweicloud.com",
    }


def test_get_iam_users_readonly_config_reads_config(monkeypatch):
    monkeypatch.setattr(
        identity,
        "_service_config",
        {
            "identity": {
                "iam_users_readonly": {
                    "provider_name": "custom-iam-provider",
                    "agency_session_name": "custom-session",
                    "region": "cn-north-4",
                    "endpoint": "https://iam.cn-north-4.myhuaweicloud.com",
                }
            }
        },
    )

    assert identity.get_iam_users_readonly_config() == {
        "provider_name": "custom-iam-provider",
        "agency_session_name": "custom-session",
        "region": "cn-north-4",
        "endpoint": "https://iam.cn-north-4.myhuaweicloud.com",
    }
