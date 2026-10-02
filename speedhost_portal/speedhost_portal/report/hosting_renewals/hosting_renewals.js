// Copyright (c) 2026, SpeedHost360 and contributors
// For license information, please see license.txt

frappe.query_reports["Hosting Renewals"] = {
	filters: [
		{
			fieldname: "days_ahead",
			label: __("Renewing Within (Days)"),
			fieldtype: "Int",
			default: 30,
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: ["", "Pending", "Active", "Suspended", "Expired", "Cancelled"],
			default: "Active",
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "include_overdue",
			label: __("Include Overdue"),
			fieldtype: "Check",
			default: 1,
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "days_left" && data) {
			if (data.days_left <= 7) value = `<span class="text-danger">${value}</span>`;
			else if (data.days_left <= 30) value = `<span class="text-warning">${value}</span>`;
		}
		return value;
	},
};
