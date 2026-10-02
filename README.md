# Speedhost Portal

Customer portal for **SpeedHost360** hosting services, built on Frappe/ERPNext v15.

Staff record each customer's hosting services in ERPNext (**Hosting Service**).
Customers log into the standard ERPNext portal (`https://clients.speedhost360.com`)
and see their own services under **My Services**: renewal date, control panel and
webmail details, mail server settings, nameservers and mailboxes. The portal is read-only.

> This app has nothing to do with the hosting control panel at
> `portal.speedhost360.com` and does not call any panel API.

**Security rule:** the app has no password or secret fields, and none should be added.
Share credentials through a one-time reset link or a ticket reply.

## Requirements

- Frappe 15.x and ERPNext 15.x (developed on Frappe 15.114.0 / ERPNext 15.115.0)
- Frappe Helpdesk is optional. The portal links to it through `helpdesk_url`.

## Install

```bash
cd ~/frappe-bench
bench get-app <git-url-of-this-repo> --branch main
bench --site <site> install-app speedhost_portal
bench --site <site> migrate
bench --site <site> enable-scheduler   # reminders run on the daily scheduler
```

After installation, `after_install` prints the manual steps that are still open on that
site. To print them again later:

```bash
bench --site <site> execute speedhost_portal.install.print_manual_steps
```

Installing the app creates:

- the **Hosting Service** DocType and its **Hosting Mailbox** child table
- the **Hosting Renewals** script report
- the Email Templates **Hosting Renewal Reminder** and **Hosting Service Expired**.
  The app creates them only if they don't exist yet, so you can edit them freely in
  *Email Template* and `migrate` won't overwrite your changes.
- a **My Services** entry in the portal sidebar, shown to users with the `Customer` role
- a **Hosting** connection on the Customer form

The app doesn't create any custom roles. It only uses roles that ERPNext already has.

| Role | Hosting Service access |
|---|---|
| System Manager, Accounts Manager | Full access (create, edit, delete, import, export) |
| Sales User | Create, read, edit, report, export. No delete. |
| Support Team | Read, edit, report, export. No create or delete. |
| Customer (portal) | No desk access. Can see their own services read-only at `/my-services`. |

## Configuration (site config)

Nothing is hardcoded. Set these keys per site:

```bash
bench --site <site> set-config helpdesk_url "https://clients.speedhost360.com/helpdesk"
bench --site <site> set-config speedhost_support_email "support@speedhost360.com"
bench --site <site> set-config speedhost_internal_alert_email "billing@speedhost360.com"
bench --site <site> set-config speedhost_kb_url "https://speedhost360.com/kb/email-setup"
bench --site <site> set-config -p speedhost_reminders_enabled 1   # 0 pauses all reminder emails
```

| Key | Default | Used for |
|---|---|---|
| `helpdesk_url` | `/helpdesk` | The "Open a support ticket" button and the support link in emails. A relative path is resolved against the site URL. |
| `speedhost_support_email` | not set | The support address in emails and on the service page |
| `speedhost_internal_alert_email` | not set | The daily staff summary of services renewing in the next 7 days. If not set, no summary is sent. |
| `speedhost_kb_url` | not set | The knowledge-base link in the "How to set up your email" help. If not set, the link is hidden. |
| `speedhost_reminders_enabled` | on | Master switch for the daily reminder job |

Outgoing mail uses the site's **default outgoing Email Account**. Configure one in
*Email Account*, otherwise reminders stay in the Email Queue.

## Giving a customer portal access

1. Open the **Customer** and create a **Contact** for them with an email address.
   Make sure the contact's *Links* table contains the Customer.
2. On the Contact, click **Invite as User**. This creates a Website User and emails them a
   link to set a password.
3. On the **Customer**, go to the **Portal Users** tab and add that user. ERPNext then gives
   the user the **Customer** role, which shows **My Services** (and Invoices, Orders and so on)
   in the portal sidebar.

A user can see the Hosting Services of every customer they are linked to, through
either Customer > Portal Users or Contact > Links. Disabled customers are hidden.
Staff can open a service on the portal from the form (**View > Preview on Portal**).

## How renewal reminders work

The `speedhost_portal.reminders.run_daily` job runs once a day:

1. **Auto-expire:** a service changes from Active to Expired the day after its renewal date
   when all of the following are true:
   - *Auto Renew* is off
   - it's unpaid, meaning it has no linked Subscription or the linked Subscription isn't
     `Active`

   A comment is added to the service. Nothing is ever suspended automatically.
2. **Expired notice:** sends the *Hosting Service Expired* template once, to services that
   expired in the last 7 days.
3. **Renewal reminders:** sends the *Hosting Renewal Reminder* template to Active services
   30, 15, 7 and 3 days before the renewal date, and on the renewal day.
4. **Internal summary:** emails `speedhost_internal_alert_email` a list of Active services
   renewing in the next 7 days.

Reminders go to the customer's portal users and primary contacts.

**Each stage is sent at most once.** `last_reminder_stage` and `last_reminder_sent_on`
record what has been sent for the current renewal date:

- Changing the renewal date resets both fields, which starts a new cycle.
- If a send fails, the error goes to the Error Log and the stage is not recorded, so the
  next run tries again.
- If the scheduler misses some days, the job sends only the most urgent stage that is due.
  It doesn't send a backlog.

To run the job by hand: `bench --site <site> execute speedhost_portal.reminders.run_daily`.

## Staff tools

- **Hosting Service list:** status colours, standard filters (customer, status, plan,
  renewal date) and a **Renewing in 30 days** button.
- **Hosting Renewals report:** customer, domain, plan, renewal date, days left, status,
  billing cycle, auto-renew and amount. It is sortable and exportable, and has filters for
  days ahead, status, customer and overdue.
- **Sync Renewal Date from Subscription:** a button on services with a linked Subscription.
  It shows the Subscription's current period end and changes the date only after you
  confirm. You then save the form yourself.
- **Customer form:** a **Hosting** connection showing the customer's services.
- The desk does **not** have a "Create Support Ticket" button, because Frappe Helpdesk
  (`HD Ticket`) is not installed on this bench. The portal's "Open a support ticket"
  button links to `helpdesk_url`.

## Testing as a customer

Run these on a development site only.

```bash
# Demo data: two customers, one portal user each, 4 services
# (refuses to run unless developer_mode is on)
bench --site <dev-site> execute speedhost_portal.demo.setup --kwargs '{"password": "<pick-one>"}'
```

Then:

1. Log in as `sh.demo.a@example.com` in a private window.
2. Open `/my-services`. You should see only *SH Demo Customer A*'s two services.
3. Open `/my-services/<one of customer B's services>`. It should return **403 Not Permitted**.

Automated tests (34) cover portal isolation, reminders and validations:

```bash
bench --site <dev-site> set-config allow_tests true
bench --site <dev-site> run-tests --app speedhost_portal --skip-test-records
```

Use `--skip-test-records` so Frappe doesn't build ERPNext's own test fixtures for
Customer, Item and Subscription.

## Upgrading

```bash
cd ~/frappe-bench/apps/speedhost_portal && git pull
cd ~/frappe-bench && bench --site <site> migrate && bench build --app speedhost_portal
```

- `migrate` applies DocType changes and runs any new patches in `patches.txt`.
- Email Templates you edited are never overwritten. To get a new default template, delete or
  rename yours and run `bench --site <site> execute speedhost_portal.email_templates.create_default_templates`.
- Customize the app through Customize Form or property setters rather than editing its
  DocType JSON on a production site.

## License

MIT
