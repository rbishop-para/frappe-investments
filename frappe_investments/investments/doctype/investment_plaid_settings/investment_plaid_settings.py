# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, getdate, today
from plaid.errors import ItemError

from frappe_investments.investments.doctype.investment_plaid_settings.investment_plaid_connector import InvestmentPlaidConnector


class InvestmentPlaidSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		automatic_sync: DF.Check
		enabled: DF.Check
		plaid_client_id: DF.Data | None
		plaid_env: DF.Literal["sandbox", "development", "production"]
		plaid_secret: DF.Password | None
	# end: auto-generated types

	@staticmethod
	@frappe.whitelist()
	def get_link_token():
		plaid = InvestmentPlaidConnector()
		return plaid.get_link_token()


@frappe.whitelist()
def get_investment_plaid_configuration():
	if frappe.db.get_single_value("Investment Plaid Settings", "enabled"):
		plaid_settings = frappe.get_single("Investment Plaid Settings")
		return {
			"plaid_env": plaid_settings.plaid_env,
			"link_token": plaid_settings.get_link_token(),
			"client_name": frappe.local.site,
		}

	return "disabled"


@frappe.whitelist()
def add_investment_institution(token, response):
	response = json.loads(response)

	plaid = InvestmentPlaidConnector()
	access_token = plaid.get_access_token(token)
	institution = None

	if not frappe.db.exists("Investment Institution", response["institution"]["name"]):
		try:
			institution = frappe.get_doc(
				{
					"doctype": "Investment Institution",
					"institution_name": response["institution"]["name"],
					"plaid_access_token": access_token,
					"enabled": 1,
				}
			)
			institution.insert()
		except Exception:
			frappe.log_error("Investment Plaid Link Error")
	else:
		institution = frappe.get_doc("Investment Institution", response["institution"]["name"])
		institution.plaid_access_token = access_token
		institution.save()

	return institution


@frappe.whitelist()
def add_investment_accounts(response, institution, company):
	try:
		response = json.loads(response)
	except TypeError:
		pass

	if isinstance(institution, str):
		institution = json.loads(institution)
	result = []

	# Get parent GL account for investments
	parent_gl_account = frappe.db.get_all(
		"Account", {"company": company, "account_type": "Asset", "is_group": 1, "disabled": 0}
	)
	if not parent_gl_account:
		frappe.throw(
			_(
				"Please setup and enable a group account with the Account Type - {0} for the company {1}"
			).format(frappe.bold(_("Asset")), company)
		)

	plaid = InvestmentPlaidConnector(institution.plaid_access_token)
	investment_accounts = plaid.get_investment_accounts()

	for account in investment_accounts:
		account_name = f"{account['name']} - {institution['institution_name']}"
		existing_investment_account = frappe.db.exists("Investment Account", account_name)

		if not existing_investment_account:
			try:
				# Create GL account for this investment account
				gl_account = frappe.get_doc(
					{
						"doctype": "Account",
						"account_name": account["name"] + " - " + response["institution"]["name"],
						"parent_account": parent_gl_account[0].name,
						"account_type": "Asset",
						"company": company,
					}
				)
				gl_account.insert(ignore_if_duplicate=True)

				# Create income and expense accounts
				income_account = frappe.get_doc(
					{
						"doctype": "Account",
						"account_name": f"Investment Income - {account['name']}",
						"parent_account": frappe.db.get_value("Account", {"company": company, "account_type": "Income", "is_group": 1}),
						"account_type": "Income",
						"company": company,
					}
				)
				income_account.insert(ignore_if_duplicate=True)

				expense_account = frappe.get_doc(
					{
						"doctype": "Account",
						"account_name": f"Investment Loss - {account['name']}",
						"parent_account": frappe.db.get_value("Account", {"company": company, "account_type": "Expense", "is_group": 1}),
						"account_type": "Expense",
						"company": company,
					}
				)
				expense_account.insert(ignore_if_duplicate=True)

				new_account = frappe.get_doc(
					{
						"doctype": "Investment Account",
						"account_name": account["name"],
						"investment_institution": institution["institution_name"],
						"company": company,
						"gl_account": gl_account.name,
						"account_for_income": income_account.name,
						"account_for_losses": expense_account.name,
						"plaid_account_id": account["account_id"],
						"enabled": 1,
					}
				)
				new_account.insert()

				result.append(new_account.name)
			except frappe.UniqueValidationError:
				frappe.msgprint(
					_("Investment account {0} already exists and could not be created again").format(
						account["name"]
					)
				)
			except Exception:
				frappe.log_error("Investment Plaid Link Error")
				frappe.throw(
					_("There was an error creating Investment Account while linking with Plaid."),
					title=_("Investment Plaid Link Failed"),
				)

	return result


