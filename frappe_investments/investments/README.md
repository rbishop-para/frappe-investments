# Frappe Investments Module

This module provides investment account tracking and integration with Plaid for automatic value synchronization.

## Features

- **Investment Institution Management**: Link investment institutions (brokerages, 401k providers, etc.) via Plaid
- **Investment Account Tracking**: Track individual investment accounts with their current values
- **Automatic Value Sync**: Nightly synchronization of investment account values
- **Smart GL Integration**: Automatically creates journal entries for investment gains/losses
- **Transfer Detection**: Intelligently distinguishes between market gains/losses and manual transfers

## Setup

### 1. Configure Plaid Settings

1. Go to **Investment Plaid Settings**
2. Enable the integration
3. Enter your Plaid Client ID and Secret
4. Select the appropriate environment (sandbox/development/production)

### 2. Link Investment Institutions

1. Click "Link a new investment institution" in Investment Plaid Settings
2. Complete the Plaid Link flow to authenticate with your investment provider
3. Select the company for the investment accounts
4. Investment accounts will be automatically discovered and created

### 3. Configure Investment Accounts

Each investment account will be created with:
- A GL account for tracking the investment value
- An income account for investment gains
- A loss account for investment losses

## How It Works

### Value Synchronization

The system syncs investment values nightly and:

1. **Gets current value** from Plaid for each investment account
2. **Detects transfers** by checking for manual journal entries that debit the investment account
3. **Calculates pure investment change** = total change - transfers
4. **Creates GL entries** for investment gains/losses only

### GL Entry Logic

- **Investment Gain**: Debit Investment Account, Credit Income Account
- **Investment Loss**: Debit Loss Account, Credit Investment Account
- **Manual Transfer**: No automatic GL entry (handled manually)

### Transfer Detection

The system queries journal entries since the last sync to detect manual transfers:

```sql
SELECT SUM(jei.debit_in_account_currency)
FROM `tabJournal Entry Account` jei
JOIN `tabJournal Entry` je ON je.name = jei.parent
WHERE jei.account = [investment_account]
AND je.posting_date >= [last_sync_date]
AND je.docstatus = 1
AND jei.debit_in_account_currency > 0
```

## Doctypes

- **Investment Institution**: Represents investment providers (Vanguard, Fidelity, etc.)
- **Investment Account**: Individual investment accounts with GL integration
- **Investment Account Type**: Customizable account types (401k, IRA, Brokerage, etc.)
- **Investment Plaid Settings**: Configuration for Plaid integration

## Scheduled Tasks

- **Daily Sync**: Runs at midnight to sync all enabled investment accounts

## Manual Sync

You can manually trigger synchronization from the Investment Plaid Settings page using the "Sync Now" button.

## Troubleshooting

### Common Issues

1. **Plaid Link Refresh Required**: The access token has expired. Re-link the institution.
2. **No Investment Accounts Found**: Ensure the Plaid product includes "investments"
3. **GL Entry Errors**: Check that income/loss accounts are properly configured

### Logs

Check the Error Log for detailed information about sync failures and Plaid API errors. 