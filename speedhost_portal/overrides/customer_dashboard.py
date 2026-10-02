# Copyright (c) 2026, SpeedHost360 and contributors
# For license information, please see license.txt

from frappe import _


def get_dashboard_data(data):
	"""hooks.override_doctype_dashboards["Customer"]: add a Hosting connection."""
	data.setdefault("transactions", []).append({"label": _("Hosting"), "items": ["Hosting Service"]})
	return data
