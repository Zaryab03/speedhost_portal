# Copyright (c) 2026, SpeedHost360 and contributors
# For license information, please see license.txt

"""Site-config driven settings. Nothing here is hardcoded per deployment:
every URL / address is read from site_config.json (bench set-config)."""

import frappe
from frappe.utils import get_url

DEFAULT_HELPDESK_PATH = "/helpdesk"


def _conf(key, default=None):
	value = frappe.conf.get(key)
	return default if value in (None, "") else value


def _as_bool(value, default=True):
	if value is None:
		return default
	if isinstance(value, str):
		return value.strip().lower() not in ("0", "false", "no", "off", "")
	return bool(value)


def reminders_enabled() -> bool:
	"""`speedhost_reminders_enabled` (default: true)."""
	return _as_bool(frappe.conf.get("speedhost_reminders_enabled"), default=True)


def get_internal_alert_email() -> str | None:
	"""`speedhost_internal_alert_email`: staff address for the daily expiry summary."""
	return _conf("speedhost_internal_alert_email")


def get_support_email() -> str | None:
	"""`speedhost_support_email`: support contact quoted in customer emails."""
	return _conf("speedhost_support_email")


def get_helpdesk_url() -> str:
	"""`helpdesk_url`, falling back to /helpdesk on this site."""
	return _absolute(_conf("helpdesk_url", DEFAULT_HELPDESK_PATH))


def get_kb_url() -> str | None:
	"""`speedhost_kb_url`: knowledge-base link for the email setup guide."""
	url = _conf("speedhost_kb_url")
	return _absolute(url) if url else None


def get_invoices_url() -> str:
	return get_url("/invoices")


def get_service_url(name: str) -> str:
	return get_url(f"/my-services/{name}")


def _absolute(url: str) -> str:
	return url if url.startswith(("http://", "https://")) else get_url(url)
