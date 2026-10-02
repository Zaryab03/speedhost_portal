# Copyright (c) 2026, SpeedHost360 and contributors
# For license information, please see license.txt

"""Shared helpers for speedhost_portal tests. All records use a `_Test SH`
prefix and are created idempotently, so re-runs on a shared dev site are safe."""

import frappe

PREFIX = "_Test SH"


def make_customer(suffix: str, disabled: int = 0) -> str:
	name = f"{PREFIX} Customer {suffix}"
	if not frappe.db.exists("Customer", name):
		frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": name,
				"customer_type": "Company",
				"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}) or "All Customer Groups",
				"territory": frappe.db.get_value("Territory", {"is_group": 0}) or "All Territories",
			}
		).insert(ignore_permissions=True)
	frappe.db.set_value("Customer", name, "disabled", disabled)
	return name


def make_website_user(email: str, roles=("Customer",)) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"user_type": "Website User",
				"send_welcome_email": 0,
				"roles": [{"role": r} for r in roles],
			}
		).insert(ignore_permissions=True)
	return email


def link_via_portal_user(customer: str, user: str):
	if not frappe.db.exists("Portal User", {"parent": customer, "user": user}):
		doc = frappe.get_doc("Customer", customer)
		doc.append("portal_users", {"user": user})
		doc.save(ignore_permissions=True)


def link_via_contact(customer: str, user: str, email: str | None = None, is_primary: int = 0) -> str:
	existing = frappe.db.get_value("Contact", {"user": user}) if user else None
	if existing:
		# Frappe may auto-create a bare Contact for a new user; link it.
		contact = frappe.get_doc("Contact", existing)
		if not contact.has_link("Customer", customer):
			contact.append("links", {"link_doctype": "Customer", "link_name": customer})
			contact.save(ignore_permissions=True)
		return contact.name
	contact = frappe.get_doc(
		{
			"doctype": "Contact",
			"first_name": (email or user).split("@")[0],
			"user": user,
			"is_primary_contact": is_primary,
			"email_ids": [{"email_id": email or user, "is_primary": 1}],
			"links": [{"link_doctype": "Customer", "link_name": customer}],
		}
	).insert(ignore_permissions=True)
	return contact.name


def make_service(customer: str, domain: str, **kwargs):
	values = {
		"doctype": "Hosting Service",
		"customer": customer,
		"service_title": f"Hosting - {domain}",
		"domain": domain,
		"status": "Active",
		"renewal_date": "2031-06-30",
		"control_panel_url": f"https://{domain}:2083",
		"control_panel_username": "tester",
		"incoming_server": f"mail.{domain}",
		"internal_notes": "SECRET-INTERNAL-NOTE",
	}
	values.update(kwargs)
	return frappe.get_doc(values).insert(ignore_permissions=True)