def sync_investment_values(investment_account_name):
	"""Sync investment account values and create GL entries for changes"""
	investment_account = frappe.get_doc("Investment Account", investment_account_name)
	
	if not investment_account.enabled:
		return

	plaid = InvestmentPlaidConnector(
		frappe.db.get_value("Investment Institution", investment_account.investment_institution, "plaid_access_token")
	)

	try:
		current_value = plaid.get_account_balance(investment_account.plaid_account_id)
		
		if current_value is None:
			frappe.log_error(f"Could not get current value for investment account {investment_account_name}")
			return

		# Get the current GL account balance
		gl_balance = frappe.db.get_value("Account", investment_account.gl_account, "account_balance") or 0
		
		# Calculate the pure investment change (excluding transfers)
		last_sync_balance = investment_account.last_sync_balance or 0
		total_change = current_value - last_sync_balance
		
		# Check for manual transfers (debits to the investment account)
		transfers_since_last_sync = get_transfers_since_last_sync(
			investment_account.gl_account, 
			investment_account.last_sync_date
		)
		
		# Pure investment gain/loss = total change - transfers
		pure_investment_change = total_change - transfers_since_last_sync
		
		if abs(pure_investment_change) > 0.01:  # Only create entries for significant changes
			create_investment_gl_entry(
				investment_account, 
				pure_investment_change, 
				current_value
			)
		
		# Update the investment account
		investment_account.last_sync_balance = current_value
		investment_account.last_sync_date = now_datetime()
		investment_account.save()
		
		frappe.logger().info(
			f"Investment account {investment_account_name} synced. "
			f"Value: {current_value}, Change: {pure_investment_change}"
		)
		
	except ItemError as e:
		if e.code == "ITEM_LOGIN_REQUIRED":
			msg = _("There was an error syncing investment values.") + " "
			msg += _("Please refresh or reset the Plaid linking of the Investment Institution {}.").format(
				investment_account.investment_institution
			) + " "
			frappe.log_error(message=msg, title=_("Investment Plaid Link Refresh Required"))
	except Exception:
		frappe.log_error(frappe.get_traceback(), _("Investment values sync error"))


def get_transfers_since_last_sync(gl_account, last_sync_date):
	"""Get total transfers (debits) to the investment account since last sync"""
	if not last_sync_date:
		return 0
	
	# Get all journal entries that debit this account since last sync
	transfers = frappe.db.sql("""
		SELECT SUM(jei.debit_in_account_currency)
		FROM `tabJournal Entry Account` jei
		JOIN `tabJournal Entry` je ON je.name = jei.parent
		WHERE jei.account = %s
		AND je.posting_date >= %s
		AND je.docstatus = 1
		AND jei.debit_in_account_currency > 0
	""", (gl_account, last_sync_date), as_list=True)
	
	return transfers[0][0] or 0


def create_investment_gl_entry(investment_account, change_amount, current_value):
	"""Create GL entry for investment gain/loss"""
	if change_amount > 0:
		# Investment gain
		account_to_credit = investment_account.account_for_income
		entry_type = "Investment Gain"
	else:
		# Investment loss
		account_to_credit = investment_account.account_for_losses
		entry_type = "Investment Loss"
	
	journal_entry = frappe.get_doc({
		"doctype": "Journal Entry",
		"voucher_type": "Investment Adjustment",
		"posting_date": today(),
		"company": investment_account.company,
		"user_remark": f"Investment value adjustment for {investment_account.account_name}",
		"accounts": [
			{
				"account": investment_account.gl_account,
				"debit_in_account_currency": abs(change_amount) if change_amount > 0 else 0,
				"credit_in_account_currency": abs(change_amount) if change_amount < 0 else 0,
			},
			{
				"account": account_to_credit,
				"debit_in_account_currency": abs(change_amount) if change_amount < 0 else 0,
				"credit_in_account_currency": abs(change_amount) if change_amount > 0 else 0,
			}
		]
	})
	
	journal_entry.insert()
	journal_entry.submit()


@frappe.whitelist()
def enqueue_investment_synchronization():
	investment_accounts = frappe.get_all(
		"Investment Account", 
		filters={"enabled": 1, "plaid_account_id": ["!=", ""]}, 
		fields=["name"]
	)

	for account in investment_accounts:
		frappe.enqueue(
			"frappe_investments.investments.doctype.investment_plaid_settings.investment_plaid_settings.sync_investment_values",
			investment_account_name=account.name,
		)


def automatic_investment_synchronization():
	settings = frappe.get_single("Investment Plaid Settings")
	if settings.enabled == 1 and settings.automatic_sync == 1:
		enqueue_investment_synchronization()


@frappe.whitelist()
def get_link_token_for_update(access_token):
	plaid = InvestmentPlaidConnector(access_token)
	return plaid.get_link_token(update_mode=True)
