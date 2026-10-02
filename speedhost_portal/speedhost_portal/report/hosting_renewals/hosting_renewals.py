# Copyright (c) 2026, SpeedHost360 and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, getdate, today


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Service"), "fieldname": "name", "fieldtype": "Link", "options": "Hosting Service", "width": 110},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 180},
		{"label": _("Domain"), "fieldname": "domain", "fieldtype": "Data", "width": 180},
		{"label": _("Plan"), "fieldname": "plan", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Renewal Date"), "fieldname": "renewal_date", "fieldtype": "Date", "width": 110},
		{"label": _("Days Left"), "fieldname": "days_left", "fieldtype": "Int", "width": 90},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Billing Cycle"), "fieldname": "billing_cycle", "fieldtype": "Data", "width": 110},
		{"label": _("Auto Renew"), "fieldname": "auto_renew", "fieldtype": "Check", "width": 90},
		{"label": _("Amount"), "fieldname": "renewal_amount", "fieldtype": "Currency", "width": 120},
	]


def get_data(filters):
	today_date = getdate(today())
	query_filters = {}

	if filters.customer:
		query_filters["customer"] = filters.customer
	if filters.status:
		query_filters["status"] = filters.status

	days_ahead = cint(filters.days_ahead) if filters.days_ahead not in (None, "") else 30
	upper = add_days(today_date, days_ahead)
	if cint(filters.include_overdue):
		query_filters["renewal_date"] = ["<=", upper]
	else:
		query_filters["renewal_date"] = ["between", [today_date, upper]]

	rows = frappe.get_list(
		"Hosting Service",
		filters=query_filters,
		fields=[
			"name",
			"customer",
			"domain",
			"plan",
			"renewal_date",
			"status",
			"billing_cycle",
			"auto_renew",
			"renewal_amount",
		],
		order_by="renewal_date asc, name asc",
	)
	for row in rows:
		row.days_left = date_diff(row.renewal_date, today_date)
	return rows
