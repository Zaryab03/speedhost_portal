# Copyright (c) 2026, SpeedHost360 and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

URL_FIELDS = ("control_panel_url", "webmail_url")
PORT_FIELDS = ("imap_port", "pop3_port", "smtp_port")

# One or more labels plus a TLD (letters, or an IDN "xn--" TLD).
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:(?!-)[a-z0-9-]{1,63}(?<!-)\.)+(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})$")


def normalize_domain(value: str | None) -> str:
	"""`HTTPS://Example.com/path` -> `example.com`."""
	domain = (value or "").strip().lower()
	domain = re.sub(r"^[a-z][a-z0-9+.-]*://", "", domain)
	domain = re.split(r"[/?#]", domain, maxsplit=1)[0]
	domain = domain.split("@")[-1].split(":")[0]
	return domain.strip(".")


def is_valid_domain(domain: str) -> bool:
	return bool(DOMAIN_RE.match(domain or ""))


class HostingService(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from speedhost_portal.speedhost_portal.doctype.hosting_mailbox.hosting_mailbox import HostingMailbox

		auto_renew: DF.Check
		billing_cycle: DF.Literal["", "Monthly", "Quarterly", "Half-Yearly", "Yearly"]
		control_panel_type: DF.Literal["", "cPanel", "Plesk", "DirectAdmin", "CyberPanel", "Other"]
		control_panel_url: DF.Data | None
		control_panel_username: DF.Data | None
		customer: DF.Link
		customer_name: DF.Data | None
		domain: DF.Data
		imap_port: DF.Int
		incoming_server: DF.Data | None
		internal_notes: DF.SmallText | None
		last_reminder_sent_on: DF.Date | None
		last_reminder_stage: DF.Data | None
		mail_security: DF.Literal["", "SSL/TLS", "STARTTLS"]
		mailboxes: DF.Table[HostingMailbox]
		nameserver_1: DF.Data | None
		nameserver_2: DF.Data | None
		outgoing_server: DF.Data | None
		plan: DF.Link | None
		pop3_port: DF.Int
		renewal_amount: DF.Currency
		renewal_date: DF.Date
		server_ip: DF.Data | None
		service_title: DF.Data
		smtp_port: DF.Int
		start_date: DF.Date | None
		status: DF.Literal["Pending", "Active", "Suspended", "Expired", "Cancelled"]
		subscription: DF.Link | None
		webmail_url: DF.Data | None
	# end: auto-generated types

	def validate(self):
		self.validate_domain()
		self.validate_urls()
		self.validate_ports()
		self.validate_dates()
		self.validate_status()
		self.validate_mailboxes()
		self.reset_reminders_on_renewal_change()

	def validate_domain(self):
		self.domain = normalize_domain(self.domain)
		if not is_valid_domain(self.domain):
			frappe.throw(
				_("{0} is not a valid domain name. Use a bare domain such as example.com.").format(
					frappe.bold(self.domain or _("(empty)"))
				),
				title=_("Invalid Domain"),
			)

	def validate_urls(self):
		for fieldname in URL_FIELDS:
			value = (self.get(fieldname) or "").strip()
			self.set(fieldname, value)
			if value and (not value.lower().startswith("https://") or re.search(r"\s", value)):
				frappe.throw(
					_("{0} must be a secure URL starting with https://").format(
						frappe.bold(_(self.meta.get_label(fieldname)))
					),
					title=_("Invalid URL"),
				)

	def validate_ports(self):
		for fieldname in PORT_FIELDS:
			port = self.get(fieldname)
			if port and not (1 <= port <= 65535):
				frappe.throw(
					_("{0} must be between 1 and 65535.").format(frappe.bold(_(self.meta.get_label(fieldname))))
				)

	def validate_dates(self):
		if self.start_date and self.renewal_date and getdate(self.renewal_date) < getdate(self.start_date):
			frappe.throw(_("Renewal Date cannot be before Start Date."), title=_("Invalid Dates"))

	def validate_status(self):
		if self.status == "Active" and not self.renewal_date:
			frappe.throw(_("Set a Renewal Date before marking the service Active."))

	def validate_mailboxes(self):
		"""Normalize addresses; warn (never block) when a mailbox is on another domain."""
		mismatched = []
		for row in self.mailboxes:
			row.email_address = (row.email_address or "").strip().lower()
			mailbox_domain = row.email_address.rpartition("@")[2]
			if self.domain and mailbox_domain != self.domain:
				mismatched.append(row.email_address)

		if mismatched:
			frappe.msgprint(
				_("These mailboxes are not on {0}: {1}").format(
					frappe.bold(self.domain), ", ".join(frappe.bold(m) for m in mismatched)
				),
				title=_("Mailbox Domain Mismatch"),
				indicator="orange",
			)

	def reset_reminders_on_renewal_change(self):
		"""A new renewal date starts a new reminder cycle."""
		if not self.is_new() and self.has_value_changed("renewal_date"):
			self.last_reminder_sent_on = None
			self.last_reminder_stage = None

	@frappe.whitelist()
	def get_subscription_renewal_date(self):
		"""Return the linked Subscription's current period end for the form to
		offer as the new renewal date. Never writes anything itself."""
		self.check_permission("write")
		if not self.subscription:
			frappe.throw(_("No Subscription is linked to this service."))

		period_end = frappe.db.get_value("Subscription", self.subscription, "current_invoice_end")
		if not period_end:
			frappe.throw(
				_("Subscription {0} has no current period end date yet.").format(frappe.bold(self.subscription))
			)
		return {"current": self.renewal_date, "period_end": period_end}



def get_list_context(context=None):
	"""Portal list context for /my-services (see speedhost_portal.portal)."""
	from speedhost_portal.portal import get_list_context as portal_list_context

	return portal_list_context(context)
