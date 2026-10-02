# Copyright (c) 2026, SpeedHost360 and contributors
# For license information, please see license.txt

"""Default Email Templates used by speedhost_portal.reminders.

These are created only when missing (after_install and a patch), never
overwritten, so staff can freely edit the wording in Desk > Email Template.
Regular Frappe fixtures would be force-overwritten on every `bench migrate`.

Available variables: customer_name, service_title, domain, renewal_date,
days_left, renewal_when, renewal_amount, billing_cycle, invoices_url, service_url,
helpdesk_url, support_email.
"""

import frappe

_SUPPORT_FOOTER = """
<p>Need help? <a href="{{ helpdesk_url }}">Open a support ticket</a>{% if support_email %} or email
<a href="mailto:{{ support_email }}">{{ support_email }}</a>{% endif %}.</p>
<p>Thank you,<br>SpeedHost360</p>
"""

TEMPLATES = [
	{
		"name": "Hosting Renewal Reminder",
		"subject": "Your hosting for {{ domain }} renews {{ renewal_when }}",
		"response_html": """<p>Dear {{ customer_name }},</p>
<p>Your hosting service <b>{{ service_title }}</b> ({{ domain }}) is due for renewal
<b>{{ renewal_when }}</b>.</p>
<ul>
	<li>Renewal date: <b>{{ renewal_date }}</b></li>
	{% if billing_cycle %}<li>Billing cycle: {{ billing_cycle }}</li>{% endif %}
	{% if renewal_amount %}<li>Renewal amount: <b>{{ renewal_amount }}</b></li>{% endif %}
</ul>
<p>Please pay your renewal invoice before the renewal date to avoid any interruption to your
website and email: <a href="{{ invoices_url }}">view your invoices</a>.</p>
<p>You can see your service details any time at <a href="{{ service_url }}">{{ service_url }}</a>.</p>
"""
		+ _SUPPORT_FOOTER,
	},
	{
		"name": "Hosting Service Expired",
		"subject": "Your hosting for {{ domain }} has expired",
		"response_html": """<p>Dear {{ customer_name }},</p>
<p>Your hosting service <b>{{ service_title }}</b> ({{ domain }}) expired on <b>{{ renewal_date }}</b>
and has not been renewed.</p>
{% if renewal_amount %}<p>Renewal amount: <b>{{ renewal_amount }}</b></p>{% endif %}
<p>To keep your website and email running, please pay your renewal invoice as soon as possible:
<a href="{{ invoices_url }}">view your invoices</a>. If you have already paid, please reply with
your payment reference so we can update your account.</p>
<p>Service details: <a href="{{ service_url }}">{{ service_url }}</a></p>
"""
		+ _SUPPORT_FOOTER,
	},
]


def create_default_templates() -> list[str]:
	"""Create any missing default template. Returns the names created."""
	created = []
	for template in TEMPLATES:
		if frappe.db.exists("Email Template", template["name"]):
			continue
		frappe.get_doc(
			{
				"doctype": "Email Template",
				"name": template["name"],
				"__newname": template["name"],  # Email Template autoname is "Prompt"
				"subject": template["subject"],
				"use_html": 1,
				"response_html": template["response_html"],
			}
		).insert(ignore_permissions=True)
		created.append(template["name"])
	return created
