// Copyright (c) 2026, SpeedHost360 and contributors
// For license information, please see license.txt

frappe.ui.form.on("Hosting Service", {
	refresh(frm) {
		if (!frm.is_new() && frm.doc.subscription && frm.perm[0]?.write) {
			frm.add_custom_button(__("Sync Renewal Date from Subscription"), () =>
				speedhost_portal.sync_renewal_date(frm)
			);
		}

		if (!frm.is_new() && frm.doc.customer) {
			frm.add_custom_button(
				__("Preview on Portal"),
				() => window.open(`/my-services/${encodeURIComponent(frm.doc.name)}`, "_blank"),
				__("View")
			);
		}
	},

	start_date(frm) {
		if (frm.doc.start_date && !frm.doc.renewal_date && frm.doc.billing_cycle) {
			const months = { Monthly: 1, Quarterly: 3, "Half-Yearly": 6, Yearly: 12 }[frm.doc.billing_cycle];
			frm.set_value("renewal_date", frappe.datetime.add_months(frm.doc.start_date, months));
		}
	},

	billing_cycle(frm) {
		frm.trigger("start_date");
	},
});

frappe.provide("speedhost_portal");

speedhost_portal.sync_renewal_date = (frm) => {
	frm.call("get_subscription_renewal_date").then(({ message }) => {
		if (!message) return;
		const { current, period_end } = message;

		if (current === period_end) {
			frappe.show_alert({
				message: __("Renewal Date already matches the Subscription."),
				indicator: "green",
			});
			return;
		}

		frappe.confirm(
			__("Change Renewal Date from {0} to {1} (Subscription {2} current period end)?", [
				frappe.datetime.str_to_user(current) || __("(not set)"),
				frappe.datetime.str_to_user(period_end),
				frm.doc.subscription,
			]),
			() => {
				frm.set_value("renewal_date", period_end);
				frappe.show_alert({
					message: __("Renewal Date updated. Save to keep the change."),
					indicator: "orange",
				});
			}
		);
	});
};
