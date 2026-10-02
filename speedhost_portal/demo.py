# Copyright (c) 2026, SpeedHost360 and contributors
# For license information, please see license.txt

"""Dev-site demo data for manually testing portal isolation.

	bench --site <dev-site> execute speedhost_portal.demo.setup --kwargs '{"password": "..."}'

Creates two customers ("SH Demo Customer A/B"), one portal user each, and a
few Hosting Services. User A is linked the ERPNext v15 way (Customer > Portal
Users); user B through a Contact with a Dynamic Link to the customer. Safe to
re-run. Refuses to run unless developer_mode is on.
"""

import frappe
from frappe.utils import add_days, today

DEMO = {
	"SH Demo Customer A": ("sh.demo.a@example.com", "portal_user", "alpha-demo.com"),
	"SH Demo Customer B": ("sh.demo.b@example.com", "contact", "bravo-demo.com"),
}


def setup(password: str):
	if not frappe.conf.developer_mode:
		frappe.throw("speedhost_portal.demo only runs on a developer_mode site.")

	for customer_name, (email, link_via, domain) in DEMO.items():
		customer = _customer(customer_name)
		user = _user(email, customer_name, password)
		if link_via == "portal_user":
			if not frappe.db.exists("Portal User", {"parent": customer, "user": user}):
				doc = frappe.get_doc("Customer", customer)
				doc.append("portal_users", {"user": user})
				doc.save(ignore_permissions=True)
		else:
			_contact(email, customer_name, customer, user)

		_service(customer, f"Business Hosting - {domain}", domain, add_days(today(), 5), with_internal=True)
		_service(customer, f"Starter Hosting - mail.{domain}", f"mail.{domain}", add_days(today(), 40))

	frappe.db.commit()
	return {"users": [v[0] for v in DEMO.values()]}


def _customer(name):
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
	return name


def _user(email, first_name, password):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first_name,
				"user_type": "Website User",
				"send_welcome_email": 0,
				"roles": [{"role": "Customer"}],
			}
		).insert(ignore_permissions=True)
	from frappe.utils.password import update_password

	update_password(email, password)
	return email


def _contact(email, first_name, customer, user):
	name = frappe.db.get_value("Contact", {"user": user})
	if not name:
		contact = frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": first_name,
				"user": user,
				"email_ids": [{"email_id": email, "is_primary": 1}],
				"links": [{"link_doctype": "Customer", "link_name": customer}],
			}
		)
		contact.insert(ignore_permissions=True)


def _service(customer, title, domain, renewal_date, with_internal=False):
	if frappe.db.exists("Hosting Service", {"customer": customer, "domain": domain}):
		return
	doc = frappe.get_doc(
		{
			"doctype": "Hosting Service",
			"customer": customer,
			"service_title": title,
			"domain": domain,
			"status": "Active",
			"control_panel_type": "cPanel",
			"control_panel_url": f"https://{domain}:2083",
			"control_panel_username": domain.split(".")[0][:8],
			"webmail_url": f"https://{domain}/webmail",
			"incoming_server": f"mail.{domain}",
			"outgoing_server": f"mail.{domain}",
			"mail_security": "SSL/TLS",
			"nameserver_1": "ns1.example.net",
			"nameserver_2": "ns2.example.net",
			"server_ip": "203.0.113.10",
			"billing_cycle": "Yearly",
			"start_date": add_days(renewal_date, -365),
			"renewal_date": renewal_date,
			"renewal_amount": 12000,
			"mailboxes": [
				{"email_address": f"info@{domain}", "quota_mb": 1024, "status": "Active"},
				{"email_address": f"sales@{domain}", "quota_mb": 512, "status": "Suspended"},
			],
		}
	)
	if with_internal:
		doc.internal_notes = "INTERNAL-ONLY-MARKER do not show on portal"
	doc.insert(ignore_permissions=True)
