from speedhost_portal.email_templates import create_default_templates


def execute():
	"""Create the reminder Email Templates on sites that installed the app
	before they existed. Existing (possibly edited) templates are untouched."""
	create_default_templates()
