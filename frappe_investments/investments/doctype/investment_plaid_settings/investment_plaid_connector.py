# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
import plaid
from frappe import _
from plaid.errors import APIError, InvalidRequestError, ItemError


class InvestmentPlaidConnector:
	def __init__(self, access_token=None):
		self.access_token = access_token
		self.settings = frappe.get_single("Investment Plaid Settings")
		self.products = ["investments"]
		self.client_name = frappe.local.site
		self.client = plaid.Client(
			client_id=self.settings.plaid_client_id,
			secret=self.settings.get_password("plaid_secret"),
			environment=self.settings.plaid_env,
			api_version="2020-09-14",
		)

	def get_access_token(self, public_token):
		if public_token is None:
			frappe.log_error("Plaid: Public token is missing")
		response = self.client.Item.public_token.exchange(public_token)
		access_token = response["access_token"]
		return access_token

	def get_token_request(self, update_mode=False):
		country_codes = ["US", "CA"]  # No European access for investments
		args = {
			"client_name": self.client_name,
			"language": frappe.local.lang if frappe.local.lang in ["en", "fr", "es", "nl"] else "en",
			"country_codes": country_codes,
			"user": {"client_user_id": frappe.generate_hash(frappe.session.user, length=32)},
		}

		if update_mode:
			args["access_token"] = self.access_token
		else:
			args.update(
				{
					"client_id": self.settings.plaid_client_id,
					"secret": self.settings.plaid_secret,
					"products": self.products,
				}
			)

		return args

	def get_link_token(self, update_mode=False):
		token_request = self.get_token_request(update_mode)

		try:
			response = self.client.LinkToken.create(token_request)
		except InvalidRequestError:
			frappe.log_error("Plaid: Invalid request error")
			frappe.msgprint(_("Please check your Plaid client ID and secret values"))
		except APIError as e:
			frappe.log_error("Plaid: Authentication error")
			frappe.throw(_(str(e)), title=_("Authentication Failed"))
		else:
			return response["link_token"]

	def get_investment_accounts(self):
		"""Get investment accounts from Plaid"""
		try:
			response = self.client.Accounts.get(access_token=self.access_token)
			# Filter for investment accounts only
			investment_accounts = [
				account for account in response["accounts"] 
				if account.get("type") == "investment"
			]
			return investment_accounts
		except ItemError as e:
			raise e
		except Exception:
			frappe.log_error("Plaid: Investment accounts sync error")
			return []

	def get_investment_holdings(self, account_id):
		"""Get investment holdings for a specific account"""
		try:
			response = self.client.InvestmentsHoldings.get(access_token=self.access_token)
			# Filter holdings for the specific account
			account_holdings = [
				holding for holding in response["holdings"] 
				if holding.get("account_id") == account_id
			]
			return account_holdings
		except ItemError as e:
			raise e
		except Exception:
			frappe.log_error("Plaid: Investment holdings sync error")
			return []

	def get_account_balance(self, account_id):
		"""Get current balance for an investment account"""
		try:
			response = self.client.Accounts.get(access_token=self.access_token)
			for account in response["accounts"]:
				if account.get("account_id") == account_id:
					return account.get("balances", {}).get("current", 0)
			return 0
		except ItemError as e:
			raise e
		except Exception:
			frappe.log_error("Plaid: Account balance sync error")
			return 0 