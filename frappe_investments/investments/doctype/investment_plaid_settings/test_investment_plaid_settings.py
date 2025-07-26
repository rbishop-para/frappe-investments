# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import unittest
import frappe
from frappe_investments.investments.doctype.investment_plaid_settings.investment_plaid_settings import (
	get_transfers_since_last_sync,
	create_investment_gl_entry
)


class TestInvestmentPlaidSettings(unittest.TestCase):
	def test_get_transfers_since_last_sync(self):
		"""Test transfer detection logic"""
		# Test with no last sync date
		transfers = get_transfers_since_last_sync("test_account", None)
		self.assertEqual(transfers, 0)
		
		# Test with valid last sync date (should return 0 if no transfers exist)
		transfers = get_transfers_since_last_sync("test_account", "2025-01-01")
		self.assertEqual(transfers, 0)

	def test_create_investment_gl_entry(self):
		"""Test GL entry creation for investment gains/losses"""
		# This would require a mock investment account
		# For now, just test that the function exists
		self.assertTrue(callable(create_investment_gl_entry))


def test_investment_plaid_integration():
	"""Test the complete investment Plaid integration flow"""
	# This would test the full integration flow
	# For now, just verify the module can be imported
	try:
		from frappe_investments.investments.doctype.investment_plaid_settings.investment_plaid_connector import InvestmentPlaidConnector
		assert True
	except ImportError:
		assert False, "InvestmentPlaidConnector could not be imported"
