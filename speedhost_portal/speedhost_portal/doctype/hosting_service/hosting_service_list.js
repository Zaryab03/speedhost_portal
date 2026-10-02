// Copyright (c) 2026, SpeedHost360 and contributors
// For license information, please see license.txt

frappe.listview_settings["Hosting Service"] = {
	add_fields: ["status", "renewal_date"],

	get_indicator(doc) {
		const colors = {
			Pending: "blue",
			Active: "green",
			Suspended: "orange",
			Expired: "red",
			Cancelled: "gray",
		};
		return [__(doc.status), colors[doc.status] || "gray", `status,=,${doc.status}`];
	},

	onload(listview) {
		listview.page.add_inner_button(__("Renewing in 30 days"), () => {
			const today = frappe.datetime.get_today();
			listview.filter_area.clear(false).then(() =>
				listview.filter_area.add([
					["Hosting Service", "status", "=", "Active"],
					["Hosting Service", "renewal_date", "Between", [today, frappe.datetime.add_days(today, 30)]],
				])
			);
		});

		listview.page.add_inner_button(__("Hosting Renewals Report"), () =>
			frappe.set_route("query-report", "Hosting Renewals")
		);
	},
};
