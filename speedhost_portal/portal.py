# Copyright (c) 2026, SpeedHost360 and contributors
# For license information, please see license.txt

"""Customer-portal access for Hosting Service.

Website users get NO desk DocPerm on Hosting Service; everything they see goes
through this module, which (1) resolves the customers a user belongs to and
(2) only ever reads the whitelisted PORTAL_FIELDS. Internal fields
(internal_notes, last_reminder_*) are never selected for portal output.
"""

import frappe
from frappe import _
from frappe.utils import date_diff, getdate, today

from speedhost_portal import utils

DOCTYPE = "Hosting Service"

# The only Hosting Service fields the portal may ever read.
PORTAL_FIELDS = (
	"name",
	"service_title",
	"domain",
	"status",
	"plan",
	"control_panel_type",
	"control_panel_url",
	"control_panel_username",
	"webmail_url",
	"incoming_server",
	"imap_port",
	"pop3_port",
	"outgoing_server",
	"smtp_port",
	"mail_security",
	"nameserver_1",
	"nameserver_2",
	"server_ip",
	"start_date",
	"renewal_date",
	"billing_cycle",
	"auto_renew",
)
PORTAL_LIST_FIELDS = ("name", "service_title", "domain", "status", "plan", "renewal_date", "billing_cycle")
PORTAL_MAILBOX_FIELDS = ("email_address", "quota_mb", "status")

STATUS_COLORS = {
	"Pending": "blue",
	"Active": "green",
	"Suspended": "orange",
	"Expired": "red",
	"Cancelled": "gray",
}
RENEWAL_WARNING_DAYS = 30
RENEWAL_DANGER_DAYS = 7


# --------------------------------------------------------------------------- access


def get_customers_for_user(user: str | None = None) -> list[str]:
	"""Customers a user may see on the portal.

	A user belongs to a customer through either standard ERPNext link:
	- a row in Customer > Portal Users (ERPNext v15's own portal mechanism), or
	- a Contact whose `user` is this user and which has a Dynamic Link to the Customer.
	Disabled customers are excluded.
	"""
	user = user or frappe.session.user
	if not user or user == "Guest":
		return []

	customers = set(
		frappe.get_all("Portal User", filters={"user": user, "parenttype": "Customer"}, pluck="parent")
	)

	contacts = frappe.get_all("Contact", filters={"user": user}, pluck="name")
	if contacts:
		customers.update(
			frappe.get_all(
				"Dynamic Link",
				filters={"parenttype": "Contact", "parent": ["in", contacts], "link_doctype": "Customer"},
				pluck="link_name",
			)
		)

	if not customers:
		return []

	return frappe.get_all(
		"Customer", filters={"name": ["in", list(customers)], "disabled": 0}, pluck="name", order_by="name"
	)


def is_desk_user(user: str) -> bool:
	return frappe.get_cached_value("User", user, "user_type") == "System User"


def has_website_permission(doc, ptype="read", user=None, verbose=False):
	"""hooks.has_website_permission for Hosting Service. Portal is read-only."""
	user = user or frappe.session.user
	if ptype != "read" or not user or user == "Guest":
		return False

	if isinstance(doc, str):
		doc = frappe.get_doc(DOCTYPE, doc)

	# Staff may preview a service on the portal if they can read it in desk.
	if is_desk_user(user):
		return bool(frappe.has_permission(DOCTYPE, "read", doc=doc, user=user))

	return bool(doc.customer) and doc.customer in get_customers_for_user(user)


# --------------------------------------------------------------------------- list


def get_list_context(context=None):
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in to view your services."), frappe.PermissionError)

	return {
		"title": _("My Services"),
		"show_sidebar": True,
		"show_search": True,
		"no_breadcrumbs": False,
		"no_cache": 1,
		"head_include": portal_css_link(),
		"row_template": "speedhost_portal/templates/includes/hosting_service_row.html",
		"get_list": get_service_list,
		"order_by": "renewal_date asc",
	}


def get_service_list(
	doctype=None, txt=None, filters=None, limit_start=0, limit_page_length=20, order_by=None, **kwargs
):
	"""`get_list` for /my-services. Always scoped to the session user's customers;
	any `customer` filter supplied in the query string is ignored."""
	customers = get_customers_for_user()
	if not customers:
		return []

	query_filters = {"customer": ["in", customers]}
	status = (filters or {}).get("status")
	if isinstance(status, str) and status in STATUS_COLORS:
		query_filters["status"] = status

	or_filters = None
	if txt:
		like = f"%{txt}%"
		or_filters = {"service_title": ["like", like], "domain": ["like", like]}

	rows = frappe.get_all(
		DOCTYPE,
		fields=list(PORTAL_LIST_FIELDS),
		filters=query_filters,
		or_filters=or_filters,
		order_by="renewal_date asc, name asc",
		start=limit_start,
		page_length=limit_page_length,
	)
	for row in rows:
		decorate(row)
	return rows


# --------------------------------------------------------------------------- detail


def get_service_for_portal(name: str) -> frappe._dict:
	"""Whitelisted, permission-checked view of one service. Raises
	PermissionError for both missing and foreign services (no enumeration)."""
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in to view your services."), frappe.PermissionError)

	if not name or not frappe.db.exists(DOCTYPE, name):
		frappe.throw(_("Not Permitted"), frappe.PermissionError)

	doc = frappe.get_doc(DOCTYPE, name)
	if not frappe.has_website_permission(doc, ptype="read"):
		frappe.throw(_("Not Permitted"), frappe.PermissionError)

	service = frappe._dict({field: doc.get(field) for field in PORTAL_FIELDS})
	service.mailboxes = [
		frappe._dict({field: row.get(field) for field in PORTAL_MAILBOX_FIELDS}) for row in doc.mailboxes
	]
	return decorate(service)


def decorate(service):
	"""Add display-only keys: plan name, status colour and renewal indicator."""
	service.plan_name = (
		frappe.get_cached_value("Item", service.plan, "item_name") or service.plan if service.plan else None
	)
	service.status_color = STATUS_COLORS.get(service.status, "gray")
	service.update(get_renewal_indicator(service.renewal_date, service.status))
	return service


def get_renewal_indicator(renewal_date, status=None) -> dict:
	"""{"days_left", "renewal_label", "renewal_color"}; color is one of
	"" (fine), "warning" (<=30 days) or "danger" (<=7 days or overdue)."""
	if not renewal_date:
		return {"days_left": None, "renewal_label": "", "renewal_color": ""}

	days_left = date_diff(getdate(renewal_date), getdate(today()))
	if status in ("Cancelled", "Expired"):
		return {"days_left": days_left, "renewal_label": "", "renewal_color": ""}

	if days_left < 0:
		label = _("Overdue by {0} days").format(-days_left) if days_left < -1 else _("Overdue by 1 day")
	elif days_left == 0:
		label = _("Renews today")
	elif days_left == 1:
		label = _("Renews tomorrow")
	else:
		label = _("Renews in {0} days").format(days_left)

	if days_left <= RENEWAL_DANGER_DAYS:
		color = "danger"
	elif days_left <= RENEWAL_WARNING_DAYS:
		color = "warning"
	else:
		color = ""
	return {"days_left": days_left, "renewal_label": label, "renewal_color": color}


def portal_css_link() -> str:
	return '<link rel="stylesheet" href="/assets/speedhost_portal/css/portal.css">'


def get_detail_extras() -> dict:
	return {
		"helpdesk_url": utils.get_helpdesk_url(),
		"kb_url": utils.get_kb_url(),
		"support_email": utils.get_support_email(),
	}
