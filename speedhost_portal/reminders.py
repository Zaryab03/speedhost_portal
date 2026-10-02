# Copyright (c) 2026, SpeedHost360 and contributors
# For license information, please see license.txt

"""Daily renewal reminders (hooks.scheduler_events["daily"]).

Order of work each run:
1. Auto-expire: Active, auto_renew off, unpaid, renewal_date before today -> Expired.
2. Expired notice: once per renewal cycle ("Hosting Service Expired" template).
3. Renewal reminders at 30, 15, 7, 3 days and on the renewal day
   ("Hosting Renewal Reminder" template).
4. Internal summary of services renewing in the next 7 days.

Idempotency: last_reminder_stage records the most urgent stage already sent for
the current renewal_date (it is cleared when renewal_date changes). A stage is
only sent if it is more urgent than the stored one, so nothing is sent twice. A
failed send is logged and the stage stays unrecorded, so the next run retries.
If the job misses days, only the most urgent due stage is sent (no backlog).
"""

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, escape_html, fmt_money, format_date, getdate, today

from speedhost_portal import utils

DOCTYPE = "Hosting Service"
REMINDER_TEMPLATE = "Hosting Renewal Reminder"
EXPIRED_TEMPLATE = "Hosting Service Expired"

REMINDER_STAGES = (30, 15, 7, 3, 0)
EXPIRED_STAGE = "expired"
# Only send the expired notice for services that expired recently, so that
# importing old data or switching reminders on never mails a backlog.
EXPIRED_NOTICE_WINDOW_DAYS = 7
INTERNAL_SUMMARY_DAYS = 7
SAVEPOINT = "speedhost_reminder"


def run_daily():
	if not utils.reminders_enabled():
		return

	today_date = getdate(today())
	for step in (auto_expire_services, send_expired_notices, send_renewal_reminders):
		try:
			step(today_date)
		except Exception:
			frappe.log_error(title=f"Hosting reminders: {step.__name__} failed")

	try:
		send_internal_summary(today_date)
	except Exception:
		frappe.log_error(title="Hosting reminders: internal summary failed")


# --------------------------------------------------------------------------- stages


def get_due_stage(days_left: int, last_stage: str | None) -> int | None:
	"""Most urgent reminder stage due for `days_left`, or None if nothing is due.

	>>> get_due_stage(30, None)
	30
	>>> get_due_stage(29, "30")  # 30-day reminder already sent
	>>> get_due_stage(12, "30")  # missed 15 -> send 15 once
	15
	"""
	if days_left is None or days_left < 0 or days_left > max(REMINDER_STAGES):
		return None

	stage = min(s for s in REMINDER_STAGES if s >= days_left)
	if last_stage == EXPIRED_STAGE:
		return None
	if last_stage not in (None, ""):
		try:
			if int(last_stage) <= stage:
				return None
		except ValueError:
			pass  # unknown value: treat as nothing sent yet
	return stage


# --------------------------------------------------------------------------- steps


def auto_expire_services(today_date):
	"""Mark lapsed, unpaid, non-auto-renewing services Expired. Never suspends."""
	candidates = frappe.get_all(
		DOCTYPE,
		filters={"status": "Active", "auto_renew": 0, "renewal_date": ["<", today_date]},
		fields=["name", "subscription", "renewal_date"],
	)
	for service in candidates:
		if is_paid(service):
			continue
		frappe.db.savepoint(SAVEPOINT)
		try:
			frappe.db.set_value(DOCTYPE, service.name, "status", "Expired")
			frappe.get_doc(DOCTYPE, service.name).add_comment(
				"Info",
				_("Status set to Expired automatically: renewal date {0} passed without payment.").format(
					format_date(service.renewal_date)
				),
			)
			_commit()
		except Exception:
			frappe.db.rollback(save_point=SAVEPOINT)
			frappe.log_error(title=f"Hosting reminders: could not expire {service.name}")


def is_paid(service) -> bool:
	"""A service counts as paid only if it is linked to an Active Subscription."""
	if not service.get("subscription"):
		return False
	return frappe.db.get_value("Subscription", service.subscription, "status") == "Active"


def send_expired_notices(today_date):
	services = frappe.get_all(
		DOCTYPE,
		filters={
			"status": "Expired",
			"renewal_date": [">=", add_days(today_date, -EXPIRED_NOTICE_WINDOW_DAYS)],
			# "!=" matches NULL too (Frappe wraps it in ifnull).
			"last_reminder_stage": ["!=", EXPIRED_STAGE],
		},
		pluck="name",
	)
	for name in services:
		doc = frappe.get_doc(DOCTYPE, name)
		if doc.last_reminder_stage == EXPIRED_STAGE:
			continue
		_send_and_record(doc, EXPIRED_TEMPLATE, EXPIRED_STAGE, today_date)


def send_renewal_reminders(today_date):
	services = frappe.get_all(
		DOCTYPE,
		filters={
			"status": "Active",
			"renewal_date": ["between", [today_date, add_days(today_date, max(REMINDER_STAGES))]],
		},
		fields=["name", "renewal_date", "last_reminder_stage"],
	)
	for service in services:
		days_left = date_diff(service.renewal_date, today_date)
		stage = get_due_stage(days_left, service.last_reminder_stage)
		if stage is None:
			continue
		doc = frappe.get_doc(DOCTYPE, service.name)
		_send_and_record(doc, REMINDER_TEMPLATE, str(stage), today_date)


