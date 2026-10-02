# Copyright (c) 2026, SpeedHost360 and contributors
# For license information, please see license.txt

import click
import frappe

from speedhost_portal.email_templates import create_default_templates

REQUIRED_ROLES = ("System Manager", "Accounts Manager", "Sales User", "Support Team", "Customer")
CONFIG_KEYS = (
	("helpdesk_url", "Helpdesk portal link on the service page (default: /helpdesk)"),
	("speedhost_support_email", "support address quoted in emails and on the portal"),
	("speedhost_internal_alert_email", "staff address for the daily 7-day expiry summary"),
	("speedhost_kb_url", "knowledge-base link in the email setup help"),
	("speedhost_reminders_enabled", "set to 0 to pause reminder emails (default: on)"),
)


def after_install():
	created = create_default_templates()
	frappe.db.commit()
	print_manual_steps(created)


def get_manual_steps() -> list[str]:
	steps = []

	missing_roles = [r for r in REQUIRED_ROLES if not frappe.db.exists("Role", r)]
	if missing_roles:
		steps.append(
			"Roles missing on this site (Hosting Service permissions reference them): "
			+ ", ".join(missing_roles)
		)

	if not frappe.db.exists("Email Account", {"default_outgoing": 1, "enable_outgoing": 1}):
		steps.append("Configure a default outgoing Email Account, otherwise reminders stay queued.")

	for key, purpose in CONFIG_KEYS:
		if frappe.conf.get(key) in (None, ""):
			steps.append(f"Optional: bench --site {frappe.local.site} set-config {key} <value>  ({purpose})")

	if not frappe.db.exists("DocType", "HD Ticket"):
		steps.append(
			"Frappe Helpdesk is not installed: point helpdesk_url at your Helpdesk portal "
			"(the desk 'Create Support Ticket' shortcut is not available)."
		)

	steps.append(
		"For each customer: create a Contact with an email, link it to the Customer, "
		"'Invite as User', then add that user under Customer > Portal Users (gives the Customer role)."
	)
	steps.append("Make sure the scheduler is enabled: bench --site <site> enable-scheduler")
	return steps


def print_manual_steps(created_templates=None):
	click.secho("\nSpeedhost Portal installed.", fg="green")
	if created_templates:
		click.echo("Created Email Templates: " + ", ".join(created_templates))
	click.secho("Remaining manual steps:", fg="yellow")
	for step in get_manual_steps():
		click.echo(f"  - {step}")
	click.echo("")
