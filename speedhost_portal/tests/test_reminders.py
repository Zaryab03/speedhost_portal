# Copyright (c) 2026, SpeedHost360 and contributors
# For license information, please see license.txt

"""Reminder stage logic, idempotency, retry and expiry.

Each step takes `today_date`, so tests "travel in time" around a renewal date
far in the future (2031) instead of depending on the real date or on other
services that happen to exist on the site. frappe.sendmail is always mocked.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate

from speedhost_portal import reminders
from speedhost_portal.reminders import get_due_stage
from speedhost_portal.tests.utils import link_via_contact, link_via_portal_user, make_customer, make_service, make_website_user

RENEWAL = getdate("2031-06-30")
USER = "sh.test.reminder@example.com"


def calls_for(mock, name):
	return [c for c in mock.call_args_list if c.kwargs.get("reference_name") == name]


class TestReminderStages(FrappeTestCase):
	def test_stage_table(self):
		cases = [
			(31, None, None),
			(30, None, 30),
			(29, None, 30),
			(29, "30", None),
			(15, "30", 15),
			(12, "30", 15),  # missed the 15-day run: send it late, once
			(12, "15", None),
			(7, "15", 7),
			(3, "7", 3),
			(1, "3", None),  # 3-day reminder covers 1 day left
			(0, "3", 0),
			(0, "0", None),
			(-1, None, None),
			(5, "expired", None),
			(5, "garbage", 7),
		]
		for days_left, last, expected in cases:
			self.assertEqual(get_due_stage(days_left, last), expected, (days_left, last))


class TestReminderJob(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.customer = make_customer("Reminders")
		make_website_user(USER)
		link_via_portal_user(cls.customer, USER)

	def setUp(self):
		self.service = make_service(
			self.customer,
			f"reminder-{frappe.generate_hash(length=6)}.com",
			renewal_date=RENEWAL,
			renewal_amount=15000,
			service_title="Pro <script>alert(1)</script>",
		)

	def run_reminders(self, days_before, mock):
		reminders.send_renewal_reminders(add_days(RENEWAL, -days_before))
		return calls_for(mock, self.service.name)

	@patch("frappe.sendmail")
	def test_each_stage_sent_exactly_once(self, sendmail):
		for days_before in (31, 30, 30, 29, 20, 15, 14, 7, 6, 3, 2, 0, 0):
			self.run_reminders(days_before, sendmail)

		sent = calls_for(sendmail, self.service.name)
		self.assertEqual(len(sent), 5)
		self.assertEqual(frappe.db.get_value("Hosting Service", self.service.name, "last_reminder_stage"), "0")
		self.assertEqual(sent[0].kwargs["recipients"], [USER])

	@patch("frappe.sendmail")
	def test_template_content_and_escaping(self, sendmail):
		sent = self.run_reminders(7, sendmail)
		self.assertEqual(len(sent), 1)
		message = sent[0].kwargs["message"]
		self.assertIn(self.service.domain, sent[0].kwargs["subject"])
		self.assertIn("in 7 days", sent[0].kwargs["subject"])
		self.assertIn("/invoices", message)
		self.assertIn(f"/my-services/{self.service.name}", message)
		self.assertIn("15,000", message)
		self.assertNotIn("<script>", message)

	def test_failed_send_is_logged_and_retried(self):
		with patch("frappe.sendmail", side_effect=Exception("SMTP down")), patch("frappe.log_error") as log:
			reminders.send_renewal_reminders(add_days(RENEWAL, -30))
			self.assertTrue(log.called)
		self.assertIsNone(frappe.db.get_value("Hosting Service", self.service.name, "last_reminder_stage"))

		with patch("frappe.sendmail") as sendmail:
			sent = self.run_reminders(29, sendmail)
		self.assertEqual(len(sent), 1)
		self.assertEqual(frappe.db.get_value("Hosting Service", self.service.name, "last_reminder_stage"), "30")

	@patch("frappe.sendmail")
	def test_new_renewal_date_starts_new_cycle(self, sendmail):
		self.run_reminders(3, sendmail)
		self.service.reload()
		self.assertEqual(self.service.last_reminder_stage, "3")

		self.service.renewal_date = add_days(RENEWAL, 365)
		self.service.save(ignore_permissions=True)
		self.assertIsNone(self.service.last_reminder_stage)
		self.assertIsNone(self.service.last_reminder_sent_on)

	@patch("frappe.sendmail")
	def test_no_recipients_is_logged_not_recorded(self, sendmail):
		lonely = make_service(make_customer("No Contacts"), "lonely-test.com", renewal_date=RENEWAL)
		with patch("frappe.log_error") as log:
			reminders.send_renewal_reminders(add_days(RENEWAL, -7))
		self.assertEqual(calls_for(sendmail, lonely.name), [])
		self.assertTrue(log.called)
		self.assertIsNone(frappe.db.get_value("Hosting Service", lonely.name, "last_reminder_stage"))

	@patch("frappe.sendmail")
	def test_inactive_services_get_no_reminders(self, sendmail):
		for status in ("Pending", "Suspended", "Cancelled"):
			frappe.db.set_value("Hosting Service", self.service.name, "status", status)
			self.assertEqual(self.run_reminders(7, sendmail), [], status)

	def test_auto_expire(self):
		renews = make_service(self.customer, "autorenew-test.com", renewal_date=RENEWAL, auto_renew=1)

		reminders.auto_expire_services(RENEWAL)  # renewal day itself: not yet
		self.assertEqual(frappe.db.get_value("Hosting Service", self.service.name, "status"), "Active")

		reminders.auto_expire_services(add_days(RENEWAL, 1))
		self.assertEqual(frappe.db.get_value("Hosting Service", self.service.name, "status"), "Expired")
		self.assertEqual(frappe.db.get_value("Hosting Service", renews.name, "status"), "Active")

	def test_paid_subscription_prevents_expiry(self):
		with patch("frappe.db.get_value", return_value="Active"):
			self.assertTrue(reminders.is_paid(frappe._dict(subscription="SUB-X")))
		self.assertFalse(reminders.is_paid(frappe._dict(subscription=None)))

	@patch("frappe.sendmail")
	def test_expired_notice_sent_once(self, sendmail):
		reminders.auto_expire_services(add_days(RENEWAL, 1))
		for day in (1, 1, 2):
			reminders.send_expired_notices(add_days(RENEWAL, day))

		sent = calls_for(sendmail, self.service.name)
		self.assertEqual(len(sent), 1)
		self.assertIn("expired", sent[0].kwargs["subject"])
		self.assertEqual(
			frappe.db.get_value("Hosting Service", self.service.name, "last_reminder_stage"), "expired"
		)

	@patch("frappe.sendmail")
	def test_old_expired_services_are_not_mailed(self, sendmail):
		frappe.db.set_value("Hosting Service", self.service.name, "status", "Expired")
		reminders.send_expired_notices(add_days(RENEWAL, reminders.EXPIRED_NOTICE_WINDOW_DAYS + 1))
		self.assertEqual(calls_for(sendmail, self.service.name), [])

	@patch("frappe.sendmail")
	def test_switch_disables_everything(self, sendmail):
		with patch.dict(frappe.local.conf, {"speedhost_reminders_enabled": 0}):
			reminders.run_daily()
		sendmail.assert_not_called()

	@patch("frappe.sendmail")
	def test_internal_summary(self, sendmail):
		with patch.dict(frappe.local.conf, {"speedhost_internal_alert_email": "ops@example.com"}):
			reminders.send_internal_summary(add_days(RENEWAL, -5))
		summary = [c for c in sendmail.call_args_list if c.kwargs.get("recipients") == ["ops@example.com"]]
		self.assertEqual(len(summary), 1)
		self.assertIn(self.service.name, summary[0].kwargs["message"])
		self.assertNotIn("<script>", summary[0].kwargs["message"])

		sendmail.reset_mock()
		reminders.send_internal_summary(add_days(RENEWAL, -5))  # no address configured
		sendmail.assert_not_called()


class TestRecipients(FrappeTestCase):
	def test_portal_users_and_primary_contacts_deduplicated(self):
		frappe.set_user("Administrator")
		customer = make_customer("Recipients")
		user = make_website_user("sh.test.recipient@example.com")
		link_via_portal_user(customer, user)
		link_via_contact(customer, user)  # same person, also a contact
		link_via_contact(customer, None, email="sh.billing@example.com", is_primary=1)
		link_via_contact(customer, None, email="sh.random@example.com", is_primary=0)

		recipients = reminders.get_recipients(customer)
		self.assertCountEqual(recipients, ["sh.test.recipient@example.com", "sh.billing@example.com"])
