# Copyright (c) 2026, SpeedHost360 and contributors
# For license information, please see license.txt

"""Portal isolation: customer A must never see customer B's services."""

import frappe
from frappe.tests.utils import FrappeTestCase

from speedhost_portal import portal
from speedhost_portal.tests.utils import (
	link_via_contact,
	link_via_portal_user,
	make_customer,
	make_service,
	make_website_user,
)

USER_A = "sh.test.a@example.com"  # linked via Customer > Portal Users
USER_B = "sh.test.b@example.com"  # linked via Contact > Dynamic Link
USER_NONE = "sh.test.nobody@example.com"


class TestPortalPermissions(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.customer_a = make_customer("Perm A")
		cls.customer_b = make_customer("Perm B")

		make_website_user(USER_A)
		make_website_user(USER_B)
		make_website_user(USER_NONE)
		link_via_portal_user(cls.customer_a, USER_A)
		link_via_contact(cls.customer_b, USER_B)

		cls.service_a = make_service(cls.customer_a, "perm-a-test.com")
		cls.service_b = make_service(cls.customer_b, "perm-b-test.com")

	def tearDown(self):
		frappe.set_user("Administrator")

	def listed_names(self, **kwargs):
		return {row.name for row in portal.get_service_list("Hosting Service", **kwargs)}

	def test_customer_resolution_uses_both_link_types(self):
		self.assertEqual(portal.get_customers_for_user(USER_A), [self.customer_a])
		self.assertEqual(portal.get_customers_for_user(USER_B), [self.customer_b])
		self.assertEqual(portal.get_customers_for_user(USER_NONE), [])
		self.assertEqual(portal.get_customers_for_user("Guest"), [])

	def test_list_is_scoped_to_own_customer(self):
		frappe.set_user(USER_A)
		names = self.listed_names()
		self.assertIn(self.service_a.name, names)
		self.assertNotIn(self.service_b.name, names)

		frappe.set_user(USER_B)
		names = self.listed_names()
		self.assertIn(self.service_b.name, names)
		self.assertNotIn(self.service_a.name, names)

	def test_customer_filter_in_query_string_is_ignored(self):
		frappe.set_user(USER_A)
		names = self.listed_names(filters={"customer": self.customer_b})
		self.assertNotIn(self.service_b.name, names)
		self.assertIn(self.service_a.name, names)

	def test_search_cannot_reach_other_customer(self):
		frappe.set_user(USER_A)
		self.assertEqual(self.listed_names(txt="perm-b-test"), set())

	def test_unlinked_user_and_guest_see_nothing(self):
		frappe.set_user(USER_NONE)
		self.assertEqual(self.listed_names(), set())
		frappe.set_user("Guest")
		self.assertEqual(self.listed_names(), set())
		self.assertRaises(frappe.PermissionError, portal.get_list_context)

	def test_has_website_permission(self):
		check = portal.has_website_permission
		self.assertTrue(check(self.service_a, "read", USER_A))
		self.assertFalse(check(self.service_b, "read", USER_A))
		self.assertTrue(check(self.service_b, "read", USER_B))
		self.assertFalse(check(self.service_a, "read", USER_B))
		self.assertFalse(check(self.service_a, "read", USER_NONE))
		self.assertFalse(check(self.service_a, "read", "Guest"))
		# Through Frappe's own dispatcher (hooks.has_website_permission) as well,
		# with freshly loaded docs as a web request would have.
		fresh_a = frappe.get_doc("Hosting Service", self.service_a.name)
		fresh_b = frappe.get_doc("Hosting Service", self.service_b.name)
		self.assertFalse(frappe.has_website_permission(fresh_b, user=USER_A))
		self.assertTrue(frappe.has_website_permission(fresh_a, user=USER_A))

	def test_portal_is_read_only(self):
		for ptype in ("write", "create", "delete", "submit", "cancel", "share"):
			self.assertFalse(portal.has_website_permission(self.service_a, ptype, USER_A), ptype)
		# No desk DocPerm either, so /api/resource and frappe.client are closed.
		for ptype in ("read", "write", "create", "delete"):
			self.assertFalse(frappe.has_permission("Hosting Service", ptype, user=USER_A), ptype)

	def test_detail_view_blocks_foreign_and_missing_services(self):
		frappe.set_user(USER_A)
		self.assertEqual(portal.get_service_for_portal(self.service_a.name).name, self.service_a.name)
		self.assertRaises(frappe.PermissionError, portal.get_service_for_portal, self.service_b.name)
		self.assertRaises(frappe.PermissionError, portal.get_service_for_portal, "HS-DOES-NOT-EXIST")
		frappe.set_user("Guest")
		self.assertRaises(frappe.PermissionError, portal.get_service_for_portal, self.service_a.name)

	def test_portal_output_excludes_internal_fields(self):
		frappe.set_user(USER_A)
		view = portal.get_service_for_portal(self.service_a.name)
		for field in ("internal_notes", "last_reminder_sent_on", "last_reminder_stage", "customer", "renewal_amount"):
			self.assertNotIn(field, view)
		self.assertNotIn("SECRET-INTERNAL-NOTE", frappe.as_json(view))

		rows = portal.get_service_list("Hosting Service")
		self.assertNotIn("SECRET-INTERNAL-NOTE", frappe.as_json(rows))
		self.assertNotIn("internal_notes", rows[0])

	def test_disabled_customer_loses_access(self):
		make_customer("Perm A", disabled=1)
		try:
			self.assertFalse(portal.has_website_permission(self.service_a, "read", USER_A))
		finally:
			make_customer("Perm A", disabled=0)

	def test_staff_preview_follows_desk_permission(self):
		self.assertTrue(portal.has_website_permission(self.service_b, "read", "Administrator"))