def send_internal_summary(today_date):
	recipient = utils.get_internal_alert_email()
	if not recipient:
		return

	services = frappe.get_all(
		DOCTYPE,
		filters={
			"status": "Active",
			"renewal_date": ["between", [today_date, add_days(today_date, INTERNAL_SUMMARY_DAYS)]],
		},
		fields=["name", "customer", "customer_name", "domain", "renewal_date", "auto_renew", "renewal_amount"],
		order_by="renewal_date asc",
	)
	if not services:
		return

	rows = "".join(
		"<tr><td><a href='{url}'>{name}</a></td><td>{customer}</td><td>{domain}</td>"
		"<td>{date}</td><td>{days}</td><td>{auto}</td></tr>".format(
			url=frappe.utils.get_url_to_form(DOCTYPE, s.name),
			name=escape_html(s.name),
			customer=escape_html(s.customer_name or s.customer),
			domain=escape_html(s.domain),
			date=format_date(s.renewal_date),
			days=date_diff(s.renewal_date, today_date),
			auto=_("Yes") if s.auto_renew else _("No"),
		)
		for s in services
	)
	message = (
		"<p>{intro}</p><table border='1' cellpadding='6' cellspacing='0'>"
		"<tr><th>{h_service}</th><th>{h_customer}</th><th>{h_domain}</th>"
		"<th>{h_date}</th><th>{h_days}</th><th>{h_auto}</th></tr>{rows}</table>"
	).format(
		intro=_("Active hosting services renewing in the next {0} days:").format(INTERNAL_SUMMARY_DAYS),
		h_service=_("Service"),
		h_customer=_("Customer"),
		h_domain=_("Domain"),
		h_date=_("Renewal Date"),
		h_days=_("Days Left"),
		h_auto=_("Auto Renew"),
		rows=rows,
	)
	frappe.sendmail(
		recipients=[recipient],
		subject=_("Hosting renewals in the next {0} days: {1} service(s)").format(
			INTERNAL_SUMMARY_DAYS, len(services)
		),
		message=message,
	)


# --------------------------------------------------------------------------- sending


def _send_and_record(doc, template_name, stage, today_date) -> bool:
	frappe.db.savepoint(SAVEPOINT)
	try:
		recipients = get_recipients(doc.customer)
		if not recipients:
			frappe.log_error(
				title=f"Hosting reminders: no recipients for {doc.name}",
				message=_(
					"Customer {0} has no portal user or primary contact with an email address."
				).format(doc.customer),
			)
			return False

		template = frappe.get_doc("Email Template", template_name)
		args = get_template_args(doc, today_date)
		frappe.sendmail(
			recipients=recipients,
			subject=template.get_formatted_subject(args),
			message=template.get_formatted_response(args),
			reference_doctype=DOCTYPE,
			reference_name=doc.name,
		)
		frappe.db.set_value(
			DOCTYPE,
			doc.name,
			{"last_reminder_sent_on": today_date, "last_reminder_stage": stage},
			update_modified=False,
		)
		_commit()
		return True
	except Exception:
		frappe.db.rollback(save_point=SAVEPOINT)
		frappe.log_error(title=f"Hosting reminders: sending {template_name} for {doc.name} failed")
		return False


def get_recipients(customer: str) -> list[str]:
	"""Portal users of the customer plus its primary contact(s), deduplicated."""
	emails = []

	portal_users = frappe.get_all(
		"Portal User", filters={"parenttype": "Customer", "parent": customer}, pluck="user"
	)
	if portal_users:
		emails += frappe.get_all("User", filters={"name": ["in", portal_users], "enabled": 1}, pluck="email")

	contact_names = frappe.get_all(
		"Dynamic Link",
		filters={"parenttype": "Contact", "link_doctype": "Customer", "link_name": customer},
		pluck="parent",
	)
	primary_contact = frappe.db.get_value("Customer", customer, "customer_primary_contact")
	if contact_names:
		for contact in frappe.get_all(
			"Contact",
			filters={"name": ["in", contact_names]},
			fields=["name", "email_id", "user", "is_primary_contact"],
		):
			if contact.email_id and (contact.user or contact.is_primary_contact or contact.name == primary_contact):
				emails.append(contact.email_id)

	seen, result = set(), []
	for email in emails:
		key = (email or "").strip().lower()
		if key and key not in seen:
			seen.add(key)
			result.append(email.strip())
	return result


def get_template_args(doc, today_date) -> dict:
	currency = frappe.db.get_value("Customer", doc.customer, "default_currency") or frappe.db.get_default(
		"currency"
	)
	days_left = date_diff(doc.renewal_date, today_date)
	return {
		"customer_name": escape_html(doc.customer_name or doc.customer),
		"service_title": escape_html(doc.service_title),
		"domain": escape_html(doc.domain),
		"renewal_date": format_date(doc.renewal_date),
		"days_left": days_left,
		"renewal_when": get_renewal_when(days_left),
		"renewal_amount": fmt_money(doc.renewal_amount, currency=currency) if doc.renewal_amount else "",
		"billing_cycle": _(doc.billing_cycle) if doc.billing_cycle else "",
		"invoices_url": utils.get_invoices_url(),
		"service_url": utils.get_service_url(doc.name),
		"helpdesk_url": utils.get_helpdesk_url(),
		"support_email": utils.get_support_email() or "",
	}


def get_renewal_when(days_left: int) -> str:
	if days_left == 0:
		return _("today")
	if days_left == 1:
		return _("tomorrow")
	if days_left < 0:
		return _("{0} days ago").format(-days_left)
	return _("in {0} days").format(days_left)


def _commit():
	# Commit per service so one failure never rolls back reminders already sent.
	if not frappe.flags.in_test:
		frappe.db.commit()
