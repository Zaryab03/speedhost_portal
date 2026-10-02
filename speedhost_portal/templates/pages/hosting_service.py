# Copyright (c) 2026, SpeedHost360 and contributors
# For license information, please see license.txt

"""Detail page for /my-services/<name> (see website_route_rules in hooks.py)."""

import frappe
from frappe import _
from frappe.utils import escape_html

from speedhost_portal.portal import get_detail_extras, get_service_for_portal, portal_css_link

no_cache = 1


def get_context(context):
	context.no_cache = 1
	context.show_sidebar = True

	# Doctype is fixed here on purpose; never trust form_dict.doctype.
	service = get_service_for_portal(frappe.form_dict.name)

	context.service = service
	context.title = escape_html(service.service_title)  # breadcrumbs render title unescaped
	context.parents = [{"route": "my-services", "title": _("My Services")}]
	context.head_include = portal_css_link()
	context.update(get_detail_extras())
	return context
