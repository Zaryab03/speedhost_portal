# Copyright (c) 2026, SpeedHost360 and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from speedhost_portal.speedhost_portal.doctype.hosting_service.hosting_service import (
	is_valid_domain,
	normalize_domain,
)
from speedhost_portal.tests.utils import make_customer, make_service


class TestHostingService(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.customer = make_customer("Validation")

	def new(self, **kwargs):
		values = {
			"doctype": "Hosting Service",
			"customer": self.customer,
			"service_title": "Validation test",
			"domain": "validation-test.com",
			"renewal_date": "2031-01-31",
		}
		values.update(kwargs)
		return frappe.get_doc(values)

	def test_domain_normalization(self):
		cases = {
			"HTTPS://Example.COM/some/path?x=1": "example.com",
			"http://shop.example.pk:8080/": "shop.example.pk",
			" www.Example.com. ": "www.example.com",
		}
		for raw, expected in cases.items():
			self.assertEqual(normalize_domain(raw), expected)

		doc = self.new(domain="https://Normalized-Test.COM/")
		doc.insert(ignore_permissions=True)
		self.assertEqual(doc.domain, "normalized-test.com")

	def test_invalid_domains_rejected(self):
		for bad in ("localhost", "no_underscores.com", "-dash.com", "a..com", "spaces in.com"):
			self.assertFalse(is_valid_domain(normalize_domain(bad)), bad)
			self.assertRaises(frappe.ValidationError, self.new(domain=bad).insert, ignore_permissions=True)

	def test_urls_must_be_https(self):
		for field in ("control_panel_url", "webmail_url"):
			for bad in ("http://cp.example.com", "ftp://x.com", "cp.example.com", "javascript:alert(1)"):
				doc = self.new(**{field: bad})
				self.assertRaises(frappe.ValidationError, doc.insert, ignore_permissions=True)
		self.new(control_panel_url="https://cp.example.com:2083", webmail_url="HTTPS://mail.x.com").insert(
			ignore_permissions=True
		)

	def test_renewal_not_before_start(self):
		doc = self.new(start_date="2031-02-01", renewal_date="2031-01-31")
		self.assertRaises(frappe.ValidationError, doc.insert, ignore_permissions=True)
		self.new(start_date="2031-01-31", renewal_date="2031-01-31").insert(ignore_permissions=True)

	def test_active_requires_renewal_date(self):
		doc = self.new(status="Active", renewal_date=None)
		self.assertRaises(frappe.ValidationError, doc.validate_status)
		self.assertRaises(frappe.ValidationError, doc.insert, ignore_permissions=True)

	def test_ports_in_range(self):
		self.assertRaises(frappe.ValidationError, self.new(smtp_port=70000).insert, ignore_permissions=True)

	def test_mailbox_domain_mismatch_warns_but_saves(self):
		frappe.clear_messages()
		doc = self.new(
			mailboxes=[
				{"email_address": "Info@Validation-Test.com", "status": "Active"},
				{"email_address": "someone@other-domain.com", "status": "Active"},
			]
		)
		doc.insert(ignore_permissions=True)
		self.assertTrue(doc.name)
		self.assertEqual(doc.mailboxes[0].email_address, "info@validation-test.com")
		messages = " ".join(str(m) for m in frappe.get_message_log())
		self.assertIn("someone@other-domain.com", messages)
		self.assertNotIn("info@validation-test.com", messages)

	def test_no_password_fields(self):
		for doctype in ("Hosting Service", "Hosting Mailbox"):
			meta = frappe.get_meta(doctype)
			self.assertFalse([df.fieldname for df in meta.fields if df.fieldtype == "Password"])
			self.assertFalse([df.fieldname for df in meta.fields if "pass" in df.fieldname or "secret" in df.fieldname])

	def test_subscription_sync_never_writes(self):
		doc = make_service(self.customer, "sync-test.com")
		self.assertRaises(frappe.ValidationError, doc.get_subscription_renewal_date)
		self.assertEqual(str(frappe.db.get_value("Hosting Service", doc.name, "renewal_date")), "2031-06-30")
