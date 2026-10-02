app_name = "speedhost_portal"
app_title = "Speedhost Portal"
app_publisher = "SpeedHost360"
app_description = "Customer portal for SpeedHost360 hosting services on ERPNext"
app_email = "tafheem.alam.professional@gmail.com"
app_license = "mit"

required_apps = ["erpnext"]

# Customer portal
# ---------------
# Private, login-only pages served the same way ERPNext serves /invoices and
# /orders. The DocType itself is not a web view (has_web_view = 0).

website_route_rules = [
	{"from_route": "/my-services", "to_route": "Hosting Service"},
	{
		"from_route": "/my-services/<path:name>",
		"to_route": "hosting_service",
		"defaults": {"doctype": "Hosting Service"},
	},
]

has_website_permission = {
	"Hosting Service": "speedhost_portal.portal.has_website_permission",
}

portal_menu_items = [
	{
		"title": "My Services",
		"route": "/my-services",
		"reference_doctype": "Hosting Service",
		"role": "Customer",
	},
]
